# Benchmark Summary

Dataset: TPC-DS SF5 materialized to Iceberg schema `catalog_iceberg.benchmark_tpcds`.

## Engine Summary

- spark: success_rate=0.9798, total_runtime_seconds=6083.753, median_query_time_seconds=18.065, avg_throughput_qps=0.052907, max_peak_memory_bytes=0, total_spill_bytes=0, total_cpu_time_millis=0
- trino: success_rate=0.8182, total_runtime_seconds=202.296, median_query_time_seconds=0.601, avg_throughput_qps=2.36221, max_peak_memory_bytes=142676665, total_spill_bytes=0, total_cpu_time_millis=91395

## Validation

- matching query results: 81/243
