import os
import re
from pathlib import Path
from functools import lru_cache

FAPROTAX_FILE = Path("app/assets/faprotax/FAPROTAX.txt")

_mapping: dict | None = None

def _parse_input_lineage(lineage_str: str) -> list[tuple[str, str]]:
    # Expected input format from ingest: kingdom:bacteria;phylum:proteobacteria;...
    parsed = []
    for segment in lineage_str.split(";"):
        if ":" in segment:
            try:
                rank, val = segment.split(":", 1)
                rank = rank.strip().lower()
                val = val.strip().lower()
                if val and val not in ["na", "unclassified", ""]:
                    parsed.append((rank, val))
            except ValueError:
                continue
        else:
            # Fallback if unformatted strings are somehow passed
            val = segment.strip().lower()
            if val and val not in ["na", "unclassified", ""]:
                parsed.append(("unknown", val))
    return parsed

def _match_subsequence(db_path: tuple, input_lineage_tuples: list[tuple[str, str]]) -> str | None:
    """
    True subsequence matcher: 
    The entire sequence of terms in db_path must appear IN ORDER 
    within the values of input_lineage_tuples.
    Returns the taxonomic rank string of the last matched matched term, or None.
    """
    match_idx = -1
    input_idx = 0
    
    for db_taxon in db_path:
        found = False
        while input_idx < len(input_lineage_tuples):
            if input_lineage_tuples[input_idx][1] == db_taxon:
                found = True
                match_idx = input_idx
                input_idx += 1
                break
            input_idx += 1
            
        if not found:
            return None
            
    # Subsequence fully matched in order. Extract rank of the final matched step.
    return input_lineage_tuples[match_idx][0]

@lru_cache(maxsize=512)
def _resolve_functions(taxonomy: str) -> list[dict]:
    if _mapping is None:
        raise RuntimeError("FAPROTAX database not loaded. Call load_database() before resolving functions.")
        
    input_lineage_tuples = _parse_input_lineage(taxonomy)
    if not input_lineage_tuples:
        return [{"function": "none", "matched_rank": "unassigned", "confidence": "unassigned"}]
        
    func_best_match = {}
    
    for db_path, mapped_funcs in _mapping.items():
        matched_rank = _match_subsequence(db_path, input_lineage_tuples)
        
        if matched_rank:
            # Enforce confidence constraints
            conf = "high" if matched_rank in ["genus", "species"] else "low"
            
            for func in mapped_funcs:
                if func not in func_best_match:
                    func_best_match[func] = {"matched_rank": matched_rank, "confidence": conf}
                elif func_best_match[func]["confidence"] == "low" and conf == "high":
                    # Promote confidence if a stronger match path reaches the same function
                    func_best_match[func] = {"matched_rank": matched_rank, "confidence": conf}

    if not func_best_match:
        return [{"function": "none", "matched_rank": "unassigned", "confidence": "unassigned"}]
        
    results = []
    for func in sorted(func_best_match.keys()):
        results.append({
            "function": func,
            "matched_rank": func_best_match[func]["matched_rank"],
            "confidence": func_best_match[func]["confidence"]
        })
        
    return results

class FaprotaxService:
    def __init__(self):
        self.loaded = False

    def load_database(self):
        global _mapping
        if self.loaded:
            return
            
        if not FAPROTAX_FILE.exists():
            return

        with open(FAPROTAX_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_func = None
        local_mapping = {}
        
        # Simple parser for FAPROTAX
        for line in lines:
            line = line.strip()
            # Ignore empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Function definition line
            if not line.startswith("*") and not line.startswith("add_group:") and not line.startswith("subtract_group:") and not line.startswith("intersect_group:"):
                parts = line.split()
                if parts:
                    current_func = parts[0]
                continue

            # Taxonomic path line
            if line.startswith("*") and current_func:
                line = line.split("#")[0].strip()
                
                # Extract all non-empty segments representing the hierarchical path
                parts = tuple([p.strip().lower() for p in line.split("*") if p.strip()])
                if parts:
                    if parts not in local_mapping:
                        local_mapping[parts] = set()
                    local_mapping[parts].add(current_func)

        _mapping = local_mapping
        self.loaded = True

    def get_functions_for_taxa(self, taxonomy: str) -> list[dict]:
        if not self.loaded:
            self.load_database()
        return _resolve_functions(taxonomy)

faprotax_service = FaprotaxService()
