# TPC-DS Benchmark Report: Trino vs Apache Spark

## Configuration

- **Dataset**: `iceberg_hive.benchmark_tpcds_sf50`
- **Warmup runs**: 1  |  **Measured runs**: 3
- **Resource budget**: 4 vCPU / 8 Gi per engine (Spark: local[4]; Trino: 1 coordinator + 1 worker)
- **Timeout**: 1800s per query

## Engine performance summary

| Engine | Queries | Success | Fail | Success % | Total time | Median | P90 | Avg QPS | Max mem | Spill |
|---|---|---|---|---|---|---|---|---|---|---|
| **spark** | 297 | 297 | 0 | 100.0% | 2775.07s | 3.329s | 28.0s | 0.1070 | 5226 MB | 4661.8 MB |
| **trino** | 297 | 297 | 0 | 100.0% | 2656.061s | 3.817s | 19.166s | 0.1118 | 4062 MB | 0.0 MB |

> **Trino median query time is 0.9× slower than Spark** (3.817s vs 3.329s).

## Result validation

- Comparable query runs: **279**
- Hash matches: **0 / 279** (0.0%)

Hash mismatches are expected for queries without an explicit `ORDER BY`:
Spark and Trino may return rows in different orders. The harness sorts rows before hashing, so ordering differences are eliminated.
Remaining mismatches indicate genuine numeric or NULL-handling divergence.

### Mismatched queries (first 10)

| Query | Run | Spark rows | Trino rows | Spark hash | Trino hash |
|---|---|---|---|---|---|
| query1 | 1 | 100 | 1 | `65d5325a` | `ca66bb68` |
| query1 | 2 | 100 | 1 | `65d5325a` | `ca66bb68` |
| query1 | 3 | 100 | 1 | `65d5325a` | `ca66bb68` |
| query10 | 1 | 55 | 1 | `9e50e4ba` | `ca66bb68` |
| query10 | 2 | 55 | 1 | `9e50e4ba` | `ca66bb68` |
| query10 | 3 | 55 | 1 | `9e50e4ba` | `ca66bb68` |
| query11 | 1 | 100 | 1 | `b478a773` | `ca66bb68` |
| query11 | 2 | 100 | 1 | `b478a773` | `ca66bb68` |
| query11 | 3 | 100 | 1 | `b478a773` | `ca66bb68` |
| query12 | 1 | 100 | 1 | `7b2e890e` | `ca66bb68` |

## Per-query comparison (avg wall time, slowest Trino queries first)

| Query | Trino (s) | Spark (s) | Spark/Trino ratio | Faster |
|---|---|---|---|---|
| query14 | 119.176 | 27.239 | 0.23 | spark |
| query67 | 117.491 | 35.602 | 0.3 | spark |
| query47 | 49.604 | 5.878 | 0.12 | spark |
| query78 | 43.971 | 37.317 | 0.85 | spark |
| query11 | 33.539 | 17.699 | 0.53 | spark |
| query51 | 31.611 | 13.472 | 0.43 | spark |
| query57 | 23.15 | 3.666 | 0.16 | spark |
| query75 | 22.277 | 10.242 | 0.46 | spark |
| query64 | 19.748 | 52.072 | 2.64 | trino |
| query65 | 19.138 | 8.87 | 0.46 | spark |
| query4 | 18.531 | 33.889 | 1.83 | trino |
| query22 | 18.199 | 13.554 | 0.74 | spark |
| query93 | 16.831 | 28.0 | 1.66 | trino |
| query17 | 15.795 | 34.313 | 2.17 | trino |
| query74 | 13.784 | 16.61 | 1.21 | trino |
| query72 | 12.575 | 89.12 | 7.09 | trino |
| query24 | 12.484 | 19.502 | 1.56 | trino |
| query31 | 12.274 | 3.531 | 0.29 | spark |
| query70 | 11.532 | 2.411 | 0.21 | spark |
| query85 | 10.873 | 4.811 | 0.44 | spark |
| query25 | 10.122 | 32.264 | 3.19 | trino |
| query29 | 9.962 | 27.632 | 2.77 | trino |
| query59 | 7.937 | 3.111 | 0.39 | spark |
| query6 | 7.763 | 5.315 | 0.68 | spark |
| query49 | 7.573 | 8.148 | 1.08 | trino |
| query7 | 7.446 | 11.904 | 1.6 | trino |
| query50 | 7.391 | 16.042 | 2.17 | trino |
| query36 | 7.272 | 2.327 | 0.32 | spark |
| query44 | 7.232 | 1.843 | 0.25 | spark |
| query39 | 7.071 | 6.143 | 0.87 | spark |

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
