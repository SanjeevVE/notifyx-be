from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)

    # Email settings
    default_from_name = Column(String(255), nullable=True)
    default_from_email = Column(String(255), nullable=True)
    default_reply_to = Column(String(255), nullable=True)

    # Tracking settings
    tracking_domain = Column(String(255), nullable=True)  # Custom tracking domain
    enable_open_tracking = Column(Boolean, default=True)
    enable_click_tracking = Column(Boolean, default=True)

    # Sending limits
    daily_send_limit = Column(Integer, default=10000)
    hourly_send_limit = Column(Integer, default=1000)

    # Usage stats
    total_emails_sent = Column(Integer, default=0)
    total_contacts = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", back_populates="organization")
    campaigns = relationship("Campaign", back_populates="organization")
    contacts = relationship("Contact", back_populates="organization", cascade="all, delete-orphan")
    contact_lists = relationship("ContactList", back_populates="organization", cascade="all, delete-orphan")
    email_templates = relationship("EmailTemplate", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    # User preferences
    timezone = Column(String(50), default="UTC")
    preferences = Column(JSON, nullable=True)

    # Last activity
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="users")
