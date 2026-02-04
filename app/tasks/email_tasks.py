import logging
import asyncio
import uuid
import time
from datetime import datetime, timedelta
from typing import List, Optional
from celery import shared_task
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.db.database import async_session_maker
from app.models.campaign import Campaign, CampaignRecipient, Message, MessageEvent, CampaignStatus, MessageStatus
from app.models.contact import Contact, ContactStatus
from app.services.email_service import email_service
from app.core.config import settings

logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 50  # Emails per batch
SEND_RATE = 14  # Emails per second (SES limit)
RATE_DELAY = 1.0 / SEND_RATE  # Delay between emails


def run_async(coro):
    """Helper to run async code in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_campaign(self, campaign_id: int):
    """
    Main task to process a campaign.
    Splits recipients into batches and queues batch tasks.
    """
    logger.info(f"Starting campaign processing: {campaign_id}")

    try:
        run_async(_process_campaign_async(campaign_id))
    except Exception as exc:
        logger.error(f"Error processing campaign {campaign_id}: {exc}")
        run_async(_mark_campaign_failed(campaign_id, str(exc)))
        raise self.retry(exc=exc)


async def _process_campaign_async(campaign_id: int):
    """Async implementation of campaign processing"""
    async with async_session_maker() as db:
        # Get campaign
        result = await db.execute(
            select(Campaign).filter(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return

        if campaign.status not in [CampaignStatus.QUEUED, CampaignStatus.PAUSED]:
            logger.warning(f"Campaign {campaign_id} is not in QUEUED or PAUSED status")
            return

        # Update status to SENDING
        campaign.status = CampaignStatus.SENDING
        campaign.started_at = campaign.started_at or datetime.utcnow()
        await db.commit()

        # Get pending recipients
        result = await db.execute(
            select(CampaignRecipient).filter(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == "pending"
            )
        )
        recipients = result.scalars().all()

        total_recipients = len(recipients)
        total_batches = (total_recipients + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(f"Campaign {campaign_id}: {total_recipients} recipients, {total_batches} batches")

        campaign.total_recipients = total_recipients
        campaign.total_batches = total_batches
        await db.commit()

        # Queue batch tasks
        for batch_num in range(total_batches):
            batch_start = batch_num * BATCH_SIZE
            send_email_batch.delay(campaign_id, batch_start, BATCH_SIZE)

        logger.info(f"Campaign {campaign_id}: Queued {total_batches} batch tasks")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def send_email_batch(self, campaign_id: int, batch_start: int, batch_size: int):
    """
    Send a batch of emails for a campaign.
    """
    logger.info(f"Processing batch: campaign={campaign_id}, start={batch_start}, size={batch_size}")

    try:
        run_async(_send_email_batch_async(campaign_id, batch_start, batch_size))
    except Exception as exc:
        logger.error(f"Error sending batch for campaign {campaign_id}: {exc}")
        raise self.retry(exc=exc)


async def _send_email_batch_async(campaign_id: int, batch_start: int, batch_size: int):
    """Async implementation of batch email sending"""
    async with async_session_maker() as db:
        # Get campaign
        result = await db.execute(
            select(Campaign).filter(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()

        if not campaign or campaign.status != CampaignStatus.SENDING:
            logger.warning(f"Campaign {campaign_id} not in SENDING status, skipping batch")
            return

        # Get recipients for this batch
        result = await db.execute(
            select(CampaignRecipient)
            .filter(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == "pending"
            )
            .offset(batch_start)
            .limit(batch_size)
        )
        recipients = result.scalars().all()

        sent_count = 0
        failed_count = 0

        for recipient in recipients:
            # Check if campaign is paused
            await db.refresh(campaign)
            if campaign.status == CampaignStatus.PAUSED:
                logger.info(f"Campaign {campaign_id} paused, stopping batch")
                return

            # Get contact
            result = await db.execute(
                select(Contact).filter(Contact.id == recipient.contact_id)
            )
            contact = result.scalar_one_or_none()

            if not contact or contact.status != ContactStatus.SUBSCRIBED:
                recipient.status = "skipped"
                recipient.error_message = "Contact not subscribed"
                await db.commit()
                continue

            # Prepare email content with personalization
            personalized_subject = _personalize_content(campaign.subject, contact)
            personalized_html = _personalize_content(campaign.html_content, contact)
            personalized_text = _personalize_content(campaign.text_content, contact) if campaign.text_content else None

            # Generate tracking ID
            tracking_id = str(uuid.uuid4())

            # Add tracking pixel to HTML
            tracking_pixel = f'<img src="{settings.TRACKING_BASE_URL}/open/{tracking_id}.gif" width="1" height="1" style="display:none;" />'
            personalized_html = personalized_html + tracking_pixel

            # Create message record
            message = Message(
                campaign_id=campaign_id,
                contact_id=contact.id,
                recipient_email=contact.email,
                recipient_name=contact.full_name,
                subject=personalized_subject,
                html_content=personalized_html,
                text_content=personalized_text,
                tracking_id=tracking_id,
                status=MessageStatus.QUEUED,
                queued_at=datetime.utcnow(),
            )
            db.add(message)
            await db.flush()

            # Update recipient with message ID
            recipient.message_id = message.id
            recipient.status = "queued"
            recipient.queued_at = datetime.utcnow()

            # Send email via SES
            try:
                logger.info(f"[SEND] Campaign {campaign_id} | Sending to {contact.email} | Message ID: {message.id}")

                result = await email_service.send_email(
                    to_email=contact.email,
                    subject=personalized_subject,
                    html_content=personalized_html,
                    text_content=personalized_text,
                    from_email=campaign.from_email,
                    from_name=campaign.from_name,
                    reply_to=campaign.reply_to,
                )

                if result['success']:
                    message.status = MessageStatus.SENT
                    message.ses_message_id = result['message_id']
                    message.sent_at = datetime.utcnow()
                    recipient.status = "sent"
                    recipient.sent_at = datetime.utcnow()
                    sent_count += 1

                    # Create sent event
                    event = MessageEvent(
                        message_id=message.id,
                        event_type="sent",
                        event_data={
                            "ses_message_id": result['message_id'],
                            "campaign_id": campaign_id,
                            "contact_id": contact.id,
                            "subject": personalized_subject,
                            "from_email": campaign.from_email
                        },
                        timestamp=datetime.utcnow()
                    )
                    db.add(event)

                    # Update contact stats
                    contact.total_emails_sent += 1
                    contact.last_email_sent_at = datetime.utcnow()

                    logger.info(f"[SUCCESS] Campaign {campaign_id} | Sent to {contact.email} | SES ID: {result['message_id']}")
                else:
                    message.status = MessageStatus.FAILED
                    message.error_message = result.get('error', 'Unknown error')
                    recipient.status = "failed"
                    recipient.error_message = result.get('error')
                    failed_count += 1

                    # Create failed event
                    event = MessageEvent(
                        message_id=message.id,
                        event_type="failed",
                        event_data={
                            "error": result.get('error', 'Unknown error'),
                            "campaign_id": campaign_id,
                            "contact_id": contact.id
                        },
                        timestamp=datetime.utcnow()
                    )
                    db.add(event)

                    logger.error(f"[FAILED] Campaign {campaign_id} | Failed to send to {contact.email} | Error: {result.get('error')}")

            except Exception as e:
                message.status = MessageStatus.FAILED
                message.error_message = str(e)
                recipient.status = "failed"
                recipient.error_message = str(e)
                failed_count += 1

                # Create error event
                event = MessageEvent(
                    message_id=message.id,
                    event_type="error",
                    event_data={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "campaign_id": campaign_id,
                        "contact_id": contact.id
                    },
                    timestamp=datetime.utcnow()
                )
                db.add(event)

                logger.error(f"[ERROR] Campaign {campaign_id} | Error sending to {contact.email}: {e}")

            await db.commit()

            # Rate limiting
            time.sleep(RATE_DELAY)

        # Update campaign stats
        campaign.sent_count += sent_count
        campaign.failed_count += failed_count
        campaign.current_batch += 1

        # Check if campaign is complete
        result = await db.execute(
            select(CampaignRecipient).filter(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == "pending"
            )
        )
        pending = result.scalars().all()

        if len(pending) == 0:
            campaign.status = CampaignStatus.COMPLETED
            campaign.completed_at = datetime.utcnow()
            logger.info(f"Campaign {campaign_id} completed")

        await db.commit()

        logger.info(f"Batch complete: campaign={campaign_id}, sent={sent_count}, failed={failed_count}")


@celery_app.task
def check_scheduled_campaigns():
    """Check for scheduled campaigns that need to be started"""
    logger.info("Checking for scheduled campaigns")
    run_async(_check_scheduled_campaigns_async())


async def _check_scheduled_campaigns_async():
    """Async implementation of scheduled campaign check"""
    async with async_session_maker() as db:
        now = datetime.utcnow()

        result = await db.execute(
            select(Campaign).filter(
                Campaign.status == CampaignStatus.SCHEDULED,
                Campaign.scheduled_at <= now
            )
        )
        campaigns = result.scalars().all()

        for campaign in campaigns:
            logger.info(f"Starting scheduled campaign: {campaign.id}")
            campaign.status = CampaignStatus.QUEUED
            await db.commit()
            process_campaign.delay(campaign.id)


@celery_app.task
def process_webhook_event(event_type: str, event_data: dict):
    """Process incoming webhook events from SES"""
    logger.info(f"Processing webhook event: {event_type}")
    run_async(_process_webhook_event_async(event_type, event_data))


async def _process_webhook_event_async(event_type: str, event_data: dict):
    """Async implementation of webhook event processing"""
    async with async_session_maker() as db:
        # Get message by SES message ID
        ses_message_id = event_data.get('mail', {}).get('messageId')
        if not ses_message_id:
            logger.warning("Webhook event missing SES message ID")
            return

        result = await db.execute(
            select(Message).filter(Message.ses_message_id == ses_message_id)
        )
        message = result.scalar_one_or_none()

        if not message:
            logger.warning(f"Message not found for SES ID: {ses_message_id}")
            return

        # Process based on event type
        if event_type == "Delivery":
            message.status = MessageStatus.DELIVERED
            message.delivered_at = datetime.utcnow()

            # Update campaign stats
            if message.campaign_id:
                result = await db.execute(
                    select(Campaign).filter(Campaign.id == message.campaign_id)
                )
                campaign = result.scalar_one_or_none()
                if campaign:
                    campaign.delivered_count += 1

        elif event_type == "Bounce":
            bounce_type = event_data.get('bounce', {}).get('bounceType', 'Unknown')
            message.status = MessageStatus.BOUNCED
            message.bounced_at = datetime.utcnow()
            message.bounce_type = bounce_type

            # Update contact status for hard bounces
            if bounce_type == "Permanent" and message.contact_id:
                result = await db.execute(
                    select(Contact).filter(Contact.id == message.contact_id)
                )
                contact = result.scalar_one_or_none()
                if contact:
                    contact.status = ContactStatus.BOUNCED
                    contact.bounce_count += 1
                    contact.last_bounce_at = datetime.utcnow()
                    contact.bounce_type = "hard"

            # Update campaign stats
            if message.campaign_id:
                result = await db.execute(
                    select(Campaign).filter(Campaign.id == message.campaign_id)
                )
                campaign = result.scalar_one_or_none()
                if campaign:
                    campaign.bounced_count += 1

        elif event_type == "Complaint":
            message.status = MessageStatus.COMPLAINED

            # Update contact status
            if message.contact_id:
                result = await db.execute(
                    select(Contact).filter(Contact.id == message.contact_id)
                )
                contact = result.scalar_one_or_none()
                if contact:
                    contact.status = ContactStatus.COMPLAINED

            # Update campaign stats
            if message.campaign_id:
                result = await db.execute(
                    select(Campaign).filter(Campaign.id == message.campaign_id)
                )
                campaign = result.scalar_one_or_none()
                if campaign:
                    campaign.complained_count += 1

        # Create event record
        event = MessageEvent(
            message_id=message.id,
            event_type=event_type.lower(),
            event_data=event_data,
            timestamp=datetime.utcnow()
        )
        db.add(event)

        await db.commit()
        logger.info(f"Processed {event_type} event for message {message.id}")


@celery_app.task
def cleanup_old_results():
    """Clean up old task results and logs"""
    logger.info("Cleaning up old results")
    # Celery result backend handles this automatically based on result_expires setting


async def _mark_campaign_failed(campaign_id: int, error_message: str):
    """Mark a campaign as failed"""
    async with async_session_maker() as db:
        result = await db.execute(
            select(Campaign).filter(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if campaign:
            campaign.status = CampaignStatus.FAILED
            campaign.error_message = error_message
            await db.commit()


def _personalize_content(content: str, contact: Contact) -> str:
    """Replace template variables with contact data"""
    if not content:
        return content

    # Basic variable replacement
    replacements = {
        '{{email}}': contact.email or '',
        '{{full_name}}': contact.full_name or '',
        '{{first_name}}': (contact.full_name or '').split()[0] if contact.full_name else '',
        '{{last_name}}': (contact.full_name or '').split()[-1] if contact.full_name and len(contact.full_name.split()) > 1 else '',
        '{{company}}': contact.company or '',
        '{{phone}}': contact.phone or '',
    }

    for key, value in replacements.items():
        content = content.replace(key, value)

    # Replace custom fields if present
    if contact.custom_fields:
        for field_name, field_value in contact.custom_fields.items():
            content = content.replace(f'{{{{{field_name}}}}}', str(field_value or ''))

    return content
