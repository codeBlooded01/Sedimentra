"""
FastAPI Routes — Genomic Data Ingestion
=======================================
POST /api/v1/ingest/upload                    — Accept paired ASV + Taxonomy CSV upload
GET  /api/v1/ingest/status/{job_id}           — Poll job status
GET  /api/v1/ingest/report/{job_id}           — Retrieve full validation report
GET  /api/v1/ingest/preprocessing/{job_id}    — Retrieve preprocessing summary
POST /api/v1/ingest/report-generate/{job_id}  — Build descriptive + diagnostic report from raw files
"""

import uuid
import aiofiles
import logging
import pandas as pd
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.db.models.upload import UploadJob
from app.schemas.genomic import (
    UploadJobResponse,
    ValidationReport,
    PreprocessingSummary,
    JobStatus,
    SampleGenus,
    SampleInput,
    AnalyzeReportResponse,
    SampleFilterAudit,
    CsvPreviewResponse,
)
from app.services.report_engine import compute_descriptive, compute_diagnostic
from app.workers.ingest_tasks import run_ingestion_pipeline

router = APIRouter(prefix="/api/v1/ingest", tags=["Genomic Ingestion"])
logger = logging.getLogger(__name__)

MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


# ══════════════════════════════════════════════════════════════════════════════
# POST /upload
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/upload", response_model=UploadJobResponse, status_code=202)
async def upload_genomic_files(
    asv_file: UploadFile = File(..., description="ASV abundance table CSV"),
    taxonomy_file: UploadFile = File(..., description="Taxonomy inventory CSV"),
    db: AsyncSession = Depends(get_db),
):
    job_id = str(uuid.uuid4())
    upload_base = Path(settings.TMP_UPLOAD_DIR) / job_id
    upload_base.mkdir(parents=True, exist_ok=True)

    asv_path = upload_base / f"asv_{asv_file.filename}"
    taxonomy_path = upload_base / f"taxonomy_{taxonomy_file.filename}"

    try:
        await _stream_upload(asv_file, asv_path)
        await _stream_upload(taxonomy_file, taxonomy_path)
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception:
        logger.exception(f"[{job_id}] File streaming failed.")
        raise HTTPException(status_code=500, detail="File upload failed. Please try again.")

    job = UploadJob(
        id=job_id,
        status=JobStatus.PENDING.value,
        asv_tmp_path=str(asv_path),
        taxonomy_tmp_path=str(taxonomy_path),
        asv_filename=asv_file.filename,
        taxonomy_filename=taxonomy_file.filename,
    )
    db.add(job)
    await db.flush()

    task = run_ingestion_pipeline.delay(job_id, str(asv_path), str(taxonomy_path))
    job.celery_task_id = task.id
    await db.commit()

    logger.info(f"[{job_id}] Files uploaded. Celery task dispatched: {task.id}")

    return UploadJobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message="Files received. Validation is running in the background.",
        created_at=job.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# GET /status/{job_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/status/{job_id}", response_model=UploadJobResponse)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _fetch_job_or_404(db, job_id)

    status_messages = {
        JobStatus.PENDING.value: "Your files are queued for validation.",
        JobStatus.VALIDATING.value: "Validating your genomic data... this may take a moment.",
        JobStatus.PREPROCESSING.value: "Validation passed! Preparing data for analysis...",
        JobStatus.READY.value: "Your data is ready. Analysis can now begin.",
        JobStatus.FAILED.value: "Validation failed. Please review the error report.",
    }

    return UploadJobResponse(
        job_id=job.id,
        status=JobStatus(job.status),
        message=status_messages.get(job.status, "Processing..."),
        created_at=job.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# GET /report/{job_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/report/{job_id}", response_model=ValidationReport)
async def get_validation_report(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _fetch_job_or_404(db, job_id)

    if not job.validation_report:
        raise HTTPException(
            status_code=404,
            detail="Validation report not yet available. Please check status first.",
        )

    return ValidationReport(**job.validation_report)


# ══════════════════════════════════════════════════════════════════════════════
# GET /preprocessing/{job_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/preprocessing/{job_id}", response_model=PreprocessingSummary)
async def get_preprocessing_summary(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _fetch_job_or_404(db, job_id)

    if job.status != JobStatus.READY.value:
        raise HTTPException(
            status_code=400,
            detail="Preprocessing summary is only available for jobs with status 'ready'.",
        )

    if not job.preprocessing_summary:
        raise HTTPException(status_code=404, detail="Preprocessing summary not found.")

    return PreprocessingSummary(**job.preprocessing_summary)


# ══════════════════════════════════════════════════════════════════════════════
# POST /report-generate/{job_id}
# Priority 1: Use preprocessed parquet files (filtered, CLR-cleaned, artifact-free)
# Priority 2: Fall back to raw CSVs for legacy jobs without parquet outputs
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/report-generate/{job_id}", response_model=AnalyzeReportResponse)
async def generate_analysis_report(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Generate descriptive and diagnostic analysis from an ingest job.

    Uses preprocessed parquet files (asv_filtered_raw.parquet + tax_processed.parquet)
    when available — these have been through the full 16-step validation pipeline:
    singleton removal, depth filtering, artifact exclusion, and CLR transformation.

    Falls back to reading raw CSVs for legacy jobs that pre-date the parquet store.
    """
    job = await _fetch_job_or_404(db, job_id)

    # ── Attempt to load from preprocessed parquet files ────────────────────────
    use_parquet = (
        job.processed_asv_path and
        job.processed_taxonomy_path and
        Path(job.processed_asv_path).exists() and
        Path(job.processed_taxonomy_path).exists()
    )

    if use_parquet:
        logger.info(f"[{job_id}] Using preprocessed parquet files for report generation.")
        try:
            asv_df = pd.read_parquet(job.processed_asv_path)
            tax_df = pd.read_parquet(job.processed_taxonomy_path)
        except Exception as e:
            logger.exception(f"[{job_id}] Failed to read parquet files, falling back to CSV.")
            use_parquet = False

    if not use_parquet:
        # ── Fallback: raw uploaded CSVs ────────────────────────────────────────
        asv_path = job.asv_tmp_path
        tax_path = job.taxonomy_tmp_path
        if not asv_path or not tax_path:
            raise HTTPException(status_code=404, detail="No data files found for this job.")
        logger.info(f"[{job_id}] Falling back to raw CSV files for report generation.")
        try:
            asv_df = pd.read_csv(asv_path)
            tax_df = pd.read_csv(tax_path)
        except Exception as e:
            logger.exception(f"[{job_id}] Failed to read CSV files for report generation.")
            raise HTTPException(status_code=500, detail=f"Could not read uploaded files: {e}")

    # ── Identify the ASV ID column ─────────────────────────────────────────────
    id_col = None
    for candidate in ["ASV_ID", "asv_id", "#OTU ID", "OTU_ID", "Feature ID"]:
        if candidate in asv_df.columns:
            id_col = candidate
            break
    if id_col is None:
        id_col = asv_df.columns[0]

    # ── Identify the genus column in taxonomy ──────────────────────────────────
    # Parquet produced by the validation pipeline always has a lowercase "genus" column.
    # Raw CSV fallback may have Genus, genus, g__, or a composite "taxonomy" string.
    genus_col = None
    for candidate in ["genus", "Genus", "g__", "genus_name"]:
        if candidate in tax_df.columns:
            genus_col = candidate
            break

    if genus_col is None and "taxonomy" in tax_df.columns:
        # Parse genus from QIIME2-style semicolon string
        def _extract_genus(tax_str: str) -> str:
            for part in str(tax_str).split(";"):
                part = part.strip()
                if part.lower().startswith("g__"):
                    return part[3:].strip() or "unclassified"
            return "unclassified"
        tax_df["_genus"] = tax_df["taxonomy"].apply(_extract_genus)
        genus_col = "_genus"

    if genus_col is None:
        raise HTTPException(
            status_code=422,
            detail="Could not find a Genus column in the taxonomy data.",
        )

    # ── Standardize the taxonomy ID column to match ASV table ─────────────────
    # Parquet always uses ASV_ID; raw CSVs may vary.
    tax_id_col = None
    for candidate in ["ASV_ID", "asv_id", "#OTU ID", "OTU_ID", "Feature ID", id_col]:
        if candidate in tax_df.columns:
            tax_id_col = candidate
            break
    if tax_id_col is None:
        tax_id_col = tax_df.columns[0]
    if tax_id_col != id_col:
        tax_df = tax_df.rename(columns={tax_id_col: id_col})

    # ── Filter taxa with NA genus (artifact of validation pipeline parsing) ─────
    # In parquet, unresolvable genera are stored as "NA" (string). Exclude them
    # from abundance calculations so they don't dilute real genus signals.
    na_mask = tax_df[genus_col].isin(["NA", "na", "", "unclassified", "Unclassified"])
    if na_mask.any():
        logger.info(f"[{job_id}] Excluding {na_mask.sum()} ASVs with unresolved genus from report.")
        # We don't drop them from tax_df here; we handle them in the merge below.

    # ── Compile Full Taxonomy Lineage ──────────────────────────────────────────
    ranks = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]
    tax_cols_lower = {str(c).lower(): c for c in tax_df.columns}
    
    lineage_series = None
    for rank in ranks:
        if rank in tax_cols_lower:
            val_series = tax_df[tax_cols_lower[rank]].fillna("unassigned").astype(str).str.lower()
        else:
            val_series = pd.Series("unassigned", index=tax_df.index)
        
        part_series = rank + ":" + val_series
        if lineage_series is None:
            lineage_series = part_series
        else:
            lineage_series = lineage_series + ";" + part_series
            
    tax_df["lineage"] = lineage_series

    # ── Merge ASV counts with taxonomy ────────────────────────────────────────
    try:
        merged = asv_df.merge(tax_df[[id_col, genus_col, "lineage"]], on=id_col, how="left")
        merged[genus_col] = merged[genus_col].fillna("unassigned")
        merged["lineage"] = merged["lineage"].fillna("")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Merge failed: {e}")

    # ── Aggregate per-sample genus-level abundances ────────────────────────────
    # Exclude "NA" and "unassigned" from abundance sums so they don't pollute
    # diversity metrics (Shannon index, dominant genus, top-10 list).
    sample_cols = [c for c in asv_df.columns if c != id_col]
    samples_input: list[SampleInput] = []
    zero_genus_samples: list[str] = []  # Track samples dropped at this stage

    EXCLUDE_GENERA = {"NA", "na", "", "unassigned", "unclassified", "Unclassified"}

    for sample_col in sample_cols:
        try:
            genus_totals = merged.groupby([genus_col, "lineage"])[sample_col].sum()
        except (KeyError, TypeError):
            zero_genus_samples.append(sample_col)
            continue

        # Drop non-informative genera before computing relative abundances
        valid_mask = ~genus_totals.index.get_level_values(0).isin(EXCLUDE_GENERA)
        genus_totals = genus_totals[valid_mask]

        total = genus_totals.sum()
        if total == 0:
            # Sample has no resolved genus signal — track it for audit transparency
            zero_genus_samples.append(sample_col)
            logger.info(f"[{job_id}] Sample '{sample_col}' excluded from report: zero genus-level abundance after filtering unresolved ASVs.")
            continue

        # [ALIGNMENT_REQUIRED] relative_abundance | target: CLR migration | status: pending | risk: compositional_bias
        genera = [
            SampleGenus(genus=str(g), abundance=round(float(v) / total, 6), lineage=str(lin))
            for (g, lin), v in genus_totals.items()
            if float(v) > 0
        ]
        samples_input.append(SampleInput(sample_id=sample_col, genera=genera))

    if not samples_input:
        raise HTTPException(
            status_code=422,
            detail="No samples with non-zero reads found after genus aggregation.",
        )

    # ── Build phylum-level aggregation for phylum-tier thresholds ─────────────
    # The original thresholds (Firmicutes, Proteobacteria, Chloroflexi, etc.) are
    # phylum-level names. They must be evaluated against phylum-summed abundances,
    # not the genus-level map. This is only possible when the parquet taxonomy
    # provides a 'phylum' column (produced by the validation pipeline rank-parser).
    phylum_abundances: dict | None = None

    if use_parquet and "phylum" in tax_df.columns:
        try:
            EXCLUDE_PHYLA = {"NA", "na", "", "unclassified", "Unclassified"}
            # Merge ASV counts with phylum column
            phylum_merged = asv_df.merge(
                tax_df[[id_col, "phylum"]], on=id_col, how="left"
            )
            phylum_merged["phylum"] = phylum_merged["phylum"].fillna("unclassified")

            phylum_abundances = {}
            for sample_col in sample_cols:
                try:
                    phy_totals = phylum_merged.groupby("phylum")[sample_col].sum()
                except (KeyError, TypeError):
                    continue
                phy_totals = phy_totals[~phy_totals.index.isin(EXCLUDE_PHYLA)]
                total = phy_totals.sum()
                if total == 0:
                    continue
                phylum_abundances[sample_col] = {
                    str(p): round(float(v) / total, 6)
                    for p, v in phy_totals.items() if float(v) > 0
                }

            logger.info(
                f"[{job_id}] Phylum-level aggregation complete: "
                f"{len(phylum_abundances)} samples, "
                f"{sum(len(v) for v in phylum_abundances.values())} total phyla."
            )
        except Exception as e:
            logger.warning(f"[{job_id}] Phylum aggregation failed, skipping phylum thresholds: {e}")
            phylum_abundances = None

    # ── Build total reads map for confidence depth scoring ────────────────────
    total_reads_map: dict[str, int] = {}
    for sample_col in sample_cols:
        try:
            total_reads_map[sample_col] = int(asv_df[sample_col].sum())
        except Exception:
            pass

    # ── Run descriptive + diagnostic engines ──────────────────────────────────
    try:
        descriptive = compute_descriptive(samples_input)
        diagnostic  = compute_diagnostic(
            samples_input,
            phylum_abundances=phylum_abundances,
            total_reads_map=total_reads_map,
        )
    except Exception as e:
        logger.exception(f"[{job_id}] Report engine failed.")
        raise HTTPException(status_code=500, detail=f"Report computation failed: {e}")

    # ── Build transparent sample filter audit ─────────────────────────────────
    # Pull preprocessing-level drops (Step 2 low-depth, Step 10 empty-after-filter)
    # from the stored preprocessing_summary, then add report-level drops (zero genus).
    low_depth_removed: list[str] = []
    empty_after_filter: list[str] = []
    min_depth_threshold = 1000  # default — overwritten from stored summary if available

    if job.preprocessing_summary:
        prep = job.preprocessing_summary
        low_depth_removed  = prep.get("low_depth_samples_removed", [])
        empty_after_filter = prep.get("empty_samples_removed", [])
        min_depth_threshold = (
            prep.get("thresholds_used", {}).get("min_sample_depth", 1000)
        )

    all_submitted = [
        c for c in [c for c in asv_df.columns if c != id_col]
        # Re-derive original sample columns from raw ASV before parquet trimming
    ]
    # "all_submitted" here is sample_cols (columns present in the preprocessed parquet).
    # Samples removed in Step 2 / Step 10 are already absent from asv_df at this point.
    # Their names come from the preprocessing_summary stored in the job.
    total_submitted = len(sample_cols) + len(low_depth_removed) + len(empty_after_filter)
    total_dropped   = len(low_depth_removed) + len(empty_after_filter) + len(zero_genus_samples)

    filter_audit = SampleFilterAudit(
        samples_submitted=total_submitted,
        samples_retained=len(samples_input),
        samples_dropped=total_dropped,
        low_depth_samples_removed=low_depth_removed,
        empty_after_filter_samples=empty_after_filter,
        zero_genus_abundance_samples=zero_genus_samples,
        min_depth_threshold_used=min_depth_threshold,
    )

    source = "parquet (preprocessed)" if use_parquet else "csv (raw fallback)"
    logger.info(
        f"[{job_id}] Report generated from {source}. "
        f"{len(samples_input)}/{total_submitted} samples retained. "
        f"Dropped — low_depth: {len(low_depth_removed)}, "
        f"empty_after_filter: {len(empty_after_filter)}, "
        f"zero_genus: {len(zero_genus_samples)}."
    )

    return AnalyzeReportResponse(
        descriptive=descriptive,
        diagnostic=diagnostic,
        sample_filter_audit=filter_audit,
    )


# ══════════════════════════════════════════════════════════════════════════════
# GET /preview/asv/{job_id} & /preview/taxonomy/{job_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/preview/asv/{job_id}", response_model=CsvPreviewResponse)
async def preview_asv(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _fetch_job_or_404(db, job_id)
    if not job.asv_tmp_path:
        raise HTTPException(status_code=404, detail="ASV file not found.")
    
    try:
        df = pd.read_csv(job.asv_tmp_path)
        df.fillna("NaN", inplace=True)
        return CsvPreviewResponse(
            columns=df.columns.tolist(),
            rows=df.to_dict(orient="records")
        )
    except Exception as e:
        logger.exception(f"[{job_id}] Failed to read ASV preview.")
        raise HTTPException(status_code=500, detail=f"Could not read ASV file: {e}")

@router.get("/preview/taxonomy/{job_id}", response_model=CsvPreviewResponse)
async def preview_taxonomy(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _fetch_job_or_404(db, job_id)
    if not job.taxonomy_tmp_path:
        raise HTTPException(status_code=404, detail="Taxonomy file not found.")
    
    try:
        df = pd.read_csv(job.taxonomy_tmp_path)
        df.fillna("NaN", inplace=True)
        return CsvPreviewResponse(
            columns=df.columns.tolist(),
            rows=df.to_dict(orient="records")
        )
    except Exception as e:
        logger.exception(f"[{job_id}] Failed to read Taxonomy preview.")
        raise HTTPException(status_code=500, detail=f"Could not read Taxonomy file: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

async def _stream_upload(upload_file: UploadFile, dest_path: Path):
    total = 0
    async with aiofiles.open(dest_path, "wb") as out_file:
        while chunk := await upload_file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_BYTES:
                raise ValueError(
                    f"File '{upload_file.filename}' exceeds the maximum allowed size "
                    f"of {settings.MAX_UPLOAD_SIZE_MB}MB."
                )
            await out_file.write(chunk)


async def _fetch_job_or_404(db: AsyncSession, job_id: str) -> UploadJob:
    result = await db.execute(select(UploadJob).where(UploadJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job
