import logging
import asyncio
import os
import csv
from datetime import datetime
from typing import Dict, Any, List, Optional, Set

from app.celery_app import celery_app
from app.db.database import async_session_maker
from app.models.import_job import (
    ImportJob,
    ImportJobStatus,
    IMPORT_BATCH_SIZE,
    PROGRESS_UPDATE_INTERVAL,
    MAX_ERRORS_STORED,
)
from app.models.contact import Contact, ContactList, ContactListMembership
from app.models.contact_field import ContactField, FieldType, SYSTEM_FIELD_COLUMN_MAP
from app.services.field_validation import FieldValidationService
from sqlalchemy import select
from email_validator import validate_email, EmailNotValidError

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async code in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_contact_import(self, import_job_id: int):
    """
    Background task to process contact import from Excel/CSV file.

    Workflow:
    1. Load import job configuration
    2. Open file (Excel or CSV)
    3. Process rows in batches
    4. Validate and create/update contacts
    5. Update progress periodically
    6. Mark job complete
    """
    logger.info(f"Starting contact import job: {import_job_id}")

    try:
        run_async(_process_import_async(import_job_id))
    except Exception as exc:
        logger.error(f"Error processing import job {import_job_id}: {exc}")
        run_async(_mark_job_failed(import_job_id, str(exc)))
        raise self.retry(exc=exc)


async def _process_import_async(import_job_id: int):
    """Async implementation of contact import processing"""
    async with async_session_maker() as db:
        # Get import job
        result = await db.execute(
            select(ImportJob).filter(ImportJob.id == import_job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            logger.error(f"Import job {import_job_id} not found")
            return

        if job.status != ImportJobStatus.PROCESSING:
            logger.warning(f"Import job {import_job_id} is not in PROCESSING status")
            return

        if not job.file_path or not os.path.exists(job.file_path):
            raise Exception(f"Import file not found: {job.file_path}")

        # Parse mapping configuration
        column_mapping = job.column_mapping or []
        options = job.options or {}

        skip_duplicates = options.get('skip_duplicates', True)
        update_existing = options.get('update_existing', False)
        list_id = options.get('list_id')

        # Get field definitions
        field_definitions = await FieldValidationService.get_field_definitions(
            db, job.organization_id
        )

        # Build mapping dict: source_column -> (target_field, create_field, field_type)
        mapping_dict = {}
        new_fields_to_create = []

        for mapping in column_mapping:
            source = mapping['source_column']
            target = mapping['target_field']
            create_field = mapping.get('create_field', False)
            field_type = mapping.get('field_type', 'text')

            # Handle custom. prefix
            if target.startswith('custom.'):
                actual_key = target[7:]
            else:
                actual_key = target

            mapping_dict[source] = {
                'target': actual_key,
                'create_field': create_field,
                'field_type': field_type,
            }

            # Track new fields to create
            if create_field and actual_key not in field_definitions:
                new_fields_to_create.append({
                    'field_key': actual_key,
                    'display_name': source,
                    'field_type': FieldType(field_type),
                })

        # Create new custom fields
        for field_def in new_fields_to_create:
            new_field = ContactField(
                organization_id=job.organization_id,
                field_key=field_def['field_key'],
                display_name=field_def['display_name'],
                field_type=field_def['field_type'],
                is_system_field=False,
                usage_count=0,
            )
            db.add(new_field)
            field_definitions[field_def['field_key']] = new_field

        await db.commit()

        # Verify contact list if specified
        contact_list = None
        if list_id:
            result = await db.execute(
                select(ContactList).filter(
                    ContactList.id == list_id,
                    ContactList.organization_id == job.organization_id,
                )
            )
            contact_list = result.scalar_one_or_none()

        # Read file
        rows = _read_file(job.file_path)

        # Initialize counters
        imported_count = 0
        updated_count = 0
        skipped_count = 0
        failed_count = 0
        errors = []
        processed_rows = 0
        affected_custom_fields: Set[str] = set()

        # Process rows
        for row_num, row_data in enumerate(rows, start=2):  # Start at 2 (header is row 1)
            processed_rows += 1

            # Check if job was cancelled
            if processed_rows % PROGRESS_UPDATE_INTERVAL == 0:
                await db.refresh(job)
                if job.status == ImportJobStatus.CANCELLED:
                    logger.info(f"Import job {import_job_id} was cancelled")
                    return

                # Update progress
                job.processed_rows = processed_rows
                job.imported_count = imported_count
                job.updated_count = updated_count
                job.skipped_count = skipped_count
                job.failed_count = failed_count
                await db.commit()

            # Map row data to contact fields
            standard_fields = {}
            custom_fields = {}
            row_errors = []

            for source_col, value in row_data.items():
                if source_col not in mapping_dict:
                    continue

                mapping = mapping_dict[source_col]
                target_key = mapping['target']

                # Skip empty values
                if value is None or (isinstance(value, str) and not value.strip()):
                    continue

                # Clean string values
                if isinstance(value, str):
                    value = value.strip()

                # Check if system field
                if target_key in SYSTEM_FIELD_COLUMN_MAP:
                    column_name = SYSTEM_FIELD_COLUMN_MAP[target_key]
                    standard_fields[column_name] = value
                else:
                    custom_fields[target_key] = value
                    affected_custom_fields.add(target_key)

            # Validate email
            email = standard_fields.get('email')
            if not email:
                failed_count += 1
                if len(errors) < MAX_ERRORS_STORED:
                    errors.append({
                        'row': row_num,
                        'error': 'Missing email',
                    })
                continue

            try:
                validate_email(email)
                email = email.lower()
                standard_fields['email'] = email
            except EmailNotValidError:
                failed_count += 1
                if len(errors) < MAX_ERRORS_STORED:
                    errors.append({
                        'row': row_num,
                        'email': email,
                        'error': 'Invalid email format',
                    })
                continue

            # Check for existing contact
            result = await db.execute(
                select(Contact).filter(
                    Contact.organization_id == job.organization_id,
                    Contact.email == email
                )
            )
            existing_contact = result.scalar_one_or_none()

            if existing_contact:
                if skip_duplicates and not update_existing:
                    skipped_count += 1
                    # Still add to list if specified
                    if contact_list:
                        await _add_contact_to_list(db, existing_contact.id, contact_list.id)
                    continue

                if update_existing:
                    # Update existing contact
                    for key, value in standard_fields.items():
                        if key != 'email':  # Don't update email
                            setattr(existing_contact, key, value)

                    # Merge custom fields
                    old_custom = existing_contact.custom_fields or {}
                    new_custom = {**old_custom, **custom_fields}
                    existing_contact.custom_fields = new_custom

                    updated_count += 1

                    if contact_list:
                        await _add_contact_to_list(db, existing_contact.id, contact_list.id)

                    continue
                else:
                    skipped_count += 1
                    continue

            # Create new contact
            contact = Contact(
                organization_id=job.organization_id,
                email=email,
                full_name=standard_fields.get('full_name'),
                company=standard_fields.get('company'),
                phone=standard_fields.get('phone'),
                custom_fields=custom_fields if custom_fields else None,
            )

            db.add(contact)
            await db.flush()

            # Add to list if specified
            if contact_list:
                await _add_contact_to_list(db, contact.id, contact_list.id)

            imported_count += 1

            # Commit in batches
            if processed_rows % IMPORT_BATCH_SIZE == 0:
                await db.commit()

        # Final commit
        await db.commit()

        # Update usage counts for custom fields
        if affected_custom_fields:
            await FieldValidationService.increment_usage_counts(
                db, job.organization_id, affected_custom_fields
            )
            await db.commit()

        # Update list count if contacts were added
        if contact_list:
            await _update_list_count(db, contact_list.id)
            await db.commit()

        # Mark job complete
        job.status = ImportJobStatus.COMPLETED
        job.processed_rows = processed_rows
        job.imported_count = imported_count
        job.updated_count = updated_count
        job.skipped_count = skipped_count
        job.failed_count = failed_count
        job.errors = errors if errors else None
        job.completed_at = datetime.utcnow()

        # Clean up file
        if job.file_path and os.path.exists(job.file_path):
            try:
                os.remove(job.file_path)
            except Exception as e:
                logger.warning(f"Failed to delete import file: {e}")

        await db.commit()

        logger.info(
            f"Import job {import_job_id} completed: "
            f"imported={imported_count}, updated={updated_count}, "
            f"skipped={skipped_count}, failed={failed_count}"
        )


def _read_file(file_path: str) -> List[Dict[str, Any]]:
    """Read Excel or CSV file and return list of row dicts"""
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    rows = []

    if ext == '.csv':
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))

    elif ext in ('.xlsx', '.xls'):
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active

        all_rows = list(ws.iter_rows(values_only=True))
        if not all_rows:
            return []

        # First row is headers
        headers = [str(cell) if cell is not None else f"Column_{i}" for i, cell in enumerate(all_rows[0])]

        # Data rows
        for row in all_rows[1:]:
            row_dict = {}
            for i, cell in enumerate(row):
                col_name = headers[i] if i < len(headers) else f"Column_{i}"
                row_dict[col_name] = str(cell).strip() if cell is not None else ""
            rows.append(row_dict)

        wb.close()

    return rows


async def _add_contact_to_list(db, contact_id: int, list_id: int) -> bool:
    """Add a contact to a list, returns True if added"""
    result = await db.execute(
        select(ContactListMembership).filter(
            ContactListMembership.contact_id == contact_id,
            ContactListMembership.list_id == list_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return False

    membership = ContactListMembership(
        contact_id=contact_id,
        list_id=list_id,
    )
    db.add(membership)
    return True


async def _update_list_count(db, list_id: int):
    """Update the contact count for a list"""
    from sqlalchemy import func

    result = await db.execute(
        select(func.count()).select_from(ContactListMembership).filter(
            ContactListMembership.list_id == list_id
        )
    )
    count = result.scalar()

    result = await db.execute(
        select(ContactList).filter(ContactList.id == list_id)
    )
    contact_list = result.scalar_one_or_none()
    if contact_list:
        contact_list.contact_count = count


async def _mark_job_failed(import_job_id: int, error_message: str):
    """Mark an import job as failed"""
    async with async_session_maker() as db:
        result = await db.execute(
            select(ImportJob).filter(ImportJob.id == import_job_id)
        )
        job = result.scalar_one_or_none()
        if job:
            job.status = ImportJobStatus.FAILED
            job.error_message = error_message
            job.completed_at = datetime.utcnow()

            # Clean up file
            if job.file_path and os.path.exists(job.file_path):
                try:
                    os.remove(job.file_path)
                except Exception:
                    pass

            await db.commit()


@celery_app.task
def cleanup_orphaned_import_files():
    """
    Periodic task to clean up orphaned import files.
    Run daily to remove files from failed/cancelled jobs.
    """
    logger.info("Cleaning up orphaned import files")
    run_async(_cleanup_files_async())


async def _cleanup_files_async():
    """Async implementation of file cleanup"""
    from datetime import timedelta

    async with async_session_maker() as db:
        # Find jobs older than 24 hours that still have files
        cutoff = datetime.utcnow() - timedelta(hours=24)

        result = await db.execute(
            select(ImportJob).filter(
                ImportJob.created_at < cutoff,
                ImportJob.file_path.isnot(None)
            )
        )
        jobs = result.scalars().all()

        cleaned = 0
        for job in jobs:
            if job.file_path and os.path.exists(job.file_path):
                try:
                    os.remove(job.file_path)
                    job.file_path = None
                    cleaned += 1
                except Exception as e:
                    logger.warning(f"Failed to delete file {job.file_path}: {e}")

        await db.commit()
        logger.info(f"Cleaned up {cleaned} orphaned import files")
