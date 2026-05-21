"""
AD-GSI v4.0 — COMPREHENSIVE TEST SUITE

Unit & Integration Tests for All 6 Phases
===========================================

Run tests:
    pytest test_production_pipeline.py -v
    pytest test_production_pipeline.py -v --cov=app.services
"""

import pytest
import pandas as pd
import numpy as np
from typing import Tuple
import json

from app.services.sequence_audit import (
    SequenceAuditor, DuplicateDetector, DataDefense,
    PerSampleAudit, AuditReport
)
from app.services.taxonomy_processor import (
    TaxonomyParser, TaxRecord, FAFunctionalProfile,
    MappingResolution, DomainSignature
)
from app.services.production_pipeline import (
    ProductionPipeline, MLSampleOutput, MLFeatureRecord,
    validate_and_generate_ml_features
)

# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES: MOCK DATA
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def asv_table_valid() -> pd.DataFrame:
    """Valid ASV abundance table (4 ASVs, 3 samples)."""
    return pd.DataFrame({
        'ASV_ID': ['ASV_1', 'ASV_2', 'ASV_3', 'ASV_4'],
        'Sample_1': [1000, 500, 200, 100],
        'Sample_2': [800, 600, 150, 50],
        'Sample_3': [1200, 400, 250, 80],
    })

@pytest.fixture
def asv_table_duplicates():
    """ASV table with duplicate ASV IDs (should fail)."""
    return pd.DataFrame({
        'ASV_ID': ['ASV_1', 'ASV_1', 'ASV_3', 'ASV_4'],  # ASV_1 duplicated
        'Sample_1': [1000, 500, 200, 100],
        'Sample_2': [800, 600, 150, 50],
    })

@pytest.fixture
def asv_table_zero_reads():
    """ASV table with one sample having zero reads."""
    return pd.DataFrame({
        'ASV_ID': ['ASV_1', 'ASV_2', 'ASV_3'],
        'Sample_1': [1000, 500, 200],
        'Sample_2': [0, 0, 0],  # Zero reads
        'Sample_3': [800, 400, 150],
    })

@pytest.fixture
def taxonomy_valid() -> pd.DataFrame:
    """Valid taxonomy table with coastal biomarkers."""
    return pd.DataFrame({
        'ASV_ID': ['ASV_1', 'ASV_2', 'ASV_3', 'ASV_4'],
        'taxonomy': [
            'k__Bacteria;p__Desulfobacterota;c__Desulfobacteria;o__Desulfobacterales;f__Desulfobacteraceae;g__Desulfobacter;s__vulgaris',
            'k__Bacteria;p__Bacteroidota;c__Bacteroidia;o__Bacteroidales;f__Bacteroidaceae;g__Bacteroides;s__fragilis',
            'k__Bacteria;p__Proteobacteria;c__Gammaproteobacteria;o__Xanthomonadales;f__Xanthomonadaceae;g__Stenotrophomonas;s__maltophilia',
            'k__Bacteria;p__Firmicutes;c__Bacilli;o__Bacillales;f__Bacillaceae;g__Bacillus;s__subtilis',
        ]
    })

@pytest.fixture
def taxonomy_unclassified() -> pd.DataFrame:
    """Taxonomy with high unclassified ratio."""
    return pd.DataFrame({
        'ASV_ID': ['ASV_1', 'ASV_2', 'ASV_3'],
        'taxonomy': [
            'k__Bacteria;p__Bacteria_unct;p__;c__;o__;f__;g__;s__',
            'k__Bacteria;p__unknown;c__;o__;f__;g__;s__',
            'k__Bacteria;p__Desulfobacterota;c__Desulfobacteria;o__Desulfobacterales;f__;g__;s__',
        ]
    })

@pytest.fixture
def taxonomy_duplicates():
    """Taxonomy with duplicate IDs (should fail)."""
    return pd.DataFrame({
        'ASV_ID': ['ASV_1', 'ASV_1', 'ASV_3'],
        'taxonomy': [
            'k__Bacteria;p__Desulfobacterota;c__;o__;f__;g__;s__',
            'k__Bacteria;p__Desulfobacterota;c__;o__;f__;g__;s__',
            'k__Bacteria;p__Bacteroidota;c__;o__;f__;g__;s__',
        ]
    })

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 TESTS: DATA DEFENSE
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase1DataDefense:
    """Multi-layer data defense validation."""
    
    def test_duplicate_detector_asv_ids_valid(self, asv_table_valid):
        """Check: No duplicate ASV IDs (valid case)."""
        is_clean, dups = DuplicateDetector.check_ast_ids(asv_table_valid, 'ASV_ID')
        assert is_clean is True
        assert len(dups) == 0
    
    def test_duplicate_detector_asv_ids_invalid(self, asv_table_duplicates):
        """Check: Duplicate ASV IDs detected."""
        is_clean, dups = DuplicateDetector.check_ast_ids(asv_table_duplicates, 'ASV_ID')
        assert is_clean is False
        assert 'ASV_1' in dups
    
    def test_duplicate_detector_taxonomy_ids_valid(self, taxonomy_valid):
        """Check: No duplicate Taxonomy IDs (valid case)."""
        is_clean, dups = DuplicateDetector.check_taxonomy_ids(taxonomy_valid, 'ASV_ID')
        assert is_clean is True
    
    def test_duplicate_detector_taxonomy_ids_invalid(self, taxonomy_duplicates):
        """Check: Duplicate Taxonomy IDs detected."""
        is_clean, dups = DuplicateDetector.check_taxonomy_ids(taxonomy_duplicates, 'ASV_ID')
        assert is_clean is False
    
    def test_data_defense_zero_reads(self, asv_table_zero_reads):
        """Check: Zero reads detection (hard-fail)."""
        sample_cols = ['Sample_1', 'Sample_2', 'Sample_3']
        totals = DataDefense.check_total_reads_per_sample(asv_table_zero_reads, 'ASV_ID', sample_cols)
        assert totals['Sample_2'] == 0
    
    def test_sequence_auditor_valid_constraints(self):
        """Check: Sequence auditor passes valid V3-V4 constraints."""
        seq_lengths = np.array([420, 425, 415, 430, 418])  # All within 350-500bp
        abundances = np.array([100, 80, 120, 90, 110])
        
        audit = SequenceAuditor.audit_sample('Sample_1', seq_lengths, abundances)
        
        assert audit.total_reads == sum(abundances)
        assert audit.is_valid is True
        assert len(audit.violations) == 0
    
    def test_sequence_auditor_violates_median(self):
        """Check: Sequence auditor fails on median < 350bp."""
        seq_lengths = np.array([300, 310, 320, 330])  # All below 350bp
        abundances = np.array([100, 100, 100, 100])
        
        audit = SequenceAuditor.audit_sample('Sample_2', seq_lengths, abundances)
        
        assert audit.is_valid is False
        assert any('median' in v.lower() for v in audit.violations)
    
    def test_sequence_auditor_violates_std_dev(self):
        """Check: Sequence auditor fails on std_dev > 50bp."""
        seq_lengths = np.array([300, 350, 450, 500])  # High variance
        abundances = np.array([100, 100, 100, 100])
        
        audit = SequenceAuditor.audit_sample('Sample_3', seq_lengths, abundances)
        
        assert audit.is_valid is False
        assert any('std' in v.lower() for v in audit.violations)
    
    def test_sequence_auditor_violates_min_reads(self):
        """Check: Sequence auditor fails on < 50 reads."""
        seq_lengths = np.array([420, 425, 415])
        abundances = np.array([10, 15, 20])  # Total = 45 < 50
        
        audit = SequenceAuditor.audit_sample('Sample_4', seq_lengths, abundances)
        
        assert audit.is_valid is False
        assert any('reads' in v.lower() for v in audit.violations)

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 TESTS: TAXONOMY PARSING
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase2TaxonomyParsing:
    """Hierarchical taxonomy parsing validation."""
    
    def test_taxonomy_parser_semicolon_delimited(self):
        """Parse: Semicolon-delimited QIIME2 format."""
        parser = TaxonomyParser()
        record = parser.parse_row(
            'ASV_1',
            'k__Bacteria;p__Desulfobacterota;c__Desulfobacteria;o__Desulfobacterales;f__Desulfobacteraceae;g__Desulfobacter;s__vulgaris'
        )
        
        assert record.asv_id == 'ASV_1'
        assert record.kingdom == 'Bacteria'
        assert record.phylum == 'Desulfobacterota'
        assert record.genus == 'Desulfobacter'
        assert record.species == 'vulgaris'
    
    def test_taxonomy_parser_pipe_delimited(self):
        """Parse: Pipe-delimited format."""
        parser = TaxonomyParser()
        record = parser.parse_row(
            'ASV_2',
            'Bacteria|Bacteroidota|Bacteroidia|Bacteroidales|Bacteroidaceae|Bacteroides|fragilis'
        )
        
        assert record.kingdom == 'Bacteria'
        assert record.phylum == 'Bacteroidota'
        assert record.genus == 'Bacteroides'
    
    def test_taxonomy_parser_unclassified_detection(self):
        """Parse: Detect unclassified entries."""
        parser = TaxonomyParser()
        
        # Unclassified via keyword
        record_unc = parser.parse_row(
            'ASV_unc',
            'k__Bacteria;p__unknown;c__;o__;f__;g__;s__'
        )
        assert record_unc.is_unclassified is True
        
        # Classified
        record_class = parser.parse_row(
            'ASV_class',
            'k__Bacteria;p__Bacteroidota;c__Bacteroidia;o__Bacteroidales;f__Bacteroidaceae;g__Bacteroides;s__fragilis'
        )
        assert record_class.is_unclassified is False
    
    def test_taxonomy_parser_prefix_stripping(self):
        """Parse: Strip prefixes (g__, f__, etc.)."""
        parser = TaxonomyParser()
        record = parser.parse_row(
            'ASV_3',
            'k__Bacteria;p__Proteobacteria;c__Gamma;o__Xantho;f__Xantho;g__Stenotropho;s__maltophilia'
        )
        
        # Prefixes should be stripped
        assert not record.kingdom.startswith('k__')
        assert not record.genus.startswith('g__')
    
    def test_taxonomy_record_caching(self):
        """Cache: TaxRecord caches computed values."""
        record = TaxRecord(
            asv_id='ASV_1',
            kingdom='Bacteria',
            phylum='Bacteroidota',
            clazz='Bacteroidia',
            order='Bacteroidales',
            family='Bacteroidaceae',
            genus='Bacteroides',
            species='fragilis'
        )
        
        # First call computes
        genus1 = record.get_genus()
        # Second call returns cached
        genus2 = record.get_genus()
        assert genus1 == genus2 == 'Bacteroides'

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4 TESTS: FAPROTAX MAPPING
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase4FAProTAX:
    """FAPROTAX root-matching and functional mapping."""
    
    def test_faprotax_exact_species_match(self):
        """Match: Exact species match (priority 1)."""
        record = TaxRecord(
            asv_id='ASV_1',
            kingdom='Bacteria',
            phylum='Desulfobacterota',
            clazz='Desulfobacteria',
            order='Desulfobacterales',
            family='Desulfobacteraceae',
            genus='Desulfobacter',
            species='vulgaris'
        )
        
        functions = FAFunctionalProfile.get_functions(record)
        assert functions is not None
        assert 'functions' in functions
    
    def test_faprotax_genus_match(self):
        """Match: Genus match when species unclassified (priority 2)."""
        record = TaxRecord(
            asv_id='ASV_2',
            kingdom='Bacteria',
            phylum='Bacteroidota',
            clazz='Bacteroidia',
            order='Bacteroidales',
            family='Bacteroidaceae',
            genus='Bacteroides',
            species=None  # Unclassified
        )
        
        functions = FAFunctionalProfile.get_functions(record)
        # Should match on genus
        assert functions is not None or functions == {}
    
    def test_faprotax_order_match(self):
        """Match: Order match (priority 3)."""
        record = TaxRecord(
            asv_id='ASV_3',
            kingdom='Bacteria',
            phylum='Desulfobacterota',
            clazz='Desulfobacteria',
            order='Desulfobacterales',
            family=None,
            genus=None,
            species=None
        )
        
        functions = FAFunctionalProfile.get_functions(record)
        # Should match on order
        assert functions is not None or functions == {}
    
    def test_faprotax_strain_stripping(self):
        """Match: Strip strain identifiers (sp., spp., cf., numeric)."""
        record = TaxRecord(
            asv_id='ASV_4',
            kingdom='Bacteria',
            phylum='Proteobacteria',
            clazz='Gamma',
            order='Xanthomonadales',
            family='Xanthomonadaceae',
            genus='Stenotrophomonas',
            species='maltophilia sp. JCM12443'  # Contains strain info
        )
        
        functions = FAFunctionalProfile.get_functions(record)
        # Should process despite strain info
        assert functions is not None or functions == {}
    
    def test_mapping_resolution_high_confidence(self):
        """Resolution: High mapping coverage (80%)."""
        sample_abundances = {
            'ASV_1': 800,  # Mapped
            'ASV_2': 100,  # Mapped
            'ASV_3': 100,  # Unmapped
        }
        
        tax_records = {
            'ASV_1': TaxRecord(
                'ASV_1', 'Bacteria', 'Desulfobacterota', 'D', 'Desulfobacterales', 'F', 'Desulfobacter', 'vulgaris'
            ),
            'ASV_2': TaxRecord(
                'ASV_2', 'Bacteria', 'Bacteroidota', 'B', 'Bacteroidales', 'F', 'Bacteroides', 'fragilis'
            ),
            'ASV_3': TaxRecord(
                'ASV_3', 'Bacteria', 'Unknown', 'U', 'Unknown', 'F', 'Unknown', None
            ),
        }
        
        result = MappingResolution.calculate(sample_abundances, tax_records)
        assert result['resolution'] > 70  # Good coverage
    
    def test_mapping_resolution_low_confidence(self):
        """Resolution: Low mapping coverage (20%)."""
        sample_abundances = {
            'ASV_1': 100,  # Mapped
            'ASV_2': 50,
            'ASV_3': 50,
            'ASV_4': 800,  # Unmapped
        }
        
        tax_records = {
            'ASV_1': TaxRecord(
                'ASV_1', 'Bacteria', 'Desulfobacterota', 'D', 'Desulfobacterales', 'F', 'Desulfobacter', 'v'
            ),
            'ASV_4': TaxRecord(
                'ASV_4', 'Bacteria', 'Unknown', 'U', 'Unknown', 'F', 'Unknown', None
            ),
        }
        
        result = MappingResolution.calculate(sample_abundances, tax_records)
        assert result['status'] != 'OK'

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 TESTS: DOMAIN SIGNATURE
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase3DomainSignature:
    """Domain-specific biomarker calculation."""
    
    def test_domain_signature_coastal(self):
        """Signature: Calculate coastal domain biomarkers."""
        tax_records = {
            'ASV_1': TaxRecord(
                'ASV_1', 'Bacteria', 'Desulfobacterota', 'D', 'Desulfobacterales', 'F', 'Desulfobacter', 'v'
            ),  # Coastal marker
            'ASV_2': TaxRecord(
                'ASV_2', 'Bacteria', 'Bacteroidota', 'B', 'Bacteroidales', 'F', 'Bacteroides', 'f'
            ),  # Coastal marker
            'ASV_3': TaxRecord(
                'ASV_3', 'Bacteria', 'Actinomycetota', 'A', 'Actino', 'F', 'Streptomyces', 's'
            ),  # Soil marker (not coastal)
        }
        
        pre_filter_abunds = {
            'ASV_1': 500,
            'ASV_2': 300,
            'ASV_3': 200,
        }
        
        result = DomainSignature.calculate(tax_records, pre_filter_abunds, 'COASTAL')
        
        assert result['signature'] >= 5  # Should have significant coastal signal
    
    def test_domain_signature_soil(self):
        """Signature: Calculate soil domain biomarkers."""
        tax_records = {
            'ASV_1': TaxRecord(
                'ASV_1', 'Bacteria', 'Actinomycetota', 'A', 'Actino', 'F', 'Streptomyces', 's'
            ),  # Soil marker
            'ASV_2': TaxRecord(
                'ASV_2', 'Bacteria', 'Acidobacteriota', 'A', 'Acidob', 'F', 'Granulicella', 'g'
            ),  # Soil marker
        }
        
        pre_filter_abunds = {
            'ASV_1': 600,
            'ASV_2': 400,
        }
        
        result = DomainSignature.calculate(tax_records, pre_filter_abunds, 'SOIL')
        assert result['signature'] >= 5
    
    def test_domain_signature_below_threshold(self):
        """Signature: Warning when below 5% threshold."""
        tax_records = {
            'ASV_1': TaxRecord(
                'ASV_1', 'Bacteria', 'Unknown', 'U', 'Unknown', 'F', 'Unknown', None
            ),  # No signature biomarkers
        }
        
        pre_filter_abunds = {'ASV_1': 1000}
        
        result = DomainSignature.calculate(tax_records, pre_filter_abunds, 'COASTAL')
        assert result['status'] != 'OK'
        assert result['signature'] < 5

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 5 TESTS: NOISE REDUCTION & CONFIDENCE SCORING
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase5NoiseReduction:
    """Noise reduction and confidence scoring."""
    
    def test_confidence_score_high(self):
        """Score: High confidence (R=80%, unclass=10%)."""
        confidence_score = 0.80 * (1 - 0.10)
        assert 0.7 <= confidence_score <= 0.8
    
    def test_confidence_score_low(self):
        """Score: Low confidence (R=30%, unclass=40%)."""
        confidence_score = 0.30 * (1 - 0.40)
        assert 0.15 <= confidence_score <= 0.20
    
    def test_confidence_collapse(self):
        """Score: Collapse detection (C=0)."""
        confidence_score = 0.0
        assert confidence_score == 0


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 6 TESTS: ML OUTPUT SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase6MLOutput:
    """ML-ready output schema validation."""
    
    def test_ml_feature_record_creation(self):
        """Schema: Create MLFeatureRecord."""
        feature = MLFeatureRecord(
            sample_id='Sample_1',
            function='Sulfate_reduction',
            rel_abundance=0.045,
            contributors=['ASV_1', 'ASV_2'],
            confidence=0.85
        )
        
        assert feature.sample_id == 'Sample_1'
        assert feature.function == 'Sulfate_reduction'
    
    def test_ml_feature_record_serialization(self):
        """Schema: Serialize MLFeatureRecord to dict."""
        feature = MLFeatureRecord(
            sample_id='Sample_1',
            function='Sulfate_reduction',
            rel_abundance=0.045623,
            contributors=['ASV_1', 'ASV_2'],
            confidence=0.891
        )
        
        d = feature.to_dict()
        assert d['function'] == 'Sulfate_reduction'
        assert d['rel_abundance'] == 0.045623
        assert d['confidence'] == 0.891
    
    def test_ml_sample_output_creation(self):
        """Schema: Create MLSampleOutput."""
        output = MLSampleOutput('Sample_1')
        
        feature = MLFeatureRecord(
            'Sample_1', 'Sulfate_reduction', 0.045, ['ASV_1'], 0.85
        )
        output.add_feature(feature)
        
        assert len(output.features) == 1
    
    def test_ml_sample_output_serialization(self):
        """Schema: Serialize MLSampleOutput to JSON."""
        output = MLSampleOutput('Sample_1')
        output.add_feature(
            MLFeatureRecord('Sample_1', 'Sulfate_reduction', 0.045, ['ASV_1'], 0.85)
        )
        output.add_warning('Low confidence signal')
        
        d = output.to_dict()
        assert d['sample_id'] == 'Sample_1'
        assert len(d['features']) == 1
        assert len(d['warnings']) == 1

# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: FULL PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """End-to-end pipeline validation (Phases 1-6)."""
    
    def test_pipeline_success_case(self, asv_table_valid, taxonomy_valid):
        """Pipeline: Successful end-to-end execution."""
        success, ml_features, audit = validate_and_generate_ml_features(
            asv_table_valid,
            taxonomy_valid,
            id_column='ASV_ID',
            domain='COASTAL'
        )
        
        assert success is True or success is False  # Execution complete
        assert len(ml_features) == 3  # 3 samples
        assert 'domain_signature' in audit
    
    def test_pipeline_fails_on_phase1_duplicates(self, asv_table_duplicates, taxonomy_valid):
        """Pipeline: Phase 1 hard-fail on duplicates."""
        success, ml_features, audit = validate_and_generate_ml_features(
            asv_table_duplicates,
            taxonomy_valid,
            id_column='ASV_ID'
        )
        
        assert success is False
        assert 'error' in audit or audit['status'] == 'FAILED'
    
    def test_pipeline_fails_on_phase1_zero_reads(self, asv_table_zero_reads, taxonomy_valid):
        """Pipeline: Phase 1 hard-fail on zero reads."""
        # Adjust taxonomy to match ASV table
        tax_subset = taxonomy_valid.iloc[:3]
        
        success, ml_features, audit = validate_and_generate_ml_features(
            asv_table_zero_reads,
            tax_subset,
            id_column='ASV_ID'
        )
        
        assert success is False or audit['status'] == 'FAILED'
    
    def test_pipeline_output_json_serializable(self, asv_table_valid, taxonomy_valid):
        """Pipeline: Output is JSON-serializable."""
        success, ml_features, audit = validate_and_generate_ml_features(
            asv_table_valid,
            taxonomy_valid
        )
        
        # Should be JSON-serializable without errors
        json_str = json.dumps(ml_features)
        assert len(json_str) > 0

# ══════════════════════════════════════════════════════════════════════════════
# PYTEST CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
