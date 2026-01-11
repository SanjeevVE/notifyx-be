from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.models.campaign import Message, MessageEvent
from app.schemas.campaign import EmailSendRequest, MessageResponse
from app.services.email_service import email_service
from app.api.v1.auth import get_current_user

router = APIRouter()


@router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_email(
    email_data: EmailSendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a single email via AWS SES
    """
    # Send email via SES
    result = await email_service.send_email(
        to_email=email_data.to_email,
        subject=email_data.subject,
        html_content=email_data.html_content,
        text_content=email_data.text_content,
        from_email=email_data.from_email,
        from_name=email_data.from_name,
        reply_to=email_data.reply_to,
    )

    # Create message record
    message = Message(
        campaign_id=None,  # Single email, not part of a campaign
        recipient_email=email_data.to_email,
        recipient_name=email_data.to_name,
        subject=email_data.subject,
        html_content=email_data.html_content,
        text_content=email_data.text_content,
        status=result['status'],
        ses_message_id=result.get('message_id'),
        error_message=result.get('error') if not result['success'] else None,
        sent_at=datetime.utcnow() if result['success'] else None,
    )

    db.add(message)
    await db.commit()
    await db.refresh(message)

    # Create event
    event = MessageEvent(
        message_id=message.id,
        event_type='sent' if result['success'] else 'failed',
        event_data=result,
    )
    db.add(event)
    await db.commit()

    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {result.get('error')}",
        )

    return message


@router.get("/verify/{email}")
async def verify_email_identity(
    email: str,
    current_user: User = Depends(get_current_user),
):
    """
    Send verification email for AWS SES
    """
    result = await email_service.verify_email_identity(email)

    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send verification: {result.get('error')}",
        )

    return result


@router.get("/verify-status/{email}")
async def check_verification_status(
    email: str,
    current_user: User = Depends(get_current_user),
):
    """
    Check verification status of an email in AWS SES
    """
    result = await email_service.check_verification_status(email)

    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check status: {result.get('error')}",
        )

    return result


@router.get("/messages", response_model=list[MessageResponse])
async def get_messages(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all messages for the current user's organization
    """
    result = await db.execute(
        select(Message)
        .order_by(Message.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    messages = result.scalars().all()

    return messages


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific message by ID
    """
    result = await db.execute(select(Message).filter(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    return message
