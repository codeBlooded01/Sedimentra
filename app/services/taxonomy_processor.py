"""
AD-GSI v4.0 — Taxonomy Parser & FAPROTAX Mapper
================================================

Phase 2: Hierarchical Taxonomy Parsing
Phase 4: FAPROTAX Root-Matching & Resolution

Implements:
- Taxonomy standardization (split by ; or |, strip prefixes)
- Unclassified detection (strict keyword matching)
- FAPROTAX database integration
- Root-matching algorithm (exact → genus → stripped suffix → strain ID)
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# UNCLASSIFIED KEYWORDS (STRICT DEFINITION)
# ══════════════════════════════════════════════════════════════════════════════

UNCLASSIFIED_KEYWORDS = {
    "uncultured",
    "unidentified", 
    "unknown",
    "metagenome",
    "null",
    "",
}

# ══════════════════════════════════════════════════════════════════════════════
# TAXONOMY RECORD MODEL
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TaxRecord:
    """Parsed taxonomy record for a single ASV."""
    asv_id: str
    kingdom: Optional[str]
    phylum: Optional[str]
    tax_class: Optional[str]
    order: Optional[str]
    family: Optional[str]
    genus: Optional[str]
    species: Optional[str]
    
    # Cached properties
    is_unclassified: bool = False
    lowest_rank: Optional[str] = None
    lowest_rank_name: Optional[str] = None
    canonical_species: Optional[str] = None
    
    def __post_init__(self):
        """Compute cached properties."""
        # Determine lowest rank with actual data
        ranks = [
            ('species', self.species),
            ('genus', self.genus),
            ('family', self.family),
            ('order', self.order),
            ('tax_class', self.tax_class),
            ('phylum', self.phylum),
            ('kingdom', self.kingdom),
        ]
        
        for rank_name, rank_value in ranks:
            if rank_value and rank_value.lower().strip() not in UNCLASSIFIED_KEYWORDS:
                self.lowest_rank = rank_name
                self.lowest_rank_name = rank_value
                break
        
        # Check if unclassified
        if not self.lowest_rank_name:
            self.is_unclassified = True
        
        # Build canonical species string
        if self.genus and self.species and not self._is_unclass_term(self.species):
            self.canonical_species = f"{self.genus} {self.species}"
    
    @staticmethod
    def _is_unclass_term(term: str) -> bool:
        """Check if term is an unclassified keyword."""
        return term.lower().strip() in UNCLASSIFIED_KEYWORDS
    
    def get_genus(self) -> Optional[str]:
        """Extract genus, handling common prefixes."""
        if not self.genus:
            return None
        return self._strip_prefix(self.genus)
    
    def get_species(self) -> Optional[str]:
        """Extract species, stripping prefixes."""
        if not self.species:
            return None
        return self._strip_prefix(self.species)
    
    def get_order(self) -> Optional[str]:
        """Extract order, handling prefix."""
        if not self.order:
            return None
        return self._strip_prefix(self.order)
    
    def get_family(self) -> Optional[str]:
        """Extract family, handling prefix."""
        if not self.family:
            return None
        return self._strip_prefix(self.family)
    
    @staticmethod
    def _strip_prefix(term: str) -> str:
        """Strip common QIIME2/RDP prefixes like g__, f__, etc."""
        if not term:
            return term
        # Pattern: single letter + __ at start
        return re.sub(r'^[a-z]__', '', term, flags=re.IGNORECASE).strip()

# ══════════════════════════════════════════════════════════════════════════════
# TAXONOMY PARSER
# ══════════════════════════════════════════════════════════════════════════════

class TaxonomyParser:
    """Parse hierarchical taxonomy strings."""
    
    def __init__(self):
        self.delimiter_patterns = [';', '|']
    
    def parse_row(self, asv_id: str, tax_string: str) -> TaxRecord:
        """
        Parse a single taxonomy string.
        
        Format: k__Bacteria;p__Firmicutes;c__Bacilli;o__Bacillales;...
        Or:     Bacteria|Firmicutes|Bacilli|Bacillales|...
        
        Returns: TaxRecord with parsed ranks
        """
        if not tax_string or not isinstance(tax_string, str):
            logger.warning(f"[{asv_id}] Empty taxonomy string")
            return TaxRecord(asv_id=asv_id)
        
        # Detect delimiter
        delimiter = self._detect_delimiter(tax_string)
        if not delimiter:
            logger.error(f"[{asv_id}] Could not detect delimiter in: {tax_string}")
            return TaxRecord(asv_id=asv_id)
        
        # Split and parse
        ranks = tax_string.split(delimiter)
        
        # Expected order: Kingdom, Phylum, Class, Order, Family, Genus, Species
        kingdom = self._extract_rank(ranks, 0)
        phylum = self._extract_rank(ranks, 1)
        tax_class = self._extract_rank(ranks, 2)
        order = self._extract_rank(ranks, 3)
        family = self._extract_rank(ranks, 4)
        genus = self._extract_rank(ranks, 5)
        species = self._extract_rank(ranks, 6)
        
        record = TaxRecord(
            asv_id=asv_id,
            kingdom=kingdom,
            phylum=phylum,
            tax_class=tax_class,
            order=order,
            family=family,
            genus=genus,
            species=species,
        )
        
        logger.debug(f"[{asv_id}] Parsed: {record.lowest_rank} = {record.lowest_rank_name}")
        
        return record
    
    def _detect_delimiter(self, tax_string: str) -> Optional[str]:
        """Detect delimiter (semicolon or pipe)."""
        for delim in self.delimiter_patterns:
            if delim in tax_string:
                return delim
        return None
    
    def _extract_rank(self, ranks: List[str], index: int) -> Optional[str]:
        """Extract and clean a rank at given index."""
        if index >= len(ranks):
            return None
        
        rank = ranks[index].strip()
        if not rank or rank.lower() in UNCLASSIFIED_KEYWORDS:
            return None
        
        # Strip prefix if present
        rank = re.sub(r'^[a-z]__', '', rank, flags=re.IGNORECASE).strip()
        
        return rank if rank else None

# ══════════════════════════════════════════════════════════════════════════════
# FAPROTAX MAPPING
# ══════════════════════════════════════════════════════════════════════════════

class FAFunctionalProfile:
    """Minimal FAPROTAX-like functional mapping."""
    
    # Simplified FAPROTAX database (curated for coastal sediment)
    # Production: Load from full FAPROTAX database
    FUNCTIONAL_MAP = {
        # Desulfurication & Sulfate Reduction
        'desulfobacterales': {
            'functions': ['sulfate_reduction', 'hydrogen_oxidation'],
            'confidence': 0.95,
        },
        'desulfobacter': {
            'functions': ['sulfate_reduction'],
            'confidence': 0.92,
        },
        'desulfobacterium': {
            'functions': ['sulfate_reduction'],
            'confidence': 0.92,
        },
        'desulfovibrio': {
            'functions': ['sulfate_reduction', 'fermentation'],
            'confidence': 0.90,
        },
        
        # Heterotrophic Processing
        'bacteroidales': {
            'functions': ['polysaccharide_degradation', 'carbohydrate_metabolism'],
            'confidence': 0.85,
        },
        'flavobacteriaceae': {
            'functions': ['polysaccharide_degradation'],
            'confidence': 0.88,
        },
        'bacteroides': {
            'functions': ['polysaccharide_degradation', 'fermentation'],
            'confidence': 0.87,
        },
        
        # Photosynthesis
        'synechococcus': {
            'functions': ['photosynthesis', 'nitrogen_fixation'],
            'confidence': 0.96,
        },
        'synechococcales': {
            'functions': ['photosynthesis'],
            'confidence': 0.90,
        },
        'cyanobacteria': {
            'functions': ['photosynthesis'],
            'confidence': 0.92,
        },
        
        # Fermentation
        'clostridium': {
            'functions': ['fermentation', 'hydrogen_production'],
            'confidence': 0.88,
        },
        'bacillus': {
            'functions': ['spore_formation'],
            'confidence': 0.90,
        },
        
        # Nitrification & Nitrogen Cycling
        'nitrosomonas': {
            'functions': ['ammonia_oxidation'],
            'confidence': 0.94,
        },
        'nitrobacter': {
            'functions': ['nitrite_oxidation'],
            'confidence': 0.93,
        },
        
        # Methanogenesis
        'methanobrevibacter': {
            'functions': ['methanogenesis'],
            'confidence': 0.96,
        },
        'methanococcus': {
            'functions': ['methanogenesis'],
            'confidence': 0.95,
        },
    }
    
    @classmethod
    def get_functions(cls, tax_record: TaxRecord) -> Optional[Dict]:
        """
        Root-matching algorithm to assign functions.
        
        Resolution Priority:
        1. Exact species match
        2. Exact genus match
        3. Order match
        4. Genus match with stripped suffix
        5. Strain-ID stripped version
        """
        matches = []
        
        # Priority 1: Exact Species Match
        if tax_record.canonical_species:
            species_key = tax_record.canonical_species.lower()
            if species_key in cls.FUNCTIONAL_MAP:
                matches.append((1.0, cls.FUNCTIONAL_MAP[species_key]))
        
        # Priority 2: Exact Genus Match
        if tax_record.genus:
            genus_key = tax_record.genus.lower()
            if genus_key in cls.FUNCTIONAL_MAP:
                matches.append((0.95, cls.FUNCTIONAL_MAP[genus_key]))
        
        # Priority 3: Order Match
        if tax_record.order:
            order_key = tax_record.order.lower()
            if order_key in cls.FUNCTIONAL_MAP:
                matches.append((0.85, cls.FUNCTIONAL_MAP[order_key]))
        
        # Priority 4: Genus with Suffix Stripping
        if tax_record.genus:
            genus_stripped = cls._strip_strain_id(tax_record.genus).lower()
            if genus_stripped in cls.FUNCTIONAL_MAP and genus_stripped != tax_record.genus.lower():
                matches.append((0.80, cls.FUNCTIONAL_MAP[genus_stripped]))
        
        # Return best match
        if matches:
            _, best_mapping = max(matches, key=lambda x: x[0])
            return best_mapping
        
        return None
    
    @staticmethod
    def _strip_strain_id(taxon: str) -> str:
        """
        Strip strain IDs and common suffixes.
        
        Examples:
        - "Bacillus sp. 1234" → "Bacillus"
        - "Clostridium cf. xyz" → "Clostridium"
        - "Bacteroides spp." → "Bacteroides"
        """
        # Remove " sp.", " spp.", " cf." suffixes
        taxon = re.sub(r'\s+(sp\.|spp\.|cf\.)', '', taxon, flags=re.IGNORECASE).strip()
        
        # Remove numeric strain IDs at end (e.g., "Bacillus 1234")
        taxon = re.sub(r'\s+\d+$', '', taxon).strip()
        
        return taxon

# ══════════════════════════════════════════════════════════════════════════════
# MAPPING RESOLUTION CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

class MappingResolution:
    """Calculate functional mapping resolution metrics."""
    
    @staticmethod
    def calculate(
        asv_abundances: Dict[str, float],  # {asv_id: relative_abundance}
        tax_records: Dict[str, TaxRecord],  # {asv_id: TaxRecord}
    ) -> Dict:
        """
        Calculate resolution metrics:
        - R: Fraction of abundance with functional mapping
        - W: Warnings for low confidence
        """
        total_abundance = sum(asv_abundances.values())
        if total_abundance == 0:
            return {
                'resolution': 0.0,
                'mapped_abundance': 0.0,
                'unmapped_abundance': 0.0,
                'warning_level': 'CRITICAL_FAILURE',
                'message': 'Zero total abundance',
            }
        
        mapped_abundance = 0.0
        unmapped_asvs = []
        
        for asv_id, abundance in asv_abundances.items():
            if asv_id not in tax_records:
                unmapped_asvs.append((asv_id, abundance))
                continue
            
            tax_record = tax_records[asv_id]
            functions = FAFunctionalProfile.get_functions(tax_record)
            
            if functions:
                mapped_abundance += abundance
            else:
                unmapped_asvs.append((asv_id, abundance))
        
        resolution = mapped_abundance / total_abundance
        unmapped_pct = (total_abundance - mapped_abundance) / total_abundance * 100
        
        warning_level = 'OK'
        if resolution < 0.10:
            warning_level = 'CRITICAL_WARNING'
        elif resolution < 0.30:
            warning_level = 'LOW_CONFIDENCE'
        
        return {
            'resolution': round(resolution, 4),
            'mapped_abundance': round(mapped_abundance, 4),
            'unmapped_abundance': round(total_abundance - mapped_abundance, 4),
            'unmapped_pct': round(unmapped_pct, 2),
            'warning_level': warning_level,
            'message': f"Mapped {resolution*100:.1f}% of abundance ({len([a for a,_ in unmapped_asvs])} ASVs unmapped)",
        }

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN SIGNATURE CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

class DomainSignature:
    """Calculate domain-specific biomarker signature."""
    
    # Domain-specific target taxa
    TARGET_TAXA = {
        'COASTAL': {
            'names': ['desulfobacterales', 'bacteroidales', 'synechococcales', 
                     'flavobacteriaceae', 'actinomycetota'],
            'threshold': 0.05,  # 5% minimum
            'ranks': ['order', 'family', 'phylum'],  # Match at any rank
        },
        'SOIL': {
            'names': ['actinomycetota', 'acidobacteriota', 'bacillota',
                     'rhizobiales', 'burkholderiales'],
            'threshold': 0.05,
            'ranks': ['phylum', 'order'],
        },
    }
    
    @classmethod
    def calculate(
        cls,
        tax_records: Dict[str, TaxRecord],
        pre_filter_abundances: Dict[str, float],  # Pre-filtering total
        domain: str = 'COASTAL',
    ) -> Dict:
        """
        Calculate domain signature.
        
        Formula: Σ(Target Taxa Abundance) / Total Pre-Filter Abundance × 100
        """
        total_pre_filter = sum(pre_filter_abundances.values())
        
        if total_pre_filter == 0:
            return {
                'signature': 0.0,
                'status': 'FAILED',
                'message': 'Zero pre-filter abundance',
            }
        
        cfg = cls.TARGET_TAXA.get(domain, cls.TARGET_TAXA['COASTAL'])
        target_names = {name.lower() for name in cfg['names']}
        
        target_abundance = 0.0
        contributing_asvs = []
        
        for asv_id, abundance in pre_filter_abundances.items():
            if asv_id not in tax_records:
                continue
            
            tax_record = tax_records[asv_id]
            
            # Check all ranks for match
            ranks_to_check = [
                tax_record.order,
                tax_record.family,
                tax_record.phylum,
            ]
            
            for rank_val in ranks_to_check:
                if rank_val and rank_val.lower() in target_names:
                    target_abundance += abundance
                    contributing_asvs.append(asv_id)
                    break
        
        signature_pct = (target_abundance / total_pre_filter) * 100
        
        status = 'OK'
        message = f"Domain signature: {signature_pct:.1f}%"
        
        if signature_pct < cfg['threshold']:
            status = 'DOMAIN_MISMATCH_WARNING'
            message = (f"POTENTIAL DOMAIN MISMATCH: Signature only {signature_pct:.1f}% "
                      f"(expected ≥{cfg['threshold']*100:.0f}%)")
        
        return {
            'signature': round(signature_pct, 2),
            'status': status,
            'message': message,
            'contributing_asvs': len(contributing_asvs),
        }
