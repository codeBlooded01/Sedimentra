# System Audit Toolkit — Genomic Intelligence System

> Comprehensive diagnostic tools for validating architectural integrity, metagenomic data, domain-specific biomarkers, and computational efficiency.

---

## Overview

This toolkit provides **4 independent audit scripts** that can be run individually or in sequence:

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `audit_environment.py` | Environment configuration validation | `.env` file | ✅/❌ per environment variable |
| `audit_metagenomic.py` | 3-tier data structure validation | ASV CSV + Taxonomy CSV | Tier 1, 2, 3 pass/fail results |
| `audit_domain_biomarkers.py` | Soil vs. Coastal domain detection | ASV CSV + Taxonomy CSV | Biomarker detection + domain match |
| `audit_efficiency.py` | Memory optimization + streaming capability | ASV CSV (optional) | Memory footprint + recommendations |

---

## Quick Start

### 1. Environment Integrity Check

Verify all configuration variables, database connectivity, and service health:

```bash
# Run from project root
python docs/audit_environment.py

# Expected output:
# ✅ PASS: POSTGRES_USER = gis_user
# ✅ PASS: PostgreSQL connected
# ✅ PASS: Redis connected
# ✅ PASS: SMTP authentication successful
```

**What it checks**:
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` presence
- PostgreSQL connectivity (requires asyncpg in container)
- Redis connectivity (requires redis-py)
- SMTP authentication (Gmail or alternative)
- Upload directory ownership/permissions
- Disk space availability

**Common Failures**:
- `❌ FAIL: PostgreSQL connection failed` → Start Docker containers (`docker-compose up -d`)
- `❌ FAIL: SMTP authentication failed` → Verify `MAIL_PASSWORD` is an [App Password](https://myaccount.google.com/apppasswords), not regular password
- `❌ FAIL: SECRET_KEY is less than 32 characters` → Generate a secure key and set in `.env`

---

### 2. Metagenomic Data Validation

Validate uploaded CSV files through the 3-tier validation system:

```bash
# Tier 1 (Structural) + Tier 2 (Schema) + Tier 3 (Relational)
python docs/audit_metagenomic.py /path/to/asv_table.csv /path/to/taxonomy.csv

# Example with test data
python docs/audit_metagenomic.py data/test_asv.csv data/test_taxonomy.csv

# Expected output:
# ✅ PASS: ASV table parsed successfully
# ✅ PASS: All abundance values are numeric and non-negative
# ✅ PASS: All required taxonomy columns present
# ✅ PASS: No duplicate ASV IDs
# ✅ PASS: No forward orphans (100% coverage)
# ✅ PASS: No reverse orphans (100% coverage)
# ✅ PASS: Acceptable sparsity (48.2%)
```

**What each tier checks**:

**Tier 1 — Structural Integrity** ✅
- CSV file format validity
- No encoding errors
- Successfully parses to DataFrame

**Tier 2 — Schema & Data Types** ⚠️ **GAPS FOUND**
- Required columns present (ASV_ID, Kingdom, Phylum, Class, Order, Family, Genus, Species)
- Abundance columns are numeric **BUT**:
  - ❌ Currently uses `errors='coerce'` (silently converts bad data to 0)
  - ❌ No validation for negative counts (biologically impossible)
  - ❌ No validation for integer vs. float appropriately
  - **RECOMMENDATION**: Implement strict validation (reject bad data, don't coerce)

**Tier 3 — Relational ID Integrity** ✅ **PARTIAL**
- No duplicate ASV IDs in either table
- Forward orphans: ASV IDs in abundance but NOT in taxonomy
- Reverse orphans: Taxonomy IDs NOT in abundance **⚠️ NOT CURRENTLY CHECKED**
- Sparsity analysis (warns if >95% zeros)

---

### 3. Domain-Specific Biomarker Detection

Detect soil vs. coastal microbiota biomarkers:

```bash
# Infer domain from data
python docs/audit_domain_biomarkers.py /path/to/asv.csv /path/to/tax.csv

# Validate against expected domain
python docs/audit_domain_biomarkers.py /path/to/asv.csv /path/to/tax.csv SOIL

# Expected output:
# ✅ DETECTED: Actinomycetota (12.5%)
# ✅ DETECTED: Acidobacteriota (8.3%)
# ✅ N-FIXING POTENTIAL: 245 ASVs
# 
# 🟢 ASSESSMENT: Consistent with SOIL microbiota
```

**Soil Biomarkers**:
| Phylum | Indicator | Threshold |
|--------|-----------|-----------|
| **Actinomycetota** | Carbon cycling, secondary metabolites | 1% min, 10-60% optimal |
| **Acidobacteriota** | Acidic soil indicator | 1% min, 5-40% optimal |
| **Bacillota** | Spore-formers, stress resilience | 0.1% min, 0.5-10% optimal |
| **Nitrogen-fixers** | nifH gene markers | Orders: Rhizobiales, Burkholderiales |

**Coastal Biomarkers**:
| Phylum | Indicator | Threshold |
|--------|-----------|-----------|
| **Desulfobacterota** | Sulfate reduction (anaerobic) | 0.1% min, 2-30% strong signal |
| **Bacteroidales** | algal breakdown, DMSP degradation | 1% min, 5-40% optimal |
| **Firmicutes** | Fermentation under hypoxia | 0.1% min, 1-15% optimal |
| **Sulfur-cyclers** | dsrA gene markers | >2% indicates active sulfur cycling |

**Domain Mismatch Warning Example**:
```
❌ ALERT: DOMAIN MISMATCH - No soil biomarkers detected

If uploading as "Soil" but data shows coastal biomarkers:
→ Check sample metadata
→ Verify uploan type classification
→ Re-confirm expected domain
```

---

### 4. Computational Efficiency Analysis

Analyze memory usage and streaming capability:

```bash
# Analyze dataset with Pandas memory estimation
python docs/audit_efficiency.py /path/to/asv.csv

# Expected output:
# Input file size: 45.2 MB
# Pandas memory: 156.3 MB (+246% overhead)
# Polars estimate: 62.5 MB (40% of Pandas)
# 
# Dataset: 50,000 rows × 1,200 columns (WIDE)
# ⚠️ RECOMMENDATION: Use Polars with lazy evaluation
# 
# Sparsity: 73.2% (manageable)
```

**What it checks**:
- File size vs. in-memory footprint (to detect format inefficiencies)
- Dataset classification (TALL vs. WIDE)
- Sparsity analysis (warns if >95%)
- Async/streaming implementation (aiofiles, chunked reading)
- Celery background task configuration
- Container resource limits (memory, CPU)
- Health check configuration

**Performance Recommendations Generated**:
1. **Polars for wide datasets** (>500 samples) — 40-60% memory reduction
2. **Container memory limits** — Prevent runaway processes
3. **Streaming validation** — Validate headers before full download
4. **Chunked processing** — For files >500MB
5. **Parquet output** — Native columnar format for ML tools

---

## Advanced Usage: Running Full Audit Suite

```bash
#!/bin/bash
# Run all audits in sequence

echo "=== AUDIT 1: ENVIRONMENT INTEGRITY ==="
python docs/audit_environment.py

echo -e "\n=== AUDIT 2: METAGENOMIC VALIDATION (3-TIER) ==="
python docs/audit_metagenomic.py sample_data/asv.csv sample_data/taxonomy.csv

echo -e "\n=== AUDIT 3: DOMAIN-SPECIFIC BIOMARKER DETECTION ==="
python docs/audit_domain_biomarkers.py sample_data/asv.csv sample_data/taxonomy.csv SOIL

echo -e "\n=== AUDIT 4: COMPUTATIONAL EFFICIENCY ==="
python docs/audit_efficiency.py sample_data/asv.csv

echo -e "\n=== AUDIT COMPLETE ==="
```

Save as `run_all_audits.sh` and execute:
```bash
chmod +x run_all_audits.sh
./run_all_audits.sh
```

---

## Critical Findings & Action Items

### 🔴 Priority 1 (Implement Immediately)

#### 1. **Fix Tier 2 Schema Validation** ❌ CRITICAL
**Issue**: ASV abundance validation uses `errors='coerce'` which silently converts bad data to 0

**Fix**: Replace in `app/services/validation_service.py`:
```python
# BEFORE (silently coerces bad data):
self.asv_df[col] = pd.to_numeric(self.asv_df[col], errors='coerce').fillna(0)

# AFTER (rejects bad data):
try:
    self.asv_df[col] = pd.to_numeric(self.asv_df[col], errors='raise')
except ValueError as e:
    self._add_error(ValidationLayer.SCHEMA, "non_numeric_abundance",
        f"Column '{col}' contains non-numeric values", str(e))
    return False

# Validate non-negative
if (self.asv_df[col] < 0).any():
    self._add_error(ValidationLayer.SCHEMA, "negative_counts",
        f"Column '{col}' contains biologically impossible negative counts", "")
    return False
```

#### 2. **Implement Reverse Orphan Detection** ❌ CRITICAL
**Issue**: Currently only checks forward orphans (ASV → Taxonomy). Missing reverse orphans (Taxonomy → ASV).

**Fix**: Add to `_run_tier_3_relational()`:
```python
# Check reverse orphans
reverse_orphans = tax_set - asv_set
if reverse_orphans:
    self._add_error(
        ValidationLayer.RELATIONAL,
        "reverse_orphan",
        f"{len(reverse_orphans)} taxonomy entries have no abundance data",
        f"Sample: {list(reverse_orphans)[:5]}"
    )
    return False
```

#### 3. **Add Domain-Specific Biomarker Detection** ❌ CRITICAL
**Issue**: No validation that data matches expected domain (Soil vs. Coastal)

**Fix**: Extend `GenomicValidationService` with Tier 3+ biomarker detection:
```python
def _run_tier_3_domain_check(self) -> bool:
    """Detect if taxa match expected environment."""
    
    if self.expected_domain == "SOIL":
        soil_biomarkers = self._detect_soil_biomarkers()
        if len(soil_biomarkers) < 2:
            self.report.warnings.append(
                "POTENTIAL DOMAIN MISMATCH: Expected soil biomarkers "
                "(Actinomycetota, Acidobacteriota) are absent."
            )
    
    return True  # Warning, not failure
```

#### 4. **Set Container Memory Limits** ❌ CRITICAL
**Issue**: No Docker container memory limits. Runaway processes can crash entire system.

**Fix**: Update `docker-compose.yml`:
```yaml
api:
  # ... existing config ...
  deploy:
    resources:
      limits:
        memory: 2G
      reservations:
        memory: 1G

worker:
  # ... existing config ...
  deploy:
    resources:
      limits:
        memory: 1G
      reservations:
        memory: 512M
```

### 🟡 Priority 2 (Implement Before Production)

#### 5. **Add Polars Backend for Wide Datasets**
For datasets with >500 samples, Polars can reduce memory usage by 40-60%

#### 6. **Implement NCBI Accession Validation**
- Fetch metadata for SRR/DRR/ERR accessions
- Validate sample type (reject "Human Clinical" for Soil)
- Pre-cache metadata before download

#### 7. **Add Progress Tracking for Large Uploads**
- Report upload progress percentage to frontend
- Estimate time-to-completion for >500MB files

---

## Sample Test Data

To test the audit tools, create minimal test files:

**test_asv.csv**:
```csv
ASV_ID,Sample_1,Sample_2,Sample_3
ASV_001,100,200,150
ASV_002,50,75,100
ASV_003,10,5,8
ASV_004,0,0,0
```

**test_taxonomy.csv**:
```csv
ASV_ID,Kingdom,Phylum,Class,Order,Family,Genus,Species
ASV_001,Bacteria,Actinomycetota,Actinomycetes,Actinomycetales,Streptomycetaceae,Streptomyces,sp.
ASV_002,Bacteria,Acidobacteriota,Holophagae,Holophagales,Holophagaceae,Holophaga,sp.
ASV_003,Bacteria,Bacillota,Bacilli,Bacillales,Bacillaceae,Bacillus,sp.
ASV_004,Bacteria,Bacteroidota,Bacteroidia,Chimaeraematiales,Chimaeraematiaceae,Chimaeramatum,sp.
```

Test command:
```bash
python docs/audit_metagenomic.py test_asv.csv test_taxonomy.csv
```

---

## Documentation References

- **System Architecture**: See `SYSTEM_AUDIT.md`
- **Backend Code**: `app/services/validation_service.py`
- **Frontend Integration**: `frontend/src/pages/IngestPage.jsx`
- **Docker Configuration**: `docker-compose.yml`
- **Environment Setup**: `.env` and `.env.example`

---

## Troubleshooting

### Error: "asyncpg not installed"
This audit tool expects Python packages. Run in Docker container:
```bash
docker-compose exec api python docs/audit_environment.py
```

### Error: "File not found"
Provide absolute or relative path from project root:
```bash
python docs/audit_metagenomic.py ./data/asv.csv ./data/taxonomy.csv
```

### Error: "PostgreSQL connection failed"
Ensure Docker containers are running:
```bash
docker-compose up -d
docker-compose ps  # Verify all containers are running
python docs/audit_environment.py
```

### Error: "SMTP authentication failed"
Gmail requires [App Passwords](https://myaccount.google.com/apppasswords), not regular account passwords:
1. Enable 2-factor authentication on Google account
2. Generate app password
3. Update `.env` with `MAIL_PASSWORD=<app_password>`

---

## Next Steps

1. ✅ Run `audit_environment.py` to ensure all services are running
2. ✅ Run `audit_metagenomic.py` with test data to verify validation pipeline  
3. ✅ Run `audit_domain_biomarkers.py` to confirm biomarker detection
4. ✅ Run `audit_efficiency.py` with real dataset to estimate memory usage
5. ✅ Implement Priority 1 fixes before production deployment
6. ✅ Load test with real-world wide datasets (1000+ samples)

---

**Last Updated**: March 31, 2026  
**Audit Toolkit Version**: 1.0.0
