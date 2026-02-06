from typing import Dict, Any, List, Tuple, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
import re

from app.models.contact_field import ContactField, FieldType, SYSTEM_FIELD_COLUMN_MAP
from app.models.contact import Contact
from email_validator import validate_email, EmailNotValidError


class FieldValidationService:
    """
    Service for validating contact data against field definitions
    and managing field usage counts.
    """

    @staticmethod
    async def get_field_definitions(
        db: AsyncSession,
        organization_id: int
    ) -> Dict[str, ContactField]:
        """
        Get all field definitions for an organization, keyed by field_key.
        """
        result = await db.execute(
            select(ContactField).filter(
                ContactField.organization_id == organization_id
            )
        )
        fields = result.scalars().all()
        return {f.field_key: f for f in fields}

    @staticmethod
    def validate_field_value(
        value: Any,
        field: ContactField
    ) -> Tuple[Any, Optional[str]]:
        """
        Validate a single field value against its definition.
        Returns (validated_value, error_message).
        """
        # Handle None/empty values
        if value is None or (isinstance(value, str) and not value.strip()):
            if field.is_required:
                return None, f"{field.display_name} is required"
            return None, None

        # Convert value to string for text-based fields
        str_value = str(value).strip()

        # Type-specific validation
        if field.field_type == FieldType.TEXT:
            # Apply validation rules
            if field.validation_rules:
                rules = field.validation_rules
                if rules.get('min_length') and len(str_value) < rules['min_length']:
                    return None, f"{field.display_name} must be at least {rules['min_length']} characters"
                if rules.get('max_length') and len(str_value) > rules['max_length']:
                    return None, f"{field.display_name} must be at most {rules['max_length']} characters"
                if rules.get('pattern'):
                    if not re.match(rules['pattern'], str_value):
                        return None, f"{field.display_name} format is invalid"

            # Special validation for email field
            if field.field_key == 'email':
                try:
                    validate_email(str_value)
                    return str_value.lower(), None
                except EmailNotValidError:
                    return None, "Invalid email format"

            return str_value, None

        elif field.field_type == FieldType.NUMBER:
            try:
                num_value = float(str_value)
                if field.validation_rules:
                    rules = field.validation_rules
                    if rules.get('min_value') is not None and num_value < rules['min_value']:
                        return None, f"{field.display_name} must be at least {rules['min_value']}"
                    if rules.get('max_value') is not None and num_value > rules['max_value']:
                        return None, f"{field.display_name} must be at most {rules['max_value']}"
                return num_value, None
            except (ValueError, TypeError):
                return None, f"{field.display_name} must be a number"

        elif field.field_type == FieldType.DATE:
            # Accept ISO format dates
            try:
                if isinstance(value, datetime):
                    return value.isoformat(), None
                # Try parsing common date formats
                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S'):
                    try:
                        parsed = datetime.strptime(str_value, fmt)
                        return parsed.isoformat(), None
                    except ValueError:
                        continue
                return None, f"{field.display_name} must be a valid date"
            except Exception:
                return None, f"{field.display_name} must be a valid date"

        elif field.field_type == FieldType.BOOLEAN:
            str_lower = str_value.lower()
            if str_lower in ('true', '1', 'yes', 'y', 'on'):
                return True, None
            elif str_lower in ('false', '0', 'no', 'n', 'off', ''):
                return False, None
            else:
                return None, f"{field.display_name} must be true or false"

        elif field.field_type == FieldType.SELECT:
            if field.options:
                valid_values = [opt['value'] for opt in field.options]
                if str_value in valid_values:
                    return str_value, None
                return None, f"{field.display_name} must be one of: {', '.join(valid_values)}"
            return str_value, None

        elif field.field_type == FieldType.MULTI_SELECT:
            # Multi-select values can be comma-separated or a list
            if isinstance(value, list):
                values = value
            else:
                values = [v.strip() for v in str_value.split(',') if v.strip()]

            if field.options:
                valid_values = [opt['value'] for opt in field.options]
                invalid = [v for v in values if v not in valid_values]
                if invalid:
                    return None, f"{field.display_name} contains invalid values: {', '.join(invalid)}"

            return values, None

        return str_value, None

    @classmethod
    async def validate_contact_data(
        cls,
        db: AsyncSession,
        organization_id: int,
        data: Dict[str, Any],
        existing_contact_id: Optional[int] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        """
        Validate contact data against field definitions.

        Returns:
            - standard_fields: dict of validated standard column values
            - custom_fields: dict of validated custom field values
            - errors: list of validation error messages
        """
        field_definitions = await cls.get_field_definitions(db, organization_id)

        standard_fields = {}
        custom_fields = {}
        errors = []

        for field_key, value in data.items():
            # Skip if field_key starts with underscore (internal)
            if field_key.startswith('_'):
                continue

            # Handle custom. prefix for explicit custom fields
            if field_key.startswith('custom.'):
                actual_key = field_key[7:]  # Remove 'custom.' prefix
            else:
                actual_key = field_key

            # Get field definition
            field = field_definitions.get(actual_key)
            if not field:
                # Unknown field - skip or store in custom_fields
                continue

            # Validate value
            validated_value, error = cls.validate_field_value(value, field)
            if error:
                errors.append(error)
                continue

            # Skip None values
            if validated_value is None:
                continue

            # Route to standard or custom fields
            if field.is_system_field and actual_key in SYSTEM_FIELD_COLUMN_MAP:
                column_name = SYSTEM_FIELD_COLUMN_MAP[actual_key]
                standard_fields[column_name] = validated_value
            else:
                custom_fields[actual_key] = validated_value

        # Check required fields
        for field_key, field in field_definitions.items():
            if field.is_required:
                if field.is_system_field and field_key in SYSTEM_FIELD_COLUMN_MAP:
                    column = SYSTEM_FIELD_COLUMN_MAP[field_key]
                    if column not in standard_fields:
                        errors.append(f"{field.display_name} is required")
                else:
                    if field_key not in custom_fields and field_key not in data:
                        errors.append(f"{field.display_name} is required")

        return standard_fields, custom_fields, errors

    @classmethod
    async def update_usage_counts(
        cls,
        db: AsyncSession,
        organization_id: int,
        old_custom_fields: Optional[Dict[str, Any]],
        new_custom_fields: Optional[Dict[str, Any]]
    ):
        """
        Update usage_count for fields when contact custom_fields changes.

        Increments count for newly added fields.
        Decrements count for removed fields.
        """
        old_keys: Set[str] = set(old_custom_fields.keys()) if old_custom_fields else set()
        new_keys: Set[str] = set(new_custom_fields.keys()) if new_custom_fields else set()

        added_keys = new_keys - old_keys
        removed_keys = old_keys - new_keys

        # Increment for added fields
        if added_keys:
            await db.execute(
                update(ContactField)
                .where(
                    ContactField.organization_id == organization_id,
                    ContactField.field_key.in_(added_keys)
                )
                .values(usage_count=ContactField.usage_count + 1)
            )

        # Decrement for removed fields
        if removed_keys:
            await db.execute(
                update(ContactField)
                .where(
                    ContactField.organization_id == organization_id,
                    ContactField.field_key.in_(removed_keys)
                )
                .values(usage_count=ContactField.usage_count - 1)
            )

    @classmethod
    async def increment_usage_counts(
        cls,
        db: AsyncSession,
        organization_id: int,
        field_keys: Set[str]
    ):
        """Increment usage_count for specified fields"""
        if field_keys:
            await db.execute(
                update(ContactField)
                .where(
                    ContactField.organization_id == organization_id,
                    ContactField.field_key.in_(field_keys)
                )
                .values(usage_count=ContactField.usage_count + 1)
            )

    @classmethod
    async def decrement_usage_counts(
        cls,
        db: AsyncSession,
        organization_id: int,
        field_keys: Set[str]
    ):
        """Decrement usage_count for specified fields"""
        if field_keys:
            await db.execute(
                update(ContactField)
                .where(
                    ContactField.organization_id == organization_id,
                    ContactField.field_key.in_(field_keys)
                )
                .values(usage_count=ContactField.usage_count - 1)
            )

    @classmethod
    async def check_unique_constraint(
        cls,
        db: AsyncSession,
        organization_id: int,
        field_key: str,
        value: Any,
        exclude_contact_id: Optional[int] = None
    ) -> bool:
        """
        Check if a value is unique for a field with is_unique=True.
        Returns True if value is unique (or field is not unique).
        """
        field_definitions = await cls.get_field_definitions(db, organization_id)
        field = field_definitions.get(field_key)

        if not field or not field.is_unique:
            return True

        # Build query based on whether it's a system field
        if field.is_system_field and field_key in SYSTEM_FIELD_COLUMN_MAP:
            column_name = SYSTEM_FIELD_COLUMN_MAP[field_key]
            query = select(Contact).filter(
                Contact.organization_id == organization_id,
                getattr(Contact, column_name) == value
            )
        else:
            # For custom fields, search in JSON
            query = select(Contact).filter(
                Contact.organization_id == organization_id,
                Contact.custom_fields[field_key].astext == str(value)
            )

        if exclude_contact_id:
            query = query.filter(Contact.id != exclude_contact_id)

        result = await db.execute(query)
        existing = result.scalar_one_or_none()

        return existing is None
