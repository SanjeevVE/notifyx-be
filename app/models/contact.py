from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.database import Base


class ContactStatus(str, enum.Enum):
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    COMPLAINED = "complained"


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    status = Column(Enum(ContactStatus), default=ContactStatus.SUBSCRIBED, index=True)
    custom_fields = Column(JSON, nullable=True)  # For template variables like {"title": "Mr", "department": "Sales"}
    tags = Column(JSON, nullable=True)  # List of tags for segmentation

    # Engagement metrics
    total_emails_sent = Column(Integer, default=0)
    total_emails_opened = Column(Integer, default=0)
    total_emails_clicked = Column(Integer, default=0)
    last_email_sent_at = Column(DateTime(timezone=True), nullable=True)
    last_email_opened_at = Column(DateTime(timezone=True), nullable=True)
    last_email_clicked_at = Column(DateTime(timezone=True), nullable=True)

    # Unsubscribe tracking
    unsubscribed_at = Column(DateTime(timezone=True), nullable=True)
    unsubscribe_reason = Column(String(500), nullable=True)

    # Bounce tracking
    bounce_count = Column(Integer, default=0)
    last_bounce_at = Column(DateTime(timezone=True), nullable=True)
    bounce_type = Column(String(50), nullable=True)  # hard, soft, transient

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="contacts")
    list_memberships = relationship("ContactListMembership", back_populates="contact", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="contact")
    unsubscribe_tokens = relationship("UnsubscribeToken", back_populates="contact", cascade="all, delete-orphan")

    # Unique constraint per organization
    __table_args__ = (
        UniqueConstraint('organization_id', 'email', name='uq_contact_org_email'),
    )


class ContactList(Base):
    __tablename__ = "contact_lists"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    contact_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="contact_lists")
    memberships = relationship("ContactListMembership", back_populates="contact_list", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('organization_id', 'name', name='uq_list_org_name'),
    )


class ContactListMembership(Base):
    __tablename__ = "contact_list_memberships"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    list_id = Column(Integer, ForeignKey("contact_lists.id", ondelete="CASCADE"), nullable=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    contact = relationship("Contact", back_populates="list_memberships")
    contact_list = relationship("ContactList", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint('contact_id', 'list_id', name='uq_contact_list_membership'),
    )


class UnsubscribeToken(Base):
    __tablename__ = "unsubscribe_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)
    is_used = Column(Boolean, default=False)

    # Relationships
    contact = relationship("Contact", back_populates="unsubscribe_tokens")
    campaign = relationship("Campaign", back_populates="unsubscribe_tokens")
