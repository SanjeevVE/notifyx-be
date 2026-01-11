from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.models.campaign import Campaign, CampaignStatus
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignResponse
from app.api.v1.auth import get_current_user

router = APIRouter()


@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    campaign_data: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new email campaign
    """
    campaign = Campaign(
        organization_id=current_user.organization_id,
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


@router.get("/", response_model=list[CampaignResponse])
async def get_campaigns(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all campaigns for the current user's organization
    """
    result = await db.execute(
        select(Campaign)
        .filter(Campaign.organization_id == current_user.organization_id)
        .order_by(Campaign.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    campaigns = result.scalars().all()

    return campaigns


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific campaign by ID
    """
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
    """
    Update a campaign
    """
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

    # Update fields
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
    """
    Delete a campaign
    """
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

    # Only allow deletion of draft campaigns
    if campaign.status != CampaignStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete draft campaigns",
        )

    await db.delete(campaign)
    await db.commit()
