"""
run_spark_benchmark.py
======================
Runs TPC-DS queries via SparkSession.

Supports 2 modes via SPARK_MASTER environment variable:
  - local[N]                              : single-pod (development, debug)
  - k8s://https://kubernetes.default.svc:443 : Spark-on-K8s (production benchmark)

In K8s mode:
  - Driver runs in-process in this pod (deploy-mode: client)
  - Executor pods are spawned dynamically on compute-pool + query-pool
  - spark.driver.host is retrieved from MY_POD_IP (injected by Downward API in Job YAML)
  - MinIO credentials are passed to executors via K8s secret references

Architecture (K8s mode)
-----------------------
  [Driver pod - infra node]
       |  spawn
       v
  [Executor pod 1 - compute node]  <-- S3A -> MinIO
  [Executor pod 2 - query node]    <-- S3A -> MinIO
       |
       L-- results reported back to Driver -> JSONL on PVC

Metrics collected per query
---------------------------
wall_time_seconds   perf_counter delta (driver-side, includes network + shuffle)
peak_memory_bytes   max of: cgroup RSS monitor (container total) vs SparkListener
spill_bytes         sum of memoryBytesSpilled + diskBytesSpilled via SparkListener
cpu_time_millis     sum of executorCpuTime (ns -> ms) via SparkListener
result_hash         stable_hash of fetched rows (sorted, normalized)
"""
from __future__ import annotations

import os
import time
import threading
import resource
from pathlib import Path
from threading import Lock
from typing import Any

from common import (
    ROOT,
    append_jsonl,
    ensure_dir,
    load_env,
    make_record,
    read_query_list,
    stable_hash,
)


# --- Spark listener for per-query metrics ------------------------------------

class _QueryMetrics:
    """Accumulates stage/task metrics for the most-recently-started query."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._peak_mem: int = 0
            self._spill: int = 0
            self._cpu_ns: int = 0

    def on_task_end(self, task_metrics: Any) -> None:
        with self._lock:
            self._peak_mem = max(self._peak_mem, task_metrics.peakExecutionMemory())
            self._spill += task_metrics.memoryBytesSpilled() + task_metrics.diskBytesSpilled()
            self._cpu_ns += task_metrics.executorCpuTime()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "peak_memory_bytes": self._peak_mem,
                "spill_bytes": self._spill,
                "cpu_time_millis": int(self._cpu_ns // 1_000_000),
            }


def _get_rss_mb() -> float:
    """Retrieves actual RAM usage of the ENTIRE Container (Python + JVM)."""
    # 1. Cgroup v2
    try:
        with open('/sys/fs/cgroup/memory.current', 'r') as f:
            return float(f.read().strip()) / (1024 * 1024)
    except Exception:
        pass
    # 2. Cgroup v1
    try:
        with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as f:
            return float(f.read().strip()) / (1024 * 1024)
    except Exception:
        pass
    # 3. Fallback: /proc/self/status
    try:
        with open('/proc/self/status', 'r') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return float(line.split()[1]) / 1024.0
    except Exception:
        pass
    return 0.0


class MemoryMonitor:
    """Background thread to capture Peak RSS during query execution."""

    def __init__(self, interval: float = 0.1):
        self.interval = interval
        self.peak_mb = 0.0
        self._stop_event = threading.Event()
        self._thread = None

    def _monitor(self):
        while not self._stop_event.is_set():
            current = _get_rss_mb()
            if current > self.peak_mb:
                self.peak_mb = current
            time.sleep(self.interval)

    def start(self):
        self.peak_mb = _get_rss_mb()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()

    def stop(self) -> float:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        final = _get_rss_mb()
        return max(self.peak_mb, final)


def _attach_listener(sc: Any, metrics: _QueryMetrics) -> None:
    try:
        jvm = sc._jvm
        jsc = sc._jsc.sc()

        class PythonListener(jvm.org.apache.spark.scheduler.SparkListener):
            def onTaskEnd(self, task_end):
                tm = task_end.taskMetrics()
                if tm is not None:
                    metrics.on_task_end(tm)

        jsc.addSparkListener(PythonListener())
    except Exception as e:
        raise RuntimeError(f"Py4J Listener inheritance failed: {e}")


# --- SparkSession factory ----------------------------------------------------

def _build_spark(env: dict):
    """
    Build SparkSession.
    Execution mode is controlled by env['SPARK_MASTER'].
    """
    from pyspark.sql import SparkSession

    # --- Configuration -------------------------------------------------------
    master          = env.get("SPARK_MASTER", "local[4]")
    driver_cores    = env.get("SPARK_DRIVER_CORES", "4")
    driver_memory   = env.get("SPARK_DRIVER_MEMORY", "7g")
    catalog         = env.get("SPARK_CATALOG", "iceberg")
    schema          = env.get("SPARK_SCHEMA", "benchmark_tpcds_sf5")
    warehouse       = env.get("ICEBERG_WAREHOUSE", "s3a://iceberg/lakehouse")
    metastore_uri   = env.get("ICEBERG_URI", "thrift://hive-metastore:9083")
    minio_endpoint  = env.get("MINIO_ENDPOINT", "http://minio:9000")

    is_k8s = master.startswith("k8s://")
    print(f"  Spark master: {master}")

    builder = (
        SparkSession.builder
        .appName(f"tpcds-benchmark-{schema}")
        .master(master)
        # --- Driver resources ------------------------------------------------
        .config("spark.driver.memory", driver_memory)
        .config("spark.driver.cores", driver_cores)
        # --- AQE (Enabled) ---------------------------------------------------
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.adaptive.skewJoin.enabled", "true")
        # --- Iceberg catalog -------------------------------------------------
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config(f"spark.sql.catalog.{catalog}",
                "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{catalog}.type", "hive")
        .config(f"spark.sql.catalog.{catalog}.uri", metastore_uri)
        .config(f"spark.sql.catalog.{catalog}.warehouse", warehouse)
        # --- S3A / MinIO -----------------------------------------------------
        .config("spark.hadoop.fs.s3a.endpoint", minio_endpoint)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl",
                "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
        # --- Hive Metastore --------------------------------------------------
        .config("spark.sql.catalogImplementation", "hive")
        .config("spark.hadoop.hive.metastore.uris", metastore_uri)
        # --- Dependencies ----------------------------------------------------
        .config("spark.jars.packages",
                "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.2,"
                "org.apache.hadoop:hadoop-aws:3.3.4,"
                "com.amazonaws:aws-java-sdk-bundle:1.12.262")
        .config("spark.jars.ivy", "/tmp/.ivy2")
        # --- Serialisation ---------------------------------------------------
        .config("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")
        .config("spark.sql.parquet.int96RebaseModeInRead", "CORRECTED")
    )

    # --- Spark-on-Kubernetes Specific Config ---------------------------------
    if is_k8s:
        executor_instances = env.get("SPARK_EXECUTOR_INSTANCES", "2")
        executor_cores     = env.get("SPARK_EXECUTOR_CORES", "4")
        executor_memory    = env.get("SPARK_EXECUTOR_MEMORY", "9g")
        k8s_namespace      = env.get("K8S_NAMESPACE", "data-platform")
        spark_image        = env.get("SPARK_IMAGE",
                                     "apache/spark:3.5.3-scala2.12-java17-python3-ubuntu")
        executor_template  = env.get("SPARK_EXECUTOR_POD_TEMPLATE", "")

        # Driver host must be the pod IP (injected by Downward API).
        driver_host = os.environ.get("MY_POD_IP", "")
        if not driver_host:
            try:
                import socket
                driver_host = socket.gethostbyname(socket.gethostname())
            except Exception:
                driver_host = "127.0.0.1"
        print(f"  Driver host (MY_POD_IP): {driver_host}")

        builder = (
            builder
            # --- K8s Basics --------------------------------------------------
            .config("spark.kubernetes.namespace", k8s_namespace)
            .config("spark.kubernetes.container.image", spark_image)
            .config("spark.kubernetes.container.image.pullPolicy", "IfNotPresent")
            .config("spark.kubernetes.authenticate.driver.serviceAccountName",
                    "spark-driver")
            # --- Driver networking -------------------------------------------
            .config("spark.driver.host", driver_host)
            .config("spark.driver.port", "7078")
            .config("spark.blockManager.port", "7079")
            # --- Executor sizing ---------------------------------------------
            .config("spark.executor.instances", executor_instances)
            .config("spark.executor.cores", executor_cores)
            .config("spark.executor.memory", executor_memory)
            # --- Resources Limits/Requests (Matching Trino) ------------------
            .config("spark.kubernetes.executor.request.cores", "1")
            .config("spark.kubernetes.executor.limit.cores", executor_cores)
            .config("spark.kubernetes.executor.limit.memory", executor_memory)
        )

        if executor_template:
            builder = builder.config(
                "spark.kubernetes.executor.podTemplateFile", executor_template
            )
            print(f"  Executor pod template: {executor_template}")

        # --- Pass MinIO credentials to executors via K8s Secret --------------
        builder = (
            builder
            .config(
                "spark.kubernetes.executor.secretKeyRef.AWS_ACCESS_KEY_ID",
                "spark-minio-secret:MINIO_ACCESS_KEY",
            )
            .config(
                "spark.kubernetes.executor.secretKeyRef.AWS_SECRET_ACCESS_KEY",
                "spark-minio-secret:MINIO_SECRET_KEY",
            )
        )

        # --- Executor labels -------------------------------------------------
        builder = (
            builder
            .config("spark.kubernetes.executor.label.app", "benchmark")
            .config("spark.kubernetes.executor.label.engine", "spark")
        )

        print(
            f"  K8s config: namespace={k8s_namespace}, image={spark_image}\n"
            f"  Executors: {executor_instances}x ({executor_cores} cores / {executor_memory})"
        )
    else:
        print(f"  Running in local mode with {driver_cores} cores")

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    spark.sql(f"USE {catalog}.{schema}")
    return spark


# --- Query execution ---------------------------------------------------------

def run_query(spark, sql: str) -> tuple[list, float, str, str, float]:
    monitor = MemoryMonitor()
    monitor.start()

    started = time.perf_counter()
    status = "success"
    error_message = ""
    rows: list = []

    try:
        df = spark.sql(sql)
        rows = df.collect()
    except Exception as exc:
        status = "failed"
        error_message = str(exc)[:2000]

    wall = time.perf_counter() - started
    peak_mem_mb = monitor.stop()

    return rows, wall, status, error_message, peak_mem_mb


# --- Main --------------------------------------------------------------------

def main() -> None:
    env = load_env()
    query_files = read_query_list(env)
    warmups = int(env.get("WARMUP_RUNS", 1))
    runs = int(env.get("RUNS", 3))

    results_root = Path(env.get("RESULTS_DIR", str(ROOT / "benchmark" / "results")))
    raw_dir = results_root / "raw"
    ensure_dir(raw_dir)
    output_file = raw_dir / "spark_results.jsonl"
    output_file.write_text("", encoding="utf-8")

    master = env.get("SPARK_MASTER", "local[4]")
    print(
        f"Building SparkSession ...\n"
        f"  master={master}\n"
        f"  driver={env.get('SPARK_DRIVER_CORES', 4)} cores / {env.get('SPARK_DRIVER_MEMORY', '7g')}"
    )
    spark = _build_spark(env)

    metrics = _QueryMetrics()
    try:
        _attach_listener(spark.sparkContext, metrics)
        listener_ok = True
    except Exception as exc:
        print(f"  Warning: SparkListener unavailable, metrics will be 0 ({exc})")
        listener_ok = False

    total_queries = len(query_files) * (warmups + runs)
    done = 0

    try:
        for query_file in query_files:
            query_name = query_file.stem
            sql = query_file.read_text(encoding="utf-8").strip().rstrip(";")

            if env.get("WRAP_COUNT", "false").lower() == "true":
                sql = f"SELECT COUNT(*) FROM (\n{sql}\n)"

            for run_index in range(1, warmups + runs + 1):
                is_warmup = run_index <= warmups
                run_number = 0 if is_warmup else run_index - warmups
                run_label = f"warmup-{run_index}" if is_warmup else f"run-{run_number}"

                if listener_ok:
                    metrics.reset()

                rows, wall, status, err, peak_mem_mb = run_query(spark, sql)

                m = metrics.snapshot() if listener_ok else {
                    "peak_memory_bytes": 0,
                    "spill_bytes": 0,
                    "cpu_time_millis": 0,
                }

                record = make_record(
                    engine="spark",
                    query_name=query_name,
                    run_type="warmup" if is_warmup else "measured",
                    run_number=run_number,
                    query_id=f"spark-k8s-{query_name}-{run_label}",
                    status=status,
                    wall_time_seconds=wall,
                    peak_memory_bytes=max(
                        int(peak_mem_mb * 1024 * 1024),
                        m["peak_memory_bytes"],
                    ),
                    spill_bytes=m["spill_bytes"],
                    cpu_time_millis=m["cpu_time_millis"],
                    result_hash=stable_hash(rows) if rows else "",
                    row_count=len(rows),
                    error_message=err,
                )
                append_jsonl(output_file, record)
                done += 1
                print(
                    f"[{done}/{total_queries}] spark {query_name} {run_label} "
                    f"-> {status}  wall={wall:.2f}s  "
                    f"mem={record['peak_memory_bytes'] // 1024 // 1024}MB  "
                    f"spill={m['spill_bytes'] // 1024}KB"
                )

    except KeyboardInterrupt:
        print("\nInterrupted - partial results saved.")
    finally:
        spark.stop()

    print(f"\nDone. Results: {output_file}")


if __name__ == "__main__":
    main()