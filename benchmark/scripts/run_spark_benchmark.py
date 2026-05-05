"""
run_spark_benchmark.py
======================
Runs TPC-DS queries via a local SparkSession (no Thrift Server).

Architecture
------------
The entire Spark execution lives inside this Python process:
  - SparkSession with local[<SPARK_DRIVER_CORES>] master
  - Iceberg catalog backed by the same Hive Metastore as Trino
  - Metrics collected via a custom SparkListener attached to the context

Why no Thrift Server?
---------------------
The Thrift Server is a convenience wrapper; it adds JDBC serialisation
overhead and a separate JVM process that skews latency measurements.
Running SparkSession in-process means we measure only query execution,
not protocol round-trips — consistent with how Trino's REST client works.

Metrics collected per query
---------------------------
wall_time_seconds   perf_counter delta (same method as Trino script)
peak_memory_bytes   max peakExecutionMemory across all stages
spill_bytes         sum of memoryBytesSpilled + diskBytesSpilled
cpu_time_millis     sum of executorCpuTime (ns → ms) across all tasks
result_hash         stable_hash of fetched rows
"""
from __future__ import annotations

import os
import time
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


# ─── Spark listener for per-query metrics ─────────────────────────────────────

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

import threading

class MemoryMonitor:
    def __init__(self):
        self.keep_running = False
        self.peak_memory_mb = 0

    def _get_current_memory(self):
        """Đọc RAM trực tiếp từ file hệ thống của Kubernetes Container"""
        try:
            # Dành cho Kubernetes dùng Cgroup v2 (phiên bản mới)
            if os.path.exists('/sys/fs/cgroup/memory.current'):
                with open('/sys/fs/cgroup/memory.current', 'r') as f:
                    return int(f.read().strip()) / (1024 * 1024)
            # Dành cho Kubernetes dùng Cgroup v1 (phiên bản cũ)
            elif os.path.exists('/sys/fs/cgroup/memory/memory.usage_in_bytes'):
                with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as f:
                    return int(f.read().strip()) / (1024 * 1024)
        except Exception:
            pass
        return 0

    def _monitor(self):
        while self.keep_running:
            current = self._get_current_memory()
            if current > self.peak_memory_mb:
                self.peak_memory_mb = current
            time.sleep(0.1) # Quét 10 lần mỗi giây

    def start(self):
        self.keep_running = True
        self.peak_memory_mb = self._get_current_memory()
        self.thread = threading.Thread(target=self._monitor)
        self.thread.start()

    def stop(self):
        self.keep_running = False
        self.thread.join()
        return self.peak_memory_mb


def _attach_listener(sc: Any, metrics: _QueryMetrics) -> None:
    """
    Attach a Java SparkListener that calls back into Python via Py4J.
    Uses the internal SparkContext._jvm interface so no extra JARs needed.
    """
    from pyspark import SparkContext

    jvm = sc._jvm
    jsc = sc._jsc.sc()

    # Build a Java anonymous listener via Py4J's JavaGateway callback server.
    class PythonListener(jvm.org.apache.spark.scheduler.SparkListenerInterface):
        def onTaskEnd(self, task_end):  # noqa: N802
            tm = task_end.taskMetrics()
            if tm is not None:
                metrics.on_task_end(tm)

        # Stubbed-out required interface methods
        def onStageCompleted(self, e): pass
        def onStageSubmitted(self, e): pass
        def onTaskStart(self, e): pass
        def onTaskGettingResult(self, e): pass
        def onJobStart(self, e): pass
        def onJobEnd(self, e): pass
        def onEnvironmentUpdate(self, e): pass
        def onBlockManagerAdded(self, e): pass
        def onBlockManagerRemoved(self, e): pass
        def onUnpersistRDD(self, e): pass
        def onApplicationStart(self, e): pass
        def onApplicationEnd(self, e): pass
        def onExecutorMetricsUpdate(self, e): pass
        def onExecutorAdded(self, e): pass
        def onExecutorRemoved(self, e): pass
        def onBlockUpdated(self, e): pass
        def onOtherEvent(self, e): pass
        def onSpeculativeTaskSubmitted(self, e): pass

    jsc.addSparkListener(PythonListener())


# ─── SparkSession factory ──────────────────────────────────────────────────────

def _build_spark(env: dict):
    """
    Build a SparkSession configured to be resource-equivalent to the Trino
    benchmark: uses the number of cores declared in SPARK_DRIVER_CORES (default
    4) and the memory in SPARK_DRIVER_MEMORY (default 7g).
    """
    from pyspark.sql import SparkSession

    cores = env.get("SPARK_DRIVER_CORES", "4")
    memory = env.get("SPARK_DRIVER_MEMORY", "7g")
    catalog = env.get("SPARK_CATALOG", "iceberg")
    schema = env.get("SPARK_SCHEMA", "benchmark_tpcds_sf5")
    warehouse = env.get("ICEBERG_WAREHOUSE", "s3a://iceberg/lakehouse")
    metastore_uri = env.get("ICEBERG_URI", "thrift://hive-metastore:9083")
    minio_endpoint = env.get("MINIO_ENDPOINT", "http://minio:9000")

    builder = (
        SparkSession.builder
        .appName(f"tpcds-benchmark-{schema}")
        .master(f"local[{cores}]")
        # ── Memory (mirrors Helm values for Trino worker) ────────────────────
        .config("spark.driver.memory", memory)
        .config("spark.driver.cores", cores)
        # ── Adaptive Query Execution (always on) ────────────────────────────
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.adaptive.skewJoin.enabled", "true")
        # ── Iceberg catalog (same as Trino catalog config) ───────────────────
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config(f"spark.sql.catalog.{catalog}",
                "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{catalog}.type", "hive")
        .config(f"spark.sql.catalog.{catalog}.uri", metastore_uri)
        .config(f"spark.sql.catalog.{catalog}.warehouse", warehouse)
        # ── S3A / MinIO ──────────────────────────────────────────────────────
        .config("spark.hadoop.fs.s3a.endpoint", minio_endpoint)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl",
                "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
        # ── Hive Metastore (for catalog resolution) ──────────────────────────
        .config("spark.sql.catalogImplementation", "hive")
        .config("spark.hadoop.hive.metastore.uris", metastore_uri)
        # ── Iceberg packages ─────────────────────────────────────────────────
        .config("spark.jars.packages",
                "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.2,"
                "org.apache.hadoop:hadoop-aws:3.3.4,"
                "com.amazonaws:aws-java-sdk-bundle:1.12.262")
        .config("spark.jars.ivy", "/tmp/.ivy2")
        # ── Serialisation ────────────────────────────────────────────────────
        .config("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")
        .config("spark.sql.parquet.int96RebaseModeInRead", "CORRECTED")
    )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    # Set default catalog+schema so queries don't need fully-qualified names.
    spark.sql(f"USE {catalog}.{schema}")
    return spark


# ─── Query execution ──────────────────────────────────────────────────────────
import resource
def get_memory_usage_mb():
    """Lấy lượng RAM thực tế (Resident Set Size - RSS) mà toàn bộ tiến trình Python và các tiến trình con (bao gồm JVM của Spark) đang chiếm dụng tại OS level."""
    # Trả về KB, chia 1024 để ra MB
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

def run_query(spark, sql: str) -> tuple[list, float, str, str, float]:
    monitor = MemoryMonitor()
    
    # Bắt đầu đo RAM
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
    
    # Kết thúc đo RAM và lấy kết quả đỉnh (Peak Memory)
    peak_mem_mb = monitor.stop()

    return rows, wall, status, error_message, peak_mem_mb


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    env = load_env()
    query_files = read_query_list(env)
    warmups = int(env.get("WARMUP_RUNS", 1))
    runs = int(env.get("RUNS", 3))

    results_root = Path(env.get("RESULTS_DIR", str(ROOT / "benchmark" / "results")))
    raw_dir = results_root / "raw"
    ensure_dir(raw_dir)
    output_file = raw_dir / "spark_results.jsonl"
    output_file.write_text("", encoding="utf-8")   # truncate / create

    print(f"Building SparkSession (local[{env.get('SPARK_DRIVER_CORES', 4)}], "
          f"{env.get('SPARK_DRIVER_MEMORY', '7g')}) …")
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

                rows, wall, status, err, mem_used = run_query(spark, sql)

                m = metrics.snapshot() if listener_ok else {"peak_memory_bytes": 0,
                                                             "spill_bytes": 0,
                                                             "cpu_time_millis": 0}

                record = make_record(
                    engine="spark",
                    query_name=query_name,
                    run_type="warmup" if is_warmup else "measured",
                    run_number=run_number,
                    query_id=f"spark-local-{query_name}-{run_label}",
                    status=status,
                    wall_time_seconds=wall,
                    peak_memory_bytes=mem_used,
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
                    f"→ {status}  wall={wall:.2f}s  "
                    f"mem={m['peak_memory_bytes']//1024//1024}MB  "
                    f"spill={m['spill_bytes']//1024}KB"
                )

    except KeyboardInterrupt:
        print("\nInterrupted — partial results saved.")
    finally:
        spark.stop()

    print(f"\nDone. Results: {output_file}")


if __name__ == "__main__":
    main()