from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime
from typing import List, Optional
import math
import logging

logger = logging.getLogger(__name__)

from app.db.database import get_db
from app.models.user import User
from app.models.campaign import Campaign, CampaignRecipient, CampaignStatus, Message
from app.models.contact import Contact, ContactList, ContactListMembership, ContactStatus
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignStats,
    CampaignAddRecipients,
    CampaignRecipientResponse,
    RecipientPreview,
    CampaignSendRequest,
    CampaignSendResponse,
    PaginatedCampaigns,
)
from app.api.v1.auth import get_current_user
from app.tasks.email_tasks import process_campaign

router = APIRouter()


# ============= Campaign CRUD =============

@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    campaign_data: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new email campaign"""
    campaign = Campaign(
        organization_id=current_user.organization_id,
        template_id=campaign_data.template_id,
        name=campaign_data.name,
        subject=campaign_data.subject,
        from_name=campaign_data.from_name,
        from_email=campaign_data.from_email,
        reply_to=campaign_data.reply_to,
        html_content=campaign_data.html_content,
        text_content=campaign_data.text_content,
        scheduled_at=campaign_data.scheduled_at,
    )

    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    return campaign


@router.get("/", response_model=PaginatedCampaigns)
async def get_campaigns(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: Optional[CampaignStatus] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all campaigns for the current user's organization"""
    query = select(Campaign).filter(
        Campaign.organization_id == current_user.organization_id
    )

    if status_filter:
        query = query.filter(Campaign.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.order_by(Campaign.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    campaigns = result.scalars().all()

    return PaginatedCampaigns(
        items=campaigns,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific campaign by ID"""
    result = await db.execute(
        select(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    campaign_data: CampaignUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a campaign (only draft campaigns can be fully edited)"""
    result = await db.execute(
        select(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    # Only allow full updates on draft campaigns
    if campaign.status != CampaignStatus.DRAFT:
        allowed_fields = {'name'}  # Only allow name change for non-draft
        update_data = campaign_data.model_dump(exclude_unset=True)
        if any(key not in allowed_fields for key in update_data.keys()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only update name for non-draft campaigns"
            )

    update_data = campaign_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    campaign.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(campaign)

    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a campaign (only draft campaigns)"""
    result = await db.execute(
        select(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    if campaign.status != CampaignStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete draft campaigns",
        )

    await db.delete(campaign)
    await db.commit()


# ============= Campaign Recipients =============

@router.post("/{campaign_id}/recipients", response_model=RecipientPreview)
async def add_campaign_recipients(
    campaign_id: int,
    recipients_data: CampaignAddRecipients,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add recipients to a campaign from contacts or contact lists"""
    # Get campaign
    result = await db.execute(
        select(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.SCHEDULED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only add recipients to draft or scheduled campaigns"
        )

    # Collect contact IDs
    contact_ids = set()

    # If select_all is True, get all contacts for the organization
    if recipients_data.select_all:
        # Get all active contacts for the organization
        query = select(Contact.id).filter(
            Contact.organization_id == current_user.organization_id
        )
        # Apply status filter - convert string to enum if needed
        if recipients_data.filter_status:
            try:
                # Handle both string and enum values
                if isinstance(recipients_data.filter_status, str):
                    status_enum = ContactStatus(recipients_data.filter_status.lower())
                else:
                    status_enum = recipients_data.filter_status
                query = query.filter(Contact.status == status_enum)
            except ValueError:
                # Invalid status, default to subscribed
                query = query.filter(Contact.status == ContactStatus.SUBSCRIBED)
        else:
            # Default to subscribed contacts
            query = query.filter(Contact.status == ContactStatus.SUBSCRIBED)

        result = await db.execute(query)
        all_contact_ids = [row[0] for row in result.all()]
        contact_ids.update(all_contact_ids)

        # Log for debugging
        logger.info(f"select_all: Found {len(all_contact_ids)} contacts for org {current_user.organization_id}")
    else:
        # Add from specific contact IDs
        if recipients_data.contact_ids:
            contact_ids.update(recipients_data.contact_ids)

        # Add from contact lists
        if recipients_data.list_ids:
            for list_id in recipients_data.list_ids:
                result = await db.execute(
                    select(ContactListMembership.contact_id).filter(
                        ContactListMembership.list_id == list_id
                    ).join(ContactList).filter(
                        ContactList.organization_id == current_user.organization_id
                    )
                )
                list_contact_ids = [row[0] for row in result.all()]
                contact_ids.update(list_contact_ids)

    # Get existing recipients
    result = await db.execute(
        select(CampaignRecipient.contact_id).filter(
            CampaignRecipient.campaign_id == campaign_id
        )
    )
    existing_contact_ids = {row[0] for row in result.all()}

    # Filter contacts
    total_contacts = len(contact_ids)
    excluded_unsubscribed = 0
    excluded_bounced = 0
    excluded_duplicate = len(contact_ids & existing_contact_ids)

    eligible_contact_ids = []
    for contact_id in contact_ids:
        if contact_id in existing_contact_ids:
            continue

        result = await db.execute(
            select(Contact).filter(
                Contact.id == contact_id,
                Contact.organization_id == current_user.organization_id,
            )
        )
        contact = result.scalar_one_or_none()

        if not contact:
            continue

        if recipients_data.exclude_unsubscribed and contact.status == ContactStatus.UNSUBSCRIBED:
            excluded_unsubscribed += 1
            continue

        if recipients_data.exclude_bounced and contact.status == ContactStatus.BOUNCED:
            excluded_bounced += 1
            continue

        eligible_contact_ids.append(contact_id)

    # Add recipients
    for contact_id in eligible_contact_ids:
        recipient = CampaignRecipient(
            campaign_id=campaign_id,
            contact_id=contact_id,
            status="pending"
        )
        db.add(recipient)

    # Update campaign total recipients
    campaign.total_recipients = len(existing_contact_ids) + len(eligible_contact_ids)

    await db.commit()

    return RecipientPreview(
        total_contacts=total_contacts,
        eligible_contacts=len(eligible_contact_ids),
        excluded_unsubscribed=excluded_unsubscribed,
        excluded_bounced=excluded_bounced,
        excluded_duplicate=excluded_duplicate
    )


@router.get("/{campaign_id}/recipients")
async def get_campaign_recipients(
    campaign_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recipients for a campaign"""
    # Verify campaign
    result = await db.execute(
        select(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    # Build query
    query = select(CampaignRecipient, Contact).join(
        Contact, CampaignRecipient.contact_id == Contact.id
    ).filter(CampaignRecipient.campaign_id == campaign_id)

    if status_filter:
        query = query.filter(CampaignRecipient.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(
        select(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id).subquery()
    )
    if status_filter:
        count_query = select(func.count()).select_from(
            select(CampaignRecipient).filter(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == status_filter
            ).subquery()
        )
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    recipients = []
    for recipient, contact in rows:
        recipients.append({
            "id": recipient.id,
            "campaign_id": recipient.campaign_id,
            "contact_id": recipient.contact_id,
            "status": recipient.status,
            "error_message": recipient.error_message,
            "queued_at": recipient.queued_at,
            "sent_at": recipient.sent_at,
            "email": contact.email,
            "full_name": contact.full_name,
        })

    return {
        "items": recipients,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0
    }


@router.delete("/{campaign_id}/recipients", status_code=status.HTTP_204_NO_CONTENT)
async def clear_campaign_recipients(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove all recipients from a campaign (only draft/scheduled)"""
    result = await db.execute(
        select(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.SCHEDULED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only clear recipients from draft or scheduled campaigns"
        )

    # Delete all recipients
    result = await db.execute(
        select(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id)
    )
    recipients = result.scalars().all()
    for recipient in recipients:
        await db.delete(recipient)

    campaign.total_recipients = 0
    await db.commit()


# ============= Campaign Actions =============

@router.post("/{campaign_id}/send", response_model=CampaignSendResponse)
async def send_campaign(
    campaign_id: int,
    send_data: CampaignSendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start sending a campaign or schedule it"""
    result = await db.execute(
        select(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.SCHEDULED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot send campaign with status {campaign.status}"
        )

    if campaign.total_recipients == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign has no recipients"
        )

    # Calculate estimated batches
    batch_size = 50
    estimated_batches = math.ceil(campaign.total_recipients / batch_size)

    if send_data.send_at and send_data.send_at > datetime.utcnow():
        # Schedule for later
        campaign.status = CampaignStatus.SCHEDULED
        campaign.scheduled_at = send_data.send_at
        message = f"Campaign scheduled for {send_data.send_at.isoformat()}"
    else:
        # Send immediately
        campaign.status = CampaignStatus.QUEUED
        campaign.total_batches = estimated_batches
        await db.commit()

        # Queue the campaign processing task
        process_campaign.delay(campaign_id)
        message = "Campaign queued for sending"

    await db.commit()

    return CampaignSendResponse(
        campaign_id=campaign_id,
        status=campaign.status,
        total_recipients=campaign.total_recipients,
        estimated_batches=estimated_batches,
        message=message
    )


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pause a sending campaign"""
    result = await db.execute(
        select(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    if campaign.status != CampaignStatus.SENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only pause campaigns that are currently sending"
        )

    campaign.status = CampaignStatus.PAUSED
    campaign.paused_at = datetime.utcnow()
    await db.commit()
    await db.refresh(campaign)

    return campaign


@router.post("/{campaign_id}/resume", response_model=CampaignSendResponse)
async def resume_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused campaign"""
    result = await db.execute(
        select(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    if campaign.status != CampaignStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only resume paused campaigns"
        )

    campaign.status = CampaignStatus.QUEUED
    await db.commit()

    # Re-queue the campaign
    process_campaign.delay(campaign_id)

    return CampaignSendResponse(
        campaign_id=campaign_id,
        status=campaign.status,
        total_recipients=campaign.total_recipients,
        estimated_batches=campaign.total_batches,
        message="Campaign resumed"
    )


@router.post("/{campaign_id}/cancel", response_model=CampaignResponse)
async def cancel_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a campaign (only scheduled or paused)"""
    result = await db.execute(
        select(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    if campaign.status not in [CampaignStatus.SCHEDULED, CampaignStatus.PAUSED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only cancel scheduled or paused campaigns"
        )

    campaign.status = CampaignStatus.CANCELLED
    await db.commit()
    await db.refresh(campaign)

    return campaign


# ============= Campaign Stats =============

@router.get("/{campaign_id}/stats", response_model=CampaignStats)
async def get_campaign_stats(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed statistics for a campaign"""
    result = await db.execute(
        select(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    # Calculate rates
    total = campaign.total_recipients or 1  # Avoid division by zero
    sent = campaign.sent_count or 0
    delivered = campaign.delivered_count or 0

    delivery_rate = (delivered / sent * 100) if sent > 0 else 0
    open_rate = (campaign.unique_opens / delivered * 100) if delivered > 0 else 0
    click_rate = (campaign.unique_clicks / delivered * 100) if delivered > 0 else 0
    bounce_rate = (campaign.bounced_count / sent * 100) if sent > 0 else 0
    complaint_rate = (campaign.complained_count / sent * 100) if sent > 0 else 0
    unsubscribe_rate = (campaign.unsubscribed_count / delivered * 100) if delivered > 0 else 0

    return CampaignStats(
        campaign_id=campaign_id,
        total_recipients=campaign.total_recipients,
        sent=campaign.sent_count,
        delivered=campaign.delivered_count,
        failed=campaign.failed_count,
        opened=campaign.opened_count,
        unique_opens=campaign.unique_opens,
        clicked=campaign.clicked_count,
        unique_clicks=campaign.unique_clicks,
        bounced=campaign.bounced_count,
        complained=campaign.complained_count,
        unsubscribed=campaign.unsubscribed_count,
        delivery_rate=round(delivery_rate, 2),
        open_rate=round(open_rate, 2),
        click_rate=round(click_rate, 2),
        bounce_rate=round(bounce_rate, 2),
        complaint_rate=round(complaint_rate, 2),
        unsubscribe_rate=round(unsubscribe_rate, 2)
    )
