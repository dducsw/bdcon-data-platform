# TPC-DS Benchmark on Kubernetes

This folder contains the scripts and queries to run TPC-DS benchmarks against Spark and Trino deployed on a Kubernetes cluster.

## Setup

1. The configuration is defined in `config/benchmark.env`.
2. Install Python dependencies:
   ```bash
   pip install -r ../requirements.txt
   ```

## Trino Benchmark

Trino benchmarks are executed via its REST API.

1. Port-forward the Trino Coordinator service to your local machine:
   ```bash
   kubectl port-forward svc/trino 8080:8080 -n data-platform
   ```
2. Update `config/benchmark.env` to point to `TRINO_BASE_URL=http://localhost:8080`.
3. Run the benchmark:
   ```bash
   python scripts/run_trino_benchmark.py
   ```

## Spark Benchmark

Spark benchmarks are executed via JDBC using the Spark Thrift Server, eliminating JVM cold-start overheads and matching Trino's long-running architecture.

1. Port-forward the Spark Thrift Server service to your local machine:
   ```bash
   kubectl port-forward svc/spark-thrift-server 10000:10000 -n data-platform
   ```
2. Update `config/benchmark.env` to point to `SPARK_THRIFT_HOST=localhost` and `SPARK_THRIFT_PORT=10000`.
3. Run the benchmark:
   ```bash
   python scripts/run_spark_benchmark.py
   ```

## Results

Results are saved to `results/raw/` in JSONL format. You can use `scripts/build_report.py` to generate an HTML report:

```bash
python scripts/build_report.py
```

## Kubernetes Benchmark Best Practices

To ensure reliable and valid benchmark results on your K8s cluster, keep these points in mind:

1. **Table Statistics**: The `prepare_tpcds_data.py` script automatically runs `ANALYZE TABLE` on all 24 TPC-DS tables. This is crucial for Spark AQE and Trino CBO to generate optimal query plans.
2. **Resource Isolation**: Do not run Spark and Trino benchmarks simultaneously on the same nodes unless they have strict CPU/Memory requests and limits. It is highly recommended to flush OS caches and run them sequentially, or use separate Node Pools.
3. **Storage Bottlenecks**: Monitor I/O Wait and network throughput to MinIO. If the storage layer is the bottleneck, both engines will perform similarly poorly, obscuring their actual compute capabilities.
4. **Result Fetching Overhead**: By default, queries return full result sets. For pure engine compute performance without network overhead, consider modifying the queries to wrap in `CREATE TABLE tmp AS SELECT...` or `SELECT COUNT(*) FROM (...)`.
5. **Iceberg Versions**: Ensure that the Iceberg Connector versions on both Trino and Spark are aligned to guarantee fair feature utilization (like Bloom Filters and Manifest Caching).

## Notes

- The starter suite uses six representative SQL queries under `queries/tpcds_sf5/`.
- You can replace `query_list.txt` with a larger TPC-DS query set later without changing the runners.
- Spark metrics are parsed from Spark event logs under `infrastructure/spark/logs/`.
- Trino metrics are collected from the Trino statement API.
