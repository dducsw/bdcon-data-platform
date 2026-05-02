from __future__ import annotations

import json
import time
from pathlib import Path
from pyhive import hive

from common import ROOT, ensure_dir, load_env, read_query_list, stable_hash, write_jsonl


def fetch_spark_rest_metrics(host: str, ui_port: int) -> dict:
    import urllib.request
    import urllib.error
    import json
    
    metrics = {"peak_memory_bytes": 0, "spill_bytes": 0, "cpu_time_millis": 0}
    base_url = f"http://{host}:{ui_port}/api/v1/applications"
    
    try:
        req = urllib.request.urlopen(base_url, timeout=5)
        apps = json.loads(req.read().decode('utf-8'))
        if not apps: return metrics
        app_id = apps[0]["id"]
        
        req = urllib.request.urlopen(f"{base_url}/{app_id}/sql", timeout=5)
        sqls = json.loads(req.read().decode('utf-8'))
        completed_sqls = [s for s in sqls if s.get("status") == "COMPLETED"]
        if not completed_sqls: return metrics
        
        latest_sql = sorted(completed_sqls, key=lambda x: x.get("id", 0), reverse=True)[0]
        job_ids = list(latest_sql.get("jobs", {}).keys())
        
        stage_ids = []
        for jid in job_ids:
            try:
                req = urllib.request.urlopen(f"{base_url}/{app_id}/jobs/{jid}", timeout=5)
                job = json.loads(req.read().decode('utf-8'))
                stage_ids.extend(job.get("stageIds", []))
            except urllib.error.URLError: continue
                
        peak_mem = 0
        spill_bytes = 0
        cpu_time_ns = 0
        
        for sid in set(stage_ids):
            try:
                req = urllib.request.urlopen(f"{base_url}/{app_id}/stages/{sid}", timeout=5)
                stages = json.loads(req.read().decode('utf-8'))
                for stage in stages:
                    cpu_time_ns += stage.get("executorCpuTime", 0)
                    spill_bytes += stage.get("memoryBytesSpilled", 0) + stage.get("diskBytesSpilled", 0)
                    peak_mem = max(peak_mem, stage.get("peakExecutionMemory", 0))
            except urllib.error.URLError: continue
                
        metrics["cpu_time_millis"] = int(cpu_time_ns / 1_000_000)
        metrics["spill_bytes"] = spill_bytes
        metrics["peak_memory_bytes"] = peak_mem
    except Exception as e:
        print(f"  Warning: Failed to fetch REST metrics: {e}")
        
    return metrics


def run_query(env: dict, cursor, sql_text: str) -> tuple[list, float, str]:
    started = time.perf_counter()
    status = "success"
    error_message = ""
    rows = []
    
    try:
        cursor.execute(sql_text)
        # Fetch rows if there are any results returned (DDL/DML might not return rows)
        if cursor.description is not None:
            rows = cursor.fetchall()
    except Exception as e:
        status = "failed"
        error_message = str(e)
        
    elapsed = time.perf_counter() - started
    return rows, elapsed, status, error_message


def main() -> None:
    env = load_env()
    query_files = read_query_list(env)
    warmups = int(env["WARMUP_RUNS"])
    runs = int(env["RUNS"])

    records = []
    raw_dir = ROOT / env["RESULTS_DIR"] / "raw"
    ensure_dir(raw_dir)

    output_file = raw_dir / "spark_results.jsonl"
    output_file.write_text("", encoding="utf-8")

    host = env.get("SPARK_THRIFT_HOST", "localhost")
    port = int(env.get("SPARK_THRIFT_PORT", 10000))
    catalog = env.get("SPARK_CATALOG", "catalog_iceberg")
    schema = env.get("SPARK_SCHEMA", "benchmark_tpcds_sf1")

    print(f"Connecting to Spark Thrift Server at {host}:{port}...")
    try:
        conn = hive.Connection(host=host, port=port, database=schema)
        cursor = conn.cursor()
        print("Connected successfully!")
    except Exception as e:
        print(f"Failed to connect to Spark Thrift Server: {e}")
        return

    # Enable AQE
    cursor.execute("SET spark.sql.adaptive.enabled=true")
    cursor.execute("SET spark.sql.adaptive.coalescePartitions.enabled=true")
    cursor.execute(f"USE {catalog}.{schema}")

    try:
        for query_file in query_files:
            query_name = query_file.stem
            sql_text = query_file.read_text(encoding="utf-8").strip()
            if sql_text.endswith(";"):
                sql_text = sql_text[:-1].rstrip()
                
            if str(env.get("WRAP_COUNT", "false")).lower() == "true":
                sql_text = f"SELECT COUNT(*) FROM (\n{sql_text}\n)"

            for run_index in range(1, warmups + runs + 1):
                is_warmup = run_index <= warmups
                measured_run = 0 if is_warmup else run_index - warmups
                
                rows, query_time, status, error_message = run_query(env, cursor, sql_text)

                ui_port = int(env.get("SPARK_UI_PORT", 4040))
                metrics = fetch_spark_rest_metrics(host, ui_port) if status == "success" else {"peak_memory_bytes": 0, "spill_bytes": 0, "cpu_time_millis": 0}

                record = {
                    "engine": "spark",
                    "query_name": query_name,
                    "run_type": "warmup" if is_warmup else "measured",
                    "run_number": measured_run,
                    "query_id": f"spark-thrift-{query_name}-{run_index}",
                    "status": status,
                    "query_time_seconds": round(query_time, 3),
                    "throughput_qps": round(1 / query_time, 6) if query_time > 0 else 0,
                    "peak_memory_bytes": metrics["peak_memory_bytes"],
                    "spill_bytes": metrics["spill_bytes"],
                    "cpu_time_millis": metrics["cpu_time_millis"],
                    "result_hash": stable_hash(rows) if rows else "",
                    "row_count": len(rows),
                    "error_message": error_message,
                }
                records.append(record)
                
                # Save incrementally
                with output_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")

                print(f"Spark {query_name} run {run_index} -> {status} (Query: {query_time:.2f}s)")
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user. Partial results saved to", output_file)
    finally:
        cursor.close()
        conn.close()
    
    print(f"Benchmark finished. Total records: {len(records)}")


if __name__ == "__main__":
    main()
