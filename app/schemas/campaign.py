from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from app.models.campaign import CampaignStatus


class CampaignBase(BaseModel):
    name: str
    subject: str
    from_name: str
    from_email: EmailStr
    reply_to: Optional[EmailStr] = None
    html_content: str
    text_content: Optional[str] = None


class CampaignCreate(CampaignBase):
    scheduled_at: Optional[datetime] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[EmailStr] = None
    reply_to: Optional[EmailStr] = None
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    status: Optional[CampaignStatus] = None
    scheduled_at: Optional[datetime] = None


class CampaignResponse(CampaignBase):
    id: int
    organization_id: int
    status: CampaignStatus
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_recipients: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class MessageBase(BaseModel):
    recipient_email: EmailStr
    recipient_name: Optional[str] = None


class MessageCreate(MessageBase):
    campaign_id: int
    subject: str
    html_content: str
    text_content: Optional[str] = None


class MessageResponse(MessageBase):
    id: int
    campaign_id: int
    subject: str
    status: str
    message_id: Optional[str]
    ses_message_id: Optional[str]
    sent_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class MessageEventResponse(BaseModel):
    id: int
    message_id: int
    event_type: str
    event_data: Optional[dict]
    timestamp: datetime

    class Config:
        from_attributes = True


class EmailSendRequest(BaseModel):
    to_email: EmailStr
    to_name: Optional[str] = None
    subject: str
    html_content: str
    text_content: Optional[str] = None
    from_email: Optional[EmailStr] = None
    from_name: Optional[str] = None
    reply_to: Optional[EmailStr] = None
