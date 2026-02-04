"""
Tracking Service - Handles open/click tracking and unsubscribe functionality
"""
import uuid
import base64
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Message, MessageEvent, MessageStatus,
    Contact, ContactStatus, Campaign,
    UnsubscribeToken
)


# 1x1 transparent GIF pixel (base64 decoded)
TRACKING_PIXEL = base64.b64decode(
    'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
)


def generate_tracking_id() -> str:
    """Generate a unique tracking ID for a message"""
    return uuid.uuid4().hex


def generate_unsubscribe_token() -> str:
    """Generate a secure unsubscribe token"""
    return secrets.token_urlsafe(32)


def encode_url(url: str) -> str:
    """Encode a URL for safe transmission in tracking links"""
    return base64.urlsafe_b64encode(url.encode()).decode()


def decode_url(encoded: str) -> str:
    """Decode a URL from tracking link"""
    try:
        return base64.urlsafe_b64decode(encoded.encode()).decode()
    except Exception:
        return ""


async def record_open_event(
    db: AsyncSession,
    tracking_id: str,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None
) -> Tuple[bool, Optional[Message]]:
    """
    Record an email open event.
    Returns (success, message) tuple.
    """
    # Find the message by tracking ID
    result = await db.execute(
        select(Message).where(Message.tracking_id == tracking_id)
    )
    message = result.scalar_one_or_none()

    if not message:
        return False, None

    # Update message open tracking
    is_first_open = message.opened_at is None

    message.open_count = (message.open_count or 0) + 1
    if is_first_open:
        message.opened_at = datetime.now(timezone.utc)

    # Create event record
    event = MessageEvent(
        message_id=message.id,
        event_type="opened",
        user_agent=user_agent,
        ip_address=ip_address,
        event_data={"first_open": is_first_open}
    )
    db.add(event)

    # Update campaign stats if this is a campaign message
    if message.campaign_id and is_first_open:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == message.campaign_id)
            .values(
                opened_count=Campaign.opened_count + 1,
                unique_opens=Campaign.unique_opens + 1
            )
        )
    elif message.campaign_id:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == message.campaign_id)
            .values(opened_count=Campaign.opened_count + 1)
        )

    # Update contact engagement stats
    if message.contact_id:
        await db.execute(
            update(Contact)
            .where(Contact.id == message.contact_id)
            .values(
                total_emails_opened=Contact.total_emails_opened + 1,
                last_opened_at=datetime.now(timezone.utc)
            )
        )

    await db.commit()
    return True, message


async def record_click_event(
    db: AsyncSession,
    tracking_id: str,
    link_url: str,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None
) -> Tuple[bool, Optional[Message]]:
    """
    Record a link click event.
    Returns (success, message) tuple.
    """
    # Find the message by tracking ID
    result = await db.execute(
        select(Message).where(Message.tracking_id == tracking_id)
    )
    message = result.scalar_one_or_none()

    if not message:
        return False, None

    # Update message click tracking
    is_first_click = message.clicked_at is None

    message.click_count = (message.click_count or 0) + 1
    if is_first_click:
        message.clicked_at = datetime.now(timezone.utc)

    # Create event record
    event = MessageEvent(
        message_id=message.id,
        event_type="clicked",
        event_subtype="link_click",
        link_url=link_url,
        user_agent=user_agent,
        ip_address=ip_address,
        event_data={"first_click": is_first_click}
    )
    db.add(event)

    # Update campaign stats if this is a campaign message
    if message.campaign_id and is_first_click:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == message.campaign_id)
            .values(
                clicked_count=Campaign.clicked_count + 1,
                unique_clicks=Campaign.unique_clicks + 1
            )
        )
    elif message.campaign_id:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == message.campaign_id)
            .values(clicked_count=Campaign.clicked_count + 1)
        )

    # Update contact engagement stats
    if message.contact_id:
        await db.execute(
            update(Contact)
            .where(Contact.id == message.contact_id)
            .values(
                total_emails_clicked=Contact.total_emails_clicked + 1,
                last_clicked_at=datetime.now(timezone.utc)
            )
        )

    await db.commit()
    return True, message


async def create_unsubscribe_token(
    db: AsyncSession,
    contact_id: int,
    campaign_id: Optional[int] = None
) -> str:
    """Create an unsubscribe token for a contact"""
    token = generate_unsubscribe_token()

    unsubscribe_token = UnsubscribeToken(
        token=token,
        contact_id=contact_id,
        campaign_id=campaign_id
    )
    db.add(unsubscribe_token)
    await db.commit()

    return token


async def get_unsubscribe_info(
    db: AsyncSession,
    token: str
) -> Optional[dict]:
    """Get unsubscribe token information"""
    result = await db.execute(
        select(UnsubscribeToken)
        .where(UnsubscribeToken.token == token)
        .where(UnsubscribeToken.used_at.is_(None))
    )
    unsubscribe_token = result.scalar_one_or_none()

    if not unsubscribe_token:
        return None

    # Get contact info
    contact_result = await db.execute(
        select(Contact).where(Contact.id == unsubscribe_token.contact_id)
    )
    contact = contact_result.scalar_one_or_none()

    if not contact:
        return None

    # Get campaign info if applicable
    campaign_name = None
    if unsubscribe_token.campaign_id:
        campaign_result = await db.execute(
            select(Campaign).where(Campaign.id == unsubscribe_token.campaign_id)
        )
        campaign = campaign_result.scalar_one_or_none()
        if campaign:
            campaign_name = campaign.name

    return {
        "token": token,
        "email": contact.email,
        "contact_id": contact.id,
        "campaign_id": unsubscribe_token.campaign_id,
        "campaign_name": campaign_name,
        "is_already_unsubscribed": contact.status == ContactStatus.UNSUBSCRIBED
    }


async def process_unsubscribe(
    db: AsyncSession,
    token: str,
    reason: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Process an unsubscribe request.
    Returns (success, message) tuple.
    """
    result = await db.execute(
        select(UnsubscribeToken)
        .where(UnsubscribeToken.token == token)
        .where(UnsubscribeToken.used_at.is_(None))
    )
    unsubscribe_token = result.scalar_one_or_none()

    if not unsubscribe_token:
        return False, "Invalid or expired unsubscribe link"

    # Get contact
    contact_result = await db.execute(
        select(Contact).where(Contact.id == unsubscribe_token.contact_id)
    )
    contact = contact_result.scalar_one_or_none()

    if not contact:
        return False, "Contact not found"

    if contact.status == ContactStatus.UNSUBSCRIBED:
        return True, "You have already been unsubscribed"

    # Update contact status
    contact.status = ContactStatus.UNSUBSCRIBED
    contact.unsubscribed_at = datetime.now(timezone.utc)

    # Mark token as used
    unsubscribe_token.used_at = datetime.now(timezone.utc)
    unsubscribe_token.unsubscribe_reason = reason

    # Update campaign stats if applicable
    if unsubscribe_token.campaign_id:
        await db.execute(
            update(Campaign)
            .where(Campaign.id == unsubscribe_token.campaign_id)
            .values(unsubscribed_count=Campaign.unsubscribed_count + 1)
        )

        # Create message event if we can find the message
        message_result = await db.execute(
            select(Message)
            .where(Message.campaign_id == unsubscribe_token.campaign_id)
            .where(Message.contact_id == contact.id)
        )
        message = message_result.scalar_one_or_none()
        if message:
            event = MessageEvent(
                message_id=message.id,
                event_type="unsubscribed",
                event_data={"reason": reason} if reason else None
            )
            db.add(event)

    await db.commit()
    return True, "You have been successfully unsubscribed"


def inject_tracking_pixel(html_content: str, tracking_url: str) -> str:
    """Inject tracking pixel into HTML email content"""
    pixel_html = f'<img src="{tracking_url}" width="1" height="1" style="display:none;" alt="" />'

    # Try to insert before </body> tag
    if '</body>' in html_content.lower():
        # Find the position case-insensitively
        lower_content = html_content.lower()
        pos = lower_content.rfind('</body>')
        return html_content[:pos] + pixel_html + html_content[pos:]
    else:
        # Just append to the end
        return html_content + pixel_html


def rewrite_links_for_tracking(html_content: str, tracking_base_url: str, tracking_id: str) -> str:
    """
    Rewrite links in HTML content to go through click tracking.
    Converts: <a href="https://example.com">
    To: <a href="{tracking_base_url}/click/{tracking_id}/{encoded_url}">
    """
    import re

    def replace_link(match):
        full_tag = match.group(0)
        href = match.group(1)

        # Skip mailto:, tel:, and anchor links
        if href.startswith(('mailto:', 'tel:', '#', 'javascript:')):
            return full_tag

        # Skip unsubscribe links (they should remain direct)
        if 'unsubscribe' in href.lower():
            return full_tag

        # Encode the URL and create tracking link
        encoded = encode_url(href)
        tracking_link = f"{tracking_base_url}/click/{tracking_id}/{encoded}"

        return full_tag.replace(href, tracking_link)

    # Match href attributes in anchor tags
    pattern = r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>'
    return re.sub(pattern, replace_link, html_content, flags=re.IGNORECASE)


def add_unsubscribe_link(
    html_content: str,
    unsubscribe_url: str,
    company_name: str = "NotifyX"
) -> str:
    """
    Add unsubscribe link to email footer if not already present.
    This is required for CAN-SPAM compliance.
    """
    if 'unsubscribe' in html_content.lower():
        return html_content

    footer_html = f'''
    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; text-align: center; font-size: 12px; color: #666;">
        <p>You received this email because you subscribed to {company_name}.</p>
        <p><a href="{unsubscribe_url}" style="color: #666;">Unsubscribe</a> from these emails.</p>
    </div>
    '''

    # Try to insert before </body> tag
    if '</body>' in html_content.lower():
        lower_content = html_content.lower()
        pos = lower_content.rfind('</body>')
        return html_content[:pos] + footer_html + html_content[pos:]
    else:
        return html_content + footer_html
