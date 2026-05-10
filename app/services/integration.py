"""
AD-GSI v4.0 Integration Layer
==============================

Extends GenomicValidationService with Phase 4: ML Feature Generation

This module demonstrates how to integrate the ProductionPipeline into the
existing validation workflow. It serves as the bridge between the 3-tier
validation framework and the 6-phase AD-GSI bioinformatics pipeline.

USAGE:
    service = GenomicValidationServiceML(job_id, asv_path, taxonomy_path)
    
    # Run Tiers 1-3 validation as before
    report, summary = service.validate_and_preprocess()
    
    # Then run Phase 4: ML Feature Generation (async)
    success, features, audit = service.generate_ml_features_async(domain='COASTAL')
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import pandas as pd

from app.schemas.genomic import ValidationReport, ValidationLayer
from app.services.validation_service import GenomicValidationService
from app.services.production_pipeline import (
    ProductionPipeline, 
    validate_and_generate_ml_features
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION LAYER
# ══════════════════════════════════════════════════════════════════════════════

class GenomicValidationServiceML(GenomicValidationService):
    """
    Extended GenomicValidationService with ML feature generation.
    
    Workflow:
    1. Inherit Tiers 1-3 validation from parent class
    2. After successful preprocessing, option to run Phase 4
    3. Phase 4 = 6-phase AD-GSI pipeline (data defense → ML output)
    """
    
    def __init__(self, job_id: str, asv_path: str, taxonomy_path: str):
        super().__init__(job_id, asv_path, taxonomy_path)
        self.ml_features = None
        self.ml_audit = None
    
    async def validate_preprocess_and_generate_ml(
        self,
        domain: str = 'COASTAL',
        run_ml_generation: bool = True,
    ) -> tuple:
        """
        Full workflow: Tiers 1-3 + Phase 4 (ML generation).
        
        Args:
            domain: 'COASTAL' or 'SOIL' or 'FRESHWATER'
            run_ml_generation: If True, run Phase 4 after preprocessing
        
        Returns:
            (validation_report, preprocessing_summary, ml_features, ml_audit, success)
        """
        
        # Step 1: Run existing Tiers 1-3
        logger.info(f"[{self.job_id}] Starting validation + ML generation pipeline")
        report, summary = self.validate_and_preprocess()
        
        if report.status.value == 'FAILED':
            logger.error(f"[{self.job_id}] Validation failed. Skipping ML generation.")
            return report, summary, None, None, False
        
        # Step 2: Run Phase 4 (ML generation) in background
        if not run_ml_generation:
            return report, summary, None, None, True
        
        try:
            logger.info(f"[{self.job_id}] Launching Phase 4: ML Feature Generation")
            
            success, ml_features, ml_audit = await self.generate_ml_features_async(domain)
            
            if success:
                self.ml_features = ml_features
                self.ml_audit = ml_audit
                report.passed_layers.append(ValidationLayer.ML_FEATURES)
                logger.info(f"[{self.job_id}] ✓ ML generation complete: {len(ml_features)} samples")
            else:
                logger.warning(f"[{self.job_id}] ✗ ML generation failed")
            
            return report, summary, ml_features, ml_audit, success
        
        except Exception as e:
            logger.exception(f"[{self.job_id}] ML generation crashed")
            return report, summary, None, None, False
    
    async def generate_ml_features_async(
        self,
        domain: str = 'COASTAL',
    ) -> tuple[bool, list[dict], dict]:
        """
        Async wrapper for Phase 4 pipeline.
        
        Runs in background so API can return 202 Accepted immediately.
        """
        
        return await asyncio.to_thread(
            self._run_phase4_ml_generation,
            domain
        )
    
    def _run_phase4_ml_generation(
        self,
        domain: str = 'COASTAL',
    ) -> tuple[bool, list[dict], dict]:
        """
        Phase 4: Run the full 6-phase production pipeline.
        
        This assumes preprocessing has completed and parquet files exist.
        """
        
        logger.info(f"[{self.job_id}] Phase 4: ML Feature Generation (6-phase pipeline)")
        
        # Load preprocessed parquet files
        out_dir = Path(settings.TMP_UPLOAD_DIR) / self.job_id
        asv_parquet = out_dir / "asv_processed.parquet"
        tax_parquet = out_dir / "tax_processed.parquet"
        
        if not asv_parquet.exists() or not tax_parquet.exists():
            logger.error(f"[{self.job_id}] Preprocessed files not found")
            return False, [], {'status': 'ERROR', 'message': 'Missing parquet files'}
        
        # Load data
        try:
            asv_table = pd.read_parquet(asv_parquet)
            tax_table = pd.read_parquet(tax_parquet)
        except Exception as e:
            logger.error(f"[{self.job_id}] Failed to load parquet: {e}")
            return False, [], {'status': 'ERROR', 'message': str(e)}
        
        # Run pipeline
        try:
            success, ml_features, audit_report = validate_and_generate_ml_features(
                asv_table, tax_table,
                id_column='ASV_ID',
                domain=domain,
            )
            
            # Log results
            features_written = sum(len(o['features']) for o in ml_features)
            logger.info(f"[{self.job_id}] ✓ Generated {features_written} ML features across "
                       f"{len(ml_features)} samples")
            
            # Save ML features to disk for later retrieval
            ml_output_file = out_dir / "ml_features.json"
            import json
            with open(ml_output_file, 'w') as f:
                json.dump(ml_features, f, indent=2)
            
            # Save audit report
            audit_output_file = out_dir / "ml_audit.json"
            with open(audit_output_file, 'w') as f:
                json.dump(audit_report, f, indent=2)
            
            return success, ml_features, audit_report
        
        except Exception as e:
            logger.exception(f"[{self.job_id}] Phase 4 pipeline crashed")
            return False, [], {'status': 'ERROR', 'message': str(e)}

# ══════════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLES
# ══════════════════════════════════════════════════════════════════════════════

"""
EXAMPLE 1: Synchronous validation only (existing behavior)
────────────────────────────────────────────────────────────

from app.services.integration import GenomicValidationServiceML

service = GenomicValidationServiceML(
    job_id='job-123',
    asv_path='/upload/asv.csv',
    taxonomy_path='/upload/tax.csv'
)

report, summary = service.validate_and_preprocess()
print(f"Status: {report.status}")
print(f"Samples: {summary.samples_detected if summary else 'N/A'}")


EXAMPLE 2: Full pipeline synchronously (testing)
──────────────────────────────────────────────────

import asyncio

service = GenomicValidationServiceML(
    job_id='job-456',
    asv_path='/upload/asv.csv',
    taxonomy_path='/upload/tax.csv'
)

success, ml_features, audit = asyncio.run(
    service.validate_preprocess_and_generate_ml(domain='COASTAL')
)

if success:
    for sample_output in ml_features:
        print(f"Sample: {sample_output['sample_id']}")
        print(f"  Features: {len(sample_output['features'])}")
        for feature in sample_output['features'][:3]:
            print(f"    {feature['function']}: {feature['rel_abundance']:.4f}")


EXAMPLE 3: FastAPI endpoint with 202 Accepted (production)
──────────────────────────────────────────────────────────

from fastapi import BackgroundTasks
from app.services.integration import GenomicValidationServiceML

@router.post("/ingest/analyze")
async def ingest_and_analyze(
    job_id: str,
    asv_file: UploadFile,
    tax_file: UploadFile,
    background_tasks: BackgroundTasks,
):
    # Save uploaded files
    asv_path = f"/tmp/{job_id}/asv.csv"
    tax_path = f"/tmp/{job_id}/tax.csv"
    
    # [save files to disk]
    
    # Create service and add to background
    service = GenomicValidationServiceML(job_id, asv_path, tax_path)
    background_tasks.add_task(
        asyncio.run,
        service.validate_preprocess_and_generate_ml(domain='COASTAL')
    )
    
    return {
        "job_id": job_id,
        "status": "202 Accepted",
        "message": "Analysis queued. Check /status/{job_id} for results."
    }


EXAMPLE 4: Retrieve results after async completion
────────────────────────────────────────────────────

@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    # Load ML features from disk
    ml_features_file = f"/tmp/{job_id}/ml_features.json"
    
    if not Path(ml_features_file).exists():
        return {"status": "PROCESSING"}
    
    import json
    with open(ml_features_file) as f:
        ml_features = json.load(f)
    
    return {
        "job_id": job_id,
        "status": "COMPLETE",
        "ml_features": ml_features,
        "sample_count": len(ml_features)
    }
"""
