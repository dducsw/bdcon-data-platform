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
from pathlib import Path
from threading import Lock
from typing import Any

from common import (
    ROOT,
    append_jsonl,
    ensure_dir,
    load_env,
    load_jsonl,
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
            self._job_start: int = 0
            self._job_end: int = 0

    def on_job_start(self, job_start: Any) -> None:
        with self._lock:
            ts = job_start.time()
            if self._job_start == 0 or ts < self._job_start:
                self._job_start = ts

    def on_job_end(self, job_end: Any) -> None:
        with self._lock:
            ts = job_end.time()
            if ts > self._job_end:
                self._job_end = ts

    def on_task_end(self, task_metrics: Any) -> None:
        with self._lock:
            self._peak_mem = max(self._peak_mem, task_metrics.peakExecutionMemory())
            self._spill += task_metrics.memoryBytesSpilled() + task_metrics.diskBytesSpilled()
            self._cpu_ns += task_metrics.executorCpuTime()

    def snapshot(self) -> dict:
        with self._lock:
            duration_ms = 0
            if self._job_end > self._job_start > 0:
                duration_ms = int(self._job_end - self._job_start)
            
            return {
                "peak_memory_bytes": self._peak_mem,
                "spill_bytes": self._spill,
                "cpu_time_millis": int(self._cpu_ns // 1_000_000),
                "server_side_duration_ms": duration_ms,
            }


import urllib.request
import json

def get_executor_memory(app_id: str, spark_ui_url: str = None) -> int:
    """
    Retrieves the sum of peak JVM Heap + Off-Heap Memory across all executors via Spark REST API.
    """
    if spark_ui_url is None:
        ip = os.environ.get("MY_POD_IP", "127.0.0.1")
        spark_ui_url = f"http://{ip}:4040"

    try:
        url = f"{spark_ui_url}/api/v1/applications/{app_id}/executors"
        with urllib.request.urlopen(url, timeout=5) as resp:
            executors = json.loads(resp.read().decode("utf-8"))
        
        # We sum JVMHeapMemory + JVMOffHeapMemory from peakMemoryMetrics for all non-driver executors.
        total_peak_bytes = 0
        for e in executors:
            if e.get("id") == "driver":
                continue
            
            # peakMemoryMetrics is the most reliable source for peak usage in Spark 3.x
            pmm = e.get("peakMemoryMetrics", {})
            total_peak_bytes += pmm.get("JVMHeapMemory", 0)
            total_peak_bytes += pmm.get("JVMOffHeapMemory", 0)
            
        return int(total_peak_bytes)
    except Exception as e:
        # Don't print if it's just a 404/connection error after app stop
        if "404" not in str(e):
            print(f"  Warning: Could not fetch executor memory via REST API: {e}")
        return 0


def _get_rss_mb() -> float:
    """Retrieves actual RAM usage of the Driver Container (Python + JVM)."""
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


class DriverMemoryMonitor:
    """Background thread to capture Peak RSS of the Driver during query execution."""

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
        from py4j.java_gateway import CallbackServerParameters
        
        # 1. Start the callback server on the Python side.
        # Inside a K8s pod, 127.0.0.1 is the most reliable way for JVM to talk to Python.
        sc._gateway.start_callback_server(
            CallbackServerParameters(address='127.0.0.1', port=0)
        )
        
        # 2. Get the actual port picked by the OS
        python_port = sc._gateway.get_callback_server().get_listening_port()
        
        # 3. Inform the JVM side about the correct port.
        # Some PySpark versions don't automatically update the callback client port.
        try:
            sc._gateway.java_gateway_server.resetCallbackClient(
                sc._gateway.java_gateway_server.getCallbackClient().getAddress(),
                python_port
            )
        except Exception:
            pass # Best effort if method is missing

        jsc = sc._jsc.sc()

        class PythonListener(object):
            def onJobStart(self, job_start):
                metrics.on_job_start(job_start)

            def onJobEnd(self, job_end):
                metrics.on_job_end(job_end)

            def onTaskEnd(self, task_end):
                tm = task_end.taskMetrics()
                if tm is not None:
                    metrics.on_task_end(tm)

            # Implement common no-op methods to avoid "Connection refused" loops 
            # for events we don't care about but Spark emits frequently.
            def onBlockUpdated(self, event): pass
            def onOtherEvent(self, event): pass
            def onTaskStart(self, event): pass
            def onStageSubmitted(self, event): pass
            def onStageCompleted(self, event): pass
            def onExecutorMetricsUpdate(self, event): pass
            def onEnvironmentUpdate(self, event): pass
            
            # Catch-all for any other SparkListener methods to avoid AttributeError
            def __getattr__(self, name):
                return lambda *args, **kwargs: None

            class Java:
                implements = ["org.apache.spark.scheduler.SparkListenerInterface"]

        jsc.addSparkListener(PythonListener())
    except Exception as e:
        raise RuntimeError(f"Py4J Listener proxy failed: {e}")


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
            .config("spark.kubernetes.executor.request.cores", executor_cores)
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
    monitor = DriverMemoryMonitor()
    monitor.start()

    started = time.perf_counter()
    status = "success"
    error_message = ""
    rows: list = []

    try:
        # Clear cache to mitigate JVM/Metadata cache bias between queries
        spark.catalog.clearCache()
        
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
    
    # Crash-resume: Load existing results to skip completed queries
    existing_results = load_jsonl(output_file)
    completed_queries = {r["query_name"] for r in existing_results if r["run_type"] == "measured"}
    if completed_queries:
        print(f"Found {len(completed_queries)} queries already completed in {output_file.name}. Resuming...")
    else:
        # Only truncate if we are starting fresh
        if not output_file.exists():
            output_file.write_text("", encoding="utf-8")

    master = env.get("SPARK_MASTER", "local[4]")
    print(
        f"Building SparkSession ...\n"
        f"  master={master}\n"
        f"  driver={env.get('SPARK_DRIVER_CORES', 4)} cores / {env.get('SPARK_DRIVER_MEMORY', '7g')}"
    )
    spark = _build_spark(env)

    app_id = spark.sparkContext.applicationId
    print(f"  Application ID: {app_id}")

    # Check off-heap memory config (as requested for methodology verification)
    offheap_enabled = spark.conf.get("spark.memory.offHeap.enabled", "false")
    print(f"  Spark off-heap memory: {offheap_enabled}")
    if offheap_enabled.lower() == "true":
        print("  Warning: Off-heap memory is enabled but not currently summed in peak_memory_bytes.")

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
            
            if query_name in completed_queries:
                print(f"Skipping {query_name} (already completed)")
                done += (warmups + runs)
                continue

            sql_full = query_file.read_text(encoding="utf-8").strip().rstrip(";")
            
            # Phase 1: Validation Run (Single run, no WRAP_COUNT, to get result hash)
            if env.get("VALIDATE_FIRST", "false").lower() == "true" and env.get("WRAP_COUNT", "false").lower() == "true":
                print(f"  [Phase 1] Validating {query_name} (full query)...")
                v_rows, v_wall, v_status, v_err, v_driver_mb = run_query(spark, sql_full)
                v_exec_bytes = get_executor_memory(app_id)
                v_hash = stable_hash(v_rows) if v_rows else ""
                
                v_record = make_record(
                    engine="spark",
                    query_name=query_name,
                    run_type="validation",
                    run_number=1,
                    query_id=f"{app_id}-{query_name}-val",
                    status=v_status,
                    wall_time_seconds=v_wall,
                    peak_memory_bytes=max(int(v_driver_mb * 1024 * 1024), v_exec_bytes),
                    result_hash=v_hash,
                    row_count=len(v_rows),
                    error_message=v_err,
                )
                append_jsonl(output_file, v_record)
                print(f"    Validation: status={v_status}, hash={v_hash[:8]}, rows={len(v_rows)}")

            # Phase 2: Measured Runs
            sql_perf = sql_full
            if env.get("WRAP_COUNT", "false").lower() == "true":
                sql_perf = f"SELECT COUNT(*) FROM (\n{sql_full}\n)"

            for run_index in range(1, warmups + runs + 1):
                is_warmup = run_index <= warmups
                run_number = 0 if is_warmup else run_index - warmups
                run_label = f"warmup-{run_index}" if is_warmup else f"run-{run_number}"

                if listener_ok:
                    metrics.reset()

                rows, wall, status, err, driver_peak_mb = run_query(spark, sql_perf)
                executor_peak_bytes = get_executor_memory(app_id)

                m = metrics.snapshot() if listener_ok else {
                    "peak_memory_bytes": 0,
                    "spill_bytes": 0,
                    "cpu_time_millis": 0,
                    "server_side_duration_ms": 0,
                }

                # Canonical wall_time is client-side perf_counter (E2E).
                # Store server-side reported time (from listener) in engine_internal_time.
                server_wall = 0.0
                if m["server_side_duration_ms"] > 0:
                    server_wall = m["server_side_duration_ms"] / 1000.0

                record = make_record(
                    engine="spark",
                    query_name=query_name,
                    run_type="warmup" if is_warmup else "measured",
                    run_number=run_number,
                    query_id=f"{app_id}-{query_name}-{run_label}",
                    status=status,
                    wall_time_seconds=wall,
                    engine_internal_time=server_wall,
                    peak_memory_bytes=max(
                        int(driver_peak_mb * 1024 * 1024),
                        executor_peak_bytes,
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
                    f"-> {status}  wall={server_wall:.2f}s (client={wall:.2f}s) "
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