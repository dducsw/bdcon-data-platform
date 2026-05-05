# TPC-DS Benchmark on Kubernetes

This repository provides a framework for running TPC-DS performance benchmarks against **Apache Spark** and **Trino** on a Kubernetes-based data platform. It leverages **Apache Iceberg** as the table format and **MinIO** (S3-compatible) as the storage layer.

---

## 🏗 Architecture Overview

The benchmark infrastructure is designed for engine-to-engine comparison:
- **Storage Layer**: MinIO (S3A) storing data in Parquet via Apache Iceberg.
- **Metastore**: Hive Metastore for schema management.
- **Engines**: 
  - **Trino**: Distributed SQL query engine (Coordinator + Workers).
  - **Spark**: Spark Thrift Server (long-running session) to match Trino's architecture.
- **Orchestration**: Python scripts (REST API for Trino, JDBC for Spark).

---

## 📋 Prerequisites: Data Preparation

Before running benchmarks, you must materialize the TPC-DS source data into Iceberg tables and compute statistics.

1. **Port-forward the engines** (if running locally):
   ```bash
   # In separate terminals
   kubectl port-forward svc/trino 8080:8080 -n data-platform
   kubectl port-forward svc/spark-thrift-server 10000:10000 -n data-platform
   ```
2. **Execute Data Preparation**:
   ```bash
   python scripts/prepare_tpcds_data.py
   ```
   *This script performs: Schema creation, data materialization (SF10), string trimming, and `ANALYZE TABLE` for statistics.*

---

## ⚙️ Configuration Reference (`benchmark.env`)

Located in `config/benchmark.env`. Key variables:

| Variable | Description |
|----------|-------------|
| `QUERY_LIST` | Path to text file listing SQL queries to run. |
| `RUNS` | Number of measured runs per query (default: 3). |
| `WARMUP_RUNS` | Number of non-measured runs before benchmarking. |
| `RESULTS_DIR` | Directory where JSONL metrics are saved. |
| `TRINO_BASE_URL` | URL of Trino Coordinator (e.g., `http://localhost:8081`). |
| `SPARK_THRIFT_HOST` | Hostname for Spark Thrift (use `spark-thrift-server` inside K8s). |

---

## 🚀 Execution Guide

### 1. Running Trino Benchmark (Local Machine)
Trino's REST API is stable over network tunnels.
```bash
# 1. Forward port
kubectl port-forward svc/trino 8081:8080 -n data-platform

# 2. Update .env: TRINO_BASE_URL=http://localhost:8081

# 3. Run
python -u scripts/run_trino_benchmark.py
```

### 2. Running Spark Benchmark (Inside Cluster)

**⚠️ WARNING:** To ensure your local code changes and the new memory monitoring logic are applied, use the `kubectl cp` workflow with the provided Job.

```bash
# 1. Deploy the Job (configured to wait for code upload)
kubectl apply -f benchmark/k8s/spark-benchmark-job.yaml

# 2. Identify the running Pod name
export SPARK_POD=$(kubectl get pods -n data-platform -l engine=spark --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')

# 3. Upload your local 'benchmark' directory to the pod
kubectl cp benchmark data-platform/${SPARK_POD}:/tmp/app/

# 4. Follow the logs to see progress and memory metrics
kubectl logs -f job/spark-benchmark-runner -n data-platform
```

---

## 📊 Results and Reporting

Benchmark results are stored in `results/raw/` as JSONL files.

### Running a Subset of Queries
To run only a few queries (e.g., for testing), create a new list file:
```bash
echo "query1.sql" > benchmark/queries/tpcds/subset.txt
echo "query2.sql" >> benchmark/queries/tpcds/subset.txt
```
Then update `QUERY_LIST=benchmark/queries/tpcds/subset.txt` in `benchmark.env`.

### Generate HTML Report
```bash
python scripts/build_report.py
```
This will produce a summary of execution times, memory usage, and CPU metrics for both engines.

---

## 🛠 Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `Broken pipe` / `WinError 10053` | Windows Thrift networking bug over port-forward. | Run the benchmark script inside a Linux-based K8s Pod. |
| `Connection refused` | Pod crashed or port not bound to `0.0.0.0`. | Check `kubectl logs`. Ensure `--conf spark.hive.server2.thrift.bind.host=0.0.0.0` is set. |
| `Metastore error` | Hive Metastore is down or unreachable. | Verify `hive-metastore` service and connectivity. |

---

## 💡 Best Practices

1. **Sequential Execution**: Do not run Spark and Trino at the same time to avoid I/O contention.
2. **Node Pools**: Use dedicated Node Pools for benchmark engines to ensure predictable CPU performance.
3. **Warmup Runs**: Always set `WARMUP_RUNS=1` to ensure JIT and filesystem caches are primed.
4. **Statistics**: Always run `ANALYZE TABLE` before benchmarking after any data change.
