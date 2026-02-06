from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.database import Base


class ImportJobStatus(str, enum.Enum):
    PENDING = "pending"         # Job created, awaiting column mapping
    PROCESSING = "processing"   # Import in progress
    COMPLETED = "completed"     # Import finished successfully
    FAILED = "failed"           # Import failed with error
    CANCELLED = "cancelled"     # Import cancelled by user


class ImportJob(Base):
    """
    Tracks Excel/CSV import jobs for contacts.

    Workflow:
    1. User uploads file -> job created with PENDING status
    2. User submits column mapping -> job starts with PROCESSING status
    3. Celery worker processes rows -> updates progress
    4. Job completes with COMPLETED/FAILED status
    """
    __tablename__ = "import_jobs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    # File information
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)  # Temporary storage path
    file_size = Column(Integer, nullable=True)  # Size in bytes

    # Job status
    status = Column(Enum(ImportJobStatus), default=ImportJobStatus.PENDING, index=True)

    # Column mapping configuration
    # Format: [{"source_column": "Email Address", "target_field": "email", "create_field": false}, ...]
    column_mapping = Column(JSON, nullable=True)

    # Import options
    # Format: {"skip_duplicates": true, "update_existing": false, "list_id": 1}
    options = Column(JSON, nullable=True)

    # Progress tracking
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    imported_count = Column(Integer, default=0)  # New contacts created
    updated_count = Column(Integer, default=0)   # Existing contacts updated
    skipped_count = Column(Integer, default=0)   # Duplicates skipped
    failed_count = Column(Integer, default=0)    # Rows that failed validation

    # Error details (limited to first 100 errors)
    # Format: [{"row": 5, "email": "bad@", "error": "Invalid email format"}, ...]
    errors = Column(JSON, nullable=True)

    # Error message for job-level failures
    error_message = Column(Text, nullable=True)

    # Celery task tracking
    celery_task_id = Column(String(255), nullable=True)

    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    organization = relationship("Organization")

    @property
    def progress_percentage(self) -> float:
        """Calculate import progress as percentage"""
        if self.total_rows == 0:
            return 0.0
        return round((self.processed_rows / self.total_rows) * 100, 1)

    @property
    def is_complete(self) -> bool:
        """Check if job has finished (success or failure)"""
        return self.status in (ImportJobStatus.COMPLETED, ImportJobStatus.FAILED, ImportJobStatus.CANCELLED)

    def __repr__(self):
        return f"<ImportJob(id={self.id}, status={self.status}, progress={self.progress_percentage}%)>"


# Configuration constants
IMPORT_BATCH_SIZE = 100           # Rows per database commit
PROGRESS_UPDATE_INTERVAL = 10     # Update job progress every N rows
MAX_ERRORS_STORED = 100           # Maximum number of errors to store in job
MAX_PREVIEW_ROWS = 5              # Number of rows to show in preview
