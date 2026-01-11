from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.database import Base


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    from_name = Column(String, nullable=False)
    from_email = Column(String, nullable=False)
    reply_to = Column(String, nullable=True)
    html_content = Column(Text, nullable=False)
    text_content = Column(Text, nullable=True)
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    total_recipients = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="campaigns")
    messages = relationship("Message", back_populates="campaign")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    recipient_email = Column(String, nullable=False, index=True)
    recipient_name = Column(String, nullable=True)
    subject = Column(String, nullable=False)
    html_content = Column(Text, nullable=False)
    text_content = Column(Text, nullable=True)

    # Email headers for threading
    message_id = Column(String, unique=True, index=True)  # AWS SES message ID
    in_reply_to = Column(String, nullable=True)
    references = Column(String, nullable=True)
    thread_id = Column(String, index=True, nullable=True)

    # Status
    status = Column(String, default="pending")  # pending, sent, failed, bounced
    ses_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    campaign = relationship("Campaign", back_populates="messages")
    events = relationship("MessageEvent", back_populates="message")


class MessageEvent(Base):
    __tablename__ = "message_events"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    event_type = Column(String, nullable=False, index=True)  # sent, delivered, opened, clicked, bounced, complained
    event_data = Column(JSON, nullable=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    message = relationship("Message", back_populates="events")


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String, nullable=False)  # info, warning, error, critical
    module = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    context_data = Column(JSON, nullable=True)  # Renamed from metadata to avoid SQLAlchemy conflict
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
