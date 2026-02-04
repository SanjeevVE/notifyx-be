from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime
import csv
import io
import os

from app.db.database import get_db
from app.models.user import User
from app.models.contact import Contact, ContactList, ContactListMembership, ContactStatus
from app.schemas.contact import (
    ContactCreate,
    ContactUpdate,
    ContactResponse,
    ContactBrief,
    ContactListCreate,
    ContactListUpdate,
    ContactListResponse,
    ContactListWithContacts,
    ContactImportResult,
    ContactBulkAddToList,
    ContactBulkDelete,
    PaginatedContacts,
    PaginatedContactLists,
)
from app.api.v1.auth import get_current_user
from email_validator import validate_email, EmailNotValidError

router = APIRouter()


# ============= Sample CSV Download =============

@router.get("/sample-csv")
async def download_sample_csv():
    """Download a sample CSV file for contact import"""
    # Get the path to the sample file
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    sample_file = os.path.join(current_dir, "sample_contacts.csv")

    if not os.path.exists(sample_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample file not found"
        )

    return FileResponse(
        path=sample_file,
        filename="sample_contacts.csv",
        media_type="text/csv"
    )


# ============= Contact List Routes (MUST be before /{contact_id} routes) =============

@router.post("/lists", response_model=ContactListResponse, status_code=status.HTTP_201_CREATED)
async def create_contact_list(
    list_data: ContactListCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new contact list"""
    # Check if list with same name exists
    result = await db.execute(
        select(ContactList).filter(
            ContactList.organization_id == current_user.organization_id,
            ContactList.name == list_data.name
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A list with this name already exists"
        )

    contact_list = ContactList(
        organization_id=current_user.organization_id,
        name=list_data.name,
        description=list_data.description,
    )

    db.add(contact_list)
    await db.commit()
    await db.refresh(contact_list)

    return contact_list


@router.get("/lists", response_model=PaginatedContactLists)
async def list_contact_lists(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all contact lists"""
    query = select(ContactList).filter(
        ContactList.organization_id == current_user.organization_id
    )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.order_by(ContactList.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    lists = result.scalars().all()

    return PaginatedContactLists(
        items=lists,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/lists/{list_id}", response_model=ContactListResponse)
async def get_contact_list(
    list_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific contact list"""
    result = await db.execute(
        select(ContactList).filter(
            ContactList.id == list_id,
            ContactList.organization_id == current_user.organization_id,
        )
    )
    contact_list = result.scalar_one_or_none()

    if not contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact list not found"
        )

    return contact_list


@router.patch("/lists/{list_id}", response_model=ContactListResponse)
async def update_contact_list(
    list_id: int,
    list_data: ContactListUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a contact list"""
    result = await db.execute(
        select(ContactList).filter(
            ContactList.id == list_id,
            ContactList.organization_id == current_user.organization_id,
        )
    )
    contact_list = result.scalar_one_or_none()

    if not contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact list not found"
        )

    update_data = list_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact_list, field, value)

    contact_list.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(contact_list)

    return contact_list


@router.delete("/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact_list(
    list_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a contact list (contacts are not deleted, only the list)"""
    result = await db.execute(
        select(ContactList).filter(
            ContactList.id == list_id,
            ContactList.organization_id == current_user.organization_id,
        )
    )
    contact_list = result.scalar_one_or_none()

    if not contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact list not found"
        )

    await db.delete(contact_list)
    await db.commit()


@router.post("/lists/{list_id}/contacts", status_code=status.HTTP_200_OK)
async def add_contacts_to_list(
    list_id: int,
    bulk_data: ContactBulkAddToList,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add contacts to a list"""
    # Verify list exists
    result = await db.execute(
        select(ContactList).filter(
            ContactList.id == list_id,
            ContactList.organization_id == current_user.organization_id,
        )
    )
    contact_list = result.scalar_one_or_none()

    if not contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact list not found"
        )

    added = 0
    for contact_id in bulk_data.contact_ids:
        # Verify contact belongs to same organization
        result = await db.execute(
            select(Contact).filter(
                Contact.id == contact_id,
                Contact.organization_id == current_user.organization_id,
            )
        )
        contact = result.scalar_one_or_none()
        if contact:
            was_added = await _add_contact_to_list(db, contact_id, list_id)
            if was_added:
                added += 1

    await _update_list_count(db, list_id)
    await db.commit()

    return {"added": added}


@router.delete("/lists/{list_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_contact_from_list(
    list_id: int,
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a contact from a list"""
    result = await db.execute(
        select(ContactListMembership).filter(
            ContactListMembership.list_id == list_id,
            ContactListMembership.contact_id == contact_id,
        ).join(ContactList).filter(
            ContactList.organization_id == current_user.organization_id
        )
    )
    membership = result.scalar_one_or_none()

    if membership:
        await db.delete(membership)
        await _update_list_count(db, list_id)
        await db.commit()


@router.get("/lists/{list_id}/contacts", response_model=List[ContactBrief])
async def get_list_contacts(
    list_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all contacts in a list"""
    # Verify list exists and belongs to organization
    result = await db.execute(
        select(ContactList).filter(
            ContactList.id == list_id,
            ContactList.organization_id == current_user.organization_id,
        )
    )
    contact_list = result.scalar_one_or_none()
    if not contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact list not found"
        )

    # Get contacts in this list
    result = await db.execute(
        select(Contact).join(ContactListMembership).filter(
            ContactListMembership.list_id == list_id
        ).order_by(Contact.full_name, Contact.email)
    )
    contacts = result.scalars().all()
    return contacts


# ============= Bulk Operations & Import =============

@router.delete("/bulk/delete", status_code=status.HTTP_200_OK)
async def bulk_delete_contacts(
    bulk_data: ContactBulkDelete,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple contacts"""
    result = await db.execute(
        select(Contact).filter(
            Contact.id.in_(bulk_data.contact_ids),
            Contact.organization_id == current_user.organization_id,
        )
    )
    contacts = result.scalars().all()

    deleted_count = 0
    for contact in contacts:
        await db.delete(contact)
        deleted_count += 1

    await db.commit()

    return {"deleted": deleted_count}


@router.post("/import", response_model=ContactImportResult)
async def import_contacts(
    file: UploadFile = File(...),
    list_id: Optional[int] = Query(None, description="Add imported contacts to this list"),
    skip_duplicates: bool = Query(True, description="Skip contacts that already exist"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import contacts from a CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported"
        )

    # Read file content
    content = await file.read()
    text_content = content.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(text_content))

    # Validate list if provided
    contact_list = None
    if list_id:
        result = await db.execute(
            select(ContactList).filter(
                ContactList.id == list_id,
                ContactList.organization_id == current_user.organization_id,
            )
        )
        contact_list = result.scalar_one_or_none()
        if not contact_list:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact list not found"
            )

    total_rows = 0
    imported = 0
    skipped = 0
    failed = 0
    errors = []

    for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
        total_rows += 1

        # Get email (required field)
        email = row.get('email', row.get('Email', row.get('EMAIL', ''))).strip().lower()
        if not email:
            failed += 1
            errors.append({"row": row_num, "error": "Missing email"})
            continue

        # Validate email
        try:
            validate_email(email)
        except EmailNotValidError:
            failed += 1
            errors.append({"row": row_num, "email": email, "error": "Invalid email format"})
            continue

        # Check for duplicates
        result = await db.execute(
            select(Contact).filter(
                Contact.organization_id == current_user.organization_id,
                Contact.email == email
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            if skip_duplicates:
                skipped += 1
                # Still add to list if specified
                if contact_list:
                    await _add_contact_to_list(db, existing.id, contact_list.id)
                continue

        # Get other fields
        full_name = row.get('full_name', row.get('name', row.get('Name', row.get('Full Name', '')))).strip() or None
        company = row.get('company', row.get('Company', '')).strip() or None
        phone = row.get('phone', row.get('Phone', '')).strip() or None

        # Create contact
        contact = Contact(
            organization_id=current_user.organization_id,
            email=email,
            full_name=full_name,
            company=company,
            phone=phone,
        )

        db.add(contact)
        await db.flush()  # Get the ID

        # Add to list if specified
        if contact_list:
            await _add_contact_to_list(db, contact.id, contact_list.id)

        imported += 1

    await db.commit()

    # Update list count if contacts were added
    if contact_list:
        await _update_list_count(db, contact_list.id)
        await db.commit()

    return ContactImportResult(
        total_rows=total_rows,
        imported=imported,
        skipped=skipped,
        failed=failed,
        errors=errors[:10]  # Only return first 10 errors
    )


# ============= Contact CRUD =============

@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact_data: ContactCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new contact"""
    # Check if contact already exists in this organization
    result = await db.execute(
        select(Contact).filter(
            Contact.organization_id == current_user.organization_id,
            Contact.email == contact_data.email.lower()
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact with this email already exists"
        )

    contact = Contact(
        organization_id=current_user.organization_id,
        email=contact_data.email.lower(),
        full_name=contact_data.full_name,
        company=contact_data.company,
        phone=contact_data.phone,
        custom_fields=contact_data.custom_fields,
        tags=contact_data.tags,
    )

    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    return contact


@router.get("/", response_model=PaginatedContacts)
async def list_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    status_filter: Optional[ContactStatus] = Query(None, alias="status"),
    list_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List contacts with pagination, search, and filtering"""
    query = select(Contact).filter(
        Contact.organization_id == current_user.organization_id
    )

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Contact.email.ilike(search_term),
                Contact.full_name.ilike(search_term),
                Contact.company.ilike(search_term),
            )
        )

    # Apply status filter
    if status_filter:
        query = query.filter(Contact.status == status_filter)

    # Apply list filter
    if list_id:
        query = query.join(ContactListMembership).filter(
            ContactListMembership.list_id == list_id
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.order_by(Contact.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    contacts = result.scalars().all()

    return PaginatedContacts(
        items=contacts,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


# NOTE: These routes MUST come AFTER /lists routes to avoid route conflicts

@router.get("/{contact_id}/lists", response_model=List[ContactListResponse])
async def get_contact_lists(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all lists a contact belongs to"""
    # Verify contact exists and belongs to organization
    result = await db.execute(
        select(Contact).filter(
            Contact.id == contact_id,
            Contact.organization_id == current_user.organization_id,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    # Get lists this contact belongs to
    result = await db.execute(
        select(ContactList).join(ContactListMembership).filter(
            ContactListMembership.contact_id == contact_id
        ).order_by(ContactList.name)
    )
    lists = result.scalars().all()
    return lists


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific contact by ID"""
    result = await db.execute(
        select(Contact).filter(
            Contact.id == contact_id,
            Contact.organization_id == current_user.organization_id,
        )
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    return contact


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: int,
    contact_data: ContactUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a contact"""
    result = await db.execute(
        select(Contact).filter(
            Contact.id == contact_id,
            Contact.organization_id == current_user.organization_id,
        )
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    # Update fields
    update_data = contact_data.model_dump(exclude_unset=True)
    if 'email' in update_data:
        update_data['email'] = update_data['email'].lower()

    for field, value in update_data.items():
        setattr(contact, field, value)

    contact.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(contact)

    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a contact"""
    result = await db.execute(
        select(Contact).filter(
            Contact.id == contact_id,
            Contact.organization_id == current_user.organization_id,
        )
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    await db.delete(contact)
    await db.commit()


# ============= Helper Functions =============

async def _add_contact_to_list(db: AsyncSession, contact_id: int, list_id: int) -> bool:
    """Add a contact to a list, returns True if added, False if already exists"""
    # Check if already in list
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


async def _update_list_count(db: AsyncSession, list_id: int):
    """Update the contact count for a list"""
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
