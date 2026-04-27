# Benchmark Summary

Dataset: TPC-DS SF5 materialized to Iceberg schema `catalog_iceberg.benchmark_tpcds`.

## Engine Summary

- spark: success_rate=1.0, total_runtime_seconds=4974.434, median_query_time_seconds=16.021, avg_throughput_qps=0.062251, max_peak_memory_bytes=0, total_spill_bytes=0, total_cpu_time_millis=0
- trino: success_rate=1.0, total_runtime_seconds=234.236, median_query_time_seconds=0.442, avg_throughput_qps=2.856972, max_peak_memory_bytes=500677075, total_spill_bytes=0, total_cpu_time_millis=141479

## Validation

- matching query results: 108/297
