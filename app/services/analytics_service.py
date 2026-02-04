"""
Analytics Service - Aggregate statistics and metrics for dashboard
"""
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Campaign, CampaignStatus, Message, MessageStatus, MessageEvent,
    Contact, ContactStatus, Organization
)


async def get_dashboard_overview(
    db: AsyncSession,
    organization_id: int,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get high-level dashboard statistics for an organization.
    Returns total counts and trends.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Total contacts
    total_contacts_result = await db.execute(
        select(func.count(Contact.id))
        .where(Contact.organization_id == organization_id)
    )
    total_contacts = total_contacts_result.scalar() or 0

    # Active (subscribed) contacts
    active_contacts_result = await db.execute(
        select(func.count(Contact.id))
        .where(Contact.organization_id == organization_id)
        .where(Contact.status == ContactStatus.SUBSCRIBED)
    )
    active_contacts = active_contacts_result.scalar() or 0

    # Total campaigns
    total_campaigns_result = await db.execute(
        select(func.count(Campaign.id))
        .where(Campaign.organization_id == organization_id)
    )
    total_campaigns = total_campaigns_result.scalar() or 0

    # Campaigns in period
    campaigns_in_period_result = await db.execute(
        select(func.count(Campaign.id))
        .where(Campaign.organization_id == organization_id)
        .where(Campaign.created_at >= start_date)
    )
    campaigns_in_period = campaigns_in_period_result.scalar() or 0

    # Total emails sent (all time)
    total_sent_result = await db.execute(
        select(func.sum(Campaign.sent_count))
        .where(Campaign.organization_id == organization_id)
    )
    total_emails_sent = total_sent_result.scalar() or 0

    # Emails sent in period
    sent_in_period_result = await db.execute(
        select(func.count(Message.id))
        .join(Campaign, Message.campaign_id == Campaign.id)
        .where(Campaign.organization_id == organization_id)
        .where(Message.sent_at >= start_date)
    )
    emails_in_period = sent_in_period_result.scalar() or 0

    # Aggregate metrics for the period
    metrics_result = await db.execute(
        select(
            func.sum(Campaign.sent_count).label("sent"),
            func.sum(Campaign.delivered_count).label("delivered"),
            func.sum(Campaign.opened_count).label("opened"),
            func.sum(Campaign.unique_opens).label("unique_opens"),
            func.sum(Campaign.clicked_count).label("clicked"),
            func.sum(Campaign.unique_clicks).label("unique_clicks"),
            func.sum(Campaign.bounced_count).label("bounced"),
            func.sum(Campaign.complained_count).label("complained"),
            func.sum(Campaign.unsubscribed_count).label("unsubscribed")
        )
        .where(Campaign.organization_id == organization_id)
        .where(Campaign.started_at >= start_date)
    )
    metrics = metrics_result.one()

    sent = metrics.sent or 0
    delivered = metrics.delivered or 0
    unique_opens = metrics.unique_opens or 0
    unique_clicks = metrics.unique_clicks or 0
    bounced = metrics.bounced or 0

    # Calculate rates
    delivery_rate = (delivered / sent * 100) if sent > 0 else 0
    open_rate = (unique_opens / delivered * 100) if delivered > 0 else 0
    click_rate = (unique_clicks / unique_opens * 100) if unique_opens > 0 else 0
    bounce_rate = (bounced / sent * 100) if sent > 0 else 0

    return {
        "period_days": days,
        "contacts": {
            "total": total_contacts,
            "active": active_contacts,
            "unsubscribed": total_contacts - active_contacts
        },
        "campaigns": {
            "total": total_campaigns,
            "in_period": campaigns_in_period
        },
        "emails": {
            "total_sent": total_emails_sent,
            "sent_in_period": emails_in_period
        },
        "metrics": {
            "sent": sent,
            "delivered": delivered,
            "opened": metrics.opened or 0,
            "unique_opens": unique_opens,
            "clicked": metrics.clicked or 0,
            "unique_clicks": unique_clicks,
            "bounced": bounced,
            "complained": metrics.complained or 0,
            "unsubscribed": metrics.unsubscribed or 0
        },
        "rates": {
            "delivery_rate": round(delivery_rate, 2),
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2),
            "bounce_rate": round(bounce_rate, 2)
        }
    }


async def get_campaign_performance(
    db: AsyncSession,
    organization_id: int,
    limit: int = 10,
    status_filter: Optional[CampaignStatus] = None
) -> List[Dict[str, Any]]:
    """
    Get performance metrics for recent campaigns.
    """
    query = (
        select(Campaign)
        .where(Campaign.organization_id == organization_id)
        .order_by(Campaign.created_at.desc())
        .limit(limit)
    )

    if status_filter:
        query = query.where(Campaign.status == status_filter)

    result = await db.execute(query)
    campaigns = result.scalars().all()

    performance_data = []
    for campaign in campaigns:
        sent = campaign.sent_count or 0
        delivered = campaign.delivered_count or 0
        unique_opens = campaign.unique_opens or 0
        unique_clicks = campaign.unique_clicks or 0

        performance_data.append({
            "id": campaign.id,
            "name": campaign.name,
            "subject": campaign.subject,
            "status": campaign.status.value,
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            "started_at": campaign.started_at.isoformat() if campaign.started_at else None,
            "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None,
            "recipients": campaign.total_recipients or 0,
            "metrics": {
                "sent": sent,
                "delivered": delivered,
                "opened": campaign.opened_count or 0,
                "unique_opens": unique_opens,
                "clicked": campaign.clicked_count or 0,
                "unique_clicks": unique_clicks,
                "bounced": campaign.bounced_count or 0,
                "complained": campaign.complained_count or 0,
                "unsubscribed": campaign.unsubscribed_count or 0
            },
            "rates": {
                "delivery_rate": round((delivered / sent * 100), 2) if sent > 0 else 0,
                "open_rate": round((unique_opens / delivered * 100), 2) if delivered > 0 else 0,
                "click_rate": round((unique_clicks / unique_opens * 100), 2) if unique_opens > 0 else 0,
                "bounce_rate": round((campaign.bounced_count or 0) / sent * 100, 2) if sent > 0 else 0
            }
        })

    return performance_data


async def get_daily_activity(
    db: AsyncSession,
    organization_id: int,
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    Get daily email activity (sent, delivered, opened, clicked) for charting.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Query messages with daily aggregation
    result = await db.execute(
        select(
            func.date(Message.sent_at).label("date"),
            func.count(Message.id).label("sent"),
            func.sum(case((Message.status == MessageStatus.DELIVERED, 1), else_=0)).label("delivered"),
            func.sum(case((Message.opened_at.isnot(None), 1), else_=0)).label("opened"),
            func.sum(case((Message.clicked_at.isnot(None), 1), else_=0)).label("clicked"),
            func.sum(case((Message.status == MessageStatus.BOUNCED, 1), else_=0)).label("bounced")
        )
        .join(Campaign, Message.campaign_id == Campaign.id)
        .where(Campaign.organization_id == organization_id)
        .where(Message.sent_at >= start_date)
        .where(Message.sent_at.isnot(None))
        .group_by(func.date(Message.sent_at))
        .order_by(func.date(Message.sent_at))
    )

    rows = result.all()

    # Convert to list of dicts
    activity_data = []
    for row in rows:
        activity_data.append({
            "date": row.date.isoformat() if row.date else None,
            "sent": row.sent or 0,
            "delivered": row.delivered or 0,
            "opened": row.opened or 0,
            "clicked": row.clicked or 0,
            "bounced": row.bounced or 0
        })

    return activity_data


async def get_event_timeline(
    db: AsyncSession,
    organization_id: int,
    limit: int = 50,
    event_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Get recent events (opens, clicks, bounces, etc.) for activity feed.
    """
    query = (
        select(MessageEvent, Message, Campaign)
        .join(Message, MessageEvent.message_id == Message.id)
        .outerjoin(Campaign, Message.campaign_id == Campaign.id)
        .where(
            (Campaign.organization_id == organization_id) |
            (Campaign.id.is_(None))  # Include single emails
        )
        .order_by(MessageEvent.timestamp.desc())
        .limit(limit)
    )

    if event_types:
        query = query.where(MessageEvent.event_type.in_(event_types))

    result = await db.execute(query)
    rows = result.all()

    events = []
    for event, message, campaign in rows:
        events.append({
            "id": event.id,
            "type": event.event_type,
            "subtype": event.event_subtype,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "recipient_email": message.recipient_email,
            "campaign_id": campaign.id if campaign else None,
            "campaign_name": campaign.name if campaign else None,
            "link_url": event.link_url,
            "user_agent": event.user_agent[:100] if event.user_agent else None,
            "ip_address": event.ip_address
        })

    return events


async def get_contact_growth(
    db: AsyncSession,
    organization_id: int,
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    Get daily contact growth for charting.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Query contacts grouped by creation date
    result = await db.execute(
        select(
            func.date(Contact.created_at).label("date"),
            func.count(Contact.id).label("new_contacts"),
            func.sum(case((Contact.status == ContactStatus.UNSUBSCRIBED, 1), else_=0)).label("unsubscribed")
        )
        .where(Contact.organization_id == organization_id)
        .where(Contact.created_at >= start_date)
        .group_by(func.date(Contact.created_at))
        .order_by(func.date(Contact.created_at))
    )

    rows = result.all()

    growth_data = []
    cumulative = 0
    for row in rows:
        cumulative += (row.new_contacts or 0)
        growth_data.append({
            "date": row.date.isoformat() if row.date else None,
            "new_contacts": row.new_contacts or 0,
            "unsubscribed": row.unsubscribed or 0,
            "cumulative": cumulative
        })

    return growth_data


async def get_status_breakdown(
    db: AsyncSession,
    organization_id: int
) -> Dict[str, int]:
    """
    Get breakdown of contact statuses.
    """
    result = await db.execute(
        select(
            Contact.status,
            func.count(Contact.id).label("count")
        )
        .where(Contact.organization_id == organization_id)
        .group_by(Contact.status)
    )

    rows = result.all()

    breakdown = {
        "subscribed": 0,
        "unsubscribed": 0,
        "bounced": 0,
        "complained": 0
    }

    for row in rows:
        status_name = row.status.value if row.status else "unknown"
        breakdown[status_name] = row.count

    return breakdown


async def get_top_performing_campaigns(
    db: AsyncSession,
    organization_id: int,
    metric: str = "open_rate",
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Get top performing campaigns by a specific metric.
    Metrics: open_rate, click_rate, delivery_rate
    """
    result = await db.execute(
        select(Campaign)
        .where(Campaign.organization_id == organization_id)
        .where(Campaign.status == CampaignStatus.COMPLETED)
        .where(Campaign.sent_count > 0)
        .order_by(Campaign.completed_at.desc())
        .limit(50)  # Get recent completed campaigns
    )

    campaigns = result.scalars().all()

    # Calculate rates and sort
    campaign_data = []
    for campaign in campaigns:
        sent = campaign.sent_count or 0
        delivered = campaign.delivered_count or 0
        unique_opens = campaign.unique_opens or 0
        unique_clicks = campaign.unique_clicks or 0

        if sent == 0:
            continue

        rates = {
            "open_rate": (unique_opens / delivered * 100) if delivered > 0 else 0,
            "click_rate": (unique_clicks / unique_opens * 100) if unique_opens > 0 else 0,
            "delivery_rate": (delivered / sent * 100) if sent > 0 else 0
        }

        campaign_data.append({
            "id": campaign.id,
            "name": campaign.name,
            "sent": sent,
            "open_rate": round(rates["open_rate"], 2),
            "click_rate": round(rates["click_rate"], 2),
            "delivery_rate": round(rates["delivery_rate"], 2),
            "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None
        })

    # Sort by requested metric
    if metric in ["open_rate", "click_rate", "delivery_rate"]:
        campaign_data.sort(key=lambda x: x[metric], reverse=True)

    return campaign_data[:limit]
