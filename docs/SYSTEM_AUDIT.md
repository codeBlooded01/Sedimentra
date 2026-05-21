# Genomic Intelligence System — Comprehensive System Audit Report

**Date**: March 31, 2026  
**System**: Genomic Intelligence System for Soil & Coastal Sediment Metagenomic Analysis  
**Audit Scope**: Architectural integrity, metagenomic validation, domain-specific sanity checks, computational efficiency

---

## Executive Summary

The Genomic Intelligence System is **architecturally sound** with a properly designed FastAPI backend, React/Vite frontend, and PostgreSQL+Redis data pipeline. The system implements **3-tier validation** (Structural, Schema, Relational) and uses Celery for async background processing.

**Critical Findings**:
- ✅ Frontend-Backend handshake verified (Port 5173 ↔ 8000)
- ✅ File streaming implemented (prevents RAM exhaustion for files >50MB)
- ✅ 3-tier validation pipeline in place
- ⚠️ **MISSING**: Domain-specific biomarker detection (Soil/Coastal)
- ⚠️ **MISSING**: Streaming parser for large datasets (using Pandas, not Polars)
- ⚠️ **MISSING**: NCBI Accession validation logic
- ⚠️ **INCOMPLETE**: Error handling for multipart streams >500MB

---

## 1. ARCHITECTURAL ALIGNMENT & PROTOCOL AUDIT

### 1.1 Frontend-Backend Handshake

**Status**: ✅ VERIFIED

**Configuration**:
- Frontend: React 18.3.1 on Vite (Port 5173)
- Backend: FastAPI on Uvicorn (Port 8000)
- Proxy: Configured in `vite.config.js`
```javascript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
}
```

**Verification**:
- ✅ CORS configured for `http://localhost:5173`
- ✅ Bearer token injection via Axios interceptors
- ✅ Auto-refresh on 401 implemented
- ✅ Content-Type handling for multipart/form-data

**Health Check Endpoint**: 
```
GET /health → {"status": "ok", "system": "Genomic Intelligence System", "version": "1.0.0"}
```

---

### 1.2 Multipart Stream Parsing for Files >50MB

**Current Implementation**: ❌ PARTIAL

**Current State**:
```python
# app/api/routes/ingest.py (lines 50-60)
async def _stream_upload(file: UploadFile, path: Path):
    async with aiofiles.open(path, 'wb') as f:
        while content := await file.read(1024 * 1024):  # 1MB chunks
            await f.write(content)
```

**Issues Identified**:
1. ❌ No explicit stream size validation before writing
2. ❌ No progress callback mechanism for large files
3. ❌ No automatic chunking strategy for files >500MB
4. ✅ Uses aiofiles (async I/O) ✓

**Recommendation**: Implement explicit chunk-size validation and memory-efficient buffering.

---

### 1.3 Environment Integrity Check

**Status**: ✅ CONFIGURED, ⚠️ VALIDATION GAPS

**Environment Variables**:
```
✅ DATABASE_URL: postgresql+asyncpg://gis_user:***@db:5432/genomic_db
✅ REDIS_URL: redis://redis:6379/0
✅ MAIL_SERVER: smtp.gmail.com (port 587)
✅ POSTGRES volumes: gis_pg_data (persistent)
✅ Upload volumes: upload_tmp:/tmp/gis_uploads (persistent)
```

**Docker Volume Mapping**:
```yaml
volumes:
  upload_tmp: /tmp/gis_uploads  ✅ Correctly mounted for Celery worker
  gis_pg_data: /var/lib/postgresql/data ✅ PostgreSQL persistence
```

**Missing Environment Validations**:
- ❌ No validation that `TMP_UPLOAD_DIR` has sufficient disk space
- ❌ No health check for Redis connectivity (Celery will fail silently)
- ❌ No validation for NCBI API keys (if planning SRR import)
- ⚠️ MAIL_PASSWORD stored in plaintext .env (should use secrets manager)

---

## 2. METAGENOMIC STRUCTURAL VALIDATION (TIERS 1 & 2)

### 2.1 Tier 1: Structural Validation

**Status**: ✅ IMPLEMENTED

**Implementation**:
```python
def _run_tier_1_structural(self) -> bool:
    try:
        self.asv_df = pd.read_csv(self.asv_path)
        self.tax_df = pd.read_csv(self.taxonomy_path)
    except pd.errors.ParserError as e:
        # Proper error handling with user-friendly messages
```

**Coverage**:
- ✅ Detects malformed CSV files
- ✅ Detects encoding issues
- ✅ Returns user-friendly error messages

---

### 2.2 Tier 2: Schema Validation

**Status**: ✅ IMPLEMENTED, ⚠️ INCOMPLETE

**Current Schema Checks**:
```python
required_tax = ['kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species']
missing_tax = [req for req in required_tax if req not in tax_cols]
```

**Critical Issues**:

1. ❌ **No Abundance Data Type Validation**
   - Current code: `pd.to_numeric(..., errors='coerce').fillna(0)`
   - **Problem**: Silently coerces non-numeric to 0, masking data quality issues
   - **Recommendation**: Reject with explicit error, don't silently coerce

2. ❌ **No Validation for Strictly Non-Negative Values**
   - Missing: Check for negative counts (biologically impossible)
   - Current code allows negative values post-coercion

3. ❌ **No Integer vs Float Enforcement**
   - ASV counts should be **Integers** (sequence reads)
   - Current code doesn't validate this

**Required Fix**:
```python
# Should validate:
def _validate_abundance_types(self, asv_df):
    for sample_col in self.sample_columns:
        if not all(asv_df[sample_col] >= 0):
            raise ValueError(f"Negative counts detected in {sample_col}")
        # If counts are floats, validate they're read counts (integers)
        if not all(asv_df[sample_col] == asv_df[sample_col].astype(int)):
            self.report.warnings.append(f"Non-integer counts in {sample_col}")
```

---

### 2.3 Tier 3: Relational/ID Integrity Constraint

**Status**: ✅ PARTIALLY IMPLEMENTED

**Current Implementation**:
```python
asv_set = set(self.asv_df['ASV_ID'].astype(str))
tax_set = set(self.tax_df['ASV_ID'].astype(str))
orphaned = asv_set - tax_set

if orphaned:
    self._add_error(...)
    return False
```

**Coverage**:
- ✅ Detects orphaned ASVs (in abundance but not taxonomy)
- ✅ Uses Set Theory for integrity check (O(1) membership)

**Missing Checks**:
1. ❌ **Reverse Orphans**: ASVs in taxonomy but NOT in abundance table
2. ❌ **Duplicate IDs**: Duplicate ASV_IDs in either table (silent behavior)
3. ❌ **ID Format Validation**: No check for valid ID format

**Comprehensive Set Theory Audit**:
```python
def _comprehensive_id_audit(self):
    asv_set = set(self.asv_df['ASV_ID'])
    tax_set = set(self.tax_df['ASV_ID'])
    
    # Forward orphans: In abundance but not in taxonomy
    forward_orphans = asv_set - tax_set
    
    # Reverse orphans: In taxonomy but not in abundance
    reverse_orphans = tax_set - asv_set
    
    # Duplicates
    asv_dups = len(self.asv_df) - len(asv_set)
    tax_dups = len(self.tax_df) - len(tax_set)
    
    if forward_orphans or reverse_orphans:
        raise ValidationError(...)
    if asv_dups > 0 or tax_dups > 0:
        raise ValidationError(...)
```

---

## 3. DOMAIN-SPECIFIC SANITY CHECK (TIER 3+)

### 3.1 Soil Microbiome Biomarkers

**Status**: ❌ NOT IMPLEMENTED

**Required Biomarkers** for Soil Environment:

| Phylum | Order | Indicator | Presence Threshold |
|--------|-------|-----------|-------------------|
| Actinomycetota | Actinomycetales | Soil carbon cycling | >1% relative |
| Acidobacteriota | Acidobacteriales | Acidic soil indicator | >5% relative |
| Bacillota | Bacillales | Spore-formers (resilience) | >0.5% relative |
| - | - | Nitrogen-fixation (nifH gene) | Present if N-cycling expected |

**Ecological Context**:
- **High Actinomycete abundance** (>20%): Indicates mature, stable soil microbiota
- **High Acidobacteria** (>10%): Suggests acidic pH or nutrient-poor conditions
- **Missing N-fixers in N-limited soils**: Potential data quality issue

---

### 3.2 Coastal Sediment Biomarkers

**Status**: ❌ NOT IMPLEMENTED

**Required Biomarkers** for Coastal/Marine Sediment:

| Phylum | Order | Indicator | Presence Threshold |
|--------|-------|-----------|-------------------|
| Desulfobacterota | Desulfobacterales | Sulfur cycling (anaerobic) | >2% relative |
| Bacteroidota | Bacteroidales | DMSP degradation, algal breakdown | >5% relative |
| Firmicutes | Clostridiales | Fermentation under hypoxia | >1% relative |
| - | - | Sulfate-reducing bacteria (dsrA) | Present if anaerobic |

**Ecological Context**:
- **High Desulfobacterales** (>5%): Strong indicator of active sulfur cycling
- **Low diversity + high Desulfobacterales**: Suggests anoxic conditions
- **Missing Bacteroidales in coastal sediment**: Potential domain mismatch

---

### 3.3 Domain Mismatch Detection Logic

**Current Implementation**: ❌ NOT IMPLEMENTED

**Proposed Tier 3+ Logic**:

```python
def _run_tier_3_domain_check(self) -> bool:
    """Detect if taxa match expected environment (Soil vs Coastal)."""
    
    # Infer expected domain from filename or metadata
    expected_domain = self._infer_domain_from_metadata()
    
    if expected_domain == "SOIL":
        return self._validate_soil_biomarkers()
    elif expected_domain == "COASTAL":
        return self._validate_coastal_biomarkers()
    else:
        return True  # Skip if domain uncertain
    
def _validate_soil_biomarkers(self) -> bool:
    actinomycetota = self._get_phylum_relative_abundance("Actinomycetota")
    acidobacteriota = self._get_phylum_relative_abundance("Acidobacteriota")
    
    if actinomycetota < 0.01 and acidobacteriota < 0.05:
        self.report.warnings.append(
            "POTENTIAL DOMAIN MISMATCH: Expected soil biomarkers "
            "(Actinomycetota, Acidobacteriota) are absent. "
            "Verify sample type."
        )
    return True  # Warning, not failure

def _validate_coastal_biomarkers(self) -> bool:
    desulfobacterales = self._get_order_relative_abundance("Desulfobacterales")
    bacteroidales = self._get_order_relative_abundance("Bacteroidales")
    
    if desulfobacterales < 0.02 and bacteroidales < 0.05:
        self.report.warnings.append(
            "POTENTIAL DOMAIN MISMATCH: Expected coastal biomarkers "
            "(Desulfobacterales, Bacteroidales) are absent. "
            "Verify sample type."
        )
    return True
```

---

## 4. COMPUTATIONAL EFFICIENCY & PIPELINE PERFORMANCE

### 4.1 Async Task Dispatching

**Status**: ✅ IMPLEMENTED

**Current Flow**:
```python
@router.post("/upload", ..., status_code=202)
async def upload_genomic_files(...):
    task = run_ingestion_pipeline.delay(job_id, asv_path, tax_path)
    return UploadJobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message="Files received. Validation is running in the background.",
    )
```

**Verification**:
- ✅ Returns **202 Accepted** immediately (HTTP best practice)
- ✅ Celery task dispatched asynchronously
- ✅ Frontend polls `/status/{job_id}` for progress

---

### 4.2 Memory Optimization: Pandas vs Polars

**Current Implementation**: ❌ Pandas only

**Issue**: Pandas loads entire CSV into RAM. For datasets with 100,000+ rows and 1,000+ columns:
- Pandas memory: ~1.2GB (100k rows × 1k columns × 8 bytes/float64)
- Polars with streaming: ~100MB (lazy evaluation)

**Current Docker Container Limits**: 
```yaml
# docker-compose.yml - NO memory limit set!
# Containers can consume all host memory → OOM kill
```

**Recommendations**:
1. Add Polars as optional backend for "wide" datasets
2. Implement lazy evaluation for preview mode
3. Set container memory limits (512MB - 2GB depending on dataset size)

---

### 4.3 Streaming Parser Implementation

**Status**: ⚠️ PARTIAL

**Current File Upload**:
```python
async def _stream_upload(file: UploadFile, path: Path):
    async with aiofiles.open(path, 'wb') as f:
        while content := await file.read(1024 * 1024):
            await f.write(content)
```

**Missing**: Mid-parse validation during streaming
- Doesn't validate headers until entire file is written
- For a corrupted 500MB file, only fails after fully ingested

**Recommended Enhancement**:
```python
async def _stream_upload_with_validation(file, path):
    """Stream + validate incrementally."""
    first_chunk = await file.read(1024)  # Read header
    headers = first_chunk.decode().split('\n')[0].split(',')
    
    if not _validate_headers(headers):
        raise ValueError("Invalid headers")
    
    # Continue streaming rest of file
    async with aiofiles.open(path, 'wb') as f:
        f.write(first_chunk)
        while content := await file.read(1024 * 1024):
            f.write(content)
```

---

### 4.4 Accession (SRR/DRR/ERR) Import Validation

**Status**: ❌ NOT IMPLEMENTED

**Current Code**: No NCBI integration exists

**Missing Implementation** for `/accession/lookup`:

```python
@router.post("/accession/lookup")
async def lookup_accession(accession: str):
    """
    Fetch metadata from NCBI SRA for the given accession.
    Reject if sample_type is incompatible (e.g., "Human Clinical" for Soil).
    """
    
    # Step 1: Query NCBI E-utilities
    metadata = await fetch_ncbi_metadata(accession)
    
    # Step 2: Extract sample type
    sample_type = metadata.get('sample_type')
    
    # Step 3: Validate against expected domain
    expected_domain = detect_domain_from_request()
    valid_types = {
        'SOIL': ['soil', 'environmental', 'terrestrial'],
        'COASTAL': ['marine', 'sediment', 'coastal', 'brackish'],
    }
    
    if sample_type.lower() not in valid_types.get(expected_domain, []):
        raise HTTPException(
            status_code=400,
            detail=f"Sample type '{sample_type}' incompatible with expected domain '{expected_domain}'"
        )
    
    return metadata
```

---

## 5. CRITICAL GAPS & RECOMMENDATIONS

### Priority 1 (Implement Immediately):

1. **Add Strict Abundance Validation**
   - Reject negative counts (not coerce to 0)
   - Validate integer vs float appropriately
   - File: `app/services/validation_service.py`

2. **Comprehensive ID Audit**
   - Check reverse orphans (taxonomy IDs not in abundance)
   - Detect duplicate ASV IDs
   - File: `app/services/validation_service.py`

3. **Domain-Specific Biomarker Detection**
   - Implement Tier 3+ validation for Soil/Coastal
   - Detect biomarkers early, warn user
   - File: `app/services/validation_service.py`

4. **Set Container Memory Limits**
   - Prevent runaway processes from crashing entire system
   - File: `docker-compose.yml`

### Priority 2 (Implement Before Production):

5. **Add Polars Backend Option**
   - For "wide" (many samples) datasets
   - Lazy evaluation for memory efficiency
   - File: `app/services/validation_service.py`

6. **NCBI Accession Integration**
   - Validate sample metadata before download
   - Build accession lookup service
   - File: NEW `app/services/accession_service.py`

7. **Progress Tracking for Large Uploads**
   - Report upload progress to frontend
   - File: `app/api/routes/ingest.py`

### Priority 3 (Polish & Optimization):

8. **Streaming Validation During Parse**
   - Validate headers before full download
   - File: `app/api/routes/ingest.py`

9. **Rate Limiting on Ingest Endpoint**
   - Prevent abuse (currently not rate-limited)
   - File: `app/api/routes/ingest.py`

10. **Add Parquet Output Format**
    - Native support for columnar storage
    - Enable downstream ML tools
    - File: `app/services/validation_service.py`

---

## 6. CONCLUSION

**Overall Assessment**: 🟢 **SOUND ARCHITECTURE, MISSING DOMAIN LOGIC**

The system has a solid foundation with proper async handling, 3-tier validation, and streaming I/O. However, **domain-specific validation** (biomarker detection for Soil vs Coastal) and **production-grade data validation** (abundance type checking, strict ID integrity) are missing.

**Next Steps**:
1. Implement recommended Priority 1 fixes
2. Add domain-specific biomarker detection Tier 3+
3. Integrate NCBI accession validation
4. Load test with real-world wide datasets (1000+ samples)
5. Implement memory-efficient Polars backend

---

**Report Generated**: March 31, 2026  
**Audit Conducted By**: Genomic Intelligence System Auto-Audit  
**Reviewed By**: [PENDING HUMAN REVIEW]
