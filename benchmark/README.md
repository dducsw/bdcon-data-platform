# TPC-DS Benchmark on Kubernetes

This repository provides a framework for running TPC-DS performance benchmarks against **Apache Spark** and **Trino** on a Kubernetes-based data platform. It leverages **Apache Iceberg** as the table format and **MinIO** (S3-compatible) as the storage layer.

---

## 🏗 Architecture Overview

The benchmark infrastructure is designed for engine-to-engine comparison:
- **Storage Layer**: MinIO (S3A) storing data in Parquet via Apache Iceberg.
- **Metastore**: Hive Metastore for schema management.
- **Engines**: 
  - **Trino**: Distributed SQL query engine (Coordinator + Workers).
  - **Spark**: Spark Thrift Server (long-running session) in `local[4]` mode.
- **Orchestration**: Python scripts (REST API for Trino, PyHive/JDBC for Spark).

### ⚠️ Architectural Difference (Important for Interpreting Results)

| Factor | Spark | Trino |
|---|---|---|
| **Mode** | `local[4]` (single JVM, no network) | 1 Coordinator + 2 Workers (distributed) |
| **Network Overhead** | None — all in-process | Coordinator ↔ Worker ↔ MinIO |
| **Scheduling** | Single thread pool | Distributed task scheduling |
| **Node Type** | Spot (infra-pool) | Spot (query-pool + infra-pool) |

> **Impact**: Spark has a structural advantage at small datasets (SF10 ≈ 10GB) because all data fits in a single JVM's memory with zero coordination overhead. Trino's distributed architecture starts to outperform at larger scales (SF100+) where parallelism across workers offsets coordination costs. Results must be interpreted with this difference in mind.

---

## ⚡ Engine Resource Configuration

Both engines are configured to use a total of **16 GB Heap** for fair comparison.

| Engine | Component | Count | Heap Size | CPU Request | CPU Limit | RAM Request | RAM Limit |
|:---|:---|:---:|:---|:---|:---|:---:|:---:|
| **Spark** | Local Pod | 1 | 16 GB | 2.0 | 4.0 | 12 Gi | 20 Gi |
| **Trino** | Coordinator | 1 | 4 GB | 1.0 | 2.0 | 5 Gi | 6 Gi |
| **Trino** | Worker | 2 | 6 GB | 0.75 | 1.5 | 3.5 Gi | 8 Gi |
| **Trino** | **Total** | **3** | **16 GB** | **2.5** | **5.0** | **12 Gi** | **22 Gi** |

### Node Pool Assignment

| Pod | Node Pool | Machine Type | Notes |
|---|---|---|---|
| `spark-thrift-server` | infra-pool | n2-standard-8 | Shares node with Trino coordinator |
| `trino-coordinator` | infra-pool | n2-standard-8 | CPU limit doubled to reduce planning bottleneck |
| `trino-worker × 2` | query-pool | e2-highmem-4 | ~80% CPU utilization on node |

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

| Variable | Description | Recommended |
|----------|-------------|-------------|
| `QUERY_LIST` | Path to text file listing SQL queries to run. | — |
| `RUNS` | Number of measured runs per query. | `3` (minimum) |
| `WARMUP_RUNS` | Number of non-measured warmup runs. | `2` (see Best Practices) |
| `RESULTS_DIR` | Directory where JSONL metrics are saved. | `results` |
| `TRINO_BASE_URL` | URL of Trino Coordinator. | `http://trino:8080` (in-cluster) |
| `SPARK_THRIFT_HOST` | Hostname for Spark Thrift Server. | `spark-thrift-server` (in-cluster) |
| `SPARK_THRIFT_PORT` | Port for Spark Thrift Server. | `10000` (in-cluster) |

---

## 🚀 Execution Guide

### Step 1: Create Runner Pods

Benchmarks should run from **inside the cluster** to avoid network latency from port-forwarding.

```bash
# Spark runner
kubectl run spark-benchmark-runner -n data-platform --image=python:3.11-slim -- sleep infinity

# Trino runner
kubectl run trino-benchmark-runner -n data-platform --image=python:3.11-slim -- sleep infinity
```

### Step 2: Deploy Code to Runners

```bash
# Copy benchmark code (run from project root)
kubectl cp benchmark data-platform/spark-benchmark-runner:/benchmark
kubectl cp benchmark data-platform/trino-benchmark-runner:/benchmark

# Install Spark dependencies
kubectl exec -it spark-benchmark-runner -n data-platform -- pip install pyhive thrift thrift-sasl pure-sasl
```

### Step 3: Configure Internal URLs

```bash
# Trino runner — set internal URL
kubectl exec -it trino-benchmark-runner -n data-platform -- \
  bash -c "sed -i 's|TRINO_BASE_URL=http://localhost:8081|TRINO_BASE_URL=http://trino:8080|' /benchmark/config/benchmark.env"

# Spark runner — set internal host and port
kubectl exec -it spark-benchmark-runner -n data-platform -- \
  bash -c "sed -i 's/SPARK_THRIFT_HOST=localhost/SPARK_THRIFT_HOST=spark-thrift-server/' /benchmark/config/benchmark.env"
kubectl exec -it spark-benchmark-runner -n data-platform -- \
  bash -c "sed -i 's/SPARK_THRIFT_PORT=10001/SPARK_THRIFT_PORT=10000/' /benchmark/config/benchmark.env"
```

### Step 4: Verify Configuration

```bash
kubectl exec -it spark-benchmark-runner -n data-platform -- cat /benchmark/config/benchmark.env
kubectl exec -it trino-benchmark-runner -n data-platform -- cat /benchmark/config/benchmark.env
```

> Check: `WARMUP_RUNS=2`, URLs point to internal services, `RUNS=3`.

### Step 5: Run Benchmarks (Sequential!)

> ⚠️ **Run one at a time.** Running both simultaneously causes I/O contention on MinIO and invalidates results.

```bash
# 1. Spark first
kubectl exec -it spark-benchmark-runner -n data-platform -- \
  bash -c "cd /benchmark && python3 -u scripts/run_spark_benchmark.py"

# 2. Trino second (after Spark completes)
kubectl exec -it trino-benchmark-runner -n data-platform -- \
  bash -c "cd /benchmark && python3 -u scripts/run_trino_benchmark.py"
```

### Step 6: Collect Results & Generate Report

```bash
# Copy raw results to local
kubectl cp data-platform/spark-benchmark-runner:/benchmark/results/raw/spark_results.jsonl benchmark/results/raw/spark_results.jsonl
kubectl cp data-platform/trino-benchmark-runner:/benchmark/results/raw/trino_results.jsonl benchmark/results/raw/trino_results.jsonl

# Generate report
cd benchmark && python3 scripts/build_report.py
```

Report is generated at `results/reports/summary_report.md` with:
- Per-engine performance summary (total time, median, QPS)
- Per-query comparison with **winner indicators** (🟢 Trino / 🔴 Spark / ⚪ Tie)
- Standard deviation (stability analysis)
- Cold-start analysis (warmup vs measured runs)
- Trino CPU efficiency (parallelism ratio)
- Validation/hash matching between engines

### Step 7: Cleanup (Optional)

```bash
kubectl delete pod spark-benchmark-runner -n data-platform
kubectl delete pod trino-benchmark-runner -n data-platform
```

---

## 📊 Output Files

| File | Description |
|---|---|
| `results/raw/spark_results.jsonl` | Per-query, per-run raw metrics for Spark |
| `results/raw/trino_results.jsonl` | Per-query, per-run raw metrics for Trino (incl. server_time) |
| `results/merged/benchmark_results.csv` | Combined CSV of all records |
| `results/reports/summary_report.md` | Final comparison report |
| `results/reports/summary.csv` | Engine-level summary stats |
| `results/reports/validation.csv` | Hash match validation per query |

### Running a Subset of Queries

```bash
echo "query1.sql" > benchmark/queries/tpcds/subset.txt
echo "query2.sql" >> benchmark/queries/tpcds/subset.txt
```
Then update `QUERY_LIST=benchmark/queries/tpcds/subset.txt` in `benchmark.env`.

---

## 🛠 Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `Broken pipe` / `WinError 10053` | Windows Thrift networking over port-forward | Run benchmark inside K8s Pod |
| `Connection refused` | Pod crashed or port not bound to `0.0.0.0` | Check `kubectl logs`. Ensure `--conf spark.hive.server2.thrift.bind.host=0.0.0.0` is set |
| `Metastore error` | Hive Metastore unreachable | Verify `hive-metastore` service and connectivity |
| Trino queries slow after `helm upgrade` | JVM cold start (JIT not compiled) | Wait 2-3 min after restart, or increase `WARMUP_RUNS` to 3 |
| `dict contains fields not in fieldnames` | New fields in results not in report CSV | Add the field to `fieldnames` list in `build_report.py` |
| Result hash mismatch (false positive) | Floating-point precision differences | Hash uses 2-decimal rounding in `common.py` — check if query uses floats |

---

## 💡 Best Practices

1. **Sequential Execution**: Never run Spark and Trino simultaneously — MinIO I/O contention will skew results.
2. **Warmup Runs ≥ 2**: JVM JIT compilation needs multiple runs to stabilize. `WARMUP_RUNS=1` is insufficient after pod restarts (observed 3.8x overhead on first run). Set to `2` minimum, `3` for best accuracy.
3. **Wait After Restarts**: After `helm upgrade` or pod restart, wait for workers to fully register before benchmarking. Verify with:
   ```bash
   kubectl exec -it -n data-platform deploy/trino-coordinator -- trino --execute "SELECT * FROM system.runtime.nodes"
   ```
4. **Statistics**: Always run `ANALYZE TABLE` before benchmarking after any data change.
5. **Node Pools**: Avoid scheduling non-benchmark workloads on query/infra nodes during benchmark runs.
6. **Interpreting Results**: At SF10, Spark `local[4]` has a natural advantage for simple queries (zero overhead). Trino excels at complex multi-join queries. For production-scale comparison, use SF100+.

---

## 📝 Changelog (Benchmark Methodology Fixes)

| # | File | Change | Purpose |
|---|---|---|---|
| 1 | `config/benchmark.env` | `WARMUP_RUNS=0` → `2` | Eliminate cold-start / JIT bias |
| 2 | `scripts/run_trino_benchmark.py` | Wall-clock instead of server-time | Consistent timing methodology |
| 3 | `scripts/common.py` | Hash precision `4` → `2` decimal | Reduce false hash mismatches |
| 4 | `scripts/build_report.py` | Added winner, stddev, cold-start, CPU efficiency sections | Richer debugging and analysis |
| 5 | `helm-values/trino/dev.yaml` | Coordinator CPU: `500m/1` → `1000m/2` | Reduce query planning bottleneck |
| 6 | `scripts/run_spark_benchmark.py` | Added progress, banner, summary table | Better observability during runs |
