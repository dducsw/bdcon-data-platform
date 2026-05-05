============================================================
                   BÁO CÁO KẾT QUẢ
============================================================
# TPC-DS Benchmark Report: Trino vs Apache Spark

## Configuration

- **Dataset**: `iceberg_hive.benchmark_tpcds_sf5`
- **Warmup runs**: 1  |  **Measured runs**: 3
- **Resource budget**: 4 vCPU / 8 Gi per engine (Spark: local[4]; Trino: 1 coordinator + 1 worker)
- **Timeout**: 1800s per query

## Engine performance summary

| Engine | Queries | Success | Fail | Success % | Total time | Median | P90 | Avg QPS | Max mem | Spill |
|---|---|---|---|---|---|---|---|---|---|---|
| **spark** | 297 | 297 | 0 | 100.0% | 7907.306s | 11.096s | 78.648s | 0.0376 | 0 MB | 0.0 MB |
| **trino** | 297 | 297 | 0 | 100.0% | 1420.453s | 2.678s | 11.833s | 0.2091 | 1302 MB | 0.0 MB |

> **Trino median query time is 4.1× faster than Spark** (2.678s vs 11.096s).

## Result validation

- Comparable query runs: **279**
- Hash matches: **156 / 279** (55.9%)

Hash mismatches are expected for queries without an explicit `ORDER BY`:
Spark and Trino may return rows in different orders. The harness sorts rows before hashing, so ordering differences are eliminated.
Remaining mismatches indicate genuine numeric or NULL-handling divergence.

### Mismatched queries (first 10)

| Query | Run | Spark rows | Trino rows | Spark hash | Trino hash |
|---|---|---|---|---|---|
| query12 | 1 | 100 | 100 | `7b2e890e` | `487c4d5f` |
| query12 | 2 | 100 | 100 | `7b2e890e` | `487c4d5f` |
| query12 | 3 | 100 | 100 | `7b2e890e` | `487c4d5f` |
| query13 | 1 | 1 | 1 | `0d13b64d` | `56b94e57` |
| query13 | 2 | 1 | 1 | `0d13b64d` | `56b94e57` |
| query13 | 3 | 1 | 1 | `0d13b64d` | `56b94e57` |
| query14 | 1 | 100 | 100 | `835c3769` | `f4abb14b` |
| query14 | 2 | 100 | 100 | `835c3769` | `f4abb14b` |
| query14 | 3 | 100 | 100 | `835c3769` | `f4abb14b` |
| query15 | 1 | 100 | 100 | `84d5ca5d` | `541647f6` |

## Per-query comparison (avg wall time, slowest Trino queries first)

| Query | Trino (s) | Spark (s) | Spark/Trino ratio | Faster |
|---|---|---|---|---|
| query23 | 37.073 | 108.74 | 2.93 | trino |
| query67 | 31.937 | 88.329 | 2.77 | trino |
| query14 | 26.171 | 89.461 | 3.42 | trino |
| query47 | 23.048 | 22.266 | 0.97 | spark |
| query22 | 21.071 | 42.83 | 2.03 | trino |
| query64 | 19.104 | 155.731 | 8.15 | trino |
| query4 | 16.437 | 124.83 | 7.59 | trino |
| query78 | 13.472 | 99.866 | 7.41 | trino |
| query39 | 12.528 | 28.522 | 2.28 | trino |
| query51 | 12.479 | 38.116 | 3.05 | trino |
| query9 | 10.753 | 29.07 | 2.7 | trino |
| query72 | 9.971 | 215.596 | 21.62 | trino |
| query57 | 9.932 | 9.301 | 0.94 | spark |
| query11 | 8.982 | 58.47 | 6.51 | trino |
| query65 | 8.557 | 22.55 | 2.64 | trino |
| query75 | 7.631 | 36.979 | 4.85 | trino |
| query28 | 6.829 | 31.902 | 4.67 | trino |
| query88 | 6.26 | 20.684 | 3.3 | trino |
| query31 | 6.231 | 14.521 | 2.33 | trino |
| query74 | 5.48 | 49.167 | 8.97 | trino |
| query17 | 5.274 | 79.584 | 15.09 | trino |
| query29 | 5.239 | 78.491 | 14.98 | trino |
| query25 | 4.675 | 79.149 | 16.93 | trino |
| query13 | 4.476 | 10.607 | 2.37 | trino |
| query80 | 4.392 | 118.847 | 27.06 | trino |
| query21 | 4.287 | 12.918 | 3.01 | trino |
| query59 | 4.277 | 9.892 | 2.31 | trino |
| query85 | 4.173 | 9.428 | 2.26 | trino |
| query70 | 3.957 | 7.349 | 1.86 | trino |
| query97 | 3.808 | 20.343 | 5.34 | trino |
