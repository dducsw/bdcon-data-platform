# TPC-DS Benchmark Report: Trino vs Apache Spark

## Configuration

- **Dataset**: `iceberg_hive.benchmark_tpcds_sf50`
- **Warmup runs**: 2  |  **Measured runs**: 5
- **Resource budget**: 4 vCPU / 8 Gi per engine (Spark: local[4]; Trino: 1 coordinator + 1 worker)
- **Timeout**: 1800s per query

## Engine performance summary

| Engine | Queries | Success | Fail | Success % | Total E2E | Median Engine | P90 Engine | Avg QPS | Max RSS | Spill |
|---|---|---|---|---|---|---|---|---|---|---|
| **spark** | 495 | 495 | 0 | 100.0% | 19635.02s | 12.503s | 129.432s | 0.0254 | 3409 MB (RSS) | 0.0 MB |
| **trino** | 487 | 487 | 0 | 100.0% | 5867.504s | 4.703s | 31.701s | 0.0835 | 2302 MB (RSS) | 0.0 MB |

> **Trino median engine time is 2.7× faster than Spark** (4.703s vs 12.503s).

## Result validation

- Comparable query runs: **487**
- Hash matches: **479 / 487** (98.4%)

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
| query44 | 1 | 1 | 1 | ❌ | `ac1167c0` | `36b1243f` |
| query44 | 2 | 1 | 1 | ❌ | `ac1167c0` | `36b1243f` |
| query44 | 3 | 1 | 1 | ❌ | `ac1167c0` | `36b1243f` |
| query44 | 4 | 1 | 1 | ❌ | `ac1167c0` | `36b1243f` |
| query44 | 5 | 1 | 1 | ❌ | `ac1167c0` | `36b1243f` |

## Per-query comparison (median wall time, slowest Trino queries first)

| Query | Trino (s) | Trino CV% | Spark (s) | Spark CV% | Spark/Trino ratio | Faster |
|---|---|---|---|---|---|---|
| query67 | 184.876 | 1.14% | 130.413 | 0.8% | 0.71 | spark |
| query14 | 101.235 | 3.46% | 125.24 | 3.69% | 1.24 | trino |
| query47 | 78.646 | 1.44% | 34.927 | 2.17% | 0.44 | spark |
| query4 | 71.379 | 2.03% | 192.526 | 1.33% | 2.7 | trino |
| query78 | 69.636 | 5.18% | 190.669 | 70.38% | 2.74 | trino |
| query75 | 37.651 | 1.56% | 49.686 | 7.87% | 1.32 | trino |
| query51 | 35.699 | 2.76% | 42.82 | 5.99% | 1.2 | trino |
| query57 | 35.157 | 2.01% | 13.661 | 5.52% | 0.39 | spark |
| query64 | 35.043 | 22.26% | 210.368 | 0.77% | 6.0 | trino |
| query11 | 31.701 | 1.85% | 91.917 | 0.45% | 2.9 | trino |
| query65 | 30.585 | 4.68% | 36.919 | 3.07% | 1.21 | trino |
| query93 | 27.592 | 9.05% | 118.623 | 1.9% | 4.3 | trino |
| query31 | 22.023 | 6.52% | 21.158 | 8.26% | 0.96 | spark |
| query74 | 21.346 | 2.88% | 80.706 | 3.13% | 3.78 | trino |
| query70 | 17.285 | 0.95% | 12.25 | 3.69% | 0.71 | spark |
| query72 | 16.836 | 2.78% | 251.538 | 1.26% | 14.94 | trino |
| query22 | 14.673 | 1.01% | 13.507 | 4.35% | 0.92 | spark |
| query24 | 13.93 | 7.39% | 85.822 | 1.27% | 6.16 | trino |
| query17 | 13.55 | 3.15% | 131.844 | 0.94% | 9.73 | trino |
| query59 | 13.056 | 5.91% | 6.309 | 7.27% | 0.48 | spark |
| query85 | 11.981 | 5.26% | 10.183 | 6.27% | 0.85 | spark |
| query50 | 10.663 | 6.57% | 54.405 | 5.54% | 5.1 | trino |
| query44 | 10.013 | 0.74% | 9.25 | 15.34% | 0.92 | spark |
| query36 | 9.863 | 1.1% | 10.077 | 6.74% | 1.02 | trino |
| query25 | 9.736 | 12.86% | 137.806 | 1.19% | 14.15 | trino |
| query29 | 9.595 | 3.65% | 133.271 | 2.02% | 13.89 | trino |
| query49 | 9.328 | 2.95% | 36.474 | 4.86% | 3.91 | trino |
| query34 | 8.987 | 14.95% | 6.977 | 10.52% | 0.78 | spark |
| query39 | 8.706 | 13.01% | 6.397 | 10.59% | 0.73 | spark |
| query80 | 8.569 | 8.88% | 208.707 | 0.88% | 24.36 | trino |

## Methodology & Limitations

- **Compute vs E2E**: Benchmark metrics focus on core engine compute/shuffle (Engine Internal Wall Time). 
  - E2E Wall Time (including REST/Python overhead) is preserved in raw data for audit.
- **Memory Measurement**: Metrics represent **Cluster-wide Peak RSS (Physical Memory)**. 
  - This is measured via Kubernetes Metrics API during query execution to ensure a fair 'App vs App' comparison, including JVM overhead.
- **Caching**: `spark.catalog.clearCache()` was used between queries. 
  - Note: This does NOT clear JVM JIT compilation, filesystem metadata caches, or S3A connection pools. Subsequent queries may still benefit from lower-level warming.
- **Isolation**: Engines were run sequentially with `requests=limits` (Guaranteed QoS) to ensure no resource contention.
