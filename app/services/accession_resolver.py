"""
Accession Resolver
==================
Detects which database an accession belongs to based on its prefix,
then routes metadata lookup to the correct API client.

Prefix mapping:
  SRR / SRP / SRX / SRS / SRA  →  NCBI SRA
  ERR / ERP / ERX / ERS / ERA  →  ENA (EMBL-EBI)
  DRR / DRP / DRX / DRS / DRA  →  DDBJ
"""

from app.schemas.accession import AccessionSource


# Prefix → source mapping
_PREFIX_MAP: dict[str, AccessionSource] = {
    # SRA (NCBI)
    "SRR": AccessionSource.SRA,
    "SRP": AccessionSource.SRA,
    "SRX": AccessionSource.SRA,
    "SRS": AccessionSource.SRA,
    "SRA": AccessionSource.SRA,
    # ENA (EMBL-EBI)
    "ERR": AccessionSource.ENA,
    "ERP": AccessionSource.ENA,
    "ERX": AccessionSource.ENA,
    "ERS": AccessionSource.ENA,
    "ERA": AccessionSource.ENA,
    # DDBJ
    "DRR": AccessionSource.DDBJ,
    "DRP": AccessionSource.DDBJ,
    "DRX": AccessionSource.DDBJ,
    "DRS": AccessionSource.DDBJ,
    "DRA": AccessionSource.DDBJ,
}


def detect_source(accession: str) -> AccessionSource:
    """Return the database source for a given accession number."""
    prefix = accession[:3].upper()
    source = _PREFIX_MAP.get(prefix)
    if not source:
        raise ValueError(
            f"Cannot determine database source for accession '{accession}'. "
            f"Prefix '{prefix}' is not recognized."
        )
    return source
