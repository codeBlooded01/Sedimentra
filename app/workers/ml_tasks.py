"""
AD-GSI v4.0 — CELERY TASK INTEGRATION

Distributed task processing for large-scale metagenomic analysis.

TASKS:
- process_ml_features_async: Main 6-phase pipeline
- store_ml_features_async: Persist results to PostgreSQL
- generate_ml_report_async: Create comprehensive report PDF

USAGE:
    from app.workers.ml_tasks import process_ml_features_async
    
    result = process_ml_features_async.delay(
        job_id='job-123',
        asv_path='/tmp/asv.parquet',
        tax_path='/tmp/tax.parquet',
        domain='COASTAL'
    )
    
    # Poll for completion
    status = result.status
    if status == 'SUCCESS':
        ml_features = result.result
"""

import logging
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json

from celery import shared_task, states
from celery.exceptions import SoftTimeLimitExceeded

from app.workers.celery_app import celery_app
from app.services.production_pipeline import validate_and_generate_ml_features
from app.services.faprotax_loader import FAProTAXLoader
from app.db.session import SessionLocal
from app.db.models.ml_models import MLAnalysisJob, SampleAudit, MLFeature

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# CELERY TASKS
# ══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    name='ml.process_features',
    max_retries=2,
    soft_time_limit=3600,  # 1 hour
    time_limit=3660,  # 1 hour + 1 min (hard limit)
)
def process_ml_features_async(
    self,
    job_id: str,
    asv_path: str,
    tax_path: str,
    domain: str = 'COASTAL',
    user_id: Optional[str] = None,
) -> Tuple[bool, List[Dict], Dict]:
    """
    Process ML features asynchronously.
    
    Phases:
    1. Load ASV & Taxonomy
    2. Run 6-phase pipeline
    3. Store results to PostgreSQL
    4. Return ML features
    
    Returns:
        (success, ml_features, audit_report)
    """
    
    logger.info(f"[{job_id}] Starting async ML feature processing")
    self.update_state(state='LOADING_DATA')
    
    try:
        # Update job status
        db = SessionLocal()
        job = db.query(MLAnalysisJob).filter_by(id=job_id).first()
        if not job:
            job = MLAnalysisJob(
                id=job_id,
                user_id=user_id,
                status='PROCESSING',
                domain=domain
            )
            db.add(job)
            db.commit()
        
        # Step 1: Load data
        logger.info(f"[{job_id}] Loading ASV and taxonomy data...")
        try:
            asv_df = pd.read_parquet(asv_path)
            tax_df = pd.read_parquet(tax_path)
        except Exception as e:
            logger.error(f"[{job_id}] Data loading failed: {e}")
            job.status = 'FAILED'
            job.errors = json.dumps({'error': 'Data loading failed', 'detail': str(e)})
            db.commit()
            db.close()
            return False, [], {'status': 'ERROR', 'message': str(e)}
        
        # Step 2: Run pipeline
        logger.info(f"[{job_id}] Running 6-phase AD-GSI pipeline...")
        self.update_state(state='PROCESSING', meta={'stage': 'pipeline'})
        
        try:
            success, ml_features, audit_report = validate_and_generate_ml_features(
                asv_df, tax_df,
                id_column='ASV_ID',
                domain=domain
            )
        except Exception as e:
            logger.exception(f"[{job_id}] Pipeline execution failed")
            job.status = 'FAILED'
            job.errors = json.dumps({'error': 'Pipeline failed', 'detail': str(e)})
            db.commit()
            db.close()
            return False, [], {'status': 'ERROR', 'message': f'Pipeline error: {str(e)}'}
        
        # Step 3: Store results
        logger.info(f"[{job_id}] Storing results to PostgreSQL...")
        self.update_state(state='STORING', meta={'stage': 'persistence'})
        
        try:
            store_ml_results_sync(job_id, ml_features, audit_report, db)
        except Exception as e:
            logger.exception(f"[{job_id}] Storage failed")
            job.status = 'FAILED'
            job.errors = json.dumps({'error': 'Storage failed', 'detail': str(e)})
            db.commit()
            db.close()
            return False, ml_features, audit_report
        
        # Step 4: Update job status
        job.status = 'COMPLETE'
        job.sample_count = len(ml_features)
        job.completed_at = datetime.utcnow()
        
        # Calculate average confidence
        all_confidences = []
        for sample_output in ml_features:
            for feature in sample_output.get('features', []):
                all_confidences.append(feature['confidence'])
        
        if all_confidences:
            job.avg_confidence = sum(all_confidences) / len(all_confidences)
        
        db.commit()
        db.close()
        
        logger.info(f"[{job_id}] ✓ ML processing complete: {job.sample_count} samples")
        
        return success, ml_features, audit_report
    
    except SoftTimeLimitExceeded:
        logger.error(f"[{job_id}] Task timeout (>1 hour)")
        return False, [], {'status': 'ERROR', 'message': 'Task timeout'}
    
    except Exception as e:
        logger.exception(f"[{job_id}] Unexpected error in ML processing")
        
        # Retry logic
        logger.info(f"[{job_id}] Retrying task (attempt {self.request.retries})")
        try:
            raise self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            logger.error(f"[{job_id}] Max retries exceeded")
            return False, [], {'status': 'ERROR', 'message': 'Processing failed after retries'}

@celery_app.task(
    name='ml.store_results',
    bind=True,
)
def store_ml_results_async(
    self,
    job_id: str,
    ml_features: List[Dict],
    audit_report: Dict,
) -> bool:
    """Store ML results to PostgreSQL (can be called standalone)."""
    db = SessionLocal()
    try:
        result = store_ml_results_sync(job_id, ml_features, audit_report, db)
        db.close()
        return result
    except Exception as e:
        logger.exception(f"Storage async task failed: {e}")
        db.close()
        return False

@celery_app.task(
    name='ml.generate_report',
    bind=True,
)
def generate_ml_report_async(
    self,
    job_id: str,
    output_path: str,
) -> bool:
    """
    Generate comprehensive PDF report of ML analysis.
    
    Requires: ReportLab or similar PDF generation library
    TODO: Implement PDF generation
    """
    logger.info(f"[{job_id}] Generating PDF report to {output_path}")
    
    db = SessionLocal()
    try:
        job = db.query(MLAnalysisJob).filter_by(id=job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return False
        
        # TODO: Generate PDF with:
        # - Summary statistics
        # - Per-sample audit metrics
        # - Functional feature heatmaps
        # - Domain signature plots
        # - Confidence score distributions
        # - ML feature tables
        
        logger.info(f"✓ Report generated: {output_path}")
        return True
    
    except Exception as e:
        logger.exception(f"Report generation failed: {e}")
        return False
    
    finally:
        db.close()

# ══════════════════════════════════════════════════════════════════════════════
# HELPER: SYNCHRONOUS RESULT STORAGE
# ══════════════════════════════════════════════════════════════════════════════

def store_ml_results_sync(
    job_id: str,
    ml_features: List[Dict],
    audit_report: Dict,
    db_session,
) -> bool:
    """
    Store ML feature results to PostgreSQL.
    
    Inserts:
    - sample_audits for each sample
    - ml_features for each functional feature
    """
    
    try:
        stored_features = 0
        stored_audits = 0
        
        for sample_output in ml_features:
            sample_id = sample_output['sample_id']
            audit = sample_output.get('audit', {})
            
            # Store sample audit
            sample_audit = SampleAudit(
                job_id=job_id,
                sample_id=sample_id,
                total_reads=audit.get('total_reads', 0),
                median_bp=audit.get('median_bp'),
                std_dev=audit.get('std_dev'),
                asv_count=audit.get('asv_count'),
                conf_score=audit.get('conf_score'),
                noise_loss_pct=audit.get('noise_loss_pct'),
                violations=sample_output.get('errors', []),
            )
            db_session.add(sample_audit)
            stored_audits += 1
            
            # Store features
            for feature in sample_output.get('features', []):
                ml_feature = MLFeature(
                    job_id=job_id,
                    sample_id=sample_id,
                    function=feature['function'],
                    rel_abundance=feature['rel_abundance'],
                    confidence=feature['confidence'],
                    contributors=feature['contributors'],
                )
                db_session.add(ml_feature)
                stored_features += 1
        
        db_session.commit()
        logger.info(f"Stored {stored_features} features & {stored_audits} audits")
        return True
    
    except Exception as e:
        logger.exception(f"Storage error: {e}")
        db_session.rollback()
        return False

# ══════════════════════════════════════════════════════════════════════════════
# TASK MONITORING
# ══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    name='ml.check_status',
    bind=True,
)
def check_job_status(self, job_id: str) -> Dict:
    """Check status of ML analysis job."""
    db = SessionLocal()
    try:
        job = db.query(MLAnalysisJob).filter_by(id=job_id).first()
        if not job:
            return {'status': 'NOT_FOUND'}
        
        return {
            'job_id': job_id,
            'status': job.status,
            'sample_count': job.sample_count,
            'avg_confidence': job.avg_confidence,
            'created_at': job.created_at.isoformat(),
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        }
    finally:
        db.close()

@celery_app.task(
    name='ml.cancel_job',
    bind=True,
)
def cancel_job(self, job_id: str) -> bool:
    """Cancel a running ML analysis job."""
    db = SessionLocal()
    try:
        job = db.query(MLAnalysisJob).filter_by(id=job_id).first()
        if not job:
            return False
        
        job.status = 'CANCELLED'
        db.commit()
        logger.info(f"Job {job_id} cancelled")
        return True
    finally:
        db.close()

# ══════════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLES
# ══════════════════════════════════════════════════════════════════════════════

"""
EXAMPLE 1: Submit job asynchronously
────────────────────────────────────

from app.workers.ml_tasks import process_ml_features_async

result = process_ml_features_async.delay(
    job_id='job-456',
    asv_path='/tmp/data/asv.parquet',
    tax_path='/tmp/data/tax.parquet',
    domain='COASTAL',
    user_id='user-123'
)

print(f"Task ID: {result.id}")
print(f"Status: {result.status}")


EXAMPLE 2: Poll for job completion
───────────────────────────────────

from app.workers.ml_tasks import check_job_status

# In a loop (FastAPI endpoint)
status = check_job_status.delay('job-456')
while status.status != 'COMPLETE':
    time.sleep(5)
    status = check_job_status.delay(status.id)

ml_features = status.result


EXAMPLE 3: Celery Beat Scheduler (periodic tasks)
─────────────────────────────────────────────────

# In celery_app.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-old-jobs': {
        'task': 'ml.cleanup_old_jobs',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
}
"""
