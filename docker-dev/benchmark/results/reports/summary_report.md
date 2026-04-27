# Benchmark Summary

Dataset: TPC-DS SF5 materialized to Iceberg schema `catalog_iceberg.benchmark_tpcds`.

## Engine Summary

- spark: success_rate=1.0, total_runtime_seconds=4425.354, median_query_time_seconds=14.386, avg_throughput_qps=0.069289, max_peak_memory_bytes=0, total_spill_bytes=0, total_cpu_time_millis=0
- trino: success_rate=1.0, total_runtime_seconds=196.257, median_query_time_seconds=0.362, avg_throughput_qps=3.832347, max_peak_memory_bytes=431814768, total_spill_bytes=0, total_cpu_time_millis=120249

## Validation

- matching query results: 204/297
