from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "notifyx",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.email_tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,  # Acknowledge tasks after completion
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    task_time_limit=600,  # 10 minute hard limit
    task_soft_time_limit=540,  # 9 minute soft limit (for graceful shutdown)

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_concurrency=4,  # 4 concurrent workers

    # Queue settings
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "email_sending": {"exchange": "email", "routing_key": "email.send"},
        "email_tracking": {"exchange": "email", "routing_key": "email.track"},
        "webhooks": {"exchange": "webhooks", "routing_key": "webhooks.*"},
    },

    # Route tasks to specific queues
    task_routes={
        "app.tasks.email_tasks.send_email_batch": {"queue": "email_sending"},
        "app.tasks.email_tasks.process_campaign": {"queue": "email_sending"},
        "app.tasks.email_tasks.process_webhook_event": {"queue": "webhooks"},
    },

    # Retry settings
    task_default_retry_delay=60,  # 1 minute default retry delay
    task_max_retries=3,

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour

    # Beat scheduler (for scheduled tasks)
    beat_schedule={
        "check-scheduled-campaigns": {
            "task": "app.tasks.email_tasks.check_scheduled_campaigns",
            "schedule": 60.0,  # Every minute
        },
        "cleanup-old-results": {
            "task": "app.tasks.email_tasks.cleanup_old_results",
            "schedule": 3600.0,  # Every hour
        },
    },
)

# Optional: Configure logging
celery_app.conf.update(
    worker_hijack_root_logger=False,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)
