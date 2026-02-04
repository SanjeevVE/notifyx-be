from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Email Communication Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # AWS SES
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    SES_SENDER_EMAIL: str

    # Redis (for queue)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Tracking
    TRACKING_BASE_URL: str = "http://localhost:8000/api/v1/tracking"
    UNSUBSCRIBE_BASE_URL: str = "http://localhost:8000/unsubscribe"

    # Email sending
    BATCH_SIZE: int = 50  # Emails per batch
    SES_SEND_RATE: int = 14  # Emails per second

    # CORS - Allow all origins (set to specific origins in production)
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
