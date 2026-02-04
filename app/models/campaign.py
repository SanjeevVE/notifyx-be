from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.database import Base


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    from_name = Column(String(255), nullable=False)
    from_email = Column(String(255), nullable=False)
    reply_to = Column(String(255), nullable=True)
    html_content = Column(Text, nullable=False)
    text_content = Column(Text, nullable=True)

    # Status tracking
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)

    # Recipient counts
    total_recipients = Column(Integer, default=0)
    queued_count = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)

    # Engagement metrics
    delivered_count = Column(Integer, default=0)
    opened_count = Column(Integer, default=0)
    unique_opens = Column(Integer, default=0)
    clicked_count = Column(Integer, default=0)
    unique_clicks = Column(Integer, default=0)
    bounced_count = Column(Integer, default=0)
    complained_count = Column(Integer, default=0)
    unsubscribed_count = Column(Integer, default=0)

    # Processing metadata
    current_batch = Column(Integer, default=0)
    total_batches = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="campaigns")
    template = relationship("EmailTemplate", back_populates="campaigns")
    messages = relationship("Message", back_populates="campaign", cascade="all, delete-orphan")
    recipients = relationship("CampaignRecipient", back_populates="campaign", cascade="all, delete-orphan")
    unsubscribe_tokens = relationship("UnsubscribeToken", back_populates="campaign")


class CampaignRecipient(Base):
    """Links campaigns to contacts for recipient management"""
    __tablename__ = "campaign_recipients"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Status tracking
    status = Column(String(50), default="pending", index=True)  # pending, queued, sent, failed, skipped
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)

    # Personalization data snapshot (in case contact changes later)
    personalization_data = Column(JSON, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    queued_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    campaign = relationship("Campaign", back_populates="recipients")
    contact = relationship("Contact")
    message = relationship("Message")


class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    COMPLAINED = "complained"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)  # Nullable for single emails
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)

    # Recipient info
    recipient_email = Column(String(255), nullable=False, index=True)
    recipient_name = Column(String(255), nullable=True)

    # Email content
    subject = Column(String(500), nullable=False)
    html_content = Column(Text, nullable=False)
    text_content = Column(Text, nullable=True)

    # Email headers for threading
    message_id = Column(String(255), unique=True, index=True)  # Our internal message ID
    ses_message_id = Column(String(255), nullable=True, index=True)  # AWS SES message ID
    in_reply_to = Column(String(255), nullable=True)
    references = Column(Text, nullable=True)
    thread_id = Column(String(255), index=True, nullable=True)

    # Tracking
    tracking_id = Column(String(64), unique=True, index=True)  # UUID for open/click tracking

    # Status
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING, index=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    queued_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    clicked_at = Column(DateTime(timezone=True), nullable=True)
    bounced_at = Column(DateTime(timezone=True), nullable=True)

    # Bounce details
    bounce_type = Column(String(50), nullable=True)  # hard, soft, transient
    bounce_subtype = Column(String(100), nullable=True)

    # Open/Click counts (same message can be opened/clicked multiple times)
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    campaign = relationship("Campaign", back_populates="messages")
    contact = relationship("Contact", back_populates="messages")
    events = relationship("MessageEvent", back_populates="message", cascade="all, delete-orphan")


class MessageEvent(Base):
    __tablename__ = "message_events"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # sent, delivered, opened, clicked, bounced, complained
    event_subtype = Column(String(100), nullable=True)  # For bounces: hard/soft, for clicks: link URL
    event_data = Column(JSON, nullable=True)

    # Client info for opens/clicks
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(50), nullable=True)

    # For click events
    link_url = Column(Text, nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    message = relationship("Message", back_populates="events")


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), nullable=False, index=True)  # info, warning, error, critical
    module = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    context_data = Column(JSON, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
