import boto3
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via AWS SES"""

    def __init__(self):
        self.ses_client = boto3.client(
            'ses',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.default_sender = settings.SES_SENDER_EMAIL

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        message_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email using AWS SES

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content
            text_content: Plain text content (optional)
            from_email: Sender email (defaults to SES_SENDER_EMAIL)
            from_name: Sender name
            reply_to: Reply-to address
            message_id: Custom Message-ID for threading
            in_reply_to: In-Reply-To header for threading
            references: References header for threading

        Returns:
            Dict with message_id and status
        """
        try:
            sender = from_email or self.default_sender
            if from_name:
                sender = f"{from_name} <{sender}>"

            # Build email body
            body = {}
            if html_content:
                body['Html'] = {'Data': html_content, 'Charset': 'UTF-8'}
            if text_content:
                body['Text'] = {'Data': text_content, 'Charset': 'UTF-8'}

            # Build message
            message = {
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': body
            }

            # Send email
            send_kwargs = {
                'Source': sender,
                'Destination': {'ToAddresses': [to_email]},
                'Message': message,
            }

            # Add reply-to if provided
            if reply_to:
                send_kwargs['ReplyToAddresses'] = [reply_to]

            # Add custom headers for email threading
            if message_id or in_reply_to or references:
                headers = []
                if message_id:
                    headers.append({'Name': 'Message-ID', 'Value': message_id})
                if in_reply_to:
                    headers.append({'Name': 'In-Reply-To', 'Value': in_reply_to})
                if references:
                    headers.append({'Name': 'References', 'Value': references})

                if headers:
                    send_kwargs['Message']['Headers'] = headers

            response = self.ses_client.send_email(**send_kwargs)

            logger.info(f"Email sent successfully to {to_email}. MessageId: {response['MessageId']}")

            return {
                'success': True,
                'message_id': response['MessageId'],
                'status': 'sent'
            }

        except ClientError as e:
            error_message = e.response['Error']['Message']
            logger.error(f"Failed to send email to {to_email}: {error_message}")

            return {
                'success': False,
                'error': error_message,
                'status': 'failed'
            }

        except Exception as e:
            logger.error(f"Unexpected error sending email to {to_email}: {str(e)}")

            return {
                'success': False,
                'error': str(e),
                'status': 'failed'
            }

    async def verify_email_identity(self, email: str) -> Dict[str, Any]:
        """
        Verify an email address or domain with SES

        Args:
            email: Email address or domain to verify

        Returns:
            Dict with verification status
        """
        try:
            self.ses_client.verify_email_identity(EmailAddress=email)
            logger.info(f"Verification email sent to {email}")

            return {
                'success': True,
                'message': f'Verification email sent to {email}'
            }

        except ClientError as e:
            error_message = e.response['Error']['Message']
            logger.error(f"Failed to verify email {email}: {error_message}")

            return {
                'success': False,
                'error': error_message
            }

    async def check_verification_status(self, email: str) -> Dict[str, Any]:
        """
        Check if an email address is verified

        Args:
            email: Email address to check

        Returns:
            Dict with verification status
        """
        try:
            response = self.ses_client.get_identity_verification_attributes(
                Identities=[email]
            )

            verification_attrs = response.get('VerificationAttributes', {})
            status = verification_attrs.get(email, {}).get('VerificationStatus', 'NotVerified')

            return {
                'success': True,
                'email': email,
                'status': status,
                'is_verified': status == 'Success'
            }

        except ClientError as e:
            error_message = e.response['Error']['Message']
            logger.error(f"Failed to check verification status for {email}: {error_message}")

            return {
                'success': False,
                'error': error_message
            }


# Singleton instance
email_service = EmailService()
