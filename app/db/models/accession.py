from sqlalchemy import Column, String, DateTime, JSON, Boolean
from sqlalchemy.sql import func
from app.db.models.upload import Base
import uuid


def _uuid():
    return str(uuid.uuid4())


class AccessionJob(Base):
    """
    Tracks the full lifecycle of an accession-based import:
      lookup → metadata preview → user confirmation → download → convert → validate
    """
    __tablename__ = "accession_jobs"

    id                  = Column(String, primary_key=True, default=_uuid)
    accession           = Column(String, nullable=False, index=True)
    source              = Column(String, nullable=False)        # AccessionSource value
    status              = Column(String, nullable=False, default="pending")

    # Raw metadata JSON returned by the external API
    raw_metadata        = Column(JSON, nullable=True)

    # Structured preview shown to the user
    metadata_preview    = Column(JSON, nullable=True)

    # User decision
    confirmed           = Column(Boolean, nullable=True)        # None = not yet decided

    # Celery task IDs
    celery_fetch_task   = Column(String, nullable=True)
    celery_download_task = Column(String, nullable=True)

    # Downloaded + converted file paths
    downloaded_files    = Column(JSON, nullable=True)           # list of {url, local_path, file_type}
    asv_csv_path        = Column(String, nullable=True)
    taxonomy_csv_path   = Column(String, nullable=True)

    # Handed off to the existing validation pipeline
    validation_job_id   = Column(String, nullable=True)

    # Error tracking
    error_message       = Column(String, nullable=True)

    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())
