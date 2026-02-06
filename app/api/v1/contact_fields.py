from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from app.db.database import get_db
from app.models.user import User
from app.models.contact_field import ContactField, SYSTEM_FIELDS
from app.schemas.contact_field import (
    ContactFieldCreate,
    ContactFieldUpdate,
    ContactFieldResponse,
    ContactFieldListResponse,
    ContactFieldReorder,
    generate_field_key,
)
from app.api.v1.auth import get_current_user

router = APIRouter()


# ============= List and Get Fields =============

@router.get("", response_model=ContactFieldListResponse)
async def list_contact_fields(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all contact fields for the organization.
    Returns both system fields and custom fields, ordered by display_order.
    """
    result = await db.execute(
        select(ContactField)
        .filter(ContactField.organization_id == current_user.organization_id)
        .order_by(ContactField.display_order, ContactField.created_at)
    )
    fields = result.scalars().all()

    return ContactFieldListResponse(
        items=fields,
        total=len(fields)
    )


@router.get("/{field_id}", response_model=ContactFieldResponse)
async def get_contact_field(
    field_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific contact field by ID"""
    result = await db.execute(
        select(ContactField).filter(
            ContactField.id == field_id,
            ContactField.organization_id == current_user.organization_id,
        )
    )
    field = result.scalar_one_or_none()

    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact field not found"
        )

    return field


# ============= Create Field =============

@router.post("", response_model=ContactFieldResponse, status_code=status.HTTP_201_CREATED)
async def create_contact_field(
    field_data: ContactFieldCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new custom contact field.
    System fields cannot be created via API.
    """
    # Generate field_key if not provided
    field_key = field_data.field_key
    if not field_key:
        field_key = generate_field_key(field_data.display_name)

    # Check if field_key already exists
    result = await db.execute(
        select(ContactField).filter(
            ContactField.organization_id == current_user.organization_id,
            ContactField.field_key == field_key
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A field with key '{field_key}' already exists"
        )

    # Check if trying to use a system field key
    system_keys = [f['field_key'] for f in SYSTEM_FIELDS]
    if field_key in system_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{field_key}' is a reserved system field key"
        )

    # Get next display_order
    result = await db.execute(
        select(func.max(ContactField.display_order))
        .filter(ContactField.organization_id == current_user.organization_id)
    )
    max_order = result.scalar() or 0

    # Create the field
    field = ContactField(
        organization_id=current_user.organization_id,
        field_key=field_key,
        display_name=field_data.display_name,
        description=field_data.description,
        field_type=field_data.field_type,
        is_system_field=False,
        is_required=field_data.is_required,
        is_unique=field_data.is_unique,
        default_value=field_data.default_value,
        options=[opt.model_dump() for opt in field_data.options] if field_data.options else None,
        validation_rules=field_data.validation_rules.model_dump() if field_data.validation_rules else None,
        display_order=max_order + 1,
        usage_count=0,
    )

    db.add(field)
    await db.commit()
    await db.refresh(field)

    return field


# ============= Update Field =============

@router.patch("/{field_id}", response_model=ContactFieldResponse)
async def update_contact_field(
    field_id: int,
    field_data: ContactFieldUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a contact field.
    System fields have limited updates (only display_name and description).
    Cannot change field_key or field_type.
    """
    result = await db.execute(
        select(ContactField).filter(
            ContactField.id == field_id,
            ContactField.organization_id == current_user.organization_id,
        )
    )
    field = result.scalar_one_or_none()

    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact field not found"
        )

    # Get update data
    update_data = field_data.model_dump(exclude_unset=True)

    # System fields have limited updates
    if field.is_system_field:
        allowed_updates = {'display_name', 'description'}
        disallowed = set(update_data.keys()) - allowed_updates
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update {', '.join(disallowed)} for system fields"
            )

    # Apply updates
    if 'options' in update_data and update_data['options'] is not None:
        update_data['options'] = [opt.model_dump() if hasattr(opt, 'model_dump') else opt for opt in update_data['options']]

    if 'validation_rules' in update_data and update_data['validation_rules'] is not None:
        rules = update_data['validation_rules']
        update_data['validation_rules'] = rules.model_dump() if hasattr(rules, 'model_dump') else rules

    for key, value in update_data.items():
        setattr(field, key, value)

    await db.commit()
    await db.refresh(field)

    return field


# ============= Delete Field =============

@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact_field(
    field_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a custom contact field.
    Cannot delete system fields.
    Cannot delete fields that are in use (usage_count > 0).
    """
    result = await db.execute(
        select(ContactField).filter(
            ContactField.id == field_id,
            ContactField.organization_id == current_user.organization_id,
        )
    )
    field = result.scalar_one_or_none()

    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact field not found"
        )

    if field.is_system_field:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system fields"
        )

    if field.usage_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete field: it is used by {field.usage_count} contacts. Remove the field from all contacts first."
        )

    await db.delete(field)
    await db.commit()


# ============= Reorder Fields =============

@router.post("/reorder", response_model=List[ContactFieldResponse])
async def reorder_contact_fields(
    reorder_data: ContactFieldReorder,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Reorder contact fields by providing list of field IDs in desired order.
    """
    # Get all organization fields
    result = await db.execute(
        select(ContactField).filter(
            ContactField.organization_id == current_user.organization_id
        )
    )
    fields = {f.id: f for f in result.scalars().all()}

    # Validate all IDs belong to organization
    for field_id in reorder_data.field_ids:
        if field_id not in fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field ID {field_id} not found"
            )

    # Update display_order based on position in list
    for order, field_id in enumerate(reorder_data.field_ids):
        fields[field_id].display_order = order

    await db.commit()

    # Return fields in new order
    result = await db.execute(
        select(ContactField)
        .filter(ContactField.organization_id == current_user.organization_id)
        .order_by(ContactField.display_order)
    )
    return result.scalars().all()


# ============= Seed System Fields =============

async def seed_system_fields(db: AsyncSession, organization_id: int):
    """
    Create system field definitions for a new organization.
    Called during organization/user signup.
    """
    for field_def in SYSTEM_FIELDS:
        field = ContactField(
            organization_id=organization_id,
            **field_def
        )
        db.add(field)

    await db.commit()
