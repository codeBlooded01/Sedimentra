from sqlalchemy import Column, String, DateTime, Integer, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class UploadJob(Base):
    """
    Tracks the lifecycle of a paired ASV + Taxonomy upload.
    One row = one complete ingestion attempt by DENR staff.
    """
    __tablename__ = "upload_jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    status = Column(String, nullable=False, default="pending")  # JobStatus enum value

    # File references (paths in /tmp storage)
    asv_tmp_path = Column(String, nullable=True)
    taxonomy_tmp_path = Column(String, nullable=True)
    asv_filename = Column(String, nullable=True)
    taxonomy_filename = Column(String, nullable=True)

    # Celery task tracking
    celery_task_id = Column(String, nullable=True)

    # Validation results stored as JSON (full ValidationReport)
    validation_report = Column(JSON, nullable=True)

    # Preprocessing summary stored as JSON
    preprocessing_summary = Column(JSON, nullable=True)

    # Paths to ML-ready output files
    processed_asv_path = Column(String, nullable=True)
    processed_taxonomy_path = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ProcessedDataset(Base):
    """
    Stores metadata for datasets that have passed all validation
    and are ready for the ML prediction pipeline.
    """
    __tablename__ = "processed_datasets"

    id = Column(String, primary_key=True, default=generate_uuid)
    upload_job_id = Column(String, nullable=False)

    asv_count = Column(Integer, nullable=False)
    sample_count = Column(Integer, nullable=False)
    sample_names = Column(JSON, nullable=False)   # list of sample column names

    # Stored relative paths to Parquet files (ML-ready)
    asv_parquet_path = Column(String, nullable=True)
    taxonomy_parquet_path = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
