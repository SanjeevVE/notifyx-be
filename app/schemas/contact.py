from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models.contact import ContactStatus


# ============= Contact Schemas =============

class ContactBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class ContactCreate(ContactBase):
    """Schema for creating a new contact"""
    pass


class ContactUpdate(BaseModel):
    """Schema for updating an existing contact"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[ContactStatus] = None
    custom_fields: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class ContactResponse(ContactBase):
    """Schema for contact response"""
    id: int
    organization_id: int
    status: ContactStatus
    total_emails_sent: int
    total_emails_opened: int
    total_emails_clicked: int
    last_email_sent_at: Optional[datetime]
    last_email_opened_at: Optional[datetime]
    unsubscribed_at: Optional[datetime]
    bounce_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ContactBrief(BaseModel):
    """Brief contact info for lists"""
    id: int
    email: str
    full_name: Optional[str]
    status: ContactStatus

    class Config:
        from_attributes = True


# ============= Contact List Schemas =============

class ContactListBase(BaseModel):
    name: str
    description: Optional[str] = None


class ContactListCreate(ContactListBase):
    """Schema for creating a contact list"""
    pass


class ContactListUpdate(BaseModel):
    """Schema for updating a contact list"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ContactListResponse(ContactListBase):
    """Schema for contact list response"""
    id: int
    organization_id: int
    is_active: bool
    contact_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ContactListWithContacts(ContactListResponse):
    """Contact list with its contacts"""
    contacts: List[ContactBrief] = []


# ============= Contact Import Schemas =============

class ContactImportMapping(BaseModel):
    """Column mapping for CSV import"""
    email_column: str
    full_name_column: Optional[str] = None
    company_column: Optional[str] = None
    phone_column: Optional[str] = None
    custom_field_columns: Optional[Dict[str, str]] = None  # {"custom_field_name": "csv_column_name"}


class ContactImportRequest(BaseModel):
    """Request schema for importing contacts"""
    list_id: Optional[int] = None  # Optional list to add contacts to
    mapping: ContactImportMapping
    skip_duplicates: bool = True
    update_existing: bool = False


class ContactImportResult(BaseModel):
    """Result of a contact import"""
    total_rows: int
    imported: int
    skipped: int
    failed: int
    errors: List[Dict[str, Any]] = []


# ============= Bulk Operations =============

class ContactBulkAddToList(BaseModel):
    """Add multiple contacts to a list"""
    contact_ids: List[int]


class ContactBulkDelete(BaseModel):
    """Delete multiple contacts"""
    contact_ids: List[int]


class ContactBulkUpdateStatus(BaseModel):
    """Update status for multiple contacts"""
    contact_ids: List[int]
    status: ContactStatus


# ============= Search/Filter =============

class ContactSearchParams(BaseModel):
    """Search parameters for contacts"""
    query: Optional[str] = None  # Search in email, name, company
    status: Optional[ContactStatus] = None
    list_id: Optional[int] = None
    tags: Optional[List[str]] = None
    has_opened: Optional[bool] = None
    has_clicked: Optional[bool] = None


# ============= Pagination =============

class PaginatedContacts(BaseModel):
    """Paginated contact list"""
    items: List[ContactResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedContactLists(BaseModel):
    """Paginated contact lists"""
    items: List[ContactListResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
