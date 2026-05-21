#!/usr/bin/env python3
"""
AUDIT TOOL: Computational Efficiency & Memory Optimization
===========================================================

Analyzes:
- Pandas vs Polars performance for large datasets
- Memory footprint estimation
- Streaming capability
- Async task dispatching
- Container resource limits
"""

import sys
import os
import logging
from pathlib import Path
from typing import Tuple
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# MEMORY FOOTPRINT ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def estimate_memory_footprint(asv_path: str) -> Tuple[float, float, float]:
    """Estimate memory usage for Pandas vs Polars."""
    
    print("\n" + "="*80)
    print("AUDIT 1: MEMORY FOOTPRINT ANALYSIS")
    print("="*80)
    
    asv_path = Path(asv_path)
    
    # Get file size
    file_size_mb = asv_path.stat().st_size / (1024**2)
    logger.info(f"Input file size: {file_size_mb:.1f} MB")
    
    # Load with Pandas
    logger.info(f"Loading with Pandas...")
    asv_df = pd.read_csv(asv_path)
    
    # Estimate memory
    pandas_memory_mb = asv_df.memory_usage(deep=True).sum() / (1024**2)
    rows, cols = asv_df.shape
    
    logger.info(f"✅ Pandas loaded successfully")
    logger.info(f"   Shape: {rows:,} rows × {cols} columns")
    logger.info(f"   Memory: {pandas_memory_mb:.1f} MB")
    
    # Estimate Polars memory (typically 30-50% of Pandas for numeric data)
    polars_memory_mb = pandas_memory_mb * 0.40
    logger.info(f"\n📊 Polars estimate (lazy evaluation):")
    logger.info(f"   Memory: ~{polars_memory_mb:.1f} MB (40% of Pandas)")
    
    # Memory overhead estimation
    memory_overhead = pandas_memory_mb - file_size_mb
    logger.info(f"\n📈 Overhead Analysis:")
    logger.info(f"   File size: {file_size_mb:.1f} MB")
    logger.info(f"   Pandas memory: {pandas_memory_mb:.1f} MB")
    logger.info(f"   Overhead: {memory_overhead:.1f} MB ({memory_overhead/file_size_mb*100:.0f}%)")
    
    return pandas_memory_mb, polars_memory_mb, file_size_mb

# ══════════════════════════════════════════════════════════════════════════════
# DATASET CHARACTERISTICS
# ══════════════════════════════════════════════════════════════════════════════

def analyze_dataset_characteristics(asv_path: str) -> None:
    """Analyze dataset width, sparsity, and metadata."""
    
    print("\n" + "="*80)
    print("AUDIT 2: DATASET CHARACTERISTICS")
    print("="*80)
    
    asv_path = Path(asv_path)
    
    asv_df = pd.read_csv(asv_path)
    rows, cols = asv_df.shape
    
    id_col = asv_df.columns[0]
    sample_cols = [c for c in asv_df.columns if c != id_col]
    
    logger.info(f"Dataset dimensions:")
    logger.info(f"  Rows (ASVs): {rows:,}")
    logger.info(f"  Columns: {cols}")
    logger.info(f"  Sample columns: {len(sample_cols)}")
    
    # Classify as "wide" or "tall"
    if len(sample_cols) > 500:
        logger.warning(f"⚠️  WIDE dataset: {len(sample_cols)} samples (computation intensive)")
        logger.info(f"     Recommendation: Use Polars with lazy evaluation")
    else:
        logger.info(f"✅ Dataset width is manageable")
    
    if rows > 100000:
        logger.warning(f"⚠️  TALL dataset: {rows:,} ASVs (memory intensive)")
        logger.info(f"     Recommendation: Process in chunks or use Polars streaming")
    else:
        logger.info(f"✅ Dataset height is manageable")
    
    # Sparsity
    numerical_cols = asv_df[sample_cols]
    total_cells = numerical_cols.size
    zero_cells = (numerical_cols == 0).sum().sum()
    sparsity = zero_cells / total_cells
    
    logger.info(f"\nSparsity analysis:")
    logger.info(f"  Zero cells: {zero_cells:,} / {total_cells:,}")
    logger.info(f"  Sparsity: {sparsity*100:.1f}%")
    
    if sparsity > 0.95:
        logger.warning(f"⚠️  High sparsity (>95%) - compression recommended")
    
    # Data type distribution
    logger.info(f"\nData type distribution:")
    for dtype in asv_df[sample_cols].dtypes.unique():
        count = (asv_df[sample_cols].dtypes == dtype).sum()
        logger.info(f"  {dtype}: {count} columns")

# ══════════════════════════════════════════════════════════════════════════════
# STREAMING CAPABILITY
# ══════════════════════════════════════════════════════════════════════════════

def audit_streaming_capability(asv_path: str) -> Tuple[bool, list]:
    """Assess current streaming implementation."""
    
    print("\n" + "="*80)
    print("AUDIT 3: STREAMING & ASYNC CAPABILITY")
    print("="*80)
    
    errors = []
    
    # Check ingest.py for streaming implementation
    ingest_file = Path("app/api/routes/ingest.py")
    
    logger.info(f"Checking streaming implementation...")
    
    if ingest_file.exists():
        with open(ingest_file, 'r') as f:
            content = f.read()
        
        # Check for aiofiles
        if 'aiofiles' in content:
            logger.info(f"✅ PASS: aiofiles async I/O detected")
        else:
            logger.error(f"❌ FAIL: No aiofiles import (blocking I/O?)")
            errors.append("No async file I/O (aiofiles)")
        
        # Check for chunked reading
        if 'await file.read(' in content:
            logger.info(f"✅ PASS: Chunked file reading detected")
        else:
            logger.error(f"❌ FAIL: No chunked reading (loads entire file into memory)")
            errors.append("Not using chunked file reading")
        
        # Check for 202 Accepted response
        if 'status_code=202' in content:
            logger.info(f"✅ PASS: 202 Accepted status for async returns")
        else:
            logger.error(f"⚠️  WARN: No 202 Accepted (request should return immediately)")
            errors.append("Not returning 202 Accepted for async tasks")
    else:
        logger.warning(f"⚠️  SKIP: ingest.py not found")
    
    # Check Celery configuration
    celery_file = Path("app/workers/celery_app.py")
    if celery_file.exists():
        with open(celery_file, 'r') as f:
            content = f.read()
        
        if 'Celery' in content:
            logger.info(f"✅ PASS: Celery background task dispatcher configured")
        else:
            logger.error(f"❌ FAIL: No Celery configuration")
            errors.append("Celery not properly configured")
    
    # Check for streaming validation
    validation_file = Path("app/services/validation_service.py")
    if validation_file.exists():
        with open(validation_file, 'r') as f:
            content = f.read()
        
        if 'pd.read_csv' in content:
            logger.info(f"⚠️  WARN: Using pd.read_csv (loads entire file into memory)")
            logger.info(f"         Recommendation: Use chunksize parameter or Polars streaming")
            errors.append("Using memory-intensive pd.read_csv without chunking")
        
        if 'while' not in content or 'chunk' not in content.lower():
            logger.info(f"⚠️  WARN: No chunked/streamed parsing detected")
    
    return len(errors) == 0, errors

# ══════════════════════════════════════════════════════════════════════════════
# CONTAINER RESOURCE LIMITS
# ══════════════════════════════════════════════════════════════════════════════

def audit_container_limits() -> Tuple[bool, list]:
    """Check Docker container resource limits."""
    
    print("\n" + "="*80)
    print("AUDIT 4: CONTAINER RESOURCE LIMITS")
    print("="*80)
    
    errors = []
    
    docker_compose_file = Path("docker-compose.yml")
    
    if docker_compose_file.exists():
        with open(docker_compose_file, 'r') as f:
            content = f.read()
        
        # Check for memory limits on API container
        if 'memory:' not in content or 'mem_limit:' not in content:
            logger.error(f"❌ FAIL: No container memory limits set")
            logger.info(f"         Risk: Runaway processes can consume all host memory")
            logger.info(f"         Recommendation: Add memory limits (~2GB for API, ~1GB for worker)")
            errors.append("No container memory limits")
        else:
            logger.info(f"✅ PASS: Container memory limits detected")
        
        # Check for volume mounts
        if 'volumes:' in content and 'upload_tmp' in content:
            logger.info(f"✅ PASS: Upload volume mounted for persistence")
        else:
            logger.error(f"❌ FAIL: Upload volume not properly mounted")
            errors.append("Upload volume not mounted")
        
        # Check health checks
        if 'healthcheck' in content:
            logger.info(f"✅ PASS: Health checks configured")
        else:
            logger.warning(f"⚠️  WARN: No health checks (can't auto-restart failed services)")
            errors.append("No health checks configured")
    else:
        logger.warning(f"⚠️  SKIP: docker-compose.yml not found")
    
    return len(errors) == 0, errors

# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

def generate_recommendations(asv_path: str) -> None:
    """Generate performance optimization recommendations."""
    
    print("\n" + "="*80)
    print("PERFORMANCE OPTIMIZATION RECOMMENDATIONS")
    print("="*80)
    
    pandas_mb, polars_mb, file_mb = estimate_memory_footprint(asv_path)
    
    recommendations = []
    
    # Recommendation 1: Polars for wide datasets
    if asv_path:
        asv_df = pd.read_csv(asv_path)
        sample_cols = len(asv_df.columns) - 1
        
        if sample_cols > 500:
            recommendations.append({
                'priority': 'HIGH',
                'title': 'Use Polars for wide datasets',
                'description': f'Your dataset has {sample_cols} samples. Polars can reduce memory usage by 40-60%.',
                'implementation': 'Add polars as optional backend in validation_service.py',
            })
    
    # Recommendation 2: Container memory limits
    recommendations.append({
        'priority': 'HIGH',
        'title': 'Set container memory limits',
        'description': 'Prevent runaway processes from consuming all host memory',
        'implementation': 'Add memgis_api: 2gb and gis_worker: 1gb in docker-compose.yml',
    })
    
    # Recommendation 3: Streaming validation
    if pandas_mb > 500:
        recommendations.append({
            'priority': 'HIGH',
            'title': 'Implement streaming validation',
            'description': f'File is {file_mb:.0f}MB. Validate headers before full download.',
            'implementation': 'Add header validation in _stream_upload before full file ingestion',
        })
    
    # Recommendation 4: Chunked processing
    recommendations.append({
        'priority': 'MEDIUM',
        'title': 'Use chunked processing for large files',
        'description': 'Process files in 50-100MB chunks instead of loading entire file',
        'implementation': 'Use pd.read_csv(..., chunksize=10000) in preprocessing',
    })
    
    # Recommendation 5: Parquet output
    recommendations.append({
        'priority': 'MEDIUM',
        'title': 'Output to Parquet format',
        'description': 'Native columnar format for downstream ML tools, better compression',
        'implementation': 'Add asv_df.to_parquet() in preprocessing instead of CSV',
    })
    
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. [{rec['priority']}] {rec['title']}")
        print(f"   Description: {rec['description']}")
        print(f"   Implementation: {rec['implementation']}")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN AUDIT
# ══════════════════════════════════════════════════════════════════════════════

def main(asv_path: str = None):
    """Run computational efficiency audit."""
    
    print("\n" + "="*80)
    print("GENOMIC INTELLIGENCE SYSTEM - COMPUTATIONAL EFFICIENCY AUDIT")
    print("="*80)
    
    total_errors = []
    
    # Audit 1: Memory footprint
    if asv_path and Path(asv_path).exists():
        try:
            estimate_memory_footprint(asv_path)
            analyze_dataset_characteristics(asv_path)
        except Exception as e:
            logger.error(f"Could not analyze dataset: {e}")
    else:
        logger.info("⚠️  SKIP: No ASV file provided (use: audit_efficiency.py <asv_path>)")
    
    # Audit 2: Streaming capability
    success, errors = audit_streaming_capability(asv_path or "")
    total_errors.extend(errors)
    
    # Audit 3: Container limits
    success, errors = audit_container_limits()
    total_errors.extend(errors)
    
    # Recommendations
    if asv_path and Path(asv_path).exists():
        generate_recommendations(asv_path)
    
    # Summary
    print("\n" + "="*80)
    print("AUDIT SUMMARY")
    print("="*80)
    print(f"Total issues found: {len(total_errors)}")
    
    if total_errors:
        print(f"\nIssues:")
        for err in total_errors:
            print(f"  - {err}")
        return 1
    else:
        print(f"\n🟢 COMPUTATIONAL EFFICIENCY: PASS")
        return 0

if __name__ == '__main__':
    asv_path = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(main(asv_path))
