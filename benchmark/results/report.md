# TPC-DS Benchmark Report: Trino vs Apache Spark (SF50)

## Configuration

- **Dataset**: `iceberg_hive.benchmark_tpcds_sf50`
- **Warmup runs**: 2  |  **Measured runs**: 5
- **Resource budget**: 4 vCPU / 8 Gi per engine (Spark: local[4]; Trino: 1 coordinator + 1 worker)
- **Timeout**: 1800s per query

## Engine performance summary

| Engine | Queries | Success | Fail | Success % | Total E2E | Median | P90 | Avg QPS | Max RSS | Spill |
|---|---|---|---|---|---|---|---|---|---|---|
| **spark** | 495 | 495 | 0 | 100.0% | 19635.02s | 12.503s | 129.432s | 0.0254 | 3409 MB | 0.0 MB |
| **trino** | 487 | 487 | 0 | 100.0% | 5867.504s | 4.703s | 31.701s | 0.0835 | 2302 MB | 0.0 MB |

> **Trino median query time is 2.7× faster than Spark** (4.703s vs 12.503s).

## Result validation

- Comparable query runs: **487**
- Hash matches: **479 / 487** (98.4%)

Hash mismatches are expected for queries without an explicit `ORDER BY`. Spark and Trino may return rows in different orders. The harness sorts rows before hashing, so ordering differences are eliminated. Remaining mismatches indicate genuine numeric or NULL-handling divergence.

### Mismatched queries (SF50)

| Query | Run | Spark rows | Trino rows | Match? | Spark hash | Trino hash |
|---|---|---|---|---|---|---|
| query34 | ALL | 1 | 1 | ❌ | `e5c3430b` | `ab3f30bc` |
| query44 | ALL | 1 | 1 | ❌ | `ac1167c0` | `36b1243f` |

## Per-query comparison (median wall time, slowest Trino queries first)

| Query | Trino (s) | Spark (s) | Spark/Trino ratio | Faster |
|---|---|---|---|---|
| query67 | 184.876 | 130.413 | 0.71 | spark |
| query14 | 101.235 | 125.24 | 1.24 | trino |
| query47 | 78.646 | 34.927 | 0.44 | spark |
| query4 | 71.379 | 192.526 | 2.7 | trino |
| query78 | 69.636 | 190.669 | 2.74 | trino |
| query75 | 37.651 | 49.686 | 1.32 | trino |
| query51 | 35.699 | 42.82 | 1.2 | trino |
| query57 | 35.157 | 13.661 | 0.39 | spark |
| query64 | 35.043 | 210.368 | 6.0 | trino |
| query11 | 31.701 | 91.917 | 2.9 | trino |
| query65 | 30.585 | 36.919 | 1.21 | trino |
| query93 | 27.592 | 118.623 | 4.3 | trino |
| query31 | 22.023 | 21.158 | 0.96 | spark |
| query74 | 21.346 | 80.706 | 3.78 | trino |
| query70 | 17.285 | 12.25 | 0.71 | spark |
| query72 | 16.836 | 251.538 | 14.94 | trino |
| query22 | 14.673 | 13.507 | 0.92 | spark |
| query24 | 13.93 | 85.822 | 6.16 | trino |
| query17 | 13.55 | 131.844 | 9.73 | trino |
| query59 | 13.056 | 6.309 | 0.48 | spark |
| query85 | 11.981 | 10.183 | 0.85 | spark |
| query50 | 10.663 | 54.405 | 5.1 | trino |
| query44 | 10.013 | 9.25 | 0.92 | spark |
| query36 | 9.863 | 10.077 | 1.02 | trino |
| query25 | 9.736 | 137.806 | 14.15 | trino |
| query29 | 9.595 | 133.271 | 13.89 | trino |
| query49 | 9.328 | 36.474 | 3.91 | trino |
| query34 | 8.987 | 6.977 | 0.78 | spark |
| query39 | 8.706 | 6.397 | 0.73 | spark |
| query80 | 8.569 | 208.707 | 24.36 | trino |

