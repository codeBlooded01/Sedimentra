"""
AD-GSI v4.0 — Multi-Layer Data Defense & Sequence Audit
========================================================

Phase 1: Multi-Layer Data Defense

Implements:
- Per-sample sequence distribution audit (median, std dev, read count)
- Zero-tolerance duplicate ID detection
- Hard failures for data integrity violations
- Comprehensive audit logging
"""

import logging
from typing import Dict, Tuple, List, Set
from dataclasses import dataclass
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# AUDIT RESULT MODEL
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PerSampleAudit:
    """Audit results for a single sample."""
    sample_id: str
    total_reads: int
    asv_count: int
    median_bp: float
    std_dev: float
    read_distribution: Dict  # For detailed logging
    
    # Validation results
    passes_read_threshold: bool  # > 50
    passes_median_constraint: bool  # 350-500bp
    passes_std_dev_constraint: bool  # σ ≤ 50bp
    
    # Violations
    violations: List[str] = None
    
    def __post_init__(self):
        if self.violations is None:
            self.violations = []
    
    @property
    def is_valid(self) -> bool:
        """All constraints satisfied."""
        return (self.passes_read_threshold and 
                self.passes_median_constraint and 
                self.passes_std_dev_constraint and
                len(self.violations) == 0)
    
    def add_violation(self, message: str):
        """Record a constraint violation."""
        self.violations.append(message)

# ══════════════════════════════════════════════════════════════════════════════
# DUPLICATE DETECTION
# ══════════════════════════════════════════════════════════════════════════════

class DuplicateDetector:
    """Zero-tolerance duplicate ID detection."""
    
    @staticmethod
    def check_ast_ids(asv_table: pd.DataFrame, id_column: str) -> Tuple[bool, List[str]]:
        """
        Check for duplicate ASV IDs in abundance table.
        
        Loophole: If ASV_001 appears twice with different abundances,
        summing could hide a data entry error.
        
        Returns: (is_clean, duplicates_found)
        """
        duplicates = asv_table[id_column].duplicated(keep=False)
        if duplicates.any():
            dup_ids = asv_table[duplicates][id_column].unique().tolist()
            return False, dup_ids
        
        return True, []
    
    @staticmethod
    def check_taxonomy_ids(tax_table: pd.DataFrame, id_column: str) -> Tuple[bool, List[str]]:
        """Check for duplicate ASV IDs in taxonomy table."""
        duplicates = tax_table[id_column].duplicated(keep=False)
        if duplicates.any():
            dup_ids = tax_table[duplicates][id_column].unique().tolist()
            return False, dup_ids
        
        return True, []
    
    @staticmethod
    def check_sample_asv_uniqueness(
        asv_table: pd.DataFrame,
        id_column: str,
        sample_columns: List[str],
    ) -> Tuple[bool, List[str]]:
        """
        Check that each (ASV_ID, Sample_ID) pair is unique.
        
        Build a "melt" of the table and check for duplicate combinations.
        """
        # Create ASV_ID/Sample/Count triplets
        melted = asv_table.melt(
            id_vars=[id_column],
            value_vars=sample_columns,
            var_name='sample_id',
            value_name='count'
        )
        
        # Check for duplicates in (asv_id, sample_id) combinations
        combo_duplicates = melted.duplicated(subset=[id_column, 'sample_id'], keep=False)
        
        if combo_duplicates.any():
            dup_combos = melted[combo_duplicates][[id_column, 'sample_id']].values.tolist()
            return False, dup_combos
        
        return True, []

# ══════════════════════════════════════════════════════════════════════════════
# SEQUENCE DISTRIBUTION AUDIT
# ══════════════════════════════════════════════════════════════════════════════

class SequenceAuditor:
    """Per-sample sequence distribution audit."""
    
    # Constraints (hardcoded for V3-V4 16S)
    MEDIAN_MIN_BP = 350
    MEDIAN_MAX_BP = 500
    STD_DEV_MAX = 50  # σ ≤ 50bp
    READ_COUNT_MIN = 50  # per sample
    
    @classmethod
    def audit_sample(
        cls,
        sample_id: str,
        asv_lengths: np.ndarray,  # Sequence lengths in bp
        asv_abundances: np.ndarray,  # Counts per ASV
    ) -> PerSampleAudit:
        """
        Audit a single sample's sequence distribution.
        
        Calculate weighted median and std dev of sequence lengths.
        """
        total_reads = asv_abundances.sum()
        asv_count = len(asv_abundances)
        
        # Violations list
        violations = []
        
        # Check 1: Total reads
        passes_read_threshold = total_reads >= cls.READ_COUNT_MIN
        if not passes_read_threshold:
            violations.append(
                f"Total reads ({total_reads}) < threshold ({cls.READ_COUNT_MIN})"
            )
        
        # Weighted statistics
        if total_reads > 0:
            # Weighted median
            sorted_indices = np.argsort(asv_lengths)
            sorted_lengths = asv_lengths[sorted_indices]
            sorted_counts = asv_abundances[sorted_indices]
            
            cumsum = np.cumsum(sorted_counts)
            median_idx = np.searchsorted(cumsum, total_reads / 2.0)
            median_bp = float(sorted_lengths[min(median_idx, len(sorted_lengths) - 1)])
            
            # Weighted std dev
            mean_bp = np.average(asv_lengths, weights=asv_abundances)
            variance = np.average((asv_lengths - mean_bp) ** 2, weights=asv_abundances)
            std_dev = np.sqrt(variance)
        else:
            median_bp = 0.0
            std_dev = 0.0
        
        # Check 2: Median constraint
        passes_median_constraint = (cls.MEDIAN_MIN_BP <= median_bp <= cls.MEDIAN_MAX_BP)
        if not passes_median_constraint:
            violations.append(
                f"Median length {median_bp:.1f}bp outside range [{cls.MEDIAN_MIN_BP}, {cls.MEDIAN_MAX_BP}]"
            )
        
        # Check 3: Std dev constraint
        passes_std_dev_constraint = std_dev <= cls.STD_DEV_MAX
        if not passes_std_dev_constraint:
            violations.append(
                f"Standard deviation {std_dev:.1f}bp exceeds max {cls.STD_DEV_MAX}bp"
            )
        
        audit = PerSampleAudit(
            sample_id=sample_id,
            total_reads=int(total_reads),
            asv_count=asv_count,
            median_bp=round(median_bp, 2),
            std_dev=round(std_dev, 2),
            read_distribution={
                'mean': round(np.average(asv_lengths, weights=asv_abundances), 2),
                'min': int(asv_lengths.min()),
                'max': int(asv_lengths.max()),
            },
            passes_read_threshold=passes_read_threshold,
            passes_median_constraint=passes_median_constraint,
            passes_std_dev_constraint=passes_std_dev_constraint,
        )
        
        audit.violations = violations
        
        return audit

# ══════════════════════════════════════════════════════════════════════════════
# ZERO-TOLERANCE DATA DEFENSE
# ══════════════════════════════════════════════════════════════════════════════

class DataDefense:
    """Fail-fast, fail-loud data defense system."""
    
    class ValidationError(Exception):
        """Hard failure exception."""
        pass
    
    @staticmethod
    def check_total_reads_per_sample(
        asv_table: pd.DataFrame,
        id_column: str,
        sample_columns: List[str],
    ) -> Dict[str, int]:
        """
        Hard Fail if any sample has zero total reads.
        
        Returns: {sample_id: total_reads}
        """
        sample_totals = {}
        zero_samples = []
        
        for sample_col in sample_columns:
            total = asv_table[sample_col].sum()
            sample_totals[sample_col] = total
            
            if total == 0:
                zero_samples.append(sample_col)
        
        if zero_samples:
            raise DataDefense.ValidationError(
                f"HARD FAIL: {len(zero_samples)} samples have zero total reads: {zero_samples}"
            )
        
        return sample_totals
    
    @staticmethod
    def check_duplicate_asv_tax_mapping(
        asv_ids: Set[str],
        tax_ids: Set[str],
    ) -> None:
        """
        Hard Fail if any taxonomy IDs lack abundance data.
        
        Checks: set(ASV_tax) - set(ASV_table) > 0
        """
        reverse_orphans = tax_ids - asv_ids
        
        if reverse_orphans:
            raise DataDefense.ValidationError(
                f"HARD FAIL: {len(reverse_orphans)} taxonomy entries lack abundance data. "
                f"Sample IDs: {list(reverse_orphans)[:5]}"
            )
    
    @staticmethod
    def check_relative_abundance_normalization(
        relative_abundances: Dict[str, np.ndarray],
    ) -> None:
        """
        Hard Fail if normalized abundance doesn't sum to ~1.0 per sample.
        
        Enforces: sum(relative_abundance) ≈ 1.0
        """
        tolerance = 1e-6
        
        for sample_id, rel_abund in relative_abundances.items():
            total = rel_abund.sum()
            
            if abs(total - 1.0) > tolerance:
                raise DataDefense.ValidationError(
                    f"HARD FAIL: Sample '{sample_id}' relative abundance sums to {total:.6f} "
                    f"(expected 1.0 ± {tolerance})"
                )

# ══════════════════════════════════════════════════════════════════════════════
# AUDIT REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class AuditReport:
    """Generate comprehensive audit report."""
    
    @staticmethod
    def generate(
        sample_audits: List[PerSampleAudit],
        duplicate_asvs: List[str],
        duplicate_tax: List[str],
    ) -> Dict:
        """Generate audit report for job."""
        
        failed_samples = [a for a in sample_audits if not a.is_valid]
        passed_samples = [a for a in sample_audits if a.is_valid]
        
        report = {
            'total_samples': len(sample_audits),
            'passed_samples': len(passed_samples),
            'failed_samples': len(failed_samples),
            'overall_status': 'PASS' if len(failed_samples) == 0 else 'FAIL',
            
            'duplicate_asv_ids': duplicate_asvs,
            'duplicate_tax_ids': duplicate_tax,
            
            'violations_by_type': {
                'zero_reads': len([a for a in failed_samples 
                                  if not a.passes_read_threshold]),
                'seq_length_median': len([a for a in failed_samples 
                                         if not a.passes_median_constraint]),
                'seq_length_std_dev': len([a for a in failed_samples 
                                          if not a.passes_std_dev_constraint]),
            },
            
            'sample_details': [
                {
                    'sample_id': a.sample_id,
                    'total_reads': a.total_reads,
                    'median_bp': a.median_bp,
                    'std_dev': a.std_dev,
                    'status': 'PASS' if a.is_valid else 'FAIL',
                    'violations': a.violations,
                }
                for a in sample_audits
            ],
        }
        
        return report
