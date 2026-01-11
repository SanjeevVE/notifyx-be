from fastapi import APIRouter
from app.api.v1 import auth, emails, campaigns

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(emails.router, prefix="/emails", tags=["Emails"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
