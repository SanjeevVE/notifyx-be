from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.database import Base


class FieldType(str, enum.Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTI_SELECT = "multi_select"


class ContactField(Base):
    """
    Defines custom and system fields for contacts within an organization.

    System fields (email, full_name, company, phone) map to dedicated Contact columns.
    Custom fields are stored in Contact.custom_fields JSON column.
    """
    __tablename__ = "contact_fields"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    # Field identification
    field_key = Column(String(100), nullable=False)  # snake_case identifier: "job_title"
    display_name = Column(String(255), nullable=False)  # Human readable: "Job Title"
    description = Column(Text, nullable=True)

    # Field type and configuration
    field_type = Column(Enum(FieldType), nullable=False, default=FieldType.TEXT)
    is_system_field = Column(Boolean, default=False)  # Built-in fields like email, name
    is_required = Column(Boolean, default=False)
    is_unique = Column(Boolean, default=False)  # Unique per organization
    default_value = Column(String(500), nullable=True)

    # Options for select/multi_select types
    # Format: [{"value": "option1", "label": "Option 1"}, ...]
    options = Column(JSON, nullable=True)

    # Validation rules for the field
    # Format: {"min_length": 1, "max_length": 100, "pattern": "regex", "min_value": 0, "max_value": 100}
    validation_rules = Column(JSON, nullable=True)

    # Usage tracking - prevents deletion if > 0
    usage_count = Column(Integer, default=0)

    # Display ordering in forms and lists
    display_order = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="contact_fields")

    __table_args__ = (
        UniqueConstraint('organization_id', 'field_key', name='uq_contact_field_org_key'),
    )

    def __repr__(self):
        return f"<ContactField(id={self.id}, field_key='{self.field_key}', type={self.field_type})>"


# System field definitions that map to Contact model columns
SYSTEM_FIELDS = [
    {
        "field_key": "email",
        "display_name": "Email",
        "field_type": FieldType.TEXT,
        "is_system_field": True,
        "is_required": True,
        "is_unique": True,
        "display_order": 0,
    },
    {
        "field_key": "full_name",
        "display_name": "Full Name",
        "field_type": FieldType.TEXT,
        "is_system_field": True,
        "is_required": False,
        "display_order": 1,
    },
    {
        "field_key": "company",
        "display_name": "Company",
        "field_type": FieldType.TEXT,
        "is_system_field": True,
        "is_required": False,
        "display_order": 2,
    },
    {
        "field_key": "phone",
        "display_name": "Phone",
        "field_type": FieldType.TEXT,
        "is_system_field": True,
        "is_required": False,
        "display_order": 3,
    },
]

# Mapping from system field_key to Contact model column name
SYSTEM_FIELD_COLUMN_MAP = {
    "email": "email",
    "full_name": "full_name",
    "company": "company",
    "phone": "phone",
}
