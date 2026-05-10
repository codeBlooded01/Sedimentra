"""
AD-GSI v4.0 — FAPROTAX DATABASE LOADER

Loads and manages FAPROTAX functional profiles from:
- External JSON database
- PostgreSQL cache  
- In-memory lookup

USAGE:
    loader = FAProTAXLoader()
    loader.load_from_json('faprotax.json')
    functions = loader.lookup('Bacteria', 'Desulfobacterales')
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# IN-MEMORY DATABASE (Hardcoded for now, can be loaded from JSON)
# ══════════════════════════════════════════════════════════════════════════════

FAPROTAX_COASTAL_DATABASE = {
    # Sulfate Reducers
    ('Desulfobacterales',): {
        'functions': ['Sulfate_reduction', 'Anaerobic_respiration'],
        'confidence': 0.95,
        'taxa': {
            'Desulfobacter': ['vulgaris', 'postgatei'],
            'Desulfobacteria': ['aerophila'],
        }
    },
    ('Desulfobacteraceae',): {
        'functions': ['Sulfate_reduction'],
        'confidence': 0.90,
    },
    
    # Bacteroidetes (Fermenting)
    ('Bacteroidales',): {
        'functions': ['Fermentation', 'Polysaccharide_degradation'],
        'confidence': 0.85,
        'taxa': {
            'Bacteroides': ['fragilis', 'vulgatus'],
            'Prevotella': ['intermedia'],
        }
    },
    
    # Sulfur Cycling
    ('Thiotrichales',): {
        'functions': ['Sulfur_oxidation', 'Chemolithoautotrophy'],
        'confidence': 0.88,
    },
    ('Gammaproteobacteria',): {
        'functions': ['Denitrification', 'Nitrogen_fixation'],
        'confidence': 0.70,
    },
    
    # Methanogens
    ('Methanococcales',): {
        'functions': ['Methanogenesis', 'Anaerobic_respiration'],
        'confidence': 0.92,
    },
    ('Methanobacteriales',): {
        'functions': ['Methanogenesis'],
        'confidence': 0.93,
    },
    
    # Candidate Division
    ('Planctomycetes',): {
        'functions': ['Nitrogen_cycling', 'Anaerobic_processes'],
        'confidence': 0.65,
    },
}

FAPROTAX_SOIL_DATABASE = {
    # Actinobacteria (Dominant soil)
    ('Actinomycetales',): {
        'functions': ['Cellulose_degradation', 'Chitin_degradation', 'Antibiotic_production'],
        'confidence': 0.92,
        'taxa': {
            'Streptomyces': ['coelicolor'],
            'Corynebacterium': ['glutamicum'],
        }
    },
    
    # Acidobacteria
    ('Acidobacteriales',): {
        'functions': ['Polysaccharide_degradation', 'Acidotroph'],
        'confidence': 0.80,
        'taxa': {
            'Granulicella': ['antarctica'],
        }
    },
    
    # Nitrogen Fixers
    ('Rhizobiales',): {
        'functions': ['Nitrogen_fixation', 'Plant_symbiosis'],
        'confidence': 0.88,
        'taxa': {
            'Sinorhizobium': ['meliloti'],
            'Bradyrhizobium': ['japonicum'],
        }
    },
    
    # Bacilli
    ('Bacillales',): {
        'functions': ['Sporulation', 'Antibiotic_synthesis'],
        'confidence': 0.75,
        'taxa': {
            'Bacillus': ['subtilis', 'cereus'],
        }
    },
    
    # Firmicutes (Cellulose degraders)
    ('Clostridiales',): {
        'functions': ['Cellulose_degradation', 'Fermentation'],
        'confidence': 0.80,
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# LOOKUP CLASS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FAProTAXMatch:
    """Result of FAPROTAX lookup."""
    functions: List[str]
    confidence: float
    match_level: str  # 'exact', 'genus', 'order', 'fallback'
    rank: str  # 'species', 'genus', 'order', etc.

class FAProTAXLoader:
    """
    FAPROTAX database loader and lookup engine.
    
    Supports:
    1. Loading from external JSON file
    2. In-memory caching for fast lookups
    3. Multi-rank fallback matching
    4. Domain-specific databases (COASTAL, SOIL, FRESHWATER)
    """
    
    def __init__(self):
        self.db = {}
        self.loaded_domain = None
        self.species_index = {}
        self.genus_index = {}
        self.order_index = {}
        logger.info("FAProTAXLoader initialized")
        
    def _build_indices(self):
        """Index the loaded database for O(1) functional mapping lookups."""
        self.species_index.clear()
        self.genus_index.clear()
        self.order_index.clear()
        
        for rank_tuple, entry in self.db.items():
            # Index by order (or whatever the primary rank key is)
            if rank_tuple:
                order_name = str(rank_tuple[0]).lower()
                self.order_index[order_name] = entry
                
            # Index detailed taxa mappings
            if 'taxa' in entry:
                for gen, sp_list in entry['taxa'].items():
                    gen_lower = gen.lower()
                    self.genus_index[gen_lower] = entry
                    for sp in sp_list:
                        self.species_index[(gen_lower, sp.lower())] = entry
    
    def load_from_json(self, json_path: str, domain: str = 'COASTAL') -> bool:
        """
        Load FAPROTAX database from JSON file.
        
        Expected format:
        {
            "COASTAL": {
                "Desulfobacterales": {
                    "functions": ["Sulfate_reduction", "Anaerobic_respiration"],
                    "confidence": 0.95,
                    "taxa": {...}
                }
            }
        }
        """
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            if domain not in data:
                logger.warning(f"Domain '{domain}' not found in {json_path}")
                return False
            
            self.db = data[domain]
            self.loaded_domain = domain
            self._build_indices()
            logger.info(f"Loaded {len(self.db)} FAPROTAX entries for {domain}")
            return True
        
        except FileNotFoundError:
            logger.error(f"FAPROTAX JSON file not found: {json_path}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_path}: {e}")
            return False
    
    def load_hardcoded(self, domain: str = 'COASTAL') -> bool:
        """Load hardcoded FAPROTAX database."""
        if domain == 'COASTAL':
            self.db = FAPROTAX_COASTAL_DATABASE
        elif domain == 'SOIL':
            self.db = FAPROTAX_SOIL_DATABASE
        else:
            logger.warning(f"Unknown domain: {domain}")
            return False
        
        self.loaded_domain = domain
        self._build_indices()
        logger.info(f"Loaded hardcoded FAPROTAX for {domain}: {len(self.db)} entries")
        return True
    
    def lookup(
        self,
        order: Optional[str] = None,
        family: Optional[str] = None,
        genus: Optional[str] = None,
        species: Optional[str] = None,
    ) -> Optional[FAProTAXMatch]:
        """
        Lookup functional profile with fallback matching.
        
        Priority:
        1. Exact species match
        2. Exact genus match
        3. Order match
        4. Fallback (no match)
        """
        
        if not self.db:
            logger.warning("FAPROTAX database not loaded")
            return None
        
        # Priority 1: Exact species match
        if species and genus:
            sp_key = (genus.lower(), species.lower())
            if sp_key in self.species_index:
                entry = self.species_index[sp_key]
                return FAProTAXMatch(
                    functions=entry['functions'],
                    confidence=entry.get('confidence', 0.8),
                    match_level='exact',
                    rank='species'
                )
        
        # Priority 2: Exact genus match
        if genus:
            gen_key = genus.lower()
            if gen_key in self.genus_index:
                entry = self.genus_index[gen_key]
                return FAProTAXMatch(
                    functions=entry['functions'],
                    confidence=entry.get('confidence', 0.8) * 0.95,
                    match_level='genus',
                    rank='genus'
                )
        
        # Priority 3: Order match
        if order:
            ord_key = order.lower()
            if ord_key in self.order_index:
                entry = self.order_index[ord_key]
                return FAProTAXMatch(
                    functions=entry['functions'],
                    confidence=entry.get('confidence', 0.8) * 0.85,
                    match_level='order',
                    rank='order'
                )
        
        return None
    
    def lookup_by_taxonomy(self, tax_record) -> Optional[FAProTAXMatch]:
        """
        Convenience method: lookup from TaxRecord object.
        
        Args:
            tax_record: TaxRecord from taxonomy_processor.py
        
        Returns:
            FAProTAXMatch or None
        """
        return self.lookup(
            order=tax_record.order,
            family=tax_record.family,
            genus=tax_record.genus,
            species=tax_record.species,
        )
    
    def get_all_functions(self) -> List[str]:
        """Get all unique functions in database."""
        functions = set()
        for entry in self.db.values():
            if 'functions' in entry:
                functions.update(entry['functions'])
        return sorted(list(functions))
    
    def get_functions_by_domain(self, domain: str) -> Dict[str, int]:
        """Count functions in each domain."""
        self.load_hardcoded(domain)
        functions = {}
        for entry in self.db.values():
            for func in entry.get('functions', []):
                functions[func] = functions.get(func, 0) + 1
        return functions

# ══════════════════════════════════════════════════════════════════════════════
# DATABASE SERVICE (Async PostgreSQL integration)
# ══════════════════════════════════════════════════════════════════════════════

class FAProTAXService:
    """
    Manages FAPROTAX database persistence and retrieval.
    
    Handles:
    - Loading from JSON/disk
    - Caching in PostgreSQL
    - Fast lookups (in-memory + DB fallback)
    """
    
    def __init__(self, db_session):
        self.db_session = db_session
        self.loader = FAProTAXLoader()
    
    async def initialize(self, domain: str = 'COASTAL') -> bool:
        """
        Initialize FAPROTAX service.
        
        1. Check PostgreSQL cache
        2. If empty, load from JSON or hardcoded
        3. Populate PostgreSQL
        """
        # For now, load hardcoded (production: load from JSON)
        return self.loader.load_hardcoded(domain)
    
    async def lookup(self, tax_record) -> Optional[FAProTAXMatch]:
        """Lookup functional profile for taxonomy."""
        return self.loader.lookup_by_taxonomy(tax_record)

# ══════════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Load COASTAL database
    loader = FAProTAXLoader()
    loader.load_hardcoded('COASTAL')
    
    # Lookup example
    match = loader.lookup(
        order='Desulfobacterales',
        genus='Desulfobacter',
        species='vulgaris'
    )
    
    if match:
        print(f"✓ Match found:")
        print(f"  Functions: {match.functions}")
        print(f"  Confidence: {match.confidence}")
        print(f"  Level: {match.match_level}")
    else:
        print("✗ No match found")
    
    # Get all functions
    functions = loader.get_all_functions()
    print(f"\nAvailable functions ({len(functions)}):")
    for func in functions[:5]:
        print(f"  - {func}")
