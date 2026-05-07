# TPC-DS Benchmark Report: Trino vs Apache Spark

## Configuration

- **Dataset**: `iceberg_hive.benchmark_tpcds_sf50`
- **Warmup runs**: 1  |  **Measured runs**: 3
- **Resource budget**: 4 vCPU / 8 Gi per engine (Spark: local[4]; Trino: 1 coordinator + 1 worker)
- **Timeout**: 600s per query

## Engine performance summary

| Engine | Queries | Success | Fail | Success % | Total time | Median | P90 | Avg QPS | Max mem | Spill |
|---|---|---|---|---|---|---|---|---|---|---|
| **spark** | 12 | 12 | 0 | 100.0% | 568.442s | 42.27s | 93.274s | 0.0211 | 2350 MB | 0.0 MB |
| **trino** | 12 | 12 | 0 | 100.0% | 190.45s | 15.663s | 31.76s | 0.0630 | 1151 MB | 0.0 MB |

> **Trino median query time is 2.7× faster than Spark** (15.663s vs 42.27s).

## Result validation

- Comparable query runs: **12**
- Hash matches: **9 / 12** (75.0%)

Hash mismatches are expected for queries without an explicit `ORDER BY`:
Spark and Trino may return rows in different orders. The harness sorts rows before hashing, so ordering differences are eliminated.
Remaining mismatches indicate genuine numeric or NULL-handling divergence.

### Result Divergence Report

Queries with different results (hash or row count mismatch).

| Query | Run | Spark rows | Trino rows | Match? | Spark hash | Trino hash |
|---|---|---|---|---|---|---|
| query34 | 1 | 1 | 1 | ❌ | `e5c3430b` | `ab3f30bc` |
| query34 | 2 | 1 | 1 | ❌ | `e5c3430b` | `ab3f30bc` |
| query34 | 3 | 1 | 1 | ❌ | `e5c3430b` | `ab3f30bc` |

## Per-query comparison (median wall time, slowest Trino queries first)

| Query | Trino (s) | Trino CV% | Spark (s) | Spark CV% | Spark/Trino ratio | Faster |
|---|---|---|---|---|---|---|
| query11 | 31.76 | 1.85% | 93.274 | 5.93% | 2.94 | trino |
| query31 | 22.083 | 6.58% | 22.842 | 6.95% | 1.03 | trino |
| query34 | 9.096 | 14.86% | 9.546 | 11.67% | 1.05 | trino |
| query95 | 0.271 | 5.55% | 60.725 | 1.92% | 224.08 | trino |

## Methodology & Limitations

- **Compute vs E2E**: Benchmark was run with `WRAP_COUNT=true`. 
  - If `true`, metrics focus on core engine compute/shuffle (standard for comparison).
  - If `false`, metrics include significant Python/REST serialization overhead.
- **Memory Measurement**: Metrics represent **Total JVM/System Peak Memory** across the cluster. 
  - Trino: `peakTotalMemoryBytes` (Cluster-wide).
  - Spark: Sum of `JVMHeapMemory` peak across all executors + Driver RSS.
> ⚠️ **Note**: Memory metrics are NOT directly comparable between engines due to different accounting layers. Spark metrics focus on JVM Heap, while Trino includes more system-level buffers.
- **Caching**: `spark.catalog.clearCache()` was used between queries. 
  - Note: This does NOT clear JVM JIT compilation, filesystem metadata caches, or S3A connection pools. Subsequent queries may still benefit from lower-level warming.
- **Isolation**: Engines were run sequentially with `requests=limits` (Guaranteed QoS) to ensure no resource contention.
