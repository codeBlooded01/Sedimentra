import logging
import asyncio
from pathlib import Path
from app.workers.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.db.models.upload import UploadJob
from app.services.validation_service import GenomicValidationService
from app.core.config import settings

logger = logging.getLogger(__name__)

async def _process_ingestion_async(job_id: str, asv_path: str, taxonomy_path: str):
    logger.info(f"[{job_id}] Worker starting actual ingestion pipeline.")

    service = GenomicValidationService(job_id, asv_path, taxonomy_path)
    
    # ── Execute Pandas Flow ──
    # Exceptions outside the validation schema catch block (like total DB failure) 
    # will bubble up, but internal pandas errors are caught.
    report, summary = service.validate_and_preprocess()

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(UploadJob).where(UploadJob.id == job_id))
        job = result.scalar_one_or_none()

        if job:
            job.status = report.status.value
            job.validation_report = report.model_dump()
            
            if summary:
                job.preprocessing_summary = summary.model_dump()

                # ── Store the parquet paths so report-generate can use cleaned data ──
                out_dir = Path(settings.TMP_UPLOAD_DIR) / job_id
                asv_parquet  = out_dir / "asv_filtered_raw.parquet"
                tax_parquet  = out_dir / "tax_processed.parquet"
                if asv_parquet.exists():
                    job.processed_asv_path = str(asv_parquet)
                if tax_parquet.exists():
                    job.processed_taxonomy_path = str(tax_parquet)
                
            await session.commit()
            logger.info(f"[{job_id}] Worker finished. Status: {job.status}. "
                        f"Parquet paths stored: asv={job.processed_asv_path}, tax={job.processed_taxonomy_path}")
        else:
            logger.error(f"[{job_id}] Job not found in database when concluding pipeline.")

@celery_app.task(name="run_ingestion_pipeline")
def run_ingestion_pipeline(job_id: str, asv_path: str, taxonomy_path: str):
    """
    Celery task entry point to process a multi-GB ASV + Taxonomy CSV batch.
    """
    asyncio.run(_process_ingestion_async(job_id, asv_path, taxonomy_path))
    return {"status": "dispatched", "job_id": job_id}
