"""
Descriptive + Diagnostic + Predictive compute functions.

Architecture
============
- Descriptive layer  : Shannon entropy, diversity status, top-10 genera
- Diagnostic layer   : Genus/phylum threshold flags, ecological stress level
- Predictive layer   : Pathway-indexed cycling indices (MCI, SCI, ASI),
                       multi-factor confidence scoring, cross-sample trajectory,
                       index-driven management recommendations

All predictive outputs are based on FAPROTAX-derived functional pathway
abundances, NOT raw taxon labels.  Thresholds are dataset-relative
(percentile-calibrated), not hardcoded.
"""

import json
import math
import statistics
from pathlib import Path
from typing import List, Optional, Dict, Tuple

import numpy as np
from scipy.stats import linregress as scipy_linregress
from scipy.stats import variation as scipy_variation
from skbio.diversity.alpha import shannon as skbio_shannon

from app.schemas.genomic import (
    SampleInput, SampleGenus,
    DescriptiveMetrics, DiagnosticResult, FlagDetail,
    PathwayBundle, CyclingIndices, ConfidenceAssessment,
    TrajectoryProjection, ManagementRecommendation,
)
from app.services.faprotax_service import faprotax_service


# ── Genus-level thresholds ─────────────────────────────────────────────────────
GENUS_THRESHOLDS = [
    {"name": "Nitrospira",     "max": 0.25, "severity": "warning",
     "message": "Elevated Nitrospira suggests nitrification imbalance, which may reduce available nitrogen for plant uptake and signal disrupted nitrogen cycling."},
    {"name": "Acidobacterium", "max": 0.20, "severity": "critical",
     "message": "High Acidobacterium dominance indicates strong acidification stress. This genus thrives in low-pH conditions and outcompetes beneficial microbes when soil buffering capacity fails."},
    {"name": "Desulfovibrio",  "max": 0.05, "severity": "critical",
     "message": "Desulfovibrio is a sulfate-reducing bacterium. Presence above threshold confirms active sulfate reduction, producing toxic H₂S and indicating severe anoxic disturbance."},
]

# ── Phylum-level thresholds ───────────────────────────────────────────────────
PHYLUM_THRESHOLDS = [
    {"name": "Chloroflexi",    "aliases": ["Chloroflexota"],
     "max": 0.18, "severity": "info",
     "message": "Elevated Chloroflexi can indicate reduced organic matter decomposition rates, potentially leading to nutrient lock-up in the soil matrix."},
    {"name": "Proteobacteria", "aliases": ["Pseudomonadota"],
     "max": 0.30, "severity": "warning",
     "message": "Excess Proteobacteria suggests a pulse of labile carbon or nutrient loading — a common early indicator of eutrophication-like stress."},
    {"name": "Firmicutes",     "aliases": ["Bacillota"],
     "max": 0.15, "severity": "critical",
     "message": "Firmicutes dominance above threshold is linked to anoxic microenvironments and organic overload — hallmarks of heavily disturbed or waterlogged conditions."},
    {"name": "Planctomycetes", "aliases": ["Planctomycetota"],
     "max": 0.12, "severity": "info",
     "message": "Slightly elevated Planctomycetes may reflect shifting organic carbon pools. Usually benign but worth monitoring as part of overall community restructuring."},
    {"name": "Actinobacteria", "aliases": ["Actinobacteriota", "Actinomycetota"],
     "min": 0.08, "severity": "warning",
     "message": "Below-threshold Actinobacteria indicates reduced decomposer activity. This phylum is critical for humus formation; its decline precedes long-term fertility loss."},
]

STRESS_LABELS = ["Stable", "Mildly Disturbed", "Moderately Disturbed", "Heavily Disturbed"]

# ══════════════════════════════════════════════════════════════════════════════
# FAPROTAX FUNCTION BUCKETS — loaded from external JSON config
# Source: app/assets/pathway_definitions.json
# Add or extend pathways by editing the JSON file — no Python changes needed.
# ══════════════════════════════════════════════════════════════════════════════

_PATHWAY_DEFS_PATH = Path(__file__).parent.parent / "assets" / "pathway_definitions.json"

def _load_pathway_defs() -> dict:
    """Load and return pathway bucket definitions from JSON. Converts lists to sets."""
    with open(_PATHWAY_DEFS_PATH, encoding="utf-8") as _f:
        _raw = json.load(_f)
    return {k: set(v) for k, v in _raw.items() if not k.startswith("_")}

_PATHWAY_DEFS = _load_pathway_defs()

CH4_PRODUCTION_FUNCS: set = _PATHWAY_DEFS["CH4_PRODUCTION"]
CH4_OXIDATION_FUNCS:  set = _PATHWAY_DEFS["CH4_OXIDATION"]
S_REDUCTION_FUNCS:    set = _PATHWAY_DEFS["S_REDUCTION"]
S_OXIDATION_FUNCS:    set = _PATHWAY_DEFS["S_OXIDATION"]
ANOXIC_SUPPORT_FUNCS: set = _PATHWAY_DEFS["ANOXIC_SUPPORT"]

# Fermentation is upstream of methanogenesis — treated separately with weight cap
FERMENTATION_FUNC         = next(iter(_PATHWAY_DEFS["FERMENTATION"]))  # single-entry bucket
FERMENTATION_WEIGHT       = 0.4
FERMENTATION_MAX_FRACTION = 0.35  # fermentation may contribute at most 35% of numerator

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS — DESCRIPTIVE & DIAGNOSTIC
# ══════════════════════════════════════════════════════════════════════════════

def _shannon(values: List[float]) -> float:
    """Shannon entropy (H') using natural log — delegates to scikit-bio.

    skbio.diversity.alpha.shannon normalises counts internally and uses the
    specified base.  base=math.e preserves natural-log output consistent with
    the rest of the system (thresholds calibrated for H' on ln scale).
    """
    counts = np.asarray(values, dtype=float)
    if counts.sum() == 0:
        return 0.0
    return float(skbio_shannon(counts, base=math.e))


def _diversity_status(h: float) -> str:
    if h < 1.5:  return "Low"
    if h < 2.8:  return "Normal"
    return "High"


def _stress_level(flags: List[FlagDetail]) -> int:
    criticals = sum(1 for f in flags if f.severity == "critical")
    warnings   = sum(1 for f in flags if f.severity == "warning")
    if criticals >= 2:                return 3
    if criticals == 1 or warnings >= 2: return 2
    if warnings == 1:                 return 1
    return 0


def _check_threshold(t: dict, val: float) -> bool:
    return (
        ("max" in t and val > t["max"]) or
        ("min" in t and 0 < val < t["min"])
    )


def _make_flag(t: dict, val: float, label: str) -> FlagDetail:
    from app.schemas.genomic import FunctionalAssignment
    threshold_str = f"> {int(t['max']*100)}%" if "max" in t else f"< {int(t['min']*100)}%"
    direction     = "above max threshold" if "max" in t else "below min threshold"
    funcs_dicts   = faprotax_service.get_functions_for_taxa(label)
    func_objs     = [FunctionalAssignment(**f) for f in funcs_dicts]
    return FlagDetail(
        genus          = label,
        abundance      = round(val, 4),
        threshold      = threshold_str,
        direction      = direction,
        severity       = t["severity"],
        interpretation = t["message"],
        functions      = func_objs,
    )

# ══════════════════════════════════════════════════════════════════════════════
# PATHWAY BUNDLE COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def compute_pathway_bundles(sample: SampleInput) -> PathwayBundle:
    """
    Map each genus → FAPROTAX functions → aggregate abundance per pathway bucket.

    Each genus's FAPROTAX functions are retrieved; its relative abundance is
    added to each bucket it contributes to.  A single genus may contribute to
    multiple buckets (e.g., Desulfovibrio to both S_reduction and anoxic_support).
    """
    bundle = PathwayBundle()
    ch4_prod_direct = 0.0
    fermentation_abund = 0.0
    aerobic_baseline = 0.0

    for g in sample.genera:
        funcs = {a["function"] for a in faprotax_service.get_functions_for_taxa(g.lineage)}
        abund = g.abundance

        # -- CH₄ production (direct pathways)
        for f in CH4_PRODUCTION_FUNCS:
            if f in funcs:
                ch4_prod_direct += abund
                break  # count genus once per bucket even if multi-tagged

        # -- Fermentation (tracked separately for capping)
        if FERMENTATION_FUNC in funcs:
            fermentation_abund += abund

        # -- CH₄ oxidation
        for f in CH4_OXIDATION_FUNCS:
            if f in funcs:
                bundle.ch4_oxidation += abund
                break

        # -- Sulfur reduction
        for f in S_REDUCTION_FUNCS:
            if f in funcs:
                bundle.s_reduction += abund
                break

        # -- Sulfur oxidation (expanded denominator)
        for f in S_OXIDATION_FUNCS:
            if f in funcs:
                bundle.s_oxidation += abund
                break

        # -- Anoxic support
        for f in ANOXIC_SUPPORT_FUNCS:
            if f in funcs:
                bundle.anoxic_support += abund
                break

        # -- Aerobic baseline
        if "aerobic_chemoheterotrophy" in funcs:
            aerobic_baseline += abund

    # Apply fermentation weight and cap
    ferm_weighted = fermentation_abund * FERMENTATION_WEIGHT
    max_ferm_contribution = (ch4_prod_direct + ferm_weighted) * FERMENTATION_MAX_FRACTION
    ferm_capped = min(ferm_weighted, max_ferm_contribution)

    bundle.ch4_production = round(ch4_prod_direct + ferm_capped, 6)
    bundle.ch4_oxidation  = round(bundle.ch4_oxidation, 6)
    bundle.s_reduction    = round(bundle.s_reduction, 6)
    bundle.s_oxidation    = round(bundle.s_oxidation, 6)
    bundle.anoxic_support = round(bundle.anoxic_support, 6)
    bundle.aerobic_baseline = round(aerobic_baseline, 6)
    bundle.fermentation_raw = round(fermentation_abund, 6)

    return bundle

# ══════════════════════════════════════════════════════════════════════════════
# PERCENTILE THRESHOLD CALIBRATION
# ══════════════════════════════════════════════════════════════════════════════

def calibrate_percentile_thresholds(values: List[float]) -> List[float]:
    """
    Compute [p25, p50, p75] across a list of index values.
    Used to set Low/Moderate/High/Critical tiers in a dataset-relative way.

    Falls back to empty list (caller uses literature defaults) when:
    - Fewer than 4 samples
    - Spread (max - min) < MIN_INDEX_SPREAD — prevents degenerate calibration
      when all samples cluster at the same value, which would make every tiny
      deviation above p75 appear "Critical".
    """
    MIN_INDEX_SPREAD = 0.5  # require at least this range across the dataset

    if len(values) < 4:
        return []

    sorted_vals = sorted(values)
    spread = sorted_vals[-1] - sorted_vals[0]
    if spread < MIN_INDEX_SPREAD:
        return []  # use literature fallback — dataset too homogeneous to calibrate

    n = len(values)
    p25, p50, p75 = np.percentile(values, [25, 50, 75])
    return [round(float(p25), 4), round(float(p50), 4), round(float(p75), 4)]


def _classify_risk(value: float, percentiles: List[float], fallback: List[float]) -> str:
    """Classify value into Low/Moderate/High/Critical using percentile boundaries."""
    thresholds = percentiles if len(percentiles) == 3 else fallback
    if value <= thresholds[0]: return "Low"
    if value <= thresholds[1]: return "Moderate"
    if value <= thresholds[2]: return "High"
    return "Critical"


def _ratio_label(alr_val: float, num_name: str, den_name: str, den_sufficient: bool) -> str:
    """Interprets the unbounded Additive Log-Ratio (ALR) scale."""
    if not den_sufficient:
        return f"{num_name} dominant — {den_name} near absent"
    if abs(alr_val) < 0.10:
        return f"{num_name} ≈ {den_name} (balanced)"
    dominant = num_name if alr_val > 0 else den_name
    magnitude = math.exp(abs(alr_val))
    return f"{dominant} {magnitude:.1f}× dominant"

# ══════════════════════════════════════════════════════════════════════════════
# CYCLING INDICES
# ══════════════════════════════════════════════════════════════════════════════

def _impute_bundle_vector(raw_vector: List[float]) -> List[float]:
    """Applies Martín-Fernández multiplicative replacement to a compositional vector."""
    n_comp = len(raw_vector)
    non_zeros = [x for x in raw_vector if x > 0]
    
    if not non_zeros:
        return [1.0 / n_comp] * n_comp
        
    min_nonzero = min(non_zeros)
    delta = 0.65 * min_nonzero / n_comp
    z = sum(1 for x in raw_vector if x == 0)
    discount = 1.0 - (z * delta)
    
    return [(delta if x == 0 else x * discount) for x in raw_vector]

def compute_cycling_indices(
    bundle: PathwayBundle,
    mci_percentiles: List[float],
    sci_percentiles: List[float],
) -> CyclingIndices:
    """
    Compute MCI, SCI, ASI using Additive Log-Ratio (ALR) on imputed vectors.
    """
    # TODO: provisional log-ratio fallback — requires empirical recalibration against reference ecosystem data.
    MCI_FALLBACK = [-0.5, 0.5, 1.5]
    # TODO: provisional log-ratio fallback — requires empirical recalibration against reference ecosystem data.
    SCI_FALLBACK = [-0.5, 0.5, 1.5]

    # Full compositional vector (n=6)
    raw_vector = [
        bundle.ch4_production,
        bundle.ch4_oxidation,
        bundle.s_reduction,
        bundle.s_oxidation,
        bundle.anoxic_support,
        bundle.aerobic_baseline
    ]
    imputed = _impute_bundle_vector(raw_vector)
    delta = min(imputed)  # Since delta is the imputation mathematical floor
    
    (i_ch4_prod, i_ch4_ox, i_s_red, i_s_ox, i_anoxic, i_aerobic) = imputed

    # ── MCI (ALR space)
    mci_val = math.log(i_ch4_prod) - math.log(i_ch4_ox)
    mci_sufficient = i_ch4_ox > delta
    mci_risk = _classify_risk(mci_val, mci_percentiles, MCI_FALLBACK)
    ch4_label = _ratio_label(mci_val, "CH₄ Production", "CH₄ Oxidation", mci_sufficient)

    # ── SCI (ALR space)
    sci_val = math.log(i_s_red) - math.log(i_s_ox)
    sci_sufficient = i_s_ox > delta
    sci_risk = _classify_risk(sci_val, sci_percentiles, SCI_FALLBACK)
    s_label = _ratio_label(sci_val, "S Reduction", "S Oxidation", sci_sufficient)

    # ── ASI (Kept linearly evaluated)
    asi_val = bundle.anoxic_support
    if asi_val < 0.05:  asi_level = "Minor"
    elif asi_val < 0.15: asi_level = "Moderate"
    else:               asi_level = "Pervasive"

    return CyclingIndices(
        mci=round(mci_val, 4),
        mci_risk=mci_risk,
        mci_signal_sufficient=mci_sufficient,
        ch4_prod_raw=round(bundle.ch4_production, 6),
        ch4_ox_raw=round(bundle.ch4_oxidation, 6),
        ch4_ratio_label=ch4_label,
        sci=round(sci_val, 4),
        sci_risk=sci_risk,
        sci_signal_sufficient=sci_sufficient,
        s_red_raw=round(bundle.s_reduction, 6),
        s_ox_raw=round(bundle.s_oxidation, 6),
        s_ratio_label=s_label,
        asi=round(asi_val, 4),
        asi_level=asi_level,
        mci_thresholds=mci_percentiles if mci_percentiles else MCI_FALLBACK,
        sci_thresholds=sci_percentiles if sci_percentiles else SCI_FALLBACK,
    )

# ══════════════════════════════════════════════════════════════════════════════
# CONFIDENCE ASSESSMENT
# ══════════════════════════════════════════════════════════════════════════════

CONFIDENCE_WEIGHTS = {
    "diversity":    0.20,
    "depth":        0.20,
    "coverage":     0.40,
    "consistency":  0.20,
}

def compute_confidence(
    sample: SampleInput,
    shannon: float,
    total_reads: Optional[int],
    all_risk_scores: Optional[List[float]],
) -> ConfidenceAssessment:
    """
    Transparent 4-factor confidence score. All sub-scores are 0.0–1.0.

    Weights (explicit, not black-box):
      diversity    × 0.20  — community richness as data reliability proxy
      depth        × 0.20  — sequencing depth (normalized to 50,000 reads)
      coverage     × 0.40  — fraction of community abundance with FAPROTAX assignment
      consistency  × 0.20  — cross-sample composite risk coefficient of variation
    """
    caveats = []

    # 1. Diversity component
    H_MAX = 5.0  # theoretical max for coastal sediment communities
    div_comp = min(shannon / H_MAX, 1.0)
    if shannon < 1.5:
        caveats.append("Low alpha diversity (H' < 1.5) reduces inference reliability.")

    # 2. Depth component
    if total_reads and total_reads > 0:
        depth_comp = min(math.log10(total_reads) / math.log10(50_000), 1.0)
        if total_reads < 5_000:
            caveats.append(f"Low sequencing depth ({total_reads} reads); indices may be unstable.")
    else:
        depth_comp = 0.5  # unknown depth — penalize moderately
        caveats.append("Sequencing depth unavailable; depth component estimated.")

    # 3. Functional coverage — what fraction of total abundance has FAPROTAX mapping
    total_abund = sum(g.abundance for g in sample.genera)
    mapped_abund = sum(
        g.abundance for g in sample.genera
        if any(a["function"] != "none" for a in faprotax_service.get_functions_for_taxa(g.lineage))
    )
    coverage_comp = (mapped_abund / total_abund) if total_abund > 0 else 0.0
    if coverage_comp < 0.50:
        caveats.append(f"Low FAPROTAX coverage ({coverage_comp*100:.0f}% of relative abundance mapped); functional indices reflect partial community signal.")

    # 4. Cross-sample consistency
    # scipy.stats.variation = std(ddof=1) / mean — equivalent to the manual
    # statistics.stdev / mean computation, but from a validated library.
    if all_risk_scores and len(all_risk_scores) > 1:
        mean_risk = statistics.mean(all_risk_scores)
        if mean_risk > 0.1:  # threshold to avoid noise at zero
            cv = float(scipy_variation(all_risk_scores, ddof=1))
            consistency_comp = max(0.0, 1.0 - abs(cv))
        else:
            consistency_comp = 1.0  # all stable/low risk
    else:
        consistency_comp = 0.5  # single sample — cannot assess consistency
        caveats.append("Single-sample dataset; cross-sample consistency cannot be assessed. Consistency component set to 0.50 (neutral).")

    # Composite score
    w = CONFIDENCE_WEIGHTS
    score = (
        w["diversity"]   * div_comp +
        w["depth"]       * depth_comp +
        w["coverage"]    * coverage_comp +
        w["consistency"] * consistency_comp
    )

    if score >= 0.75:   level = "High"
    elif score >= 0.50: level = "Moderate"
    else:               level = "Low"

    if level == "Low":
        caveats.append("Overall confidence is LOW. Interpret indices with caution. Field validation is recommended before acting on P1 recommendations.")

    return ConfidenceAssessment(
        score=round(score, 4),
        level=level,
        diversity_component=round(div_comp, 4),
        depth_component=round(depth_comp, 4),
        functional_coverage=round(coverage_comp, 4),
        cross_sample_consistency=round(consistency_comp, 4),
        weights=CONFIDENCE_WEIGHTS,
        caveats=caveats,
    )

# ══════════════════════════════════════════════════════════════════════════════
# TRAJECTORY PROJECTION
# ══════════════════════════════════════════════════════════════════════════════

# Numeric mapping for risk levels → used for composite trajectory signal
_RISK_TO_INT = {"Low": 0, "Moderate": 1, "High": 2, "Critical": 3}
_ASI_TO_INT  = {"Minor": 0, "Moderate": 1, "Pervasive": 2}


def _composite_risk_score(d: "DiagnosticResult") -> float:
    """
    Compute a per-sample composite risk score on a 0–3 scale.
    Weights: stress_level flags 30%, MCI 35%, SCI 35%.
    Falls back to pure stress_level when indices are unavailable.
    """
    flag_score = float(d.stress_level)  # 0–3
    if d.cycling_indices:
        ci = d.cycling_indices
        mci_int = _RISK_TO_INT.get(ci.mci_risk, 0)
        sci_int = _RISK_TO_INT.get(ci.sci_risk, 0)
        index_score = (mci_int + sci_int) / 2.0  # 0–3
        return 0.30 * flag_score + 0.70 * index_score
    return flag_score


def compute_trajectory(diagnostics: List["DiagnosticResult"]) -> Optional[TrajectoryProjection]:
    """
    Compute cross-sample functional risk trajectory.

    Uses a composite risk score (flag-based stress × 0.30 + index-based risk × 0.70)
    rather than stress_level alone.  This ensures trajectory reflects cycling index
    signals even when genus/phylum flags do not fire (e.g., taxonomy name mismatches).

    Cross-sectional analysis — NOT a temporal forecast. Returns None for < 3 samples.
    """
    n = len(diagnostics)
    if n < 3:
        return None

    risk_scores = [_composite_risk_score(d) for d in diagnostics]

    _lr = scipy_linregress(range(n), risk_scores)
    slope   = _lr.slope
    p_value = _lr.pvalue
    r_squared = _lr.rvalue ** 2
    y_mean  = float(np.mean(risk_scores))  # used for risk_summary label below
    
    if y_mean >= 2.5:    risk_summary = "Critical"
    elif y_mean >= 1.5:  risk_summary = "High"
    elif y_mean >= 0.75: risk_summary = "Moderate"
    else:                risk_summary = "Low"

    is_significant = (p_value < 0.05) and (r_squared >= 0.40)

    if slope > 0.15 and is_significant:
        direction = "Escalating Risk"
        projected_risk_state = (
            f"Functional imbalance risk is assessed as escalating (mean risk tier: {risk_summary}). "
            f"The current metabolic risk state is likely to persist or intensify "
            f"under unchanged environmental conditions (p={p_value:.3f}, R²={r_squared:.2f})."
        )
    elif slope < -0.15 and is_significant:
        direction = "Declining Risk"
        projected_risk_state = (
            f"Functional imbalance risk is assessed as declining (mean risk tier: {risk_summary}). "
            f"The community metabolic risk state shows signs of recovery; "
            f"continued monitoring is recommended to confirm the trend (p={p_value:.3f}, R²={r_squared:.2f})."
        )
    else:
        direction = "Stable/Inconclusive"
        projected_risk_state = (
            f"Cross-sample functional risk is stable or inconclusive (mean risk tier: {risk_summary}). "
            f"No significant directional escalation is detected across the dataset "
            f"(p={p_value:.3f}, R²={r_squared:.2f}). "
            f"Per-sample index values should be reviewed individually for locally elevated risk."
        )

    confidence_level = diagnostics[0].confidence.level if diagnostics[0].confidence else "Moderate"

    return TrajectoryProjection(
        direction=direction,
        slope=round(slope, 4),
        projected_risk_state=projected_risk_state,
        confidence=confidence_level,
        sample_count=n,
        assumptions=[
            "Samples are assumed to be ordered by spatial or temporal acquisition sequence.",
            "Analysis is cross-sectional; no repeated-measures or longitudinal data are used.",
            "Trajectory reflects functional risk state, not confirmed metabolic activity.",
            "Composite risk score = 30% flag-based stress + 70% cycling index risk (MCI+SCI average).",
            "Environmental conditions are assumed stable between sampling points.",
            "FAPROTAX inference represents ecological potential based on literature assignments, not confirmed in-situ flux.",
        ],
    )

# ══════════════════════════════════════════════════════════════════════════════
# MANAGEMENT RECOMMENDATIONS (index-driven)
# ══════════════════════════════════════════════════════════════════════════════

def _has_high_confidence_signal(flags: List[FlagDetail]) -> bool:
    for flag in flags:
        for assignment in flag.functions:
            if assignment.confidence == "high":
                return True
    return False

def derive_recommendations(
    indices: CyclingIndices,
    confidence: ConfidenceAssessment,
    shannon: float,
    flags: List[FlagDetail],
) -> List[ManagementRecommendation]:
    """
    Generate management recommendations triggered by CyclingIndices thresholds,
    NOT by single taxon flags.

    Language standards applied:
    - No strict temporal predictions ("will fail in X days")
    - No regulatory prescriptions without qualified caveats
    - All P1 actions include a confidence note
    - Actions are scoped to what DENR Region VIII can realistically execute
    """
    recs: List[ManagementRecommendation] = []
    conf_note = f"Confidence: {confidence.level} ({confidence.score:.2f}). {'Field validation is recommended before action.' if confidence.level != 'High' else ''}"

    # ── MCI rules ───────────────────────────────────────────────────────────

    if indices.mci_risk == "Critical":
        priority = "P1 — Immediate Action"
        obs = (
            f"Methane cycling is critically imbalanced: CH₄ production pathways are "
            f"{indices.ch4_ratio_label.lower()}. "
            f"Inferred methanogenic functional signal is dominant with insufficient opposing oxidation activity. "
            f"This indicates conditions consistent with active methanogenesis in the sediment."
        )
        local_conf_note = conf_note
        if not _has_high_confidence_signal(flags):
            priority = "P3 — Monitor"
            obs += " Downgraded from P1: all triggering functional assignments carry low or unassigned confidence. Chemical validation required before escalation."
        else:
            local_conf_note += " P1 Recommendation is strictly actionable for surface horizons (0–5 cm); elevated signals in deeper anaerobic subsurface strata are biogeochemically standard and represent natural stratification, not acute disturbance."
            
        recs.append(ManagementRecommendation(
            priority=priority,
            pathway="Methane Cycle",
            trigger_index=f"MCI = {indices.mci:.2f} ({indices.mci_risk} tier)",
            observation=obs,
            action=(
                "Collect surface sediment and overlying water samples from the monitoring station for "
                "dissolved CH₄ and BOD/COD analysis. Identify upstream organic matter sources. "
                "Assess the feasibility of increased aeration or sediment disturbance mitigation at the site. "
                "Coordinate with the regional office for prioritized field investigation."
            ),
            rationale=(
                "A high MCI value indicates that methanogenic pathway signal substantially exceeds "
                "methane-oxidizing signal in the FAPROTAX-mapped community. In coastal sediments, "
                "this pattern is associated with anoxic conditions that support CH₄ accumulation at "
                "the sediment-water interface and potential flux to the water column."
            ),
            confidence_note=local_conf_note,
        ))

    elif indices.mci_risk == "High":
        recs.append(ManagementRecommendation(
            priority="P2 — Short-term Action",
            pathway="Methane Cycle",
            trigger_index=f"MCI = {indices.mci:.2f} ({indices.mci_risk} tier)",
            observation=(
                f"Methane production pathway signal outpaces oxidation: {indices.ch4_ratio_label}. "
                "Imbalance is at a level that warrants targeted investigation but does not yet indicate confirmed critical anoxia."
            ),
            action=(
                "Increase sampling frequency for this station to biweekly or monthly intervals. "
                "Collect and submit sediment samples for dissolved gas analysis. "
                "Review land use and drainage patterns in the watershed upstream of the monitoring site."
            ),
            rationale=(
                "Moderate-to-high MCI indicates progressive shift toward methanogenic conditions. "
                "Early intervention through increased monitoring can detect escalation before it reaches critical levels."
            ),
            confidence_note=conf_note,
        ))

    if not indices.mci_signal_sufficient:
        recs.append(ManagementRecommendation(
            priority="P3 — Monitor",
            pathway="Methane Cycle",
            trigger_index=f"MCI = {indices.mci:.2f} — Low confidence: methane oxidation signal near zero",
            observation=(
                "Methane-oxidizing pathway signal (methanotrophy) is at or near the detection floor. "
                "The MCI value may be inflated due to absence of opposing signal rather than confirmed high production. "
                "This could reflect true absence of methanotrophs or insufficient FAPROTAX coverage for this community."
            ),
            action=(
                "Treat MCI at face value with caution. "
                "If resources allow, supplement with targeted qPCR for methane monooxygenase (pmoA) gene "
                "to confirm or rule out methanotrophic activity."
            ),
            rationale=(
                "When the denominator of the MCI (methanotrophy abundance) is near zero, the ratio becomes "
                "sensitive to small numerator changes. The insufficient signal flag prevents over-interpretation."
            ),
            confidence_note=conf_note,
        ))

    # ── SCI rules ───────────────────────────────────────────────────────────

    if indices.sci_risk == "Critical":
        priority = "P1 — Immediate Action"
        obs = (
            f"Sulfur cycling is critically imbalanced: {indices.s_ratio_label}. "
            "Dissimilatory sulfate reduction pathway signal strongly dominates over sulfur oxidation. "
            "This pattern is indicative of active H₂S-generating conditions in the sediment."
        )
        local_conf_note = conf_note
        if not _has_high_confidence_signal(flags):
            priority = "P3 — Monitor"
            obs += " Downgraded from P1: all triggering functional assignments carry low or unassigned confidence. Chemical validation required before escalation."
        else:
            local_conf_note += " P1 Recommendation is strictly actionable for surface horizons (0–5 cm); elevated signals in deeper anaerobic subsurface strata are biogeochemically standard and represent natural stratification, not acute disturbance."
            
        recs.append(ManagementRecommendation(
            priority=priority,
            pathway="Sulfur Cycle",
            trigger_index=f"SCI = {indices.sci:.2f} ({indices.sci_risk} tier)",
            observation=obs,
            action=(
                "Conduct targeted porewater sampling at this station for dissolved hydrogen sulfide (H₂S) "
                "and sulfate (SO₄²⁻) to chemically validate the inferred risk. "
                "Recommend a localized biological risk assessment within the immediate area of the monitoring site. "
                "Document findings and coordinate with the DENR regional environmental laboratory."
            ),
            rationale=(
                "A critical SCI value indicates that sulfate-reducing pathway functional signal substantially "
                "exceeds sulfur-oxidizing signal. This is consistent with active dissimilatory sulfate reduction, "
                "which produces H₂S — toxic to benthic fauna and an indicator of severe anoxic disturbance "
                "in coastal sediment ecosystems."
            ),
            confidence_note=local_conf_note,
        ))

    elif indices.sci_risk == "High":
        recs.append(ManagementRecommendation(
            priority="P2 — Short-term Action",
            pathway="Sulfur Cycle",
            trigger_index=f"SCI = {indices.sci:.2f} ({indices.sci_risk} tier)",
            observation=(
                f"Elevated sulfur reduction pathway signal relative to oxidation: {indices.s_ratio_label}. "
                "Conditions are favorable for H₂S accumulation in deeper sediment layers."
            ),
            action=(
                "Flag the site for elevated chemical monitoring priority in the next assessment cycle. "
                "Correlate with upstream land use data (agricultural runoff, organic waste inputs). "
                "Consider porewater sampling in the next planned field visit."
            ),
            rationale=(
                "High SCI reflects a community functional state trending toward reductive sulfur conditions. "
                "Early identification allows prioritized chemical validation before conditions escalate."
            ),
            confidence_note=conf_note,
        ))

    if not indices.sci_signal_sufficient:
        recs.append(ManagementRecommendation(
            priority="P3 — Monitor",
            pathway="Sulfur Cycle",
            trigger_index=f"SCI = {indices.sci:.2f} — Low confidence: sulfur oxidation signal near zero",
            observation=(
                "Sulfur oxidation pathway signal is at or near the detection floor across all five FAPROTAX "
                "sulfur-oxidizing function categories (including light-independent dark oxidation terms). "
                "SCI may be elevated due to absent oxidation signal rather than confirmed reductive dominance."
            ),
            action=(
                "Interpret SCI with caution. Evaluate FAPROTAX community coverage for sulfur-oxidizing genera "
                "(e.g., Thiobacillus, Sulfurimonas) in the taxonomy inventory. "
                "Note this limitation in any derived conclusions."
            ),
            rationale=(
                "Even with five sulfur oxidation terms in the denominator (including light-independent ones), "
                "absence may reflect true community composition or FAPROTAX coverage gaps for this specific sediment type."
            ),
            confidence_note=conf_note,
        ))

    # ── Combined anoxic signal ───────────────────────────────────────────────

    if indices.asi_level == "Pervasive" and indices.mci_risk in ("High", "Critical"):
        priority = "P1 — Immediate Action"
        obs = (
            "Pervasive anoxic support pathway signal (dark hydrogen oxidation, iron respiration, "
            "fumarate respiration) co-occurs with high-to-critical methane production risk. "
            "This combined signature is consistent with an established anoxic microenvironment "
            "supporting both methanogenesis and iron/sulfur reduction concurrently."
        )
        local_conf_note = conf_note
        if not _has_high_confidence_signal(flags):
            priority = "P3 — Monitor"
            obs += " Downgraded from P1: all triggering functional assignments carry low or unassigned confidence. Chemical validation required before escalation."
        else:
            local_conf_note += " P1 Recommendation is strictly actionable for surface horizons (0–5 cm); elevated signals in deeper anaerobic subsurface strata are biogeochemically standard and represent natural stratification, not acute disturbance."
            
        recs.append(ManagementRecommendation(
            priority=priority,
            pathway="Anaerobic Conditions",
            trigger_index=f"ASI = {indices.asi:.3f} (Pervasive) + MCI = {indices.mci_risk}",
            observation=obs,
            action=(
                "Initiate a comprehensive sediment health assessment at this station. "
                "Collect surface and subsurface sediment cores (0–5 cm, 5–10 cm depth) for "
                "chemical profiling (dissolved gases, redox potential, organic carbon content). "
                "Prioritize this site in the next scheduled DENR monitoring campaign."
            ),
            rationale=(
                "The co-occurrence of high methanogenic signal with pervasive anoxic support pathways "
                "suggests stratified redox conditions typical of severely disturbed coastal sediments. "
                "This pattern warrants comprehensive assessment rather than single-pathway investigation."
            ),
            confidence_note=local_conf_note,
        ))

    # ── Diversity-based recommendation ──────────────────────────────────────

    if shannon < 1.5 and indices.mci_risk in ("Moderate", "High"):
        recs.append(ManagementRecommendation(
            priority="P2 — Short-term Action",
            pathway="Microbial Diversity",
            trigger_index=f"Shannon H' = {shannon:.3f} (Low diversity) + MCI {indices.mci_risk}",
            observation=(
                f"Low alpha diversity (H' = {shannon:.3f}) co-occurs with moderate-to-high methane "
                "production risk. Low diversity may reflect a community under stress, with functional "
                "redundancy reduced — making the system more sensitive to further perturbations."
            ),
            action=(
                "Establish this site as a diversity-recovery monitoring point. "
                "Schedule repeat sampling within 60–90 days to assess community trajectory. "
                "Consider correlating with any upstream disturbance events (flooding, runoff, land use change)."
            ),
            rationale=(
                "Low Shannon entropy combined with metabolic imbalance signals indicates a system with "
                "reduced ecological resilience. In this state, further environmental stressors are more "
                "likely to push the community toward dysbiosis."
            ),
            confidence_note=conf_note,
        ))

    # Sort by priority (P1 first)
    priority_order = {"P1 — Immediate Action": 0, "P2 — Short-term Action": 1, "P3 — Monitor": 2}
    recs.sort(key=lambda r: priority_order.get(r.priority, 3))

    return recs

# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC COMPUTE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def compute_descriptive(samples: List[SampleInput]) -> List[DescriptiveMetrics]:
    results = []
    for s in samples:
        vals = [g.abundance for g in s.genera]
        h = _shannon(vals)
        observed = sum(1 for v in vals if v > 0)

        enhanced_genera = []
        for g in s.genera:
            g.functions = faprotax_service.get_functions_for_taxa(g.lineage)
            enhanced_genera.append(g)

        sorted_genera = sorted(enhanced_genera, key=lambda g: g.abundance, reverse=True)
        results.append(DescriptiveMetrics(
            sample_id          = s.sample_id,
            shannon_entropy    = round(h, 4),
            observed_genera    = observed,
            total_genera       = len(vals),
            diversity_status   = _diversity_status(h),
            dominant_genus     = sorted_genera[0].genus if sorted_genera else "",
            dominant_abundance = round(sorted_genera[0].abundance, 4) if sorted_genera else 0.0,
            top10              = sorted_genera[:10],
        ))
    return results


def compute_diagnostic(
    samples: List[SampleInput],
    phylum_abundances: Optional[dict] = None,
    total_reads_map: Optional[Dict[str, int]] = None,
) -> List[DiagnosticResult]:
    """
    Evaluate genus-level AND phylum-level ecological thresholds per sample,
    then compute pathway bundles, cycling indices, confidence, and recommendations.

    Args:
        samples:           Genus-level SampleInput list.
        phylum_abundances: Optional {sample_id: {phylum_name: rel_abundance}}.
        total_reads_map:   Optional {sample_id: int} — total read counts per sample
                           for confidence depth computation.
    """
    # ── Phase 1: compute flags and stress levels for all samples ─────────────
    results: List[DiagnosticResult] = []
    shannon_map: Dict[str, float] = {}

    for s in samples:
        genus_map = {g.genus: g.abundance for g in s.genera}
        flags: List[FlagDetail] = []

        for t in GENUS_THRESHOLDS:
            val = genus_map.get(t["name"], 0.0)
            if _check_threshold(t, val):
                flags.append(_make_flag(t, val, t["name"]))

        if phylum_abundances and s.sample_id in phylum_abundances:
            phylum_map = phylum_abundances[s.sample_id]
            for t in PHYLUM_THRESHOLDS:
                all_names = [t["name"]] + t.get("aliases", [])
                val = max(phylum_map.get(n, 0.0) for n in all_names)
                if _check_threshold(t, val):
                    flags.append(_make_flag(t, val, t["name"]))

        level = _stress_level(flags)
        h = _shannon([g.abundance for g in s.genera])
        shannon_map[s.sample_id] = h

        results.append(DiagnosticResult(
            sample_id     = s.sample_id,
            stress_level  = level,
            stress_label  = STRESS_LABELS[level],
            critical_count= sum(1 for f in flags if f.severity == "critical"),
            warning_count = sum(1 for f in flags if f.severity == "warning"),
            flags         = flags,
        ))

    # ── Phase 2: compute pathway bundles and indices (needs cross-sample percentiles) ──
    bundles: Dict[str, PathwayBundle] = {}
    sample_map: Dict[str, SampleInput] = {s.sample_id: s for s in samples}

    for s in samples:
        bundles[s.sample_id] = compute_pathway_bundles(s)

    # Calibrate percentile thresholds across all samples in ALR space
    all_mci_raw = []
    all_sci_raw = []
    for b in bundles.values():
        raw_vec = [b.ch4_production, b.ch4_oxidation, b.s_reduction, b.s_oxidation, b.anoxic_support, b.aerobic_baseline]
        imputed = _impute_bundle_vector(raw_vec)
        all_mci_raw.append(math.log(imputed[0]) - math.log(imputed[1]))
        all_sci_raw.append(math.log(imputed[2]) - math.log(imputed[3]))
        
    mci_percentiles = calibrate_percentile_thresholds(all_mci_raw)
    sci_percentiles = calibrate_percentile_thresholds(all_sci_raw)

    # ── Phase 3: enrich each result ─────────────────────────────────────────
    # We first calculate indices for all samples so we can get composite risk scores
    all_results_indices = {}
    for result in results:
        sid = result.sample_id
        bundle = bundles[sid]
        all_results_indices[sid] = compute_cycling_indices(bundle, mci_percentiles, sci_percentiles)

    # Now we can compute the composite risk scores for consistency normalization
    all_risk_scores = []
    for result in results:
        sid = result.sample_id
        # Temporarily attach indices to use helper
        result.cycling_indices = all_results_indices[sid]
        all_risk_scores.append(_composite_risk_score(result))

    for result in results:
        sid = result.sample_id
        bundle = bundles[sid]
        s = sample_map[sid]
        h = shannon_map[sid]
        reads = (total_reads_map or {}).get(sid)

        indices = all_results_indices[sid]
        confidence = compute_confidence(s, h, reads, all_risk_scores)
        recs = derive_recommendations(indices, confidence, h, result.flags)

        result.pathway_bundle  = bundle
        result.cycling_indices = indices
        result.confidence      = confidence
        result.recommendations = recs

    # ── Phase 4: cross-sample trajectory (set on all results) ───────────────
    trajectory = compute_trajectory(results)
    if trajectory:
        for result in results:
            result.trajectory = trajectory

    return results
