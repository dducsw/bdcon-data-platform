# TPC-DS Benchmark Report: Trino vs Apache Spark

## Configuration

- **Dataset**: `iceberg_hive.benchmark_tpcds_sf5`
- **Warmup runs**: 1  |  **Measured runs**: 3
- **Resource budget**: 4 vCPU / 8 Gi per engine (Spark: local[4]; Trino: 1 coordinator + 1 worker)
- **Timeout**: 1800s per query

## Engine performance summary

| Engine | Queries | Success | Fail | Success % | Total time | Median | P90 | Avg QPS | Max mem | Spill |
|---|---|---|---|---|---|---|---|---|---|---|
| **spark** | 15 | 15 | 0 | 100.0% | 156.921s | 2.944s | 40.541s | 0.0956 | 7968 MB | 0.0 MB |
| **trino** | 15 | 15 | 0 | 100.0% | 86.515s | 2.643s | 18.531s | 0.1734 | 794 MB | 0.0 MB |

> **Trino median query time is 1.1× faster than Spark** (2.643s vs 2.944s).

## Result validation

- Comparable query runs: **15**
- Hash matches: **15 / 15** (100.0%)

Hash mismatches are expected for queries without an explicit `ORDER BY`:
Spark and Trino may return rows in different orders. The harness sorts rows before hashing, so ordering differences are eliminated.
Remaining mismatches indicate genuine numeric or NULL-handling divergence.

## Per-query comparison (avg wall time, slowest Trino queries first)

| Query | Trino (s) | Spark (s) | Spark/Trino ratio | Faster |
|---|---|---|---|---|
| query4 | 18.531 | 40.541 | 2.19 | trino |
| query3 | 2.701 | 2.181 | 0.81 | spark |
| query1 | 2.643 | 2.944 | 1.11 | trino |
| query5 | 2.228 | 4.013 | 1.8 | trino |
| query2 | 1.581 | 2.362 | 1.49 | trino |

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
