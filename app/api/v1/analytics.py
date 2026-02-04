"""
Analytics API - Dashboard statistics and reporting endpoints
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models import User, CampaignStatus
from app.services import analytics_service

router = APIRouter()


@router.get("/overview")
async def get_dashboard_overview(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get high-level dashboard statistics.
    Returns contacts, campaigns, emails sent, and key rates.
    """
    data = await analytics_service.get_dashboard_overview(
        db=db,
        organization_id=current_user.organization_id,
        days=days
    )
    return data


@router.get("/campaigns/performance")
async def get_campaign_performance(
    limit: int = Query(10, ge=1, le=50),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get performance metrics for recent campaigns.
    """
    status_filter = None
    if status:
        try:
            status_filter = CampaignStatus(status)
        except ValueError:
            pass

    data = await analytics_service.get_campaign_performance(
        db=db,
        organization_id=current_user.organization_id,
        limit=limit,
        status_filter=status_filter
    )
    return {"campaigns": data}


@router.get("/campaigns/top")
async def get_top_campaigns(
    metric: str = Query("open_rate", description="Metric to sort by: open_rate, click_rate, delivery_rate"),
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get top performing campaigns by a specific metric.
    """
    data = await analytics_service.get_top_performing_campaigns(
        db=db,
        organization_id=current_user.organization_id,
        metric=metric,
        limit=limit
    )
    return {"campaigns": data}


@router.get("/activity/daily")
async def get_daily_activity(
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get daily email activity for charting.
    Returns sent, delivered, opened, clicked counts per day.
    """
    data = await analytics_service.get_daily_activity(
        db=db,
        organization_id=current_user.organization_id,
        days=days
    )
    return {"activity": data}


@router.get("/activity/events")
async def get_event_timeline(
    limit: int = Query(50, ge=1, le=200),
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent events for activity feed.
    Event types: sent, delivered, opened, clicked, bounced, complained, unsubscribed
    """
    types_list = None
    if event_types:
        types_list = [t.strip() for t in event_types.split(",")]

    data = await analytics_service.get_event_timeline(
        db=db,
        organization_id=current_user.organization_id,
        limit=limit,
        event_types=types_list
    )
    return {"events": data}


@router.get("/contacts/growth")
async def get_contact_growth(
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get daily contact growth for charting.
    Returns new contacts and cumulative count per day.
    """
    data = await analytics_service.get_contact_growth(
        db=db,
        organization_id=current_user.organization_id,
        days=days
    )
    return {"growth": data}


@router.get("/contacts/breakdown")
async def get_contacts_breakdown(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get breakdown of contact statuses.
    """
    data = await analytics_service.get_status_breakdown(
        db=db,
        organization_id=current_user.organization_id
    )
    return {"breakdown": data}
