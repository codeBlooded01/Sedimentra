from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Any
from datetime import datetime


# ── Enums ──────────────────────────────────────────────────────────────────────

class FileType(str, Enum):
    ASV_TABLE = "asv_table"
    TAXONOMY  = "taxonomy"


class JobStatus(str, Enum):
    PENDING       = "pending"
    VALIDATING    = "validating"
    PREPROCESSING = "preprocessing"
    READY         = "ready"
    FAILED        = "failed"


class ValidationLayer(str, Enum):
    STRUCTURAL    = "layer_1_structural"
    SCHEMA        = "layer_2_schema"
    RELATIONAL    = "layer_3_relational"
    PREPROCESSING = "preprocessing"


# ── Upload Schemas ─────────────────────────────────────────────────────────────

class UploadJobCreate(BaseModel):
    asv_filename:      str
    taxonomy_filename: str


class UploadJobResponse(BaseModel):
    job_id:     str
    status:     JobStatus
    message:    str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Validation Result Schemas ──────────────────────────────────────────────────

class ValidationError(BaseModel):
    """A single, human-readable validation error."""
    layer:            ValidationLayer
    code:             str
    user_message:     str
    technical_detail: Optional[str] = None


class ValidationWarning(BaseModel):
    step:    int
    code:    str
    message: str


class ValidationReport(BaseModel):
    job_id:        str
    status:        JobStatus
    passed_layers: list[ValidationLayer]   = Field(default_factory=list)
    errors:        list[ValidationError]   = Field(default_factory=list)
    warnings:      list[ValidationWarning] = Field(default_factory=list)
    summary:       Optional[str]           = None


# ── Preprocessing Result Schemas ───────────────────────────────────────────────

class AsvFilterSummary(BaseModel):
    removed_by_prevalence:     int
    removed_by_mean_abundance: int
    removed_by_rare_feature:   int
    removed_pre_clr_variance:  int
    removed_post_clr_variance: int


class LibrarySizeStats(BaseModel):
    min_reads:    int
    median_reads: int
    max_reads:    int


class FilterThresholds(BaseModel):
    min_sample_depth:   int
    prevalence:         float
    min_mean_abundance: float
    min_total_reads:    int
    pseudocount:        float


class DisturbanceTrackSummary(BaseModel):
    asv_count:                  int
    asv_count_core_only:        int
    asv_count_disturbance_only: int
    asv_count_shared:           int
    peak_rel_threshold_used:    float
    cv_threshold_used:          float
    bypass_breakdown:           dict[str, int]


class PreprocessingSummary(BaseModel):
    job_id:            str
    asv_count_before:  int
    asv_count_after:   int
    features_filtered: int
    normalization_method: str
    pseudocount_used:     float
    samples_input:             list[str]
    samples_retained:          list[str]
    low_depth_samples_removed: list[str]
    empty_samples_removed:     list[str]
    filter_summary:   AsvFilterSummary
    thresholds_used:  FilterThresholds
    library_size_stats: Optional[LibrarySizeStats] = None
    disturbance_track:    Optional[DisturbanceTrackSummary] = None
    imbalance_score_range: Optional[tuple[float, float]]   = None
    normalization_applied:     bool
    feature_alignment_applied: bool
    message:                   str


# ── Analysis Report Schemas ────────────────────────────────────────────────────

class FunctionalAssignment(BaseModel):
    function: str
    matched_rank: str = "unassigned"
    confidence: str = "unassigned"

class SampleGenus(BaseModel):
    genus: str
    abundance: float
    lineage: str = ""
    functions: list[FunctionalAssignment] = Field(default_factory=list)

class SampleInput(BaseModel):
    sample_id: str
    genera: list[SampleGenus]

class AnalyzeReportRequest(BaseModel):
    samples: list[SampleInput]

class DescriptiveMetrics(BaseModel):
    sample_id: str
    shannon_entropy: float
    observed_genera: int
    total_genera: int
    diversity_status: str
    dominant_genus: str
    dominant_abundance: float
    top10: list[SampleGenus]

class FlagDetail(BaseModel):
    genus: str
    abundance: float
    threshold: str
    direction: str
    severity: str
    interpretation: str
    functions: list[FunctionalAssignment] = Field(default_factory=list)

# ── Pathway & Index Schemas (DSS Upgrade) ─────────────────────────────────────

class PathwayBundle(BaseModel):
    """Aggregated FAPROTAX function abundances per biogeochemical pathway group.
    All values are summed relative abundances (0.0–1.0 scale) from genus-level
    FAPROTAX mapping. Used as inputs to CyclingIndices.
    """
    ch4_production: float = 0.0   # methanogenesis + hydrogenotrophic + acetoclastic + reductive_acetogenesis + formate + disproportionation + fermentation*0.4 (capped)
    ch4_oxidation: float  = 0.0   # methanotrophy
    s_reduction: float    = 0.0   # sulfate_respiration + thiosulfate_respiration + sulfur_respiration + sulfite_respiration
    s_oxidation: float    = 0.0   # dark_sulfide_oxidation + dark_sulfur_oxidation + dark_thiosulfate_oxidation + dark_oxidation_of_sulfur_compounds + anoxygenic_photoautotrophy_S_oxidizing
    anoxic_support: float = 0.0   # dark_hydrogen_oxidation + iron_respiration + fumarate_respiration
    aerobic_baseline: float = 0.0 # aerobic_chemoheterotrophy — used for context
    fermentation_raw: float = 0.0 # raw fermentation abundance before capping (for transparency)


class CyclingIndices(BaseModel):
    """Quantitative ratio-based indices derived from PathwayBundles.
    Thresholds are percentile-calibrated across all samples in the uploaded
    dataset (not hardcoded), making them dataset-relative. Insufficient signal
    is reported explicitly when denominators are near zero.
    """
    # Methane Cycle Index
    mci: float
    mci_risk: str                 # "Low" | "Moderate" | "High" | "Critical"
    mci_signal_sufficient: bool   # False when methanotrophy abundance < MIN_SIGNAL
    ch4_prod_raw: float           # numerator value
    ch4_ox_raw: float             # denominator value
    ch4_ratio_label: str          # e.g. "Production 3.2× > Oxidation"

    # Sulfur Cycle Index
    sci: float
    sci_risk: str
    sci_signal_sufficient: bool   # False when s_oxidation abundance < MIN_SIGNAL
    s_red_raw: float
    s_ox_raw: float
    s_ratio_label: str

    # Anoxic Support Index
    asi: float
    asi_level: str                # "Minor" | "Moderate" | "Pervasive"

    # Dataset-derived thresholds used (for UI transparency)
    mci_thresholds: list[float]   # [p25, p50, p75] across all samples
    sci_thresholds: list[float]


class ConfidenceAssessment(BaseModel):
    """Multi-factor, transparent confidence score. No black-box computation.
    Each component is individually reported so the analyst can trace scoring.
    """
    score: float                  # 0.0–1.0 composite
    level: str                    # "High" (≥0.75) | "Moderate" (0.50–0.74) | "Low" (<0.50)

    # Sub-scores (each 0.0–1.0, available for audit)
    diversity_component: float    # Shannon H' / 5.0, weight=0.20
    depth_component: float        # min(log10(reads)/log10(50000), 1.0), weight=0.20
    functional_coverage: float    # faprotax_mapped_abund / total_abund, weight=0.40
    cross_sample_consistency: float  # 1 - CV(stress_levels), weight=0.20; 0.5 if single sample

    weights: dict[str, float]     # {"diversity": 0.20, "depth": 0.20, "coverage": 0.40, "consistency": 0.20}
    caveats: list[str]            # auto-generated warnings (e.g. single sample, low coverage)


class TrajectoryProjection(BaseModel):
    """Cross-sample functional risk trajectory. NOT a temporal prediction.
    Describes the direction of metabolic imbalance risk across uploaded samples
    as a monotone cross-sectional trend, assuming samples are ordered by
    acquisition sequence.
    """
    direction: str                # "Escalating Risk" | "Stable" | "Declining Risk"
    slope: float                  # linear regression slope of stress_level across sample index
    projected_risk_state: str     # "current risk state is likely to persist / escalate / decline"
    confidence: str               # from ConfidenceAssessment.level
    sample_count: int             # number of samples used in regression
    assumptions: list[str]        # explicit list — rendered in UI


class ManagementRecommendation(BaseModel):
    """Index-threshold-driven, DENR-actionable recommendation.
    Triggered from CyclingIndices values, not from single-taxon flags.
    Language avoids strict temporal predictions or regulatory prescriptions.
    """
    priority: str                 # "P1 — Immediate Action" | "P2 — Short-term" | "P3 — Monitor"
    pathway: str                  # "Methane Cycle" | "Sulfur Cycle" | "Anaerobic Conditions" | "Microbial Diversity"
    trigger_index: str            # e.g. "MCI = 4.7 (High risk tier)"
    observation: str              # what the data shows — plain language
    action: str                   # recommended physical/operational action
    rationale: str                # scientific basis
    confidence_note: str          # from ConfidenceAssessment.level


class DiagnosticResult(BaseModel):
    sample_id: str
    stress_level: int
    stress_label: str
    critical_count: int
    warning_count: int
    flags: list[FlagDetail]
    # DSS upgrade fields
    pathway_bundle: Optional[PathwayBundle] = None
    cycling_indices: Optional[CyclingIndices] = None
    confidence: Optional[ConfidenceAssessment] = None
    trajectory: Optional[TrajectoryProjection] = None   # populated after all samples computed
    recommendations: list[ManagementRecommendation] = Field(default_factory=list)


class SampleFilterAudit(BaseModel):
    """Transparent accounting of every sample submitted vs. retained.

    Populated by the report-generate endpoint so the UI can display
    exactly which samples were dropped and the scientific reason why.
    Users submitted N samples and see M in the report — this closes
    the gap with full traceable justification.
    """
    samples_submitted:            int
    samples_retained:             int
    samples_dropped:              int
    low_depth_samples_removed:    list[str]   # Step 2 — < MIN_SAMPLE_DEPTH reads
    empty_after_filter_samples:   list[str]   # Step 10 — all-zero after ASV filter
    zero_genus_abundance_samples: list[str]   # Report-level — no resolved genus signal
    min_depth_threshold_used:     int         # Threshold value for panel transparency


class AnalyzeReportResponse(BaseModel):
    descriptive: list[DescriptiveMetrics]
    diagnostic: list[DiagnosticResult]
    sample_filter_audit: Optional[SampleFilterAudit] = None


class CsvPreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict]
