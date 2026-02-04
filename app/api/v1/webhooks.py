"""
Webhooks API - Handle AWS SES notifications via SNS
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models import (
    Message, MessageEvent, MessageStatus,
    Contact, ContactStatus, Campaign
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ses")
async def handle_ses_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle AWS SES notifications sent via SNS.

    SES sends notifications for:
    - Bounce: Email bounced (hard or soft)
    - Complaint: Recipient marked email as spam
    - Delivery: Email was delivered
    - Send: Email was sent (optional)
    - Reject: Email was rejected (optional)
    """
    try:
        body = await request.body()
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Get the message type from headers or payload
    message_type = request.headers.get("x-amz-sns-message-type", "")

    # Handle SNS subscription confirmation
    if message_type == "SubscriptionConfirmation":
        subscribe_url = payload.get("SubscribeURL")
        if subscribe_url:
            logger.info(f"SNS Subscription confirmation URL: {subscribe_url}")
            # In production, you would fetch this URL to confirm
            # For now, log it for manual confirmation
            return {"message": "Subscription confirmation received", "url": subscribe_url}

    # Handle actual notifications
    if message_type == "Notification":
        message_body = payload.get("Message", "{}")
        try:
            ses_message = json.loads(message_body)
        except json.JSONDecodeError:
            logger.error(f"Invalid SES message JSON: {message_body}")
            raise HTTPException(status_code=400, detail="Invalid SES message format")

        # Process in background to respond quickly
        background_tasks.add_task(
            process_ses_notification,
            ses_message,
            db
        )

        return {"message": "Notification received"}

    return {"message": "OK"}


async def process_ses_notification(ses_message: dict, db: AsyncSession):
    """Process an SES notification message"""
    notification_type = ses_message.get("notificationType", "").lower()

    # Get the mail object which contains the message ID
    mail = ses_message.get("mail", {})
    ses_message_id = mail.get("messageId")

    if not ses_message_id:
        logger.warning("SES notification missing messageId")
        return

    # Find the message by SES message ID
    result = await db.execute(
        select(Message).where(Message.ses_message_id == ses_message_id)
    )
    message = result.scalar_one_or_none()

    if not message:
        logger.warning(f"Message not found for SES ID: {ses_message_id}")
        return

    if notification_type == "bounce":
        await process_bounce(db, message, ses_message)
    elif notification_type == "complaint":
        await process_complaint(db, message, ses_message)
    elif notification_type == "delivery":
        await process_delivery(db, message, ses_message)
    elif notification_type == "send":
        await process_send(db, message, ses_message)

    await db.commit()


async def process_bounce(db: AsyncSession, message: Message, ses_message: dict):
    """Process a bounce notification"""
    bounce = ses_message.get("bounce", {})

    bounce_type = bounce.get("bounceType", "").lower()  # Permanent, Transient, Undetermined
    bounce_subtype = bounce.get("bounceSubType", "")

    # Update message
    message.status = MessageStatus.BOUNCED
    message.bounced_at = datetime.now(timezone.utc)
    message.bounce_type = "hard" if bounce_type == "permanent" else "soft"
    message.bounce_subtype = bounce_subtype

    # Create event
    event = MessageEvent(
        message_id=message.id,
        event_type="bounced",
        event_subtype=f"{bounce_type}/{bounce_subtype}",
        event_data={
            "bounce_type": bounce_type,
            "bounce_subtype": bounce_subtype,
            "bounced_recipients": bounce.get("bouncedRecipients", [])
        }
    )
    db.add(event)

    # Update campaign stats
    if message.campaign_id:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == message.campaign_id)
            .values(
                bounced_count=Campaign.bounced_count + 1,
                failed_count=Campaign.failed_count + 1
            )
        )

    # Update contact status for hard bounces
    if message.contact_id and bounce_type == "permanent":
        await db.execute(
            update(Contact)
            .where(Contact.id == message.contact_id)
            .values(
                status=ContactStatus.BOUNCED,
                total_bounces=Contact.total_bounces + 1
            )
        )

    logger.info(f"Processed bounce for message {message.id}: {bounce_type}/{bounce_subtype}")


async def process_complaint(db: AsyncSession, message: Message, ses_message: dict):
    """Process a complaint (spam report) notification"""
    complaint = ses_message.get("complaint", {})

    complaint_type = complaint.get("complaintFeedbackType", "abuse")

    # Update message
    message.status = MessageStatus.COMPLAINED

    # Create event
    event = MessageEvent(
        message_id=message.id,
        event_type="complained",
        event_subtype=complaint_type,
        event_data={
            "complaint_type": complaint_type,
            "complained_recipients": complaint.get("complainedRecipients", []),
            "user_agent": complaint.get("userAgent", "")
        }
    )
    db.add(event)

    # Update campaign stats
    if message.campaign_id:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == message.campaign_id)
            .values(complained_count=Campaign.complained_count + 1)
        )

    # Update contact status - complaints should unsubscribe the user
    if message.contact_id:
        await db.execute(
            update(Contact)
            .where(Contact.id == message.contact_id)
            .values(
                status=ContactStatus.COMPLAINED,
                unsubscribed_at=datetime.now(timezone.utc)
            )
        )

    logger.info(f"Processed complaint for message {message.id}: {complaint_type}")


async def process_delivery(db: AsyncSession, message: Message, ses_message: dict):
    """Process a delivery notification"""
    delivery = ses_message.get("delivery", {})

    # Update message
    message.status = MessageStatus.DELIVERED
    message.delivered_at = datetime.now(timezone.utc)

    # Create event
    event = MessageEvent(
        message_id=message.id,
        event_type="delivered",
        event_data={
            "smtp_response": delivery.get("smtpResponse", ""),
            "processing_time_ms": delivery.get("processingTimeMillis", 0)
        }
    )
    db.add(event)

    # Update campaign stats
    if message.campaign_id:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == message.campaign_id)
            .values(delivered_count=Campaign.delivered_count + 1)
        )

    logger.info(f"Processed delivery for message {message.id}")


async def process_send(db: AsyncSession, message: Message, ses_message: dict):
    """Process a send notification (email accepted by SES)"""
    # Message was already marked as sent when we called SES
    # This is just a confirmation

    # Create event
    event = MessageEvent(
        message_id=message.id,
        event_type="sent",
        event_data={
            "source": ses_message.get("mail", {}).get("source", ""),
            "send_timestamp": ses_message.get("mail", {}).get("timestamp", "")
        }
    )
    db.add(event)

    logger.info(f"Processed send confirmation for message {message.id}")


# Health check endpoint for webhook testing
@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoint"""
    return {"status": "ok", "service": "webhooks"}
