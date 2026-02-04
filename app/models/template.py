from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    subject = Column(String(500), nullable=False)
    html_content = Column(Text, nullable=False)
    text_content = Column(Text, nullable=True)

    # Template variables - list of variable names used in the template
    # e.g., ["first_name", "company", "unsubscribe_link"]
    variables = Column(JSON, nullable=True)

    # Template metadata
    category = Column(String(100), nullable=True)  # newsletter, transactional, marketing, etc.
    thumbnail_url = Column(String(500), nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    # Usage tracking
    times_used = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="email_templates")
    campaigns = relationship("Campaign", back_populates="template")
