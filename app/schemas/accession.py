"""
Pydantic Schemas — Accession-Based Import
==========================================
Covers the full UX flow:
  1. User submits accession number
  2. System fetches + returns metadata preview
  3. User confirms → system downloads & converts to CSV
  4. Converted CSVs enter the existing 3-layer validation pipeline
"""

from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import Optional
from datetime import datetime
import re


# ── Enums ──────────────────────────────────────────────────────────────────────

class AccessionSource(str, Enum):
    SRA  = "sra"   # NCBI — USA       (SRR, SRP, SRX, SRS, SRA prefixes)
    ENA  = "ena"   # EMBL-EBI — EU    (ERR, ERP, ERX, ERS, ERA prefixes)
    DDBJ = "ddbj"  # DDBJ — Japan     (DRR, DRP, DRX, DRS, DRA prefixes)


class AccessionJobStatus(str, Enum):
    PENDING     = "pending"
    FETCHING    = "fetching_metadata"
    PREVIEW     = "awaiting_confirmation"   # Metadata ready, waiting for user
    DOWNLOADING = "downloading"
    CONVERTING  = "converting"
    READY       = "ready"                   # CSVs ready → enters validator
    FAILED      = "failed"
    CANCELLED   = "cancelled"


class ProcessedFileType(str, Enum):
    ASV_TABLE  = "asv_table"
    TAXONOMY   = "taxonomy"
    COMBINED   = "combined"     # Some studies deposit a single combined file
    UNKNOWN    = "unknown"


# ── Request Schemas ────────────────────────────────────────────────────────────

class AccessionLookupRequest(BaseModel):
    accession: str = Field(..., description="SRR/ERR/DRR or study/experiment accession number")

    @field_validator("accession")
    @classmethod
    def validate_accession_format(cls, v: str) -> str:
        v = v.strip().upper()
        # Accepted prefixes across SRA / ENA / DRR
        pattern = re.compile(
            r"^(SRR|SRP|SRX|SRS|SRA|"   # SRA
            r"ERR|ERP|ERX|ERS|ERA|"       # ENA
            r"DRR|DRP|DRX|DRS|DRA)"       # DDBJ
            r"\d{6,12}$"
        )
        if not pattern.match(v):
            raise ValueError(
                f"'{v}' is not a valid accession number. "
                "Expected formats: SRR123456, ERR123456, DRR123456, "
                "SRP123456, ERP123456, etc."
            )
        return v


class AccessionConfirmRequest(BaseModel):
    job_id: str
    confirmed: bool = True


# ── Metadata Preview Schema (shown to user before download) ───────────────────

class ProcessedFileInfo(BaseModel):
    """A single downloadable processed file found in the accession."""
    filename: str
    url: str
    file_type: ProcessedFileType
    size_bytes: Optional[int] = None
    description: Optional[str] = None


class AccessionMetadataPreview(BaseModel):
    """
    Everything the user sees before confirming a download.
    Designed for non-technical DENR staff — plain English throughout.
    """
    job_id: str
    accession: str
    source: AccessionSource

    # Study-level metadata
    study_title: Optional[str] = None
    study_abstract: Optional[str] = None
    organism: Optional[str] = None
    environment: Optional[str] = None       # e.g. "marine sediment", "soil"
    collection_date: Optional[str] = None
    geo_location: Optional[str] = None      # e.g. "Philippines: Leyte"
    sample_count: Optional[int] = None
    sequencing_platform: Optional[str] = None
    instrument_model: Optional[str] = None

    # What files are available for download
    processed_files: list[ProcessedFileInfo] = Field(default_factory=list)
    has_processed_tables: bool = False      # True if ASV/taxonomy CSVs found

    # Plain-English readiness message for DENR staff
    readiness_message: str = ""

    submitted_by: Optional[str] = None
    submission_date: Optional[str] = None


# ── Job Tracking Schema ────────────────────────────────────────────────────────

class AccessionJobResponse(BaseModel):
    job_id: str
    accession: str
    source: AccessionSource
    status: AccessionJobStatus
    message: str
    metadata_preview: Optional[AccessionMetadataPreview] = None
    validation_job_id: Optional[str] = None  # Set when handed off to validator
    created_at: datetime

    class Config:
        from_attributes = True
