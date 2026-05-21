"""
AD-GSI v4.0 — FASTAPI ENDPOINTS

REST API for metagenomic analysis submission and retrieval.

Endpoints:
POST   /analyze/submit       - Submit new analysis job
GET    /analyze/status/{id}  - Check job status
GET    /analyze/features/{id} - Retrieve ML features
GET    /analyze/audit/{id}   - Retrieve sample audits
POST   /analyze/cancel/{id}  - Cancel running job
GET    /analyze/domains      - List available domains
"""

import logging
import tempfile
from typing import Optional, List
from pathlib import Path
from datetime import datetime
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
import pandas as pd

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models.ml_models import MLAnalysisJob, SampleAudit, MLFeature
from app.workers.ml_tasks import process_ml_features_async, check_job_status
from app.services.integration import GenomicValidationServiceML

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["metagenomic-analysis"])

# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class AnalysisSubmitRequest(BaseModel):
    domain: str = 'COASTAL'  # COASTAL | SOIL | FRESHWATER
    run_ml_generation: bool = True

class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # PROCESSING | COMPLETE | FAILED | CANCELLED
    samples: int = 0
    avg_confidence: Optional[float] = None
    created_at: str
    completed_at: Optional[str] = None

class MLFeatureResponse(BaseModel):
    function: str
    rel_abundance: float
    confidence: float
    contributors: List[str]

class SampleFeatureResponse(BaseModel):
    sample_id: str
    total_reads: int
    features: List[MLFeatureResponse]
    confidence_score: float
    errors: List[str]

class AnalysisResultsResponse(BaseModel):
    job_id: str
    domain: str
    samples: List[SampleFeatureResponse]
    domain_signature: float

# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/submit", response_model=dict)
async def submit_analysis(
    asv_file: UploadFile = File(...),
    tax_file: UploadFile = File(...),
    domain: str = Query('COASTAL', regex='^(COASTAL|SOIL|FRESHWATER)$'),
    background_tasks: BackgroundTasks = None,
) -> dict:
    """
    Submit new metagenomic analysis job.
    
    Returns 202 Accepted with job_id for polling.
    """
    
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create temporary directory
        temp_dir = Path(settings.TMP_UPLOAD_DIR) / job_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded files
        asv_path = temp_dir / "asv.csv"
        tax_path = temp_dir / "tax.csv"
        
        asv_content = await asv_file.read()
        tax_content = await tax_file.read()
        
        with open(asv_path, 'wb') as f:
            f.write(asv_content)
        with open(tax_path, 'wb') as f:
            f.write(tax_content)
        
        logger.info(f"[{job_id}] Files received: ASV={asv_path.stat().st_size} bytes, "
                   f"TAX={tax_path.stat().st_size} bytes")
        
        # Create job record
        db = SessionLocal()
        try:
            job = MLAnalysisJob(
                id=job_id,
                status='QUEUED',
                domain=domain,
            )
            db.add(job)
            db.commit()
        finally:
            db.close()
        
        # Queue background task
        if background_tasks:
            background_tasks.add_task(
                run_analysis_pipeline,
                job_id=job_id,
                asv_path=str(asv_path),
                tax_path=str(tax_path),
                domain=domain,
            )
        
        return {
            "job_id": job_id,
            "status": "202 Accepted",
            "message": "Analysis queued. Poll /analyze/status/{job_id} for results.",
            "poll_url": f"/analyze/status/{job_id}",
        }
    
    except Exception as e:
        logger.exception("Submission failed")
        raise HTTPException(status_code=500, detail=f"Submission failed: {str(e)}")

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Check status of analysis job."""
    
    db = SessionLocal()
    try:
        job = db.query(MLAnalysisJob).filter_by(id=job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return JobStatusResponse(
            job_id=job_id,
            status=job.status,
            samples=job.sample_count or 0,
            avg_confidence=job.avg_confidence,
            created_at=job.created_at.isoformat(),
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
        )
    
    finally:
        db.close()

@router.get("/features/{job_id}", response_model=AnalysisResultsResponse)
async def get_ml_features(job_id: str) -> AnalysisResultsResponse:
    """Retrieve ML features for completed analysis."""
    
    db = SessionLocal()
    try:
        job = db.query(MLAnalysisJob).filter_by(id=job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        if job.status != 'COMPLETE':
            raise HTTPException(status_code=202, detail="Analysis still processing")
        
        # Get all features grouped by sample
        features = db.query(MLFeature).filter_by(job_id=job_id).all()
        audits = db.query(SampleAudit).filter_by(job_id=job_id).all()
        
        audit_map = {a.sample_id: a for a in audits}
        
        # Group features by sample
        sample_features = {}
        for feature in features:
            if feature.sample_id not in sample_features:
                sample_features[feature.sample_id] = []
            sample_features[feature.sample_id].append(feature)
        
        # Build response
        samples = []
        for sample_id, sample_feature_list in sample_features.items():
            audit = audit_map.get(sample_id)
            
            sample_resp = SampleFeatureResponse(
                sample_id=sample_id,
                total_reads=audit.total_reads if audit else 0,
                features=[
                    MLFeatureResponse(
                        function=f.function,
                        rel_abundance=f.rel_abundance,
                        confidence=f.confidence,
                        contributors=f.contributors
                    )
                    for f in sample_feature_list
                ],
                confidence_score=audit.conf_score if audit else 0.0,
                errors=audit.violations if audit else [],
            )
            samples.append(sample_resp)
        
        return AnalysisResultsResponse(
            job_id=job_id,
            domain=job.domain,
            samples=samples,
            domain_signature=0.0,  # Would come from audit report
        )
    
    finally:
        db.close()

@router.get("/audit/{job_id}")
async def get_sample_audits(job_id: str) -> dict:
    """Retrieve sample audit metrics for job."""
    
    db = SessionLocal()
    try:
        job = db.query(MLAnalysisJob).filter_by(id=job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        audits = db.query(SampleAudit).filter_by(job_id=job_id).all()
        
        audit_list = []
        for audit in audits:
            audit_list.append({
                'sample_id': audit.sample_id,
                'total_reads': audit.total_reads,
                'median_bp': audit.median_bp,
                'std_dev': audit.std_dev,
                'asv_count': audit.asv_count,
                'conf_score': audit.conf_score,
                'noise_loss_pct': audit.noise_loss_pct,
                'constraints': {
                    'median_bp_valid': bool(audit.median_valid),
                    'std_dev_valid': bool(audit.std_dev_valid),
                    'reads_valid': bool(audit.reads_valid),
                },
                'violations': audit.violations or [],
            })
        
        return {
            'job_id': job_id,
            'sample_count': len(audits),
            'audits': audit_list,
        }
    
    finally:
        db.close()

@router.post("/cancel/{job_id}")
async def cancel_analysis(job_id: str) -> dict:
    """Cancel running analysis job."""
    
    db = SessionLocal()
    try:
        job = db.query(MLAnalysisJob).filter_by(id=job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        if job.status in ['COMPLETE', 'FAILED']:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job in {job.status} state"
            )
        
        job.status = 'CANCELLED'
        db.commit()
        
        logger.info(f"Job {job_id} cancelled by user")
        
        return {
            'job_id': job_id,
            'status': 'CANCELLED',
            'message': 'Job cancellation requested',
        }
    
    finally:
        db.close()

@router.get("/domains")
async def list_domains() -> dict:
    """List available analysis domains."""
    
    return {
        'domains': [
            {
                'id': 'COASTAL',
                'name': 'Coastal Sediment',
                'biomarkers': ['Desulfobacterales', 'Bacteroidales', 'Sulfur-cyclers'],
                'description': 'Marine sulfate-reducing, anaerobic environments'
            },
            {
                'id': 'SOIL',
                'name': 'Soil',
                'biomarkers': ['Actinomycetota', 'Acidobacteriota', 'N-fixers'],
                'description': 'Terrestrial, aerobic soil environments'
            },
            {
                'id': 'FRESHWATER',
                'name': 'Freshwater',
                'biomarkers': ['Betaproteobacteria', 'Actinobacteria'],
                'description': 'Freshwater lake and river microbiomes'
            },
        ]
    }

@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
    }

# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASK RUNNER
# ══════════════════════════════════════════════════════════════════════════════

async def run_analysis_pipeline(
    job_id: str,
    asv_path: str,
    tax_path: str,
    domain: str,
) -> None:
    """
    Run the full analysis pipeline (Celery task wrapper).
    
    This is called via FastAPI BackgroundTasks, which then
    kicks off Celery task for actual processing.
    """
    
    logger.info(f"[{job_id}] Starting background analysis task")
    
    try:
        # Convert CSV to Parquet for efficiency
        asv_df = pd.read_csv(asv_path)
        tax_df = pd.read_csv(tax_path)
        
        temp_dir = Path(asv_path).parent
        asv_parquet = temp_dir / "asv.parquet"
        tax_parquet = temp_dir / "tax.parquet"
        
        asv_df.to_parquet(asv_parquet)
        tax_df.to_parquet(tax_parquet)
        
        # Queue Celery task
        result = process_ml_features_async.delay(
            job_id=job_id,
            asv_path=str(asv_parquet),
            tax_path=str(tax_parquet),
            domain=domain,
        )
        
        logger.info(f"[{job_id}] Celery task queued: {result.id}")
    
    except Exception as e:
        logger.exception(f"[{job_id}] Background task failed: {e}")
        
        # Mark job as failed
        db = SessionLocal()
        try:
            job = db.query(MLAnalysisJob).filter_by(id=job_id).first()
            if job:
                job.status = 'FAILED'
                job.errors = str(e)
                db.commit()
        finally:
            db.close()

# ══════════════════════════════════════════════════════════════════════════════
# ROUTER REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

def register_analyze_routes(app):
    """Register analysis routes to FastAPI app."""
    app.include_router(router)
