from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from typing import Optional, List
import logging

from app.db.database import get_db
from app.models.user import User
from app.models.campaign import Message, MessageEvent, MessageStatus, Campaign
from app.models.contact import Contact
from app.schemas.campaign import (
    EmailSendRequest,
    MessageResponse,
    MessageEventResponse,
    EmailLogResponse,
    PaginatedEmailLogs,
    PaginatedMessages
)
from app.services.email_service import email_service
from app.api.v1.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_email(
    email_data: EmailSendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a single email via AWS SES
    """
    # Try to find the contact by email (for updating stats)
    contact = None
    contact_result = await db.execute(
        select(Contact).filter(
            Contact.organization_id == current_user.organization_id,
            Contact.email == email_data.to_email.lower()
        )
    )
    contact = contact_result.scalar_one_or_none()

    # Send email via SES
    result = await email_service.send_email(
        to_email=email_data.to_email,
        subject=email_data.subject,
        html_content=email_data.html_content,
        text_content=email_data.text_content,
        from_email=email_data.from_email,
        from_name=email_data.from_name,
        reply_to=email_data.reply_to,
    )

    # Create message record
    message = Message(
        campaign_id=None,  # Single email, not part of a campaign
        contact_id=contact.id if contact else None,  # Link to contact if found
        recipient_email=email_data.to_email,
        recipient_name=email_data.to_name or (contact.full_name if contact else None),
        subject=email_data.subject,
        html_content=email_data.html_content,
        text_content=email_data.text_content,
        status=result['status'],
        ses_message_id=result.get('message_id'),
        error_message=result.get('error') if not result['success'] else None,
        sent_at=datetime.utcnow() if result['success'] else None,
    )

    db.add(message)
    await db.flush()

    # Create event
    event = MessageEvent(
        message_id=message.id,
        event_type='sent' if result['success'] else 'failed',
        event_data=result,
    )
    db.add(event)

    # Update contact stats if email was sent successfully and contact exists
    if result['success'] and contact:
        contact.total_emails_sent += 1
        contact.last_email_sent_at = datetime.utcnow()
        logger.info(f"Updated contact {contact.id} stats: total_emails_sent={contact.total_emails_sent}")

    await db.commit()
    await db.refresh(message)

    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {result.get('error')}",
        )

    return message


@router.get("/verify/{email}")
async def verify_email_identity(
    email: str,
    current_user: User = Depends(get_current_user),
):
    """
    Send verification email for AWS SES
    """
    result = await email_service.verify_email_identity(email)

    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send verification: {result.get('error')}",
        )

    return result


@router.get("/verify-status/{email}")
async def check_verification_status(
    email: str,
    current_user: User = Depends(get_current_user),
):
    """
    Check verification status of an email in AWS SES
    """
    result = await email_service.check_verification_status(email)

    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check status: {result.get('error')}",
        )

    return result


@router.get("/messages", response_model=list[MessageResponse])
async def get_messages(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all messages for the current user's organization
    """
    result = await db.execute(
        select(Message)
        .order_by(Message.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    messages = result.scalars().all()

    return messages


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific message by ID
    """
    result = await db.execute(select(Message).filter(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    return message


# ============= Email Logs Endpoint =============

@router.get("/logs", response_model=PaginatedEmailLogs)
async def get_email_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    campaign_id: Optional[int] = Query(None, description="Filter by campaign ID"),
    contact_id: Optional[int] = Query(None, description="Filter by contact ID"),
    status_filter: Optional[MessageStatus] = Query(None, alias="status", description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by email or subject"),
    days: Optional[int] = Query(None, description="Filter logs from last N days"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get email logs with pagination, filtering, and search.

    This endpoint provides detailed logs of all sent emails including:
    - Status tracking (sent, delivered, opened, clicked, bounced, failed)
    - Timestamps for each status change
    - Associated campaign and contact information
    - Event history for each email
    """
    logger.info(f"Fetching email logs for organization {current_user.organization_id}")

    # Build base query with organization filter through campaigns or contacts
    query = select(Message).options(selectinload(Message.events))

    # Filter by campaigns belonging to user's organization
    if campaign_id:
        query = query.filter(Message.campaign_id == campaign_id)
    else:
        # Get all campaign IDs for this organization
        campaign_subquery = select(Campaign.id).filter(
            Campaign.organization_id == current_user.organization_id
        )
        query = query.filter(
            or_(
                Message.campaign_id.in_(campaign_subquery),
                Message.campaign_id.is_(None)  # Include single emails
            )
        )

    # Filter by contact
    if contact_id:
        query = query.filter(Message.contact_id == contact_id)

    # Filter by status
    if status_filter:
        query = query.filter(Message.status == status_filter)

    # Filter by date range
    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Message.created_at >= cutoff_date)

    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Message.recipient_email.ilike(search_term),
                Message.subject.ilike(search_term),
                Message.recipient_name.ilike(search_term),
            )
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get summary stats
    stats_base = query.subquery()

    # Count by status
    sent_count = await db.execute(
        select(func.count()).select_from(stats_base).filter(stats_base.c.status.in_(['sent', 'delivered', 'pending', 'queued']))
    )
    total_sent = sent_count.scalar() or 0

    delivered_count = await db.execute(
        select(func.count()).select_from(stats_base).filter(stats_base.c.status == 'delivered')
    )
    total_delivered = delivered_count.scalar() or 0

    opened_count = await db.execute(
        select(func.count()).select_from(stats_base).filter(stats_base.c.opened_at.isnot(None))
    )
    total_opened = opened_count.scalar() or 0

    clicked_count = await db.execute(
        select(func.count()).select_from(stats_base).filter(stats_base.c.clicked_at.isnot(None))
    )
    total_clicked = clicked_count.scalar() or 0

    bounced_count = await db.execute(
        select(func.count()).select_from(stats_base).filter(stats_base.c.status == 'bounced')
    )
    total_bounced = bounced_count.scalar() or 0

    failed_count = await db.execute(
        select(func.count()).select_from(stats_base).filter(stats_base.c.status == 'failed')
    )
    total_failed = failed_count.scalar() or 0

    # Apply pagination
    query = query.order_by(Message.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    messages = result.scalars().all()

    # Build response with campaign names
    log_items = []
    for message in messages:
        campaign_name = None
        if message.campaign_id:
            campaign_result = await db.execute(
                select(Campaign.name).filter(Campaign.id == message.campaign_id)
            )
            campaign_name = campaign_result.scalar_one_or_none()

        events = [
            MessageEventResponse(
                id=e.id,
                message_id=e.message_id,
                event_type=e.event_type,
                event_subtype=e.event_subtype,
                event_data=e.event_data,
                user_agent=e.user_agent,
                ip_address=e.ip_address,
                link_url=e.link_url,
                timestamp=e.timestamp
            )
            for e in (message.events or [])
        ]

        log_items.append(
            EmailLogResponse(
                id=message.id,
                campaign_id=message.campaign_id,
                campaign_name=campaign_name,
                contact_id=message.contact_id,
                recipient_email=message.recipient_email,
                recipient_name=message.recipient_name,
                subject=message.subject,
                status=message.status,
                ses_message_id=message.ses_message_id,
                error_message=message.error_message,
                created_at=message.created_at,
                queued_at=message.queued_at,
                sent_at=message.sent_at,
                delivered_at=message.delivered_at,
                opened_at=message.opened_at,
                clicked_at=message.clicked_at,
                bounced_at=message.bounced_at,
                open_count=message.open_count or 0,
                click_count=message.click_count or 0,
                events=events
            )
        )

    logger.info(f"Retrieved {len(log_items)} email logs (total: {total})")

    return PaginatedEmailLogs(
        items=log_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
        total_sent=total_sent,
        total_delivered=total_delivered,
        total_opened=total_opened,
        total_clicked=total_clicked,
        total_bounced=total_bounced,
        total_failed=total_failed
    )


@router.get("/logs/{message_id}/events", response_model=List[MessageEventResponse])
async def get_message_events(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all events for a specific message
    """
    # Verify message exists
    result = await db.execute(select(Message).filter(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    # Get events
    result = await db.execute(
        select(MessageEvent)
        .filter(MessageEvent.message_id == message_id)
        .order_by(MessageEvent.timestamp.desc())
    )
    events = result.scalars().all()

    return events
