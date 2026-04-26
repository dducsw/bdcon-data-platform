# Benchmark Summary

Dataset: TPC-DS SF5 materialized to Iceberg schema `catalog_iceberg.benchmark_tpcds`.

## Engine Summary

- spark: success_rate=0.9798, total_runtime_seconds=7557.221, median_query_time_seconds=23.604, avg_throughput_qps=0.043154, max_peak_memory_bytes=0, total_spill_bytes=0, total_cpu_time_millis=0
- trino: success_rate=0.8182, total_runtime_seconds=179.842, median_query_time_seconds=0.534, avg_throughput_qps=2.7543, max_peak_memory_bytes=104977365, total_spill_bytes=0, total_cpu_time_millis=86683

## Validation

- matching query results: 0/291
