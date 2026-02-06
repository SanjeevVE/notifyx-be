from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models.import_job import ImportJobStatus
from app.models.contact_field import FieldType


class ColumnMapping(BaseModel):
    """Maps a source Excel/CSV column to a target contact field"""
    source_column: str  # Excel column header name
    target_field: str   # Target field: "email", "full_name", or "custom.job_title"
    create_field: bool = False  # If true, create a new custom field
    field_type: FieldType = FieldType.TEXT  # Type for new custom fields

    @field_validator('target_field')
    @classmethod
    def validate_target_field(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('target_field cannot be empty')
        return v.strip()


class ImportOptions(BaseModel):
    """Options for contact import"""
    skip_duplicates: bool = True  # Skip contacts with existing email
    update_existing: bool = False  # Update existing contacts instead of skip
    list_id: Optional[int] = None  # Add imported contacts to this list


class ImportUploadResponse(BaseModel):
    """Response after uploading a file, before mapping"""
    import_job_id: int
    file_name: str
    columns: List[str]  # Excel column headers
    preview_rows: List[Dict[str, Any]]  # First N rows for preview
    total_rows: int
    suggested_mappings: Dict[str, str]  # Auto-detected mappings: {"email": "Email Address"}


class ImportStartRequest(BaseModel):
    """Request to start import after column mapping"""
    mappings: List[ColumnMapping]
    options: ImportOptions = ImportOptions()

    @field_validator('mappings')
    @classmethod
    def validate_mappings(cls, v: List[ColumnMapping]) -> List[ColumnMapping]:
        if not v:
            raise ValueError('At least one column mapping is required')

        # Check that email is mapped
        email_mapped = any(m.target_field == 'email' for m in v)
        if not email_mapped:
            raise ValueError('Email column must be mapped')

        # Check for duplicate target fields
        targets = [m.target_field for m in v]
        duplicates = [t for t in targets if targets.count(t) > 1]
        if duplicates:
            raise ValueError(f'Duplicate target field mappings: {set(duplicates)}')

        return v


class ImportJobResponse(BaseModel):
    """Response for import job status"""
    id: int
    organization_id: int
    file_name: str
    status: ImportJobStatus
    total_rows: int
    processed_rows: int
    imported_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    progress_percentage: float
    errors: Optional[List[Dict[str, Any]]]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ImportJobBrief(BaseModel):
    """Brief response for import job lists"""
    id: int
    file_name: str
    status: ImportJobStatus
    total_rows: int
    imported_count: int
    failed_count: int
    progress_percentage: float
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class PaginatedImportJobs(BaseModel):
    """Paginated list of import jobs"""
    items: List[ImportJobBrief]
    total: int
    page: int
    page_size: int
    total_pages: int


class ImportError(BaseModel):
    """Details of a single import error"""
    row: int
    email: Optional[str] = None
    error: str
    field: Optional[str] = None


# Auto-mapping suggestions based on common column names
COLUMN_NAME_SUGGESTIONS = {
    'email': ['email', 'e-mail', 'email address', 'e-mail address', 'mail', 'email_address'],
    'full_name': ['name', 'full name', 'full_name', 'contact name', 'display name', 'fullname'],
    'company': ['company', 'company name', 'organization', 'organisation', 'business', 'employer'],
    'phone': ['phone', 'phone number', 'telephone', 'tel', 'mobile', 'cell', 'phone_number'],
}


def suggest_column_mappings(columns: List[str]) -> Dict[str, str]:
    """
    Suggest field mappings based on column names.

    Returns dict mapping target_field to source_column.
    Example: {"email": "Email Address", "full_name": "Name"}
    """
    suggestions = {}
    columns_lower = {col.lower().strip(): col for col in columns}

    for target_field, possible_names in COLUMN_NAME_SUGGESTIONS.items():
        for name in possible_names:
            if name in columns_lower:
                suggestions[target_field] = columns_lower[name]
                break

    return suggestions
