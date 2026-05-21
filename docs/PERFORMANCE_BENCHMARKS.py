"""
AD-GSI v4.0 — PERFORMANCE BENCHMARKS & OPTIMIZATION GUIDE

Profiling, benchmarking, and optimization recommendations for production deployment.
"""

import logging
import time
import pandas as pd
import numpy as np
from typing import Dict, Tuple
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# BENCHMARK DATA GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_benchmark_data(
    num_asvs: int = 10000,
    num_samples: int = 100,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate synthetic ASV & taxonomy data for benchmarking.
    
    Scenarios:
    - Small: 1K ASVs × 50 samples    (~50K data points)
    - Medium: 5K ASVs × 100 samples  (~500K data points)
    - Large: 10K ASVs × 100 samples  (~1M data points)
    - XL: 50K ASVs × 200 samples     (~10M data points)
    """
    
    np.random.seed(seed)
    
    # Generate ASV table
    asv_ids = [f'ASV_{i}' for i in range(num_asvs)]
    sample_ids = [f'Sample_{i}' for i in range(num_samples)]
    
    # Sparse abundance matrix (80% zeros, following real metagenomics)
    data = {}
    data['ASV_ID'] = asv_ids
    
    for sample_id in sample_ids:
        # Generate Poisson abundances (rare tail distribution)
        abundances = np.random.poisson(lam=2, size=num_asvs)
        data[sample_id] = abundances
    
    asv_df = pd.DataFrame(data)
    
    # Generate taxonomy
    ranks = [
        'k__Bacteria',
        'k__Archaea',
    ]
    phyla = [
        'p__Bacteroidota',
        'p__Desulfobacterota',
        'p__Proteobacteria',
        'p__Firmicutes',
        'p__Actinomycetota',
    ]
    
    tax_data = {
        'ASV_ID': asv_ids,
        'taxonomy': [
            f"{np.random.choice(ranks)};p__{np.random.choice(phyla)};c__;o__;f__;g__;s__"
            for _ in range(num_asvs)
        ]
    }
    
    tax_df = pd.DataFrame(tax_data)
    
    return asv_df, tax_df

# ══════════════════════════════════════════════════════════════════════════════
# BENCHMARK RUNNER
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""
    scenario: str
    num_asvs: int
    num_samples: int
    duration_sec: float
    memory_mb: float
    asv_datapoints: int
    throughput_mps: float  # Million points per second
    
    def __str__(self):
        return (f"{self.scenario:15} | ASVs: {self.num_asvs:>6} | "
                f"Samples: {self.num_samples:>3} | Duration: {self.duration_sec:>7.2f}s | "
                f"Memory: {self.memory_mb:>7.1f}MB | Throughput: {self.throughput_mps:>6.2f} MptS")

class PipelineBenchmark:
    """End-to-end pipeline benchmarking."""
    
    def __init__(self):
        self.results = []
    
    def run_scenario(
        self,
        scenario_name: str,
        num_asvs: int,
        num_samples: int,
    ) -> BenchmarkResult:
        """Run a single benchmark scenario."""
        
        logger.info(f"Running scenario: {scenario_name} ({num_asvs} ASVs × {num_samples} samples)")
        
        # Generate data
        asv_df, tax_df = generate_benchmark_data(num_asvs, num_samples)
        
        # Time the pipeline
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024
        
        start_time = time.time()
        
        # Import here to avoid circular deps
        from app.services.production_pipeline import validate_and_generate_ml_features
        
        try:
            success, ml_features, audit = validate_and_generate_ml_features(
                asv_df, tax_df,
                id_column='ASV_ID',
                domain='COASTAL'
            )
        except Exception as e:
            logger.error(f"Scenario {scenario_name} failed: {e}")
            return None
        
        end_time = time.time()
        mem_after = process.memory_info().rss / 1024 / 1024
        
        duration = end_time - start_time
        memory_mb = mem_after - mem_before
        datapoints = num_asvs * num_samples
        throughput_mps = (datapoints / 1_000_000) / duration
        
        result = BenchmarkResult(
            scenario=scenario_name,
            num_asvs=num_asvs,
            num_samples=num_samples,
            duration_sec=duration,
            memory_mb=max(0, memory_mb),
            asv_datapoints=datapoints,
            throughput_mps=throughput_mps,
        )
        
        self.results.append(result)
        logger.info(f"✓ {result}")
        
        return result
    
    def run_all_scenarios(self) -> None:
        """Run full benchmark suite."""
        
        logger.info("=" * 100)
        logger.info("AD-GSI v4.0 PERFORMANCE BENCHMARKS")
        logger.info("=" * 100)
        
        scenarios = [
            ('Small', 1_000, 50),
            ('Medium', 5_000, 100),
            ('Large', 10_000, 100),
            ('XL', 50_000, 200),
        ]
        
        for scenario, num_asvs, num_samples in scenarios:
            self.run_scenario(scenario, num_asvs, num_samples)
            time.sleep(1)  # Cooldown between runs
        
        self.print_summary()
    
    def print_summary(self) -> None:
        """Print benchmark summary table."""
        
        logger.info("\n" + "=" * 100)
        logger.info("SUMMARY")
        logger.info("=" * 100)
        
        for result in self.results:
            if result:
                print(result)
        
        # Scaling analysis
        logger.info("\n" + "-" * 100)
        logger.info("SCALING ANALYSIS")
        logger.info("-" * 100)
        
        if len(self.results) >= 2:
            r1 = self.results[0]
            r2 = self.results[1]
            
            data_ratio = r2.asv_datapoints / r1.asv_datapoints
            duration_ratio = r2.duration_sec / r1.duration_sec
            scaling = duration_ratio / data_ratio
            
            logger.info(f"Data scaling: {data_ratio:.1f}×")
            logger.info(f"Duration scaling: {duration_ratio:.1f}×")
            logger.info(f"Efficiency: {scaling:.2f}× (1.0 = linear, <1 = sublinear)")

# ══════════════════════════════════════════════════════════════════════════════
# OPTIMIZATION RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

OPTIMIZATION_GUIDE = """
AD-GSI v4.0 OPTIMIZATION STRATEGIES
====================================

1. PARALLEL PROCESSING
   ─────────────────────
   Current: Sequential per-sample processing (Phase 4-6)
   
   Opportunity: Process multiple samples in parallel
   - Use multiprocessing.Pool for CPU-bound work
   - Each process: Single sample through Phase 4-6
   - I/O-bound work (DB persistence): Use asyncio
   
   Expected speedup: 4-8× on 8-core machine

2. VECTORIZATION
   ──────────────
   Current: Row-by-row numpy operations (SequenceAuditor)
   
   Opportunity: Use NumPy broadcasting for weighted statistics
   - Calculate weighted median across all samples at once
   - Vectorize confidence score calculation
   
   Expected speedup: 2-3×

3. CACHING
   ────────
   Current: TaxRecord caches parsed taxonomy per ASV
   
   Opportunity: 
   - Cache FAPROTAX lookups (LRU cache)
   - Memoize unclassified detection
   - Cache ordered/family matches for faster fallback
   
   Expected speedup: 1.5-2× (taxonomy parsing phase)

4. DATAFRAME OPTIMIZATION
   ──────────────────────
   Current: Pandas with default index
   
   Opportunity:
   - Use multi-level index for (ASV_ID, Sample_ID)
   - Pre-allocate DataFrames before building
   - Use sparse matrices for abundance table (80% zeros)
   - Consider Polars for larger datasets (5M+ points)
   
   Expected speedup: 1.2-2× (depends on sparsity)

5. DATABASE BATCH OPERATIONS
   ────────────────────────
   Current: One insert per feature (1000s of statements)
   
   Opportunity:
   - Use SQLAlchemy bulk_insert_mappings()
   - Transaction batching (commit every N rows)
   - Use PostgreSQL COPY for mass inserts
   
   Expected speedup: 10-50× (persistence phase)

6. FAPROTAX DATABASE
   ──────────────────
   Current: In-memory hardcoded (23 entries)
   
   Opportunity:
   - Load full FAPROTAX JSON at startup
   - Index by taxonomy rank (O(1) lookups)
   - Cache misses: Pre-compute fallback chains
   
   Expected impact: 20-30% faster Phase 4

7. ASYNCHRONOUS I/O
   ──────────────────
   Current: Blocking file operations
   
   Opportunity:
   - Use aiofiles for async parquet reading
   - Async database connections (asyncpg)
   - Parallel file I/O for multiple jobs
   
   Expected speedup: 2-3× when processing 10+ concurrent jobs

RECOMMENDED PRODUCTION SETUP
════════════════════════════

1. Load Balancer
   - Nginx reverse proxy (80/443 → 8000)
   - Round-robin across 4 Uvicorn workers

2. Celery Workers
   - 2-4 workers (depends on CPU cores)
   - Each with prefetch_multiplier=2
   - Concurrency=2-4 threads per worker

3. PostgreSQL
   - Connection pooling: PgBouncer (100 connections)
   - Indexes on (job_id, sample_id) for fast queries
   - Backup strategy: WAL archiving + daily snapshots

4. Redis
   - Cache FAPROTAX database
   - Celery result backend (6-hour timeout)
   - Session caching for API

5. Monitoring
   - Prometheus metrics (Celery task duration, fail rate)
   - Grafana dashboards (throughput, latency, resource usage)
   - Alerts on confidence collapse, Phase 1 failures

PERFORMANCE TARGETS
════════════════════

Target SLAs (per job):
- Small (1K ASVs × 50 samples):  < 5 seconds
- Medium (5K ASVs × 100 samples): < 30 seconds
- Large (10K ASVs × 100 samples): < 60 seconds

Throughput:
- Single job: 1-2M data points/second
- 10 concurrent jobs: 10-20M data points/second

Resource Usage:
- Memory per job: 100-500 MB (scales with ASV count)
- Disk per job: 50-200 MB (Parquet + JSON output)

Error Rate Target:
- Phase 1 failures: < 1% (hard-fail as designed)
- Phase 4-6 completions: > 99%
"""

# ══════════════════════════════════════════════════════════════════════════════
# MAIN: RUN BENCHMARKS
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    print(OPTIMIZATION_GUIDE)
    print("\n" + "=" * 100)
    
    benchmark = PipelineBenchmark()
    benchmark.run_all_scenarios()
