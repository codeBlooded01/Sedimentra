"""
FastAPI Routes — Accession-Based Import
========================================
Step 1: POST /api/v1/accession/lookup
        → Validate accession format, detect source, dispatch metadata fetch
        → Returns job_id immediately

Step 2: GET /api/v1/accession/preview/{job_id}
        → Poll until metadata preview is ready
        → Returns structured preview for user to review

Step 3: POST /api/v1/accession/confirm/{job_id}
        → User confirms (or cancels) the download
        → Triggers download + convert + validate pipeline

Step 4: GET /api/v1/accession/status/{job_id}
        → Track the full pipeline progress

Step 5: GET /api/v1/accession/validation/{job_id}
        → Get the final validation report (delegates to upload validator)
"""

import uuid
import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models.accession import AccessionJob
from app.schemas.accession import (
    AccessionLookupRequest,
    AccessionConfirmRequest,
    AccessionJobResponse,
    AccessionJobStatus,
    AccessionMetadataPreview,
)
from app.services.accession_resolver import detect_source
from app.workers.accession_tasks import (
    fetch_accession_metadata,
    download_and_convert_accession,
)

router = APIRouter(prefix="/api/v1/accession", tags=["Accession Import"])
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: LOOKUP — Submit accession number
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/lookup", response_model=AccessionJobResponse, status_code=202)
async def lookup_accession(
    request: AccessionLookupRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit an accession number (SRR/ERR/DRR/SRP/ERP/DRP/etc.).
    The system detects the source database and fetches metadata in the background.
    Poll /preview/{job_id} to get the metadata preview.
    """
    accession = request.accession  # Already validated and uppercased by Pydantic
    source = detect_source(accession)

    job_id = str(uuid.uuid4())
    job = AccessionJob(
        id=job_id,
        accession=accession,
        source=source.value,
        status=AccessionJobStatus.PENDING.value,
    )
    db.add(job)
    await db.flush()

    # Dispatch background metadata fetch
    task = fetch_accession_metadata.delay(job_id, accession)
    job.celery_fetch_task = task.id
    await db.commit()

    logger.info(f"[{job_id}] Accession lookup initiated: {accession} ({source.value})")

    return AccessionJobResponse(
        job_id=job_id,
        accession=accession,
        source=source,
        status=AccessionJobStatus.PENDING,
        message=f"Looking up accession '{accession}' in {source.value.upper()}. "
                "This usually takes 5–15 seconds.",
        created_at=job.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: PREVIEW — Poll for metadata
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/preview/{job_id}", response_model=AccessionJobResponse)
async def get_accession_preview(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Poll this endpoint every 3 seconds after calling /lookup.
    When status = 'awaiting_confirmation', metadata_preview is populated
    and ready to display to the user.
    """
    job = await _fetch_job_or_404(db, job_id)

    preview = None
    if job.metadata_preview:
        preview = AccessionMetadataPreview(**job.metadata_preview)

    status_messages = {
        AccessionJobStatus.PENDING.value:    "Connecting to database...",
        AccessionJobStatus.FETCHING.value:   "Retrieving accession metadata...",
        AccessionJobStatus.PREVIEW.value:    "Metadata ready. Please review and confirm.",
        AccessionJobStatus.FAILED.value:     job.error_message or "Metadata fetch failed.",
    }

    return AccessionJobResponse(
        job_id=job.id,
        accession=job.accession,
        source=job.source,
        status=AccessionJobStatus(job.status),
        message=status_messages.get(job.status, "Processing..."),
        metadata_preview=preview,
        created_at=job.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: CONFIRM — User approves or cancels download
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/confirm/{job_id}", response_model=AccessionJobResponse)
async def confirm_accession_download(
    job_id: str,
    request: AccessionConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    User confirms or cancels after reviewing the metadata preview.
    confirmed=true  → triggers download + convert + validate pipeline
    confirmed=false → cancels the job
    """
    job = await _fetch_job_or_404(db, job_id)

    if job.status != AccessionJobStatus.PREVIEW.value:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not awaiting confirmation (current status: '{job.status}'). "
                   "Please call /preview first.",
        )

    if not request.confirmed:
        job.status = AccessionJobStatus.CANCELLED.value
        job.confirmed = False
        await db.commit()
        return AccessionJobResponse(
            job_id=job.id,
            accession=job.accession,
            source=job.source,
            status=AccessionJobStatus.CANCELLED,
            message="Import cancelled. No data was downloaded.",
            created_at=job.created_at,
        )

    # User confirmed — trigger download
    job.confirmed = True
    job.status = AccessionJobStatus.DOWNLOADING.value
    await db.flush()

    task = download_and_convert_accession.delay(job_id)
    job.celery_download_task = task.id
    await db.commit()

    logger.info(f"[{job_id}] User confirmed download for {job.accession}.")

    return AccessionJobResponse(
        job_id=job.id,
        accession=job.accession,
        source=job.source,
        status=AccessionJobStatus.DOWNLOADING,
        message="Download started. The system is retrieving and converting your data.",
        created_at=job.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: STATUS — Track full pipeline progress
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/status/{job_id}", response_model=AccessionJobResponse)
async def get_accession_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """Track the download + convert + validate pipeline."""
    job = await _fetch_job_or_404(db, job_id)

    status_messages = {
        AccessionJobStatus.PENDING.value:      "Queued for processing.",
        AccessionJobStatus.FETCHING.value:     "Fetching metadata from external database...",
        AccessionJobStatus.PREVIEW.value:      "Metadata ready. Awaiting your confirmation.",
        AccessionJobStatus.DOWNLOADING.value:  "Downloading data files from the database...",
        AccessionJobStatus.CONVERTING.value:   "Converting files to the required format...",
        AccessionJobStatus.READY.value:        "Data downloaded and validated successfully.",
        AccessionJobStatus.FAILED.value:       job.error_message or "An error occurred.",
        AccessionJobStatus.CANCELLED.value:    "Import was cancelled.",
    }

    return AccessionJobResponse(
        job_id=job.id,
        accession=job.accession,
        source=job.source,
        status=AccessionJobStatus(job.status),
        message=status_messages.get(job.status, "Processing..."),
        validation_job_id=job.validation_job_id,
        created_at=job.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: Get final validation report (delegates to upload validator)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/validation/{job_id}")
async def get_accession_validation_report(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve the 3-layer validation report for an accession import.
    Redirects to the standard upload validation report endpoint.
    """
    job = await _fetch_job_or_404(db, job_id)

    if not job.validation_job_id:
        raise HTTPException(
            status_code=404,
            detail="Validation has not started yet for this accession.",
        )

    # The validation report lives under the upload job
    return {
        "accession_job_id": job_id,
        "validation_job_id": job.validation_job_id,
        "report_url": f"/api/v1/ingest/report/{job.validation_job_id}",
        "message": (
            f"Validation report available at /api/v1/ingest/report/{job.validation_job_id}"
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

async def _fetch_job_or_404(db: AsyncSession, job_id: str) -> AccessionJob:
    result = await db.execute(select(AccessionJob).where(AccessionJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Accession job '{job_id}' not found.")
    return job
