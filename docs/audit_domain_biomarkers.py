#!/usr/bin/env python3
"""
AUDIT TOOL: Domain-Specific Biomarker Detection
===============================================

Detects:
- SOIL microbiota biomarkers (Actinomycetota, Acidobacteriota, N-fixers)
- COASTAL sediment biomarkers (Desulfobacterales, Bacteroidales, sulfur-cycling)
- Domain mismatch warnings
- Unusual ecological patterns
"""

import sys
import logging
from pathlib import Path
from typing import Tuple, Dict, List
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# BIOMARKER DATABASES
# ══════════════════════════════════════════════════════════════════════════════

SOIL_BIOMARKERS = {
    'Actinomycetota': {
        'threshold': 0.01,  # 1% minimum
        'description': 'Soil carbon cycling, secondary metabolite producers',
        'strong_range': (0.10, 0.60),  # 10-60% indicates stable soil
    },
    'Acidobacteriota': {
        'threshold': 0.01,  # 1% minimum
        'description': 'Acidic soil indicator, nutrient-poor soils',
        'strong_range': (0.05, 0.40),
    },
    'Bacillota': {
        'threshold': 0.001,  # 0.1% minimum
        'description': 'Spore-forming bacteria, stress resilience',
        'strong_range': (0.005, 0.10),
    },
}

SOIL_ORDERS_NITROGEN_FIXING = [
    'Rhizobiales',
    'Burkholderiales',
    'Nostocales',
    'Chloroflexales',
]

COASTAL_BIOMARKERS = {
    'Desulfobacterota': {
        'threshold': 0.001,  # 0.1% minimum
        'description': 'Sulfate-reducing bacteria (anaerobic sulfur cycling)',
        'strong_range': (0.02, 0.30),  # >2% indicates strong anaerobic conditions
    },
    'Bacteroidota': {
        'threshold': 0.01,  # 1% minimum
        'description': 'DMSP degradation, algal polysaccharide breakdown',
        'strong_range': (0.05, 0.40),
    },
    'Firmicutes': {
        'threshold': 0.001,  # 0.1% minimum
        'description': 'Fermentation under hypoxia, sulfide production',
        'strong_range': (0.01, 0.15),
    },
}

COASTAL_ORDERS_SULFUR_CYCLING = [
    'Desulfobacterales',
    'Desulfovibrionales',
    'Syntrophobacterales',
    'Desulfuromonadales',
]

# ══════════════════════════════════════════════════════════════════════════════
# BIOMARKER DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def detect_soil_biomarkers(tax_df: pd.DataFrame, asv_df: pd.DataFrame, 
                          asv_id_col: str, sample_cols: list) -> Dict:
    """Detect soil-specific biomarkers."""
    
    print("\n" + "="*80)
    print("TIER 3+: SOIL MICROBIOME BIOMARKER DETECTION")
    print("="*80)
    
    results = {
        'detected_biomarkers': [],
        'missing_biomarkers': [],
        'warnings': [],
        'assessment': 'NEUTRAL',
    }
    
    # Normalize abundance data
    merged = asv_df.set_index(asv_id_col).merge(
        tax_df.set_index(tax_df.columns[0])[['phylum', 'order']].rename(columns={tax_df.columns[0]: asv_id_col}),
        left_index=True,
        right_index=True,
        how='left'
    )
    
    # Calculate relative abundance per sample
    sample_totals = asv_df[sample_cols].sum()
    
    # Check for each soil biomarker
    for phylum, biomarker_info in SOIL_BIOMARKERS.items():
        phylum_rows = tax_df[tax_df['phylum'].str.lower() == phylum.lower()]
        
        if len(phylum_rows) > 0:
            # Sum abundance for this phylum
            phylum_asv_ids = phylum_rows[tax_df.columns[0]].astype(str)
            relevant_rows = asv_df[asv_df[asv_id_col].astype(str).isin(phylum_asv_ids)]
            
            if len(relevant_rows) > 0:
                phylum_counts = relevant_rows[sample_cols].sum()
                relative_abundance = (phylum_counts / sample_totals).mean()
                
                if relative_abundance >= biomarker_info['threshold']:
                    logger.info(f"✅ DETECTED: {phylum}")
                    logger.info(f"           Relative abundance: {relative_abundance*100:.2f}%")
                    logger.info(f"           {biomarker_info['description']}")
                    results['detected_biomarkers'].append({
                        'phylum': phylum,
                        'relative_abundance': relative_abundance,
                        'info': biomarker_info,
                    })
                else:
                    logger.warning(f"⚠️  LOW: {phylum} ({relative_abundance*100:.2f}%)")
                    results['missing_biomarkers'].append(phylum)
            else:
                logger.warning(f"⚠️  ABSENT: {phylum}")
                results['missing_biomarkers'].append(phylum)
        else:
            logger.warning(f"⚠️  NOT IN TAXONOMY: {phylum}")
            results['missing_biomarkers'].append(phylum)
    
    # Check for nitrogen-fixing capability
    nfix_orders = tax_df[tax_df['order'].str.lower().isin([o.lower() for o in SOIL_ORDERS_NITROGEN_FIXING])]
    if len(nfix_orders) > 0:
        logger.info(f"✅ N-FIXING POTENTIAL: {len(nfix_orders)} ASVs (nitrogen-cycling capability)")
        results['detected_biomarkers'].append({
            'marker': 'Nitrogen-fixing orders',
            'count': len(nfix_orders),
        })
    
    # Assessment
    if len(results['detected_biomarkers']) >= 2:
        results['assessment'] = 'SOIL_MICROBIOTA'
        logger.info(f"\n🟢 ASSESSMENT: Consistent with SOIL microbiota")
    elif len(results['detected_biomarkers']) == 1:
        results['assessment'] = 'LIKELY_SOIL'
        logger.info(f"\n🟡 ASSESSMENT: Possible soil microbiota (1/3 major biomarkers)")
    else:
        results['assessment'] = 'DOMAIN_MISMATCH'
        results['warnings'].append(
            "POTENTIAL DOMAIN MISMATCH: Expected soil biomarkers "
            "(Actinomycetota, Acidobacteriota) are absent. "
            "Verify sample type matches uploaded data."
        )
        logger.error(f"\n🔴 ALERT: DOMAIN MISMATCH - No soil biomarkers detected")
    
    return results

def detect_coastal_biomarkers(tax_df: pd.DataFrame, asv_df: pd.DataFrame,
                             asv_id_col: str, sample_cols: list) -> Dict:
    """Detect coastal/marine sediment biomarkers."""
    
    print("\n" + "="*80)
    print("TIER 3+: COASTAL SEDIMENT BIOMARKER DETECTION")
    print("="*80)
    
    results = {
        'detected_biomarkers': [],
        'missing_biomarkers': [],
        'warnings': [],
        'assessment': 'NEUTRAL',
    }
    
    # Normalize abundance data
    sample_totals = asv_df[sample_cols].sum()
    
    # Check for each coastal biomarker
    for phylum, biomarker_info in COASTAL_BIOMARKERS.items():
        phylum_rows = tax_df[tax_df['phylum'].str.lower() == phylum.lower()]
        
        if len(phylum_rows) > 0:
            # Sum abundance for this phylum
            phylum_asv_ids = phylum_rows[tax_df.columns[0]].astype(str)
            relevant_rows = asv_df[asv_df[asv_id_col].astype(str).isin(phylum_asv_ids)]
            
            if len(relevant_rows) > 0:
                phylum_counts = relevant_rows[sample_cols].sum()
                relative_abundance = (phylum_counts / sample_totals).mean()
                
                if relative_abundance >= biomarker_info['threshold']:
                    logger.info(f"✅ DETECTED: {phylum}")
                    logger.info(f"           Relative abundance: {relative_abundance*100:.2f}%")
                    logger.info(f"           {biomarker_info['description']}")
                    results['detected_biomarkers'].append({
                        'phylum': phylum,
                        'relative_abundance': relative_abundance,
                        'info': biomarker_info,
                    })
                    
                    # Special note for high Desulfobacterota
                    if phylum == 'Desulfobacterota' and relative_abundance > 0.05:
                        logger.info(f"           ⚠️  HIGH SULFATE REDUCTION: Strong anaerobic conditions")
                else:
                    logger.warning(f"⚠️  LOW: {phylum} ({relative_abundance*100:.2f}%)")
                    results['missing_biomarkers'].append(phylum)
            else:
                logger.warning(f"⚠️  ABSENT: {phylum}")
                results['missing_biomarkers'].append(phylum)
        else:
            logger.warning(f"⚠️  NOT IN TAXONOMY: {phylum}")
            results['missing_biomarkers'].append(phylum)
    
    # Check for sulfur-cycling capability
    sulfur_orders = tax_df[tax_df['order'].str.lower().isin([o.lower() for o in COASTAL_ORDERS_SULFUR_CYCLING])]
    if len(sulfur_orders) > 0:
        logger.info(f"✅ SULFUR-CYCLING POTENTIAL: {len(sulfur_orders)} ASVs (sulfur metabolism)")
        results['detected_biomarkers'].append({
            'marker': 'Sulfur-cycling orders',
            'count': len(sulfur_orders),
        })
    
    # Assessment
    if len(results['detected_biomarkers']) >= 2:
        results['assessment'] = 'COASTAL_SEDIMENT'
        logger.info(f"\n🟢 ASSESSMENT: Consistent with COASTAL SEDIMENT microbiota")
    elif len(results['detected_biomarkers']) == 1:
        results['assessment'] = 'LIKELY_COASTAL'
        logger.info(f"\n🟡 ASSESSMENT: Possible coastal microbiota (1/3 major biomarkers)")
    else:
        results['assessment'] = 'DOMAIN_MISMATCH'
        results['warnings'].append(
            "POTENTIAL DOMAIN MISMATCH: Expected coastal biomarkers "
            "(Desulfobacterales, Bacteroidales) are absent. "
            "Verify sample type matches uploaded data."
        )
        logger.error(f"\n🔴 ALERT: DOMAIN MISMATCH - No coastal biomarkers detected")
    
    return results

# ══════════════════════════════════════════════════════════════════════════════
# MAIN DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def detect_domain(asv_path: str, tax_path: str, expected_domain: str = None) -> int:
    """Detect and validate sample domain."""
    
    print("\n" + "="*80)
    print("GENOMIC INTELLIGENCE SYSTEM - DOMAIN-SPECIFIC BIOMARKER AUDIT")
    print("="*80)
    
    asv_path = Path(asv_path)
    tax_path = Path(tax_path)
    
    if not asv_path.exists() or not tax_path.exists():
        logger.error("Files not found")
        return 1
    
    # Load data
    asv_df = pd.read_csv(asv_path)
    tax_df = pd.read_csv(tax_path)
    
    asv_id_col = asv_df.columns[0]
    sample_cols = [c for c in asv_df.columns if c != asv_id_col]
    
    # Standardize taxonomy column names
    tax_df.columns = [c.lower() for c in tax_df.columns]
    
    # Run both detections
    soil_results = detect_soil_biomarkers(tax_df, asv_df, asv_id_col, sample_cols)
    
    print("\n")
    coastal_results = detect_coastal_biomarkers(tax_df, asv_df, asv_id_col, sample_cols)
    
    # Summary
    print("\n" + "="*80)
    print("DOMAIN DETECTION SUMMARY")
    print("="*80)
    
    print(f"\nSOIL Assessment: {soil_results['assessment']}")
    print(f"  Detected: {len(soil_results['detected_biomarkers'])} biomarkers")
    
    print(f"\nCOASTAL Assessment: {coastal_results['assessment']}")
    print(f"  Detected: {len(coastal_results['detected_biomarkers'])} biomarkers")
    
    # Determine best match
    soil_score = len(soil_results['detected_biomarkers'])
    coastal_score = len(coastal_results['detected_biomarkers'])
    
    if soil_score > coastal_score:
        print(f"\n🟢 INFERRED DOMAIN: SOIL MICROBIOTA")
        inferred = 'SOIL'
    elif coastal_score > soil_score:
        print(f"\n🟢 INFERRED DOMAIN: COASTAL SEDIMENT")
        inferred = 'COASTAL'
    else:
        print(f"\n🟡 INCONCLUSIVE: Both domains equally scored")
        inferred = 'UNKNOWN'
    
    # Validate against expected domain
    if expected_domain:
        if expected_domain.upper() == inferred:
            print(f"\n✅ VALIDATION PASS: Inferred domain matches expected '{expected_domain}'")
            return 0
        else:
            print(f"\n❌ VALIDATION FAIL: Inferred domain '{inferred}' != expected '{expected_domain}'")
            return 1
    
    return 0

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python audit_domain_biomarkers.py <asv_path> <tax_path> [expected_domain]")
        print("Example: python audit_domain_biomarkers.py data/asv.csv data/tax.csv SOIL")
        sys.exit(1)
    
    expected = sys.argv[3] if len(sys.argv) > 3 else None
    exit_code = detect_domain(sys.argv[1], sys.argv[2], expected)
    sys.exit(exit_code)
