# TPC-DS Benchmark Summary Report

- **Dataset**: `Dataset: catalog_iceberg.benchmark_tpcds_sf1`
- **Runs**: 0 warmup, 1 measured

## Engine Performance Summary

| Engine | Success Rate | Total Time | Median Time | Avg QPS | Max Peak Mem | Total Spill |
|---|---|---|---|---|---|---|
| spark | 100.0% | 969.937s | 8.899s | 0.102 | 242.5 MB | 0.0 MB |
| trino | 100.0% | 218.483s | 0.967s | 0.453 | 318.2 MB | 0.0 MB |

## Validation Result Summary

- **Total Result Matching**: 58/99 (58.6%)

### Mismatched Queries (Sample)

| Query | Run | Spark Hash | Trino Hash |
|---|---|---|---|
| query11 | 1 | `67c14f19` | `9a702aea` |
| query12 | 1 | `fef6f60a` | `9cee6e0c` |
| query13 | 1 | `a2fcf6cf` | `f3c2e9f6` |
| query14 | 1 | `14de120c` | `eb3758f1` |
| query15 | 1 | `976fa86b` | `ec75ecb5` |
| query18 | 1 | `653c489e` | `330de6af` |
| query20 | 1 | `bad6e1ba` | `9f15fa18` |
| query21 | 1 | `59950529` | `025accdb` |
| query26 | 1 | `0a18f50c` | `6353c4a9` |
| query27 | 1 | `68f17a18` | `fe1b24d4` |

## Per-Query Comparison (Average Time in Seconds)

| Query | Trino (s) | Spark (s) | Ratio (S/T) |
|---|---|---|---|
| query1 | 3.885 | 9.138 | 2.4x |
| query10 | 1.269 | 14.316 | 11.3x |
| query11 | 3.932 | 15.416 | 3.9x |
| query12 | 0.479 | 7.768 | 16.2x |
| query13 | 2.259 | 9.944 | 4.4x |
| query14 | 25.000 | 21.712 | 0.9x |
| query15 | 0.861 | 6.850 | 8.0x |
| query16 | 0.730 | 10.599 | 14.5x |
| query17 | 1.641 | 12.156 | 7.4x |
| query18 | 1.207 | 11.840 | 9.8x |
| query19 | 0.839 | 8.172 | 9.7x |
| query2 | 2.294 | 9.316 | 4.1x |
| query20 | 0.605 | 6.778 | 11.2x |
| query21 | 0.703 | 7.393 | 10.5x |
| query22 | 6.088 | 9.327 | 1.5x |
| query23 | 8.880 | 17.200 | 1.9x |
| query24 | 1.529 | 9.711 | 6.4x |
| query25 | 1.299 | 13.499 | 10.4x |
| query26 | 0.605 | 8.532 | 14.1x |
| query27 | 0.783 | 9.958 | 12.7x |
