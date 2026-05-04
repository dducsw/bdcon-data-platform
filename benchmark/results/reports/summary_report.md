# TPC-DS Benchmark Summary Report

- **Dataset**: `Dataset: iceberg_hive.benchmark_tpcds_sf10`
- **Runs**: 1 warmup, 3 measured

## Engine Performance Summary

| Engine | Success Rate | Total Time | Median Time | Avg QPS | Max Peak Mem | Total CPU Time | Total Spill |
|---|---|---|---|---|---|---|---|
| spark | 100.0% | 214.728s | 5.966s | 0.140 | 0 B | 0.0s | 0 B |
| trino | 100.0% | 264.716s | 4.344s | 0.113 | 1.4 GB | 461.1s | 0 B |

## Validation Result Summary

- **Total Result Matching**: 24/30 (80.0%)

### Mismatched Queries (Sample)

| Query | Run | Spark Hash | Trino Hash |
|---|---|---|---|
| query5 | 1 | `c44925b4` | `c981c67d` |
| query5 | 2 | `c44925b4` | `c981c67d` |
| query5 | 3 | `c44925b4` | `c981c67d` |
| query7 | 1 | `4502c7da` | `4c4c7f3a` |
| query7 | 2 | `4502c7da` | `4c4c7f3a` |
| query7 | 3 | `4502c7da` | `4c4c7f3a` |

## Per-Query Comparison

| Query | Trino Avg (s) | Spark Avg (s) | Ratio (S/T) | Winner | Trino StdDev | Spark StdDev | Trino Peak Mem |
|---|---|---|---|---|---|---|---|
| query1 | 5.375 | 1.662 | 0.3x | 🔴 Spark | 1.733 | 0.145 | 107.2 MB |
| query10 | 2.752 | 9.691 | 3.5x | 🟢 Trino | 0.196 | 0.242 | 12.9 MB |
| query2 | 3.974 | 2.103 | 0.5x | 🔴 Spark | 0.218 | 0.066 | 77.4 MB |
| query3 | 4.671 | 1.254 | 0.3x | 🔴 Spark | 0.836 | 0.095 | 167.1 MB |
| query4 | 36.031 | 28.342 | 0.8x | 🔴 Spark | 6.351 | 0.045 | 1.4 GB |
| query5 | 5.420 | 6.644 | 1.2x | 🟢 Trino | 0.442 | 0.407 | 277.7 MB |
| query6 | 3.193 | 5.346 | 1.7x | 🟢 Trino | 0.289 | 0.186 | 76.0 MB |
| query7 | 4.482 | 8.557 | 1.9x | 🟢 Trino | 0.257 | 0.803 | 305.3 MB |
| query8 | 2.750 | 1.292 | 0.5x | 🔴 Spark | 0.138 | 0.030 | 95.0 MB |
| query9 | 19.591 | 6.686 | 0.3x | 🔴 Spark | 0.569 | 0.032 | 578.5 MB |

**Score: Trino 4 — Spark 6 — Tie 0** (out of 10 queries)

## Cold-Start Analysis

| Engine | Query | Warmup (s) | Run 1 (s) | Run 2+ Avg (s) | Warmup Overhead |
|---|---|---|---|---|---|
| spark | query1 | 3.14 | 1.83 | 1.58 | 2.0x |
| spark | query10 | 10.20 | 9.92 | 9.58 | 1.1x |
| spark | query2 | 2.70 | 2.15 | 2.08 | 1.3x |
| spark | query3 | 1.85 | 1.36 | 1.20 | 1.5x |
| spark | query4 | 33.54 | 28.39 | 28.32 | 1.2x |
| spark | query5 | 8.82 | 7.11 | 6.41 | 1.4x |
| spark | query6 | 6.36 | 5.53 | 5.25 | 1.2x |
| spark | query7 | 9.69 | 8.62 | 8.52 | 1.1x |
| spark | query8 | 2.32 | 1.27 | 1.30 | 1.8x |
| spark | query9 | 7.05 | 6.72 | 6.67 | 1.1x |
| trino | query1 | 17.28 | 7.05 | 4.54 | 3.8x |
| trino | query10 | 4.03 | 2.98 | 2.64 | 1.5x |
| trino | query2 | 5.81 | 3.81 | 4.06 | 1.4x |
| trino | query3 | 5.08 | 5.52 | 4.25 | 1.2x |
| trino | query4 | 52.42 | 43.29 | 32.40 | 1.6x |
| trino | query5 | 8.60 | 5.33 | 5.47 | 1.6x |
| trino | query6 | 3.54 | 3.48 | 3.05 | 1.2x |
| trino | query7 | 8.41 | 4.76 | 4.34 | 1.9x |
| trino | query8 | 3.76 | 2.91 | 2.67 | 1.4x |
| trino | query9 | 23.54 | 20.11 | 19.33 | 1.2x |

## Trino CPU Efficiency

| Query | Wall Time (s) | CPU Time (s) | Parallelism | Peak Memory |
|---|---|---|---|---|
| query1 | 5.38 | 4.9 | 0.9x | 107.2 MB |
| query10 | 2.75 | 3.9 | 1.4x | 12.9 MB |
| query2 | 3.97 | 5.3 | 1.3x | 77.4 MB |
| query3 | 4.67 | 6.5 | 1.4x | 167.1 MB |
| query4 | 36.03 | 60.9 | 1.7x | 1.4 GB |
| query5 | 5.42 | 8.6 | 1.6x | 277.7 MB |
| query6 | 3.19 | 4.8 | 1.5x | 76.0 MB |
| query7 | 4.48 | 7.6 | 1.7x | 305.3 MB |
| query8 | 2.75 | 4.6 | 1.7x | 95.0 MB |
| query9 | 19.59 | 46.7 | 2.4x | 578.5 MB |

## ⚠️ Architecture Notes

| Factor | Spark | Trino |
|---|---|---|
| **Mode** | `local[4]` (single JVM, no network) | 1 Coordinator + 2 Workers (distributed) |
| **Network Overhead** | None (in-process) | Coordinator ↔ Worker ↔ MinIO |
| **Node Type** | Standard | Workers on Spot Nodes |

> **Note**: Spark runs in local[4] mode which eliminates all network and serialization
> overhead. This gives Spark a structural advantage that is unrelated to query engine
> performance. Results should be interpreted with this architectural difference in mind.
