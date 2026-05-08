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
   *This script performs: Schema creation, data materialization (SF50), string trimming, and `ANALYZE TABLE` for statistics.*

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

### 1. Running Trino Benchmark

#### Option A: Run from Local Machine (Development)
Trino's REST API is stable over network tunnels.
```bash
# 1. Forward port
kubectl port-forward svc/trino 8081:8080 -n data-platform

# 2. Update benchmark.env: TRINO_BASE_URL=http://localhost:8081

# 3. Run
python -u scripts/run_trino_benchmark.py
```

#### Option B: Run Inside Cluster (Production/Distributed)
Use this mode to minimize network latency between the runner and the Trino coordinator.

1. **Scale up Trino workers**:
   ```bash
   kubectl scale deployment trino-worker -n data-platform --replicas=2
   ```

2. **Wait for workers to be Ready**:
   ```bash
   kubectl get pods -n data-platform -l app=trino,component=worker
   ```

3. **Deploy the Trino Benchmark Job**:
   ```bash
   kubectl apply -f benchmark/k8s/trino-benchmark-job.yaml
   ```

4. **Monitor logs**:
   ```bash
   kubectl logs -n data-platform -l job-name=trino-benchmark-runner -f
   ```


### 2. Running Spark Benchmark (Distributed Cluster Mode)

To ensure a fair comparison with Trino, Spark is configured to run in distributed mode with 2 executors on separate physical nodes.

#### Pre-requisites: Resource Preparation
Because the cluster nodes have limited capacity (4 cores/node), you must ensure enough space is available:

1. **Increase Namespace Quota**:
   ```bash
   kubectl patch resourcequota data-platform-quota -n data-platform --patch '{"spec": {"hard": {"limits.cpu": "100", "requests.cpu": "64"}}}'
   ```
2. **Free up Compute Nodes**: Scale down Trino workers to avoid CPU contention:
   ```bash
   kubectl scale deployment trino-worker -n data-platform --replicas=0
   ```

#### Execution Workflow
Use the "wait for code" pattern to apply local changes without rebuilding images:

1. **Deploy the multi-node Job**:
   ```bash
   kubectl apply -f benchmark/k8s/spark-benchmark-job-multi-node.yaml
   ```

2. **Wait for Pod to reach `Running` status**, then identify the pod name:
   ```bash
   # Power shell
   $SPARK_POD = (kubectl get pods -n data-platform -l job-name=spark-benchmark-runner -o jsonpath='{.items[0].metadata.name}')
   ```

3. **Upload the local code** to the pod:
   ```bash
   kubectl cp benchmark data-platform/${SPARK_POD}:/tmp/app/ -c spark-benchmark
   ```

4. **Monitor logs**:
   ```bash
   kubectl logs -n data-platform $SPARK_POD -f
   ```

---

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


kubectl cp data-platform/trino-benchmark-runner-m2k5x:/benchmark/results/raw/trino_results.jsonl benchmark/results/raw/trino_results1.jsonl