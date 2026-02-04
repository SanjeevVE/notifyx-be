from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models.campaign import CampaignStatus, MessageStatus


# ============= Campaign Schemas =============

class CampaignBase(BaseModel):
    name: str
    subject: str
    from_name: str
    from_email: EmailStr
    reply_to: Optional[EmailStr] = None
    html_content: str
    text_content: Optional[str] = None


class CampaignCreate(CampaignBase):
    """Schema for creating a new campaign"""
    template_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None


class CampaignUpdate(BaseModel):
    """Schema for updating an existing campaign"""
    name: Optional[str] = None
    subject: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[EmailStr] = None
    reply_to: Optional[EmailStr] = None
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    template_id: Optional[int] = None
    status: Optional[CampaignStatus] = None
    scheduled_at: Optional[datetime] = None


class CampaignResponse(CampaignBase):
    """Schema for campaign response"""
    id: int
    organization_id: int
    template_id: Optional[int] = None
    status: CampaignStatus
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None

    # Recipient counts
    total_recipients: int = 0
    queued_count: int = 0
    sent_count: int = 0
    failed_count: int = 0

    # Engagement metrics
    delivered_count: int = 0
    opened_count: int = 0
    unique_opens: int = 0
    clicked_count: int = 0
    unique_clicks: int = 0
    bounced_count: int = 0
    complained_count: int = 0
    unsubscribed_count: int = 0

    # Processing info
    current_batch: int = 0
    total_batches: int = 0
    error_message: Optional[str] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CampaignBrief(BaseModel):
    """Brief campaign info for lists"""
    id: int
    name: str
    subject: str
    status: CampaignStatus
    total_recipients: int
    sent_count: int
    opened_count: int
    clicked_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class CampaignStats(BaseModel):
    """Detailed campaign statistics"""
    campaign_id: int
    total_recipients: int
    sent: int
    delivered: int
    failed: int
    opened: int
    unique_opens: int
    clicked: int
    unique_clicks: int
    bounced: int
    complained: int
    unsubscribed: int

    # Rates (percentages)
    delivery_rate: float
    open_rate: float
    click_rate: float
    bounce_rate: float
    complaint_rate: float
    unsubscribe_rate: float


# ============= Campaign Recipients Schemas =============

class CampaignAddRecipients(BaseModel):
    """Add recipients to a campaign"""
    contact_ids: Optional[List[int]] = None  # Specific contact IDs
    list_ids: Optional[List[int]] = None  # Add all contacts from these lists
    select_all: bool = False  # Select all subscribed contacts
    filter_status: Optional[str] = "subscribed"  # Filter by status when select_all
    exclude_unsubscribed: bool = True
    exclude_bounced: bool = True


class CampaignRecipientResponse(BaseModel):
    """Campaign recipient info"""
    id: int
    campaign_id: int
    contact_id: int
    status: str
    error_message: Optional[str] = None
    queued_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None

    # Contact info
    email: str
    full_name: Optional[str] = None

    class Config:
        from_attributes = True


class RecipientPreview(BaseModel):
    """Preview of recipients before adding"""
    total_contacts: int
    eligible_contacts: int
    excluded_unsubscribed: int
    excluded_bounced: int
    excluded_duplicate: int


# ============= Campaign Send Schemas =============

class CampaignSendRequest(BaseModel):
    """Request to send/schedule a campaign"""
    send_at: Optional[datetime] = None  # None = send immediately


class CampaignSendResponse(BaseModel):
    """Response after starting campaign send"""
    campaign_id: int
    status: CampaignStatus
    total_recipients: int
    estimated_batches: int
    message: str


# ============= Message Schemas =============

class MessageBase(BaseModel):
    recipient_email: EmailStr
    recipient_name: Optional[str] = None


class MessageCreate(MessageBase):
    campaign_id: Optional[int] = None
    contact_id: Optional[int] = None
    subject: str
    html_content: str
    text_content: Optional[str] = None


class MessageResponse(BaseModel):
    """Schema for message response"""
    id: int
    campaign_id: Optional[int] = None
    contact_id: Optional[int] = None
    recipient_email: str
    recipient_name: Optional[str] = None
    subject: str
    status: MessageStatus
    tracking_id: Optional[str] = None
    ses_message_id: Optional[str] = None
    error_message: Optional[str] = None

    # Timestamps
    queued_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None

    # Counts
    open_count: int = 0
    click_count: int = 0

    created_at: datetime

    class Config:
        from_attributes = True


class MessageBrief(BaseModel):
    """Brief message info"""
    id: int
    recipient_email: str
    status: MessageStatus
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============= Message Event Schemas =============

class MessageEventResponse(BaseModel):
    """Schema for message event response"""
    id: int
    message_id: int
    event_type: str
    event_subtype: Optional[str] = None
    event_data: Optional[Dict[str, Any]] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    link_url: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


# ============= Email Send Schemas =============

class EmailSendRequest(BaseModel):
    """Request to send a single email"""
    to_email: EmailStr
    to_name: Optional[str] = None
    subject: str
    html_content: str
    text_content: Optional[str] = None
    from_email: Optional[EmailStr] = None
    from_name: Optional[str] = None
    reply_to: Optional[EmailStr] = None


class EmailSendResponse(BaseModel):
    """Response after sending an email"""
    success: bool
    message_id: Optional[str] = None
    tracking_id: Optional[str] = None
    status: str
    error: Optional[str] = None


# ============= Pagination =============

class PaginatedCampaigns(BaseModel):
    """Paginated campaign list"""
    items: List[CampaignResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedMessages(BaseModel):
    """Paginated message list"""
    items: List[MessageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============= Email Log Schemas =============

class EmailLogResponse(BaseModel):
    """Schema for email log entry"""
    id: int
    campaign_id: Optional[int] = None
    campaign_name: Optional[str] = None
    contact_id: Optional[int] = None
    recipient_email: str
    recipient_name: Optional[str] = None
    subject: str
    status: MessageStatus
    ses_message_id: Optional[str] = None
    error_message: Optional[str] = None

    # Timestamps
    created_at: datetime
    queued_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None

    # Counts
    open_count: int = 0
    click_count: int = 0

    # Events
    events: List[MessageEventResponse] = []

    class Config:
        from_attributes = True


class PaginatedEmailLogs(BaseModel):
    """Paginated email logs list"""
    items: List[EmailLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    # Summary stats
    total_sent: int = 0
    total_delivered: int = 0
    total_opened: int = 0
    total_clicked: int = 0
    total_bounced: int = 0
    total_failed: int = 0
