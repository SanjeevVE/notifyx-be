from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from datetime import datetime
import re

from app.db.database import get_db
from app.models.user import User
from app.models.template import EmailTemplate
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateBrief,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateVariableInfo,
    TemplateValidationResult,
    PaginatedTemplates,
)
from app.api.v1.auth import get_current_user

router = APIRouter()

# Regex pattern to find template variables like {{variable_name}} or {{ variable_name }}
VARIABLE_PATTERN = re.compile(r'\{\{\s*(\w+)\s*\}\}')


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new email template"""
    # Extract variables from template content
    variables = _extract_variables(template_data.html_content)
    if template_data.subject:
        variables.extend(_extract_variables(template_data.subject))
    variables = list(set(variables))  # Remove duplicates

    template = EmailTemplate(
        organization_id=current_user.organization_id,
        name=template_data.name,
        description=template_data.description,
        subject=template_data.subject,
        html_content=template_data.html_content,
        text_content=template_data.text_content,
        variables=template_data.variables or variables,
        category=template_data.category,
    )

    db.add(template)
    await db.commit()
    await db.refresh(template)

    return template


@router.get("/", response_model=PaginatedTemplates)
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None,
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List email templates with pagination"""
    query = select(EmailTemplate).filter(
        EmailTemplate.organization_id == current_user.organization_id
    )

    if active_only:
        query = query.filter(EmailTemplate.is_active == True)

    if category:
        query = query.filter(EmailTemplate.category == category)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            EmailTemplate.name.ilike(search_term) |
            EmailTemplate.subject.ilike(search_term)
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.order_by(EmailTemplate.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    templates = result.scalars().all()

    return PaginatedTemplates(
        items=templates,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific template by ID"""
    result = await db.execute(
        select(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == current_user.organization_id,
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    return template


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_data: TemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a template"""
    result = await db.execute(
        select(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == current_user.organization_id,
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    update_data = template_data.model_dump(exclude_unset=True)

    # Re-extract variables if content changed
    if 'html_content' in update_data or 'subject' in update_data:
        html = update_data.get('html_content', template.html_content)
        subject = update_data.get('subject', template.subject)
        variables = _extract_variables(html)
        variables.extend(_extract_variables(subject))
        update_data['variables'] = list(set(variables))

    for field, value in update_data.items():
        setattr(template, field, value)

    template.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(template)

    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a template"""
    result = await db.execute(
        select(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == current_user.organization_id,
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    await db.delete(template)
    await db.commit()


@router.post("/{template_id}/preview", response_model=TemplatePreviewResponse)
async def preview_template(
    template_id: int,
    preview_data: TemplatePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Preview a template with sample data"""
    result = await db.execute(
        select(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == current_user.organization_id,
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Render template with sample data
    rendered_subject = _render_template(template.subject, preview_data.sample_data)
    rendered_html = _render_template(template.html_content, preview_data.sample_data)
    rendered_text = _render_template(template.text_content, preview_data.sample_data) if template.text_content else None

    return TemplatePreviewResponse(
        subject=rendered_subject,
        html_content=rendered_html,
        text_content=rendered_text
    )


@router.get("/{template_id}/variables", response_model=TemplateVariableInfo)
async def get_template_variables(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get variables used in a template"""
    result = await db.execute(
        select(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == current_user.organization_id,
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    variables = template.variables or _extract_variables(template.html_content + template.subject)

    # Generate sample data structure
    sample_data = {var: f"[{var}]" for var in variables}

    return TemplateVariableInfo(
        variables=variables,
        sample_data=sample_data
    )


@router.post("/validate", response_model=TemplateValidationResult)
async def validate_template(
    template_data: TemplateCreate,
    current_user: User = Depends(get_current_user),
):
    """Validate template content without saving"""
    errors = []
    warnings = []

    # Check for empty subject
    if not template_data.subject or not template_data.subject.strip():
        errors.append("Subject line is required")

    # Check for empty content
    if not template_data.html_content or not template_data.html_content.strip():
        errors.append("HTML content is required")

    # Check for unsubscribe link (required for compliance)
    if '{{unsubscribe_link}}' not in template_data.html_content.lower():
        warnings.append("Template should include an {{unsubscribe_link}} for compliance")

    # Extract variables
    variables = _extract_variables(template_data.html_content)
    variables.extend(_extract_variables(template_data.subject))
    variables = list(set(variables))

    # Check for common required variables
    common_vars = ['first_name', 'name', 'email']
    has_personalization = any(var in variables for var in common_vars)
    if not has_personalization:
        warnings.append("Consider adding personalization variables like {{first_name}} or {{name}}")

    return TemplateValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        variables_found=variables
    )


@router.post("/{template_id}/duplicate", response_model=TemplateResponse)
async def duplicate_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a copy of an existing template"""
    result = await db.execute(
        select(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == current_user.organization_id,
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    new_template = EmailTemplate(
        organization_id=current_user.organization_id,
        name=f"{template.name} (Copy)",
        description=template.description,
        subject=template.subject,
        html_content=template.html_content,
        text_content=template.text_content,
        variables=template.variables,
        category=template.category,
    )

    db.add(new_template)
    await db.commit()
    await db.refresh(new_template)

    return new_template


# ============= Helper Functions =============

def _extract_variables(content: str) -> List[str]:
    """Extract variable names from template content"""
    if not content:
        return []
    matches = VARIABLE_PATTERN.findall(content)
    return list(set(matches))


def _render_template(content: str, data: dict) -> str:
    """Render template by replacing variables with data values"""
    if not content:
        return content

    def replace_var(match):
        var_name = match.group(1)
        return str(data.get(var_name, match.group(0)))

    return VARIABLE_PATTERN.sub(replace_var, content)
