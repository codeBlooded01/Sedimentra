import logging
import asyncio
from app.workers.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.db.models.accession import AccessionJob

logger = logging.getLogger(__name__)

async def _mark_accession_failed(job_id: str, error_msg: str):
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(AccessionJob).where(AccessionJob.id == job_id))
        job = result.scalar_one_or_none()
        if job:
            job.status = "failed"
            job.error_message = error_msg
            await session.commit()

@celery_app.task(name="fetch_accession_metadata")
def fetch_accession_metadata(job_id: str, accession: str):
    logger.warning(f"Mocking fetch_accession_metadata for job {job_id}")
    asyncio.run(_mark_accession_failed(job_id, "Metadata fetch not implemented."))
    return {"status": "mocked_fail"}

@celery_app.task(name="download_and_convert_accession")
def download_and_convert_accession(job_id: str):
    logger.warning(f"Mocking download_and_convert_accession for job {job_id}")
    asyncio.run(_mark_accession_failed(job_id, "Download not implemented."))
    return {"status": "mocked_fail"}
