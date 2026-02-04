"""
Tracking API - Open/click tracking and unsubscribe endpoints
These endpoints are PUBLIC and do not require authentication.
"""
from fastapi import APIRouter, Depends, Request, Query, Form
from fastapi.responses import Response, RedirectResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_db
from app.services.tracking_service import (
    record_open_event,
    record_click_event,
    decode_url,
    get_unsubscribe_info,
    process_unsubscribe,
    TRACKING_PIXEL
)

router = APIRouter()


@router.get("/open/{tracking_id}.gif", include_in_schema=False)
async def track_open(
    tracking_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Track email opens via a 1x1 transparent GIF pixel.
    This endpoint is called when the email client loads images.
    """
    # Get client info for analytics
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    # Record the open event (don't wait for it to complete)
    await record_open_event(
        db=db,
        tracking_id=tracking_id,
        user_agent=user_agent,
        ip_address=ip_address
    )

    # Return transparent 1x1 GIF
    return Response(
        content=TRACKING_PIXEL,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@router.get("/click/{tracking_id}/{encoded_url:path}")
async def track_click(
    tracking_id: str,
    encoded_url: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Track link clicks and redirect to the original URL.
    The URL is base64 encoded for safe transmission.
    """
    # Decode the original URL
    original_url = decode_url(encoded_url)

    if not original_url:
        # If URL is invalid, redirect to a safe fallback
        return RedirectResponse(url="/", status_code=302)

    # Get client info for analytics
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    # Record the click event
    await record_click_event(
        db=db,
        tracking_id=tracking_id,
        link_url=original_url,
        user_agent=user_agent,
        ip_address=ip_address
    )

    # Redirect to the original URL
    return RedirectResponse(url=original_url, status_code=302)


@router.get("/unsubscribe/{token}")
async def unsubscribe_page(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Display unsubscribe confirmation page.
    This is a public page that doesn't require authentication.
    """
    info = await get_unsubscribe_info(db, token)

    if not info:
        return HTMLResponse(
            content=get_error_page("Invalid or expired unsubscribe link"),
            status_code=404
        )

    if info["is_already_unsubscribed"]:
        return HTMLResponse(
            content=get_success_page(info["email"], already_unsubscribed=True),
            status_code=200
        )

    return HTMLResponse(
        content=get_unsubscribe_form_page(
            token=token,
            email=info["email"],
            campaign_name=info.get("campaign_name")
        ),
        status_code=200
    )


@router.post("/unsubscribe/{token}")
async def process_unsubscribe_request(
    token: str,
    reason: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Process the unsubscribe request.
    """
    success, message = await process_unsubscribe(db, token, reason)

    if success:
        info = await get_unsubscribe_info(db, token)
        email = info["email"] if info else "your email"
        return HTMLResponse(
            content=get_success_page(email),
            status_code=200
        )
    else:
        return HTMLResponse(
            content=get_error_page(message),
            status_code=400
        )


def get_base_styles() -> str:
    """Return common CSS styles for unsubscribe pages"""
    return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            max-width: 500px;
            width: 90%;
            text-align: center;
        }
        h1 {
            color: #333;
            margin-bottom: 20px;
        }
        p {
            color: #666;
            line-height: 1.6;
        }
        .email {
            font-weight: bold;
            color: #333;
        }
        .btn {
            display: inline-block;
            padding: 12px 30px;
            margin: 10px 5px;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            text-decoration: none;
        }
        .btn-primary {
            background-color: #dc3545;
            color: white;
        }
        .btn-primary:hover {
            background-color: #c82333;
        }
        .btn-secondary {
            background-color: #6c757d;
            color: white;
        }
        .btn-secondary:hover {
            background-color: #5a6268;
        }
        textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            margin: 15px 0;
            font-family: inherit;
            resize: vertical;
        }
        .success-icon {
            font-size: 48px;
            color: #28a745;
            margin-bottom: 20px;
        }
        .error-icon {
            font-size: 48px;
            color: #dc3545;
            margin-bottom: 20px;
        }
    """


def get_unsubscribe_form_page(token: str, email: str, campaign_name: Optional[str] = None) -> str:
    """Generate the unsubscribe confirmation form page"""
    campaign_text = f" from <strong>{campaign_name}</strong>" if campaign_name else ""

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Unsubscribe</title>
        <style>{get_base_styles()}</style>
    </head>
    <body>
        <div class="container">
            <h1>Unsubscribe</h1>
            <p>
                Are you sure you want to unsubscribe
                <span class="email">{email}</span>{campaign_text}?
            </p>
            <p>You will no longer receive marketing emails from us.</p>

            <form method="POST" action="/api/v1/tracking/unsubscribe/{token}">
                <textarea
                    name="reason"
                    placeholder="Optional: Tell us why you're unsubscribing..."
                    rows="3"
                ></textarea>

                <div>
                    <button type="submit" class="btn btn-primary">
                        Unsubscribe
                    </button>
                </div>
            </form>
        </div>
    </body>
    </html>
    """


def get_success_page(email: str, already_unsubscribed: bool = False) -> str:
    """Generate the success page after unsubscribing"""
    if already_unsubscribed:
        message = f"<span class='email'>{email}</span> is already unsubscribed from our mailing list."
    else:
        message = f"<span class='email'>{email}</span> has been successfully removed from our mailing list."

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Unsubscribed Successfully</title>
        <style>{get_base_styles()}</style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✓</div>
            <h1>Unsubscribed</h1>
            <p>{message}</p>
            <p>We're sorry to see you go. If you change your mind, you can always resubscribe.</p>
        </div>
    </body>
    </html>
    """


def get_error_page(message: str) -> str:
    """Generate an error page"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Error</title>
        <style>{get_base_styles()}</style>
    </head>
    <body>
        <div class="container">
            <div class="error-icon">✕</div>
            <h1>Error</h1>
            <p>{message}</p>
            <p>If you believe this is a mistake, please contact our support team.</p>
        </div>
    </body>
    </html>
    """
