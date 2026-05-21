# Genomic Intelligence System — Audit Summary & Action Plan

**Date**: March 31, 2026  
**Status**: 🟡 **READY FOR PRODUCTION WITH CRITICAL FIXES**

---

## Executive Summary

The **Genomic Intelligence System** has a **sound architectural foundation** with proper async handling, file streaming, and 3-tier validation. However, **critical data validation gaps** and missing domain-specific logic must be addressed before production deployment.

### System Components: Status Report

| Component | Status | Notes |
|-----------|--------|-------|
| **FastAPI Backend** | ✅ Solid | Async I/O, proper error handling, rate limiting |
| **React Frontend** | ✅ Solid | Vite dev server, proper API integration, auth flow |
| **PostgreSQL** | ✅ Solid | Async SQLAlchemy, connection pooling configured |
| **Redis/Celery** | ✅ Solid | Background task dispatch working, 202 Accepted returned |
| **File Streaming** | ⚠️ Partial | Uses aiofiles ✓, but no validation during stream ✗ |
| **Tier 1-2 Validation** | ⚠️ Incomplete | Parses CSV ✓, but silently coerces bad data ✗ |
| **Tier 3 Validation** | ⚠️ Incomplete | Checks forward orphans ✓, missing reverse orphans ✗ |
| **Domain Detection** | ❌ Missing | No biomarker detection for Soil vs. Coastal |
| **Container Limits** | ❌ Missing | No memory limits = potential OOM kill on wide data |
| **NCBI Integration** | ❌ Missing | No accession validation (SRR/DRR/ERR import) |

---

## Critical Findings

### 🔴 Blocker 1: Schema Validation Uses Silent Coercion

**File**: `app/services/validation_service.py` (Line ~60)

**Problem**:
```python
# CURRENT (DANGEROUS):
asv_df[col] = pd.to_numeric(asv_df[col], errors='coerce').fillna(0)
```

This silently converts **all bad data to 0**, masking data quality issues:
- Non-numeric values (e.g., `"high"`, `"NA"`) → become 0
- String accessions mixed with counts → become 0
- Negative numbers → stay negative (biologically impossible)

**Impact**: Users upload corrupted data, system silently "fixes" it, produces meaningless results.

**Fix**:
```python
# CORRECTED (STRICT VALIDATION):
try:
    values = pd.to_numeric(col_data, errors='raise')
    if (values < 0).any():
        raise ValueError(f"Negative counts detected")
    asv_df[col] = values
except ValueError as e:
    self._add_error(
        ValidationLayer.SCHEMA,
        "abundance_type_error",
        f"Sample '{col}' contains invalid abundance data",
        str(e)
    )
    return False
```

**Severity**: 🔴 **CRITICAL** — Affects data integrity

---

### 🔴 Blocker 2: Reverse Orphan Detection Missing

**File**: `app/services/validation_service.py` (Line ~140)

**Problem**:
```python
# CURRENT:
orphaned = asv_set - tax_set  # Only checks FORWARD orphans
if orphaned:
    return False
# Missing: tax_set - asv_set (REVERSE orphans)
```

**Example**:
```
ASV Table has IDs: [ASV_001, ASV_002, ASV_003]
Taxonomy has IDs:  [ASV_001, ASV_002, ASV_003, ASV_004, ASV_005]

Current check: ✅ PASS (all ASV IDs have taxonomy)
Missing check: ❌ FAIL (ASV_004, ASV_005 have no abundance data)
```

**Fix**:
```python
forward_orphans = asv_set - tax_set
reverse_orphans = tax_set - asv_set

if forward_orphans or reverse_orphans:
    self._add_error(...)
    return False
```

**Severity**: 🔴 **CRITICAL** — Causes null values in downstream ML models

---

### 🔴 Blocker 3: Missing Domain-Specific Validation

**File**: `app/services/validation_service.py` (NOT IMPLEMENTED)

**Problem**: No validation that uploaded data matches expected environment (Soil vs. Coastal)

**Impact**: User uploads coastal sediment data but says "Soil" — system accepts it. Results are meaningless.

**Fix**: Implement Tier 3+ biomarker detection:

```python
def _run_tier_3_domain_check(self) -> bool:
    """Verify taxa match expected environment."""
    
    # Infer or retrieve expected domain from metadata
    expected_domain = self.metadata.get('environment', 'UNKNOWN')
    
    if expected_domain == 'SOIL':
        return self._validate_soil_biomarkers()
    elif expected_domain == 'COASTAL':
        return self._validate_coastal_biomarkers()
    
    return True

def _validate_soil_biomarkers(self) -> bool:
    """Check for Soil microbiota indicators."""
    
    actino_abundance = self._get_phylum_abundance("Actinomycetota")
    bacteria_abundance = self._get_phylum_abundance("Acidobacteriota")
    
    if actino_abundance < 0.01 and bacteria_abundance < 0.01:
        self.report.warnings.append(
            "DOMAIN MISMATCH WARNING: Expected soil biomarkers "
            "(Actinomycetota, Acidobacteriota) not detected. "
            "Verify sample classification."
        )
        # Continue with warning, don't fail
    
    return True
```

**Biomarkers to detect**:
- **SOIL**: Actinomycetota (>1%), Acidobacteriota (>1%), Nitrogen-fixers
- **COASTAL**: Desulfobacterales (>0.1%), Bacteroidales (>1%), Sulfur-cyclers

**Severity**: 🔴 **CRITICAL** — Prevents domain mismatch errors

---

### 🔴 Blocker 4: No Container Memory Limits

**File**: `docker-compose.yml`

**Problem**:
```yaml
api:
  # No memory limits set!
  # Container can consume all available RAM
  # If wide dataset loaded → OOM kill → system crash
```

**Fix**:
```yaml
api:
  deploy:
    resources:
      limits:
        memory: 2G  # Maximum memory
      reservations:
        memory: 1G  # Reserved memory
  
  worker:
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
```

**Impact**: Without limits, processing 1000+ sample datasets could crash entire Docker Compose stack.

**Severity**: 🔴 **CRITICAL** — Production stability

---

## Implementation Roadmap

### Phase 1: Critical Fixes (1-2 hours)

**Target**: Address all 🔴 blockers before any production data ingestion

```bash
# 1. Fix Schema Validation (20 min)
# File: app/services/validation_service.py
# - Replace coerce logic with strict validation
# - Add negative count detection
# - Reject + report, don't silently "fix"

# 2. Add Reverse Orphan Detection (15 min)
# File: app/services/validation_service.py
# - Add tax_set - asv_set check

# 3. Add Domain Biomarker Detection (45 min)
# File: app/services/validation_service.py
# - Implement _validate_soil_biomarkers()
# - Implement _validate_coastal_biomarkers()
# - Add to validation pipeline

# 4. Set Container Memory Limits (10 min)
# File: docker-compose.yml
# - Add memory limits to api, worker services
```

### Phase 2: Production Optimization (2-4 hours)

**Target**: Optimize for real-world wide datasets

```bash
# 5. Add Polars Backend (60 min)
# For datasets with >500 samples
# Reduces memory usage 40-60%

# 6. Implement Streaming CSV Validation (30 min)
# Validate headers before full file ingestion
# Fail fast on 1GB+ files with corrupt headers

# 7. Add NCBI Accession Validation (60 min)
# Fetch SRR/DRR/ERR metadata
# Reject if sample_type != expected domain

# 8. Add Health Checks (15 min)
# Monitor Redis, PostgreSQL, Celery worker health
# Auto-restart on failure
```

### Phase 3: Advanced Features (Post-Production)

```bash
# 9. Parquet Output Format
# Better compression, faster reading for ML

# 10. Real-time Upload Progress
# WebSocket integration for progress tracking

# 11. Distributed Processing
# Multi-worker Celery setup for parallel validation
```

---

## Audit Tools Provided

I've created **4 independent audit scripts** in the `/docs` folder:

### 1. `audit_environment.py` ✅
Validates environment configuration and service health

```bash
python docs/audit_environment.py
# Checks: PostgreSQL, Redis, SMTP, disk space, permissions
```

### 2. `audit_metagenomic.py` ✅
Validates CSV file structure and data integrity (Tiers 1-3)

```bash
python docs/audit_metagenomic.py asv.csv taxonomy.csv
# Tier 1: Structural (CSV format, encoding)
# Tier 2: Schema (numeric types, non-negative values) [PARTIAL]
# Tier 3: Relational (ID integrity) [PARTIAL]
```

### 3. `audit_domain_biomarkers.py` ✅
Detects soil vs. coastal microbiota biomarkers

```bash
python docs/audit_domain_biomarkers.py asv.csv taxonomy.csv SOIL
# Detects: Actinomycetota, Acidobacteriota, N-fixers
# Detects: Desulfobacterales, Bacteroidales, sulfur-cyclers
# Warns on domain mismatch
```

### 4. `audit_efficiency.py` ✅
Analyzes memory usage and streaming capability

```bash
python docs/audit_efficiency.py asv.csv
# Estimates: Pandas vs Polars memory
# Detects: Aiofiles, chunked reading, Celery config
# Recommends: Optimization strategies
```

### 5. `run_audits.sh` ✅
Runs all 4 audits in sequence with colored output

```bash
bash docs/run_audits.sh
```

---

## Quick Start: Implementing Priority Fixes

### Step 1: Fix Schema Validation

**File**: `app/services/validation_service.py`

**Location**: Line ~60 in `_run_tier_2_schema()`

**Change from**:
```python
for col in sample_cols:
    if not pd.api.types.is_numeric_dtype(self.asv_df[col]):
        self.asv_df[col] = pd.to_numeric(self.asv_df[col], errors='coerce').fillna(0)
```

**Change to**:
```python
for col in sample_cols:
    try:
        # Strict conversion: reject bad data
        self.asv_df[col] = pd.to_numeric(self.asv_df[col], errors='raise')
        
        # Validate non-negative (sequence counts can't be negative)
        if (self.asv_df[col] < 0).any():
            self._add_error(
                ValidationLayer.SCHEMA,
                "negative_counts",
                f"Sample '{col}' contains negative values (biologically impossible)",
                f"Found {(self.asv_df[col] < 0).sum()} negative values"
            )
            return False
    except (ValueError, TypeError) as e:
        self._add_error(
            ValidationLayer.SCHEMA,
            "non_numeric_abundance",
            f"Sample '{col}' contains non-numeric values",
            str(e)
        )
        return False
```

### Step 2: Add Reverse Orphan Detection

**File**: `app/services/validation_service.py`

**Location**: Add after forward orphan check (Line ~150)

**Add**:
```python
# Reverse orphans: Taxonomy IDs NOT in abundance table
reverse_orphans = tax_set - asv_set
if reverse_orphans:
    self._add_error(
        ValidationLayer.RELATIONAL,
        "reverse_orphan",
        f"Mismatch: {len(reverse_orphans)} taxonomy entries lack abundance data",
        f"Sample IDs: {list(reverse_orphans)[:5]}"
    )
    return False
```

### Step 3: Set Container Memory Limits

**File**: `docker-compose.yml`

**Locate**:
```yaml
api:
  build:
    ...
  container_name: gis_api
  restart: unless-stopped
  # ← ADD deploy section here:
```

**Add**:
```yaml
  deploy:
    resources:
      limits:
        memory: 2G
      reservations:
        memory: 1G
```

**Also for worker**:
```yaml
worker:
  deploy:
    resources:
      limits:
        memory: 1G
      reservations:
        memory: 512M
```

---

## Production Deployment Checklist

Before deploying to production:

- [ ] **Phase 1 Fixes Complete**
  - [ ] Schema validation rejects bad data
  - [ ] Reverse orphan detection implemented
  - [ ] Domain biomarker detection added
  - [ ] Container memory limits set

- [ ] **Testing Complete**
  - [ ] `audit_environment.py` passes
  - [ ] `audit_metagenomic.py` passes with test data
  - [ ] `audit_efficiency.py` tested with real datasets
  - [ ] Load test with 500+ sample dataset

- [ ] **Security**
  - [ ] SECRET_KEY is ≥32 random characters
  - [ ] MAIL_PASSWORD uses App Password (not regular password)
  - [ ] POSTGRES_PASSWORD follows security policy
  - [ ] No secrets in version control

- [ ] **Documentation**
  - [ ] README updated with audit procedures
  - [ ] Team trained on biomarker detection
  - [ ] Runbook created for troubleshooting

---

## References

- **Detailed System Audit**: `docs/SYSTEM_AUDIT.md`
- **Audit Toolkit Usage**: `docs/AUDIT_TOOLKIT.md`
- **Backend Code**: `app/services/validation_service.py`
- **Frontend Ingest UI**: `frontend/src/pages/IngestPage.jsx`

---

## Support

For questions or clarifications on audit findings:

1. Review the detailed report: `docs/SYSTEM_AUDIT.md`
2. Run audit tools with your test data: `bash docs/run_audits.sh`
3. Check AUDIT_TOOLKIT.md for troubleshooting

---

**Audit Completed**: March 31, 2026  
**System Status**: 🟡 **Ready for production after implementing Phase 1 fixes**  
**Estimated Fix Time**: 2-3 hours  
**Estimated Testing Time**: 2-4 hours
