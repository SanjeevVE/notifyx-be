"""
API Dependencies - Common dependencies used across API endpoints
"""
from app.api.v1.auth import get_current_user

__all__ = ["get_current_user"]
