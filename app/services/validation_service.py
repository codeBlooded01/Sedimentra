import logging
import re
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import variation as scipy_variation
from skbio.stats.composition import clr as skbio_clr

from app.schemas.genomic import (
    ValidationReport,
    ValidationError,
    ValidationWarning,
    ValidationLayer,
    JobStatus,
    PreprocessingSummary,
    AsvFilterSummary,
    FilterThresholds,
    LibrarySizeStats,
    DisturbanceTrackSummary,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class GenomicValidationService:

    def __init__(self, job_id: str, asv_path: str, taxonomy_path: str):
        self.job_id        = job_id
        self.asv_path      = Path(asv_path)
        self.taxonomy_path = Path(taxonomy_path)

        self.report = ValidationReport(
            job_id=job_id,
            status=JobStatus.VALIDATING,
        )

        self.asv_df = None
        self.tax_df = None

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _add_error(self, layer: ValidationLayer, code: str,
                   user_message: str, detail: str = None):
        self.report.errors.append(ValidationError(
            layer=layer,
            code=code,
            user_message=user_message,
            technical_detail=detail
        ))

    def _warn(self, step: int, code: str, message: str):
        """Typed warning — keeps call sites clean and schema-aligned."""
        self.report.warnings.append(
            ValidationWarning(step=step, code=code, message=message)
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ORCHESTRATOR
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def validate_and_preprocess(
        self,
    ) -> tuple[ValidationReport, PreprocessingSummary | None]:

        logger.info(f"[{self.job_id}] Starting validation pipeline.")

        try:
            if not self._run_tier_1_structural():
                self.report.status = JobStatus.FAILED
                return self.report, None
            self.report.passed_layers.append(ValidationLayer.STRUCTURAL)

            if not self._run_tier_2_schema():
                self.report.status = JobStatus.FAILED
                return self.report, None
            self.report.passed_layers.append(ValidationLayer.SCHEMA)

            if not self._run_tier_3_relational():
                self.report.status = JobStatus.FAILED
                return self.report, None
            self.report.passed_layers.append(ValidationLayer.RELATIONAL)

            self.report.status = JobStatus.PREPROCESSING
            summary = self._preprocess_and_save()
            
            self.report.status = JobStatus.READY
            self.report.passed_layers.append(ValidationLayer.PREPROCESSING)
            return self.report, summary
            
        except Exception as e:
            logger.exception(f"[{self.job_id}] Pipeline crashed unexpectedly")
            
            current_layer = ValidationLayer.STRUCTURAL
            if len(self.report.passed_layers) == 1:
                current_layer = ValidationLayer.SCHEMA
            elif len(self.report.passed_layers) == 2:
                current_layer = ValidationLayer.RELATIONAL
            elif len(self.report.passed_layers) >= 3:
                current_layer = ValidationLayer.PREPROCESSING
                
            self._add_error(
                current_layer,
                "unexpected_crash",
                "An unexpected system error occurred while processing the file. Please ensure your file strictly matches the standard format and layout.",
                str(e)
            )
            self.report.status = JobStatus.FAILED
            return self.report, None

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TIER 1 — STRUCTURAL
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _run_tier_1_structural(self) -> bool:
        """Parses CSV files. Catches pd.errors.ParserError for corruption."""
        logger.info(f"[{self.job_id}] Tier 1: Structural Validation")

        try:
            self.asv_df = pd.read_csv(self.asv_path)
        except pd.errors.ParserError as e:
            self._add_error(
                ValidationLayer.STRUCTURAL, "asv_parse_error",
                "Incorrect file format. Please upload the structured .csv "
                "file provided by the lab.", str(e)
            )
            return False

        try:
            self.tax_df = pd.read_csv(self.taxonomy_path)
        except pd.errors.ParserError as e:
            self._add_error(
                ValidationLayer.STRUCTURAL, "tax_parse_error",
                "The taxonomy file format is invalid. Ensure it is a valid CSV.",
                str(e)
            )
            return False

        return True

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TIER 2 — SCHEMA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _run_tier_2_schema(self) -> bool:
        """
        ID normalisation, sample detection, taxonomy parsing,
        and taxonomy quality assessment (FAPROTAX guard).

        Taxonomy quality check rationale:
          FAPROTAX functional mapping depends on genus-level assignments.
          If > 40% of ASVs lack genus, the functional predictions become
          statistically unreliable. Flag early so the researcher can
          re-run DADA2 with a higher-resolution reference before investing
          compute time in downstream modelling.
        """
        logger.info(f"[{self.job_id}] Tier 2: Schema Hardening & ID Normalisation")

        # ── ID normalisation ───────────────────────────────────────────────────
        self.asv_df.rename(
            columns={self.asv_df.columns[0]: 'ASV_ID'}, inplace=True
        )
        self.tax_df.rename(
            columns={self.tax_df.columns[0]: 'ASV_ID'}, inplace=True
        )

        self.asv_df['ASV_ID'] = (
            self.asv_df['ASV_ID'].astype(str).str.strip().str.lower()
        )
        self.tax_df['ASV_ID'] = (
            self.tax_df['ASV_ID'].astype(str).str.strip().str.lower()
        )

        # ── Sample column detection ────────────────────────────────────────────
        potential_samples   = [c for c in self.asv_df.columns if c != 'ASV_ID']
        self.sample_columns = []

        for col in potential_samples:
            converted     = pd.to_numeric(self.asv_df[col], errors='coerce')
            missing_ratio = converted.isna().mean()

            if missing_ratio < 0.5:
                self.sample_columns.append(col)
                if missing_ratio > 0:
                    self._warn(2, "non_numeric_coerced",
                        f"Sample '{col}' had {int(missing_ratio*100)}% "
                        "non-numeric values coerced to 0.")
            else:
                self._warn(2, "metadata_column_excluded",
                    f"Column '{col}' excluded from analysis "
                    "(detected as metadata/text).")

            self.asv_df[col] = converted.fillna(0)

        # ── Taxonomy parsing ───────────────────────────────────────────────────
        tax_cols       = [c for c in self.tax_df.columns if c != 'ASV_ID']
        expected_ranks = {
            'kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species'
        }

        if len(tax_cols) != 1:
            if not expected_ranks.issubset(
                set(c.lower() for c in self.tax_df.columns)
            ):
                self._warn(2, "taxonomy_format_ambiguous",
                    "Taxonomy format ambiguous and missing standard ranks.")
        else:
            tax_str_col = tax_cols[0]

            def parse_rank(tax_str):
                ranks = {r: "NA" for r in [
                    'kingdom', 'phylum', 'class', 'order',
                    'family', 'genus', 'species'
                ]}
                if pd.isna(tax_str):
                    return pd.Series(ranks)
                parts = re.split(r'[;,:]', str(tax_str))
                prefix_map = {
                    'k__': 'kingdom', 'p__': 'phylum', 'c__': 'class',
                    'o__': 'order',   'f__': 'family', 'g__': 'genus',
                    's__': 'species'
                }
                for part in parts:
                    part = part.strip()
                    for p, r in prefix_map.items():
                        if part.lower().startswith(p):
                            val = part[len(p):].strip()
                            ranks[r] = val if val else "NA"
                return pd.Series(ranks)

            parsed_tax = self.tax_df[tax_str_col].apply(parse_rank)
            self.tax_df = pd.concat(
                [self.tax_df[['ASV_ID']], parsed_tax], axis=1
            )

        # ── Taxonomy quality assessment — FAPROTAX guard ───────────────────────
        tax_rank_cols  = [
            'kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species'
        ]
        existing_ranks = [r for r in tax_rank_cols if r in self.tax_df.columns]

        if existing_ranks:
            na_rates        = (self.tax_df[existing_ranks] == 'NA').mean()
            genus_na_rate   = float(na_rates.get('genus',   1.0))
            species_na_rate = float(na_rates.get('species', 1.0))

            if genus_na_rate > 0.40:
                self._warn(2, "low_taxonomy_resolution",
                    f"{genus_na_rate*100:.0f}% of ASVs have no genus assignment. "
                    "FAPROTAX functional mapping will be severely limited. "
                    "Consider re-running DADA2 with a higher-resolution reference "
                    "database (e.g. SILVA 138 instead of SILVA 132).")

            if species_na_rate > 0.60:
                self._warn(2, "low_species_resolution",
                    f"{species_na_rate*100:.0f}% of ASVs lack species-level "
                    "assignment. Predictive disturbance models relying on "
                    "species identity will have reduced resolution.")

        return True

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TIER 3 — RELATIONAL & DOMAIN SANITY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _run_tier_3_relational(self) -> bool:
        """
        ASV↔taxonomy mapping check and tiered sparsity assessment.

        Sparsity tiers are calibrated for coastal sediment metagenomes,
        which are naturally sparser than gut microbiome datasets:
          > 90% → elevated   (normal for sediment, monitor)
          > 95% → high       (PCA stability at risk)
          > 98% → critical   (borderline failure, warn strongly)
          > 99% → HARD FAIL  (statistically unusable)
        """
        logger.info(f"[{self.job_id}] Tier 3: Relational Validation")

        # ── Orphan ASV check ───────────────────────────────────────────────────
        asv_set  = set(self.asv_df['ASV_ID'].astype(str))
        tax_set  = set(self.tax_df['ASV_ID'].astype(str))
        orphaned = asv_set - tax_set

        if orphaned:
            self._add_error(
                ValidationLayer.RELATIONAL, "orphan_asv",
                f"Mismatch detected: {len(orphaned)} ASVs have no taxonomy "
                "entries. Please check your inventory file.",
                f"Orphaned IDs sample: {list(orphaned)[:5]}"
            )
            return False

        # ── Tiered sparsity assessment ─────────────────────────────────────────
        numerical_data = self.asv_df[self.sample_columns]
        zeros          = (numerical_data <= 0).sum().sum()
        total_cells    = numerical_data.size
        sparsity       = zeros / total_cells if total_cells > 0 else 1.0

        if sparsity > 0.99:
            self._add_error(
                ValidationLayer.RELATIONAL, "extreme_sparsity",
                "Over 99% of the ASV table is zeros. "
                "This dataset is statistically unusable for CLR or PCA.",
                f"Sparsity: {sparsity*100:.2f}%"
            )
            return False
        elif sparsity > 0.98:
            self._warn(3, "critical_sparsity",
                f"Sparsity at {sparsity*100:.1f}%. CLR and PCA results will be "
                "highly unstable. Consider loosening upstream DADA2 parameters "
                "or increasing sequencing depth.")
        elif sparsity > 0.95:
            self._warn(3, "high_sparsity",
                f"Sparsity at {sparsity*100:.1f}%. PCA clustering may be "
                "unreliable. Flag for manual review before reporting results.")
        elif sparsity > 0.90:
            self._warn(3, "elevated_sparsity",
                f"Sparsity at {sparsity*100:.1f}%. Normal for coastal sediment "
                "metagenomes. Monitor downstream ordination stability.")

        return True

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PREPROCESSING / NORMALISATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _preprocess_and_save(self) -> PreprocessingSummary:
        """
        Dual-Track Preprocessing Pipeline.

        Data orientation:
          asv_df shape: (n_asvs, n_samples)
          ASVs are ROWS  → feature-wise operations use axis=1
          Samples are COLUMNS → sample-wise operations use axis=0

        Track A — Core microbiome (strict AND logic):
          Prevalence AND mean abundance AND total reads must all pass.
          → CLR transformation → asv_clr.parquet
          → Feeds PCA, clustering, ML regression.
          → Provides stable reference frame for imbalance detection.

        Track B — Disturbance-sensitive layer (selective OR bypass):
          Guardrails: prevalence AND total reads (non-negotiable).
          Bypass: mean OR relative-peak OR CV — any one sufficient.
          → Raw counts only. NO CLR.
          → Feeds imbalance scoring, anomaly detection, early warning.
          → CLR intentionally omitted: disturbance signals (spikes, shifts)
            live in count space; CLR compresses exactly the variance Track B
            is designed to preserve.

        CLR axis contract:
          axis=0 centers each COLUMN (sample) by its log-geometric-mean.
          axis=1 would be Z-scoring across samples — NOT CLR.

        Imbalance score formula (per sample s):
          richness_ratio(s) = disturbance_only_richness(s) / core_richness(s)
          spike_count(s)    = Track B-only ASVs with rel. abundance >= PEAK_REL
          cv_inflation(s)   = mean CV of Track B-only ASVs
                              / (mean CV of Track A ASVs + ε)

          imbalance_score(s) = W1 * richness_ratio
                             + W2 * log1p(spike_count)
                             + W3 * cv_inflation

        Steps:
           1.   Negative count guard
           2.   Sample depth removal + column list update
           3.   DataFrame column sync
           4.   Single-sample guard
           5.   Prevalence mask
           6.   Mean abundance mask
           7.   Rare-feature mask
           8.   Track A combined mask + high-removal warning + audit trail
           8B.  Track B disturbance mask + disturbance output files
           9.   Pre-CLR zero-variance feature removal  (ddof=0, axis=1, tol=1e-9)
          10.   All-zero column guard
          11.   Library size reporting
          11B.  Compositional dominance check           (pre-CLR guard)
          12.   Taxonomy alignment — first pass
          13.   CLR transformation                      (clip→log→center, axis=0)
          14.   Post-CLR zero-variance feature removal  (ddof=0, axis=1, tol=1e-9)
          15.   Final taxonomy re-sync
          16.   CLR centering assertion
          17.   Persistence — single .copy()
          17B.  Imbalance score computation
        """
        logger.info(f"[{self.job_id}] Executing Preprocessing Pipeline")
        out_dir = Path(settings.TMP_UPLOAD_DIR) / self.job_id
        out_dir.mkdir(parents=True, exist_ok=True)

        asv_count_before        = len(self.asv_df)
        original_sample_columns = list(self.sample_columns)

        # Defaults — overwritten by their respective steps if triggered
        empty_samples       = []
        n_flat_pre          = 0
        n_flat_post         = 0
        disturbance_summary = None
        disturbance_ids     = set()
        disturbance_df      = pd.DataFrame()
        imbalance_score_range = None

        # ── 1. NEGATIVE COUNT GUARD ────────────────────────────────────────────
        # Raw sequencing counts are non-negative integers by definition.
        # Negative values indicate pre-normalised or log-transformed input,
        # which renders the +0.5 pseudocount and CLR interpretation invalid.
        if (self.asv_df[self.sample_columns] < 0).any().any():
            self._add_error(
                ValidationLayer.PREPROCESSING, "negative_counts",
                "Negative values detected. Input must be raw, non-negative "
                "abundance counts. Pre-normalised data is incompatible with CLR.",
                "Verify the table has not been rarefied or log-transformed."
            )
            raise ValueError("Negative counts are incompatible with CLR.")

        # ── 2. SAMPLE DEPTH REMOVAL ────────────────────────────────────────────
        MIN_SAMPLE_DEPTH = getattr(settings, "MIN_SAMPLE_DEPTH", 1_000)
        sample_sums      = self.asv_df[self.sample_columns].sum(axis=0)
        failed_samples   = sample_sums[
            sample_sums < MIN_SAMPLE_DEPTH
        ].index.tolist()

        if failed_samples:
            self._warn(2, "low_depth_samples",
                f"Removed {len(failed_samples)} low-depth sample(s) "
                f"(< {MIN_SAMPLE_DEPTH} reads): {failed_samples}. "
                "Insufficient depth makes CLR geometry unreliable.")
            self.sample_columns = [
                c for c in self.sample_columns if c not in failed_samples
            ]

        # ── 3. DATAFRAME COLUMN SYNC ───────────────────────────────────────────
        # No .copy() — single authorised copy is at Step 17.
        self.asv_df = self.asv_df[['ASV_ID'] + self.sample_columns]

        # ── 4. SINGLE-SAMPLE GUARD ─────────────────────────────────────────────
        if len(self.sample_columns) < 2:
            self._add_error(
                ValidationLayer.PREPROCESSING, "insufficient_samples",
                "At least 2 samples are required for CLR transformation.",
                f"Samples remaining after depth filter: {self.sample_columns}"
            )
            raise ValueError("CLR requires >= 2 samples.")

        num_samples = len(self.sample_columns)

        # ── 5. PREVALENCE MASK ─────────────────────────────────────────────────
        PREVALENCE_THRESHOLD = getattr(settings, "PREVALENCE_THRESHOLD", 0.10)
        thresh_prev = max(1, int(np.ceil(PREVALENCE_THRESHOLD * num_samples)))
        prevalence  = (self.asv_df[self.sample_columns] > 0).sum(axis=1)
        mask_prev   = prevalence >= thresh_prev

        # ── 6. MEAN ABUNDANCE MASK ─────────────────────────────────────────────
        # Mean computed across ALL samples including zeros — intentionally strict.
        # An ASV with mean < 1.0 contributes less than one read per sample on
        # average and is indistinguishable from sequencing noise at this scale.
        # Configurable via settings.MIN_MEAN_ABUNDANCE for per-study tuning.
        MIN_MEAN_ABUNDANCE = getattr(settings, "MIN_MEAN_ABUNDANCE", 1.0)
        mean_abundance     = self.asv_df[self.sample_columns].mean(axis=1)
        mask_abund         = mean_abundance >= MIN_MEAN_ABUNDANCE

        # ── 7. RARE-FEATURE MASK ───────────────────────────────────────────────
        # Absolute floor: catches edge cases where 2-sample datasets pass the
        # mean filter (mean = 1.0, total = 2) but are still noise.
        MIN_TOTAL_READS = getattr(settings, "MIN_TOTAL_READS", 10)
        total_reads     = self.asv_df[self.sample_columns].sum(axis=1)
        mask_total      = total_reads >= MIN_TOTAL_READS

        # ── 8. TRACK A — STRICT COMBINED MASK + AUDIT TRAIL ───────────────────
        # All three conditions AND-ed: the strictest standard for stable analysis.
        combined_mask = mask_prev & mask_abund & mask_total

        n_prev  = int((~mask_prev).sum())
        n_abund = int((mask_prev & ~mask_abund).sum())
        n_rare  = int((mask_prev & mask_abund & ~mask_total).sum())

        # High-removal warning: near-empty core is a silent risk
        pct_removed = (~combined_mask).sum() / len(combined_mask)
        if pct_removed > 0.80:
            self._warn(8, "aggressive_filtering",
                f"{pct_removed*100:.0f}% of ASVs removed by Track A filters. "
                "Risk: near-empty core microbiome. "
                "Consider lowering MIN_MEAN_ABUNDANCE or PREVALENCE_THRESHOLD "
                "in settings for this dataset.")

        self._warn(8, "asv_filter_summary",
            f"Track A filter summary — "
            f"Prevalence (< {PREVALENCE_THRESHOLD*100:.0f}%): {n_prev} removed | "
            f"Mean abundance (< {MIN_MEAN_ABUNDANCE}): {n_abund} removed | "
            f"Rare-feature floor (< {MIN_TOTAL_READS} reads): {n_rare} removed.")

        # Audit trail — identities, not just counts.
        # Answers: "Which taxa did you remove and why?"
        dropped_mask = ~combined_mask
        if dropped_mask.any():
            dropped_df = self.asv_df[dropped_mask][['ASV_ID']].copy()
            dropped_df['failed_prevalence']  = (~mask_prev[dropped_mask]).values
            dropped_df['failed_mean_abund']  = (~mask_abund[dropped_mask]).values
            dropped_df['failed_total_reads'] = (~mask_total[dropped_mask]).values
            dropped_df['mean_abundance']     = mean_abundance[dropped_mask].values
            dropped_df['prevalence_count']   = prevalence[dropped_mask].values
            dropped_df['total_reads']        = total_reads[dropped_mask].values
            dropped_df.to_parquet(
                out_dir / "dropped_asvs.parquet", index=False
            )

        # ── 8B. TRACK B — DISTURBANCE-SENSITIVE LAYER ─────────────────────────
        # Guardrails (prevalence + total reads) are non-negotiable.
        # They block sequencing artifacts regardless of biological signal strength.
        # rare ≠ meaningful; rare + unsupported = noise.
        #
        # Bypass conditions (any one sufficient to survive):
        #   mean     — consistent low-level signal
        #   peak_rel — relative bloom spike in at least one sample
        #   cv       — high coefficient of variation (community instability)
        #
        # Peak uses RELATIVE abundance (not absolute reads) so it is
        # scale-independent: 1% of a 1,000-read sample and 1% of a
        # 100,000-read sample are treated identically.
        #
        # CV is computed on relative abundance (not raw counts) so it measures
        # proportional fluctuation, not sequencing depth variation.
        ENABLE_DISTURBANCE_TRACK = getattr(
            settings, "ENABLE_DISTURBANCE_TRACK", True
        )
        PEAK_REL_THRESHOLD = getattr(settings, "PEAK_REL_THRESHOLD", 0.01)  # 1%
        CV_THRESHOLD       = getattr(settings, "CV_THRESHOLD", 0.50)        # 50%

        # Pre-compute relative abundance — reused by Track B, dominance check,
        # and reporting
        sample_col_sums  = self.asv_df[self.sample_columns].sum(axis=0)
        relative_counts  = self.asv_df[self.sample_columns].div(
            sample_col_sums, axis=1
        )

        # Replacing Rel. CV with CLR-based Aitchison variance for filtering
        local_mat = self.asv_df[self.sample_columns].to_numpy(dtype=float)
        local_mat = np.clip(local_mat + 1.0, a_min=1e-12, a_max=None)
        local_clr = skbio_clr(local_mat.T).T
        clr_dispersion = pd.Series(local_clr.var(axis=1, ddof=0), index=self.asv_df['ASV_ID'].values)

        if ENABLE_DISTURBANCE_TRACK:
            # Relative peak: max relative abundance across all samples per ASV
            peak_relative = relative_counts.max(axis=1)
            mask_peak     = peak_relative >= PEAK_REL_THRESHOLD
            
            # Use CLR dispersion explicitly instead of relative CV
            CLR_DISP_THRESHOLD = getattr(settings, "CLR_DISPERSION_THRESHOLD", 2.0)
            mask_variance = clr_dispersion.values >= CLR_DISP_THRESHOLD

            bypass_mask = mask_abund | mask_peak | mask_variance
            db_combined = mask_prev & mask_total & bypass_mask

            disturbance_df = self.asv_df[db_combined].reset_index(drop=True)

            # Mutually exclusive breakdown — peak takes priority
            survived_peak      = int((db_combined & mask_peak).sum())
            survived_var_only  = int(
                (db_combined & ~mask_peak & mask_variance).sum()
            )
            survived_mean_only = int(
                (db_combined & ~mask_peak & ~mask_variance & mask_abund).sum()
            )

            core_ids        = set(self.asv_df[combined_mask]['ASV_ID'])
            disturbance_ids = set(disturbance_df['ASV_ID'])

            self._warn(8, "disturbance_track_summary",
                f"Track B (disturbance layer): {len(disturbance_df)} ASVs retained. "
                f"Disturbance-only (not in core): "
                f"{len(disturbance_ids - core_ids)} | "
                f"Shared with core: {len(disturbance_ids & core_ids)} | "
                f"Bypass — Peak: {survived_peak} | "
                f"Variance-only: {survived_var_only} | "
                f"Mean-only: {survived_mean_only}.")

            disturbance_summary = DisturbanceTrackSummary(
                asv_count=len(disturbance_df),
                asv_count_core_only=len(core_ids - disturbance_ids),
                asv_count_disturbance_only=len(disturbance_ids - core_ids),
                asv_count_shared=len(disturbance_ids & core_ids),
                peak_rel_threshold_used=float(PEAK_REL_THRESHOLD),
                cv_threshold_used=float(CLR_DISP_THRESHOLD),
                bypass_breakdown={
                    "peak":          survived_peak,
                    "variance_only": survived_var_only,
                    "mean_only":     survived_mean_only,
                }
            )

            # Sync Track B taxonomy independently of Track A
            db_tax = self.tax_df[
                self.tax_df['ASV_ID'].isin(disturbance_ids)
            ].reset_index(drop=True)

            disturbance_df.to_parquet(
                out_dir / "asv_disturbance.parquet", index=False
            )
            db_tax.to_parquet(
                out_dir / "tax_disturbance.parquet", index=False
            )

        # ── Apply Track A mask ─────────────────────────────────────────────────
        self.asv_df = self.asv_df[combined_mask].reset_index(drop=True)

        if self.asv_df.empty:
            self._add_error(
                ValidationLayer.PREPROCESSING, "empty_after_filter",
                "All ASVs were removed during quality filtering. "
                "Your dataset may be too sparse or sequencing depth too low.",
                f"Thresholds — Prevalence >= {thresh_prev}/{num_samples} | "
                f"Mean >= {MIN_MEAN_ABUNDANCE} | Total >= {MIN_TOTAL_READS}."
            )
            raise ValueError("Empty dataset after combined ASV filtering.")

        # ── 9. PRE-CLR ZERO-VARIANCE FEATURE REMOVAL ──────────────────────────
        # ddof=0: population variance — sklearn-consistent; avoids NaN on
        # single-row edge cases where ddof=1 divides by zero.
        # axis=1: variance per ASV across samples (ASVs are rows).
        # tol=1e-9: floating-point equality to zero is numerically unreliable.
        feature_var   = self.asv_df[self.sample_columns].var(axis=1, ddof=0)
        flat_pre_mask = feature_var > 1e-9
        n_flat_pre    = int((~flat_pre_mask).sum())

        if n_flat_pre > 0:
            self._warn(9, "zero_variance_pre_clr",
                f"{n_flat_pre} zero-variance ASV(s) removed before CLR "
                "(identical raw count across all retained samples).")
            self.asv_df = self.asv_df[flat_pre_mask].reset_index(drop=True)

        # ── 10. ALL-ZERO COLUMN GUARD ──────────────────────────────────────────
        # A sample that cleared depth check can become all-zero if all its
        # ASVs were filtered. Explicit removal is safer than silently patching.
        sample_sums_post = self.asv_df[self.sample_columns].sum(axis=0)
        empty_samples    = sample_sums_post[
            sample_sums_post == 0
        ].index.tolist()

        if empty_samples:
            self._warn(10, "empty_samples_post_filter",
                f"{len(empty_samples)} sample(s) became all-zero after ASV "
                f"filtering and were dropped: {empty_samples}.")
            self.sample_columns = [
                c for c in self.sample_columns if c not in empty_samples
            ]
            self.asv_df = self.asv_df[['ASV_ID'] + self.sample_columns]
            num_samples = len(self.sample_columns)

            if num_samples < 2:
                self._add_error(
                    ValidationLayer.PREPROCESSING,
                    "insufficient_samples_post_asv_filter",
                    "Fewer than 2 samples remain after removing empty columns.",
                    f"Surviving samples: {self.sample_columns}"
                )
                raise ValueError(
                    "CLR requires >= 2 samples after all-zero column removal."
                )

        # ── 11. LIBRARY SIZE REPORTING ─────────────────────────────────────────
        sample_sums_final = self.asv_df[self.sample_columns].sum(axis=0)
        self._warn(11, "library_size_stats",
            f"Final library size — "
            f"Min: {int(sample_sums_final.min())} | "
            f"Median: {int(sample_sums_final.median())} | "
            f"Max: {int(sample_sums_final.max())} reads.")

        # ── 11B. COMPOSITIONAL DOMINANCE CHECK ────────────────────────────────
        # If one ASV accounts for > 80% of a sample's reads, CLR will
        # mathematically suppress every other feature in that sample.
        # The resulting imbalance score would be a math artefact, not biology.
        # Flag BEFORE CLR runs — not after — so the researcher can verify
        # whether this is a contamination event or a genuine bloom.
        DOMINANCE_THRESHOLD = getattr(settings, "DOMINANCE_THRESHOLD", 0.80)
        rel_abund_final     = self.asv_df[self.sample_columns].div(
            sample_sums_final, axis=1
        )
        sample_dominance    = rel_abund_final.max(axis=0)
        dominated_samples   = sample_dominance[
            sample_dominance > DOMINANCE_THRESHOLD
        ].index.tolist()

        if dominated_samples:
            self._warn(11, "compositional_dominance",
                f"{len(dominated_samples)} sample(s) dominated "
                f"(> {int(DOMINANCE_THRESHOLD*100)}%) by a single ASV: "
                f"{dominated_samples}. CLR distances for these samples may "
                "reflect mathematical compression rather than biological signal. "
                "Verify these are not contamination or bloom artefacts before "
                "reporting imbalance scores.")

        # ── 12. TAXONOMY ALIGNMENT — FIRST PASS ───────────────────────────────
        # Second sync follows at Step 15 because post-CLR variance removal
        # (Step 14) may further reduce the ASV set.
        filtered_ids = set(self.asv_df['ASV_ID'])
        self.tax_df  = self.tax_df[
            self.tax_df['ASV_ID'].isin(filtered_ids)
        ].reset_index(drop=True)

        if self.tax_df['ASV_ID'].nunique() != len(self.tax_df):
            self._warn(12, "duplicate_taxonomy_ids",
                f"Duplicate ASV_IDs in taxonomy after alignment. "
                f"Rows: {len(self.tax_df)}, unique IDs: "
                f"{self.tax_df['ASV_ID'].nunique()}. "
                "Downstream joins may produce duplicate rows.")

        if self.tax_df.empty:
            self._warn(12, "taxonomy_sync_failed",
                "Taxonomy sync failed — no matching IDs after filtering.")

        # ── 13. CLR TRANSFORMATION ─────────────────────────────────────────────
        # skbio.stats.composition.clr implements the Aitchison (1986) CLR.
        # It treats each ROW as a composition (sample), so we transpose the
        # (ASVs × Samples) matrix before calling and transpose back after.
        #
        # Pseudocount: +0.5 on raw integer counts (Laplace prior), uniform across
        # all samples so the additive constant is symmetric and CLR comparability
        # is preserved.  np.clip safety-belt after pseudocount addition.
        PSEUDOCOUNT = getattr(settings, "CLR_PSEUDOCOUNT", 0.5)

        mat = self.asv_df[self.sample_columns].to_numpy(dtype=float)
        mat = np.clip(mat + PSEUDOCOUNT, a_min=1e-12, a_max=None)

        # Transpose: (ASVs × Samples) → (Samples × ASVs) so skbio_clr centers
        # each SAMPLE (row) by its own log-geometric-mean, then transpose back.
        clr_mat = skbio_clr(mat.T).T

        # ── 14. POST-CLR ZERO-VARIANCE FEATURE REMOVAL ────────────────────────
        # Catches ASVs variable in raw counts but flat in log-ratio space —
        # invisible before the log transform runs.
        # Same ddof and tol as Step 9 for consistency.
        clr_var        = clr_mat.var(axis=1, ddof=0)
        flat_post_mask = clr_var > 1e-9
        n_flat_post    = int((~flat_post_mask).sum())

        if n_flat_post > 0:
            self._warn(14, "zero_variance_post_clr",
                f"{n_flat_post} ASV(s) became zero-variance after CLR and "
                "were removed (constant relative abundance across all samples).")
            self.asv_df = self.asv_df[flat_post_mask].reset_index(drop=True)
            clr_mat     = clr_mat[flat_post_mask]

        # ── 15. FINAL TAXONOMY RE-SYNC ─────────────────────────────────────────
        # Step 14 may have reduced the ASV set. The Step 12 sync is now stale.
        # Without this, tax_df has more rows than asv_df, breaking genus
        # collapse, FAPROTAX mapping, and every downstream join.
        final_ids   = set(self.asv_df['ASV_ID'])
        self.tax_df = self.tax_df[
            self.tax_df['ASV_ID'].isin(final_ids)
        ].reset_index(drop=True)

        # ── 16. CLR CENTERING ASSERTION ────────────────────────────────────────
        # Defining property of CLR: every sample column must sum to zero in
        # log-ratio space. Failure means the transformation is corrupt and all
        # downstream ordination is invalid. atol=1e-10 absorbs float accumulation.
        sample_means = np.mean(clr_mat, axis=0)
        if not np.allclose(sample_means, 0, atol=1e-10):
            logger.error(
                f"[{self.job_id}] CLR centering failure — sample means != 0 "
                f"(max deviation: {np.abs(sample_means).max():.2e}). "
                "Downstream ordination results will be invalid."
            )

        # ── 17. PERSISTENCE — SINGLE .copy() ──────────────────────────────────
        self.asv_df.to_parquet(
            out_dir / "asv_filtered_raw.parquet", index=False
        )

        clr_df = self.asv_df.copy()
        clr_df[self.sample_columns] = clr_mat
        clr_df.to_parquet(out_dir / "asv_clr.parquet", index=False)

        self.tax_df.to_parquet(out_dir / "tax_processed.parquet", index=False)

        # ── 17B. INDEPENDENT DISPERSION SCORE COMPUTATION ─────────────────────
        # Primary scientific output of the study.
        # Imbalance is reported strictly via independent dispersion metrics on
        # CLR geometric scale. Legacy relative abundance composites and W1/W2/W3
        # weights have been eradicated to respect compositional constraints.
        if ENABLE_DISTURBANCE_TRACK and disturbance_summary is not None:

            core_asvs        = set(self.asv_df['ASV_ID'])
            disturbance_only = disturbance_ids - core_asvs

            db_only_df = disturbance_df[
                disturbance_df['ASV_ID'].isin(disturbance_only)
            ].reset_index(drop=True)

            scores = []
            for col in self.sample_columns:
                col_sum = sample_col_sums.get(col, 1)

                core_present = int((self.asv_df[col] > 0).sum())
                dist_present = int((db_only_df[col] > 0).sum()) \
                               if not db_only_df.empty else 0

                if not db_only_df.empty and col_sum > 0:
                    rel_in_sample = db_only_df[col] / col_sum
                    spike_count   = int((rel_in_sample >= PEAK_REL_THRESHOLD).sum())
                else:
                    spike_count = 0

                # Mean Aitchison variation associated specifically with this sample's disturbance taxa
                sample_db_mask = db_only_df[col] > 0
                sample_db_ids = db_only_df.loc[sample_db_mask, 'ASV_ID'].values
                if len(sample_db_ids) > 0:
                    try:
                        sample_disp_score = float(clr_dispersion[sample_db_ids].mean())
                    except Exception:
                        sample_disp_score = 0.0
                else:
                    sample_disp_score = 0.0

                scores.append({
                    "sample":                col,
                    "core_richness":         core_present,
                    "disturbance_richness":  dist_present,
                    "spike_count":           spike_count,
                    "dispersion_score":      round(sample_disp_score, 6),
                })

            imbalance_df = pd.DataFrame(scores)
            imbalance_df.to_parquet(
                out_dir / "imbalance_scores.parquet", index=False
            )

            score_min = float(imbalance_df['dispersion_score'].min())
            score_max = float(imbalance_df['dispersion_score'].max())
            top_sample = imbalance_df.loc[
                imbalance_df['dispersion_score'].idxmax(), 'sample'
            ]
            imbalance_score_range = (score_min, score_max)

            self._warn(17, "dispersion_scores_computed",
                f"Dispersion metrics computed for {len(imbalance_df)} samples. "
                f"Score range: {score_min:.4f} – {score_max:.4f}. "
                f"Highest dispersion: {top_sample}.")

        # ── RETURN ─────────────────────────────────────────────────────────────
        return PreprocessingSummary(
            job_id=self.job_id,
            asv_count_before=asv_count_before,
            asv_count_after=len(self.asv_df),
            features_filtered=(asv_count_before - len(self.asv_df)),
            normalization_method="clr",
            pseudocount_used=PSEUDOCOUNT,
            samples_input=original_sample_columns,
            samples_retained=self.sample_columns,
            low_depth_samples_removed=failed_samples,
            empty_samples_removed=empty_samples,
            filter_summary=AsvFilterSummary(
                removed_by_prevalence=n_prev,
                removed_by_mean_abundance=n_abund,
                removed_by_rare_feature=n_rare,
                removed_pre_clr_variance=n_flat_pre,
                removed_post_clr_variance=n_flat_post,
            ),
            thresholds_used=FilterThresholds(
                min_sample_depth=MIN_SAMPLE_DEPTH,
                prevalence=PREVALENCE_THRESHOLD,
                min_mean_abundance=MIN_MEAN_ABUNDANCE,
                min_total_reads=MIN_TOTAL_READS,
                pseudocount=PSEUDOCOUNT,
            ),
            library_size_stats=LibrarySizeStats(
                min_reads=int(sample_sums_final.min()),
                median_reads=int(sample_sums_final.median()),
                max_reads=int(sample_sums_final.max()),
            ),
            disturbance_track=disturbance_summary,
            imbalance_score_range=imbalance_score_range,
            normalization_applied=True,
            feature_alignment_applied=True,
            message=(
                f"Preprocessing complete. "
                f"{asv_count_before - len(self.asv_df)} ASV(s) and "
                f"{len(failed_samples) + len(empty_samples)} sample(s) removed. "
                f"CLR (raw counts + {PSEUDOCOUNT} pseudocount) applied to "
                f"{len(self.asv_df)} features across {num_samples} samples."
            )
        )
