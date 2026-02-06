from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models.contact_field import FieldType
import re


class FieldOption(BaseModel):
    """Option for select/multi_select field types"""
    value: str
    label: str


class ValidationRules(BaseModel):
    """Validation rules for a field"""
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None  # Regex pattern
    min_value: Optional[float] = None  # For number fields
    max_value: Optional[float] = None  # For number fields


class ContactFieldBase(BaseModel):
    """Base schema for contact field"""
    display_name: str
    field_type: FieldType = FieldType.TEXT
    description: Optional[str] = None
    is_required: bool = False
    is_unique: bool = False
    default_value: Optional[str] = None
    options: Optional[List[FieldOption]] = None
    validation_rules: Optional[ValidationRules] = None
    display_order: Optional[int] = 0


class ContactFieldCreate(BaseModel):
    """Schema for creating a custom field"""
    display_name: str
    field_key: Optional[str] = None  # Auto-generated from display_name if not provided
    field_type: FieldType = FieldType.TEXT
    description: Optional[str] = None
    is_required: bool = False
    is_unique: bool = False
    default_value: Optional[str] = None
    options: Optional[List[FieldOption]] = None
    validation_rules: Optional[ValidationRules] = None

    @field_validator('field_key')
    @classmethod
    def validate_field_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r'^[a-z][a-z0-9_]*$', v):
            raise ValueError('field_key must be snake_case (lowercase letters, numbers, and underscores, starting with a letter)')
        if len(v) > 100:
            raise ValueError('field_key must be 100 characters or less')
        return v

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('display_name cannot be empty')
        return v.strip()

    @field_validator('options')
    @classmethod
    def validate_options(cls, v: Optional[List[FieldOption]], info) -> Optional[List[FieldOption]]:
        field_type = info.data.get('field_type')
        if field_type in (FieldType.SELECT, FieldType.MULTI_SELECT):
            if not v or len(v) == 0:
                raise ValueError('options are required for select/multi_select field types')
        return v


class ContactFieldUpdate(BaseModel):
    """Schema for updating a field (cannot change field_key or is_system_field)"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_required: Optional[bool] = None
    default_value: Optional[str] = None
    options: Optional[List[FieldOption]] = None
    validation_rules: Optional[ValidationRules] = None
    display_order: Optional[int] = None

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError('display_name cannot be empty')
        return v.strip() if v else v


class ContactFieldResponse(BaseModel):
    """Response schema for a contact field"""
    id: int
    organization_id: int
    field_key: str
    display_name: str
    description: Optional[str]
    field_type: FieldType
    is_system_field: bool
    is_required: bool
    is_unique: bool
    default_value: Optional[str]
    options: Optional[List[FieldOption]]
    validation_rules: Optional[Dict[str, Any]]
    usage_count: int
    display_order: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ContactFieldBrief(BaseModel):
    """Brief response for field lists and dropdowns"""
    id: int
    field_key: str
    display_name: str
    field_type: FieldType
    is_system_field: bool
    is_required: bool

    class Config:
        from_attributes = True


class ContactFieldReorder(BaseModel):
    """Request schema for reordering fields"""
    field_ids: List[int]  # List of field IDs in desired order


class ContactFieldListResponse(BaseModel):
    """Response containing list of fields"""
    items: List[ContactFieldResponse]
    total: int


def generate_field_key(display_name: str) -> str:
    """
    Generate a snake_case field_key from display_name.

    Examples:
        "Job Title" -> "job_title"
        "First Name" -> "first_name"
        "Company (Main)" -> "company_main"
    """
    # Convert to lowercase
    key = display_name.lower()
    # Replace spaces and special characters with underscores
    key = re.sub(r'[^a-z0-9]+', '_', key)
    # Remove leading/trailing underscores
    key = key.strip('_')
    # Collapse multiple underscores
    key = re.sub(r'_+', '_', key)
    # Ensure it starts with a letter
    if key and not key[0].isalpha():
        key = 'field_' + key
    return key[:100]  # Limit to 100 characters
