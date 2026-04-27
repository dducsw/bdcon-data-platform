# Benchmark Summary

Dataset: TPC-DS SF5 materialized to Iceberg schema `catalog_iceberg.benchmark_tpcds`.

## Engine Summary

- spark: success_rate=1.0, total_runtime_seconds=4347.548, median_query_time_seconds=14.094, avg_throughput_qps=0.070561, max_peak_memory_bytes=0, total_spill_bytes=0, total_cpu_time_millis=0
- trino: success_rate=1.0, total_runtime_seconds=230.719, median_query_time_seconds=0.481, avg_throughput_qps=3.217879, max_peak_memory_bytes=489195151, total_spill_bytes=0, total_cpu_time_millis=137906

## Validation

- matching query results: 216/297
