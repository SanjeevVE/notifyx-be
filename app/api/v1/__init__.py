from fastapi import APIRouter
from app.api.v1 import auth, emails, campaigns, contacts, templates, tracking, webhooks, analytics

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(emails.router, prefix="/emails", tags=["Emails"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["Contacts"])
api_router.include_router(templates.router, prefix="/templates", tags=["Templates"])
api_router.include_router(tracking.router, prefix="/tracking", tags=["Tracking"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
