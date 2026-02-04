from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any


class TemplateBase(BaseModel):
    """Base schema for email template"""
    name: str
    description: Optional[str] = None
    subject: str
    html_content: str
    text_content: Optional[str] = None
    category: Optional[str] = None


class TemplateCreate(TemplateBase):
    """Schema for creating a new template"""
    variables: Optional[List[str]] = None  # List of variable names used in template


class TemplateUpdate(BaseModel):
    """Schema for updating an existing template"""
    name: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    category: Optional[str] = None
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None


class TemplateResponse(TemplateBase):
    """Schema for template response"""
    id: int
    organization_id: int
    variables: Optional[List[str]]
    is_active: bool
    is_default: bool
    times_used: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TemplateBrief(BaseModel):
    """Brief template info for lists"""
    id: int
    name: str
    subject: str
    category: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class TemplatePreviewRequest(BaseModel):
    """Request to preview a template with sample data"""
    sample_data: Dict[str, Any]  # Variable values for preview


class TemplatePreviewResponse(BaseModel):
    """Preview of rendered template"""
    subject: str
    html_content: str
    text_content: Optional[str]


class TemplateVariableInfo(BaseModel):
    """Information about variables in a template"""
    variables: List[str]  # List of variable names found
    sample_data: Dict[str, str]  # Sample data structure


class TemplateValidationResult(BaseModel):
    """Result of template validation"""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    variables_found: List[str] = []


# ============= Pagination =============

class PaginatedTemplates(BaseModel):
    """Paginated template list"""
    items: List[TemplateResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
