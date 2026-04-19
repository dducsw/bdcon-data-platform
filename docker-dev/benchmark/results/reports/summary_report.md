# Benchmark Summary

Dataset: TPC-DS SF5 materialized to Iceberg schema `catalog_iceberg.benchmark_tpcds`.

## Engine Summary

- spark: success_rate=1.0, total_runtime_seconds=281.993, median_query_time_seconds=15.278, avg_throughput_qps=0.064411, max_peak_memory_bytes=51643872, total_spill_bytes=0, total_cpu_time_millis=62344
- trino: success_rate=1.0, total_runtime_seconds=15.266, median_query_time_seconds=0.849, avg_throughput_qps=1.265316, max_peak_memory_bytes=21746881, total_spill_bytes=0, total_cpu_time_millis=6815

## Validation

- matching query results: 0/18
