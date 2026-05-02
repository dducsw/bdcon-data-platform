from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from common import ROOT, ensure_dir, load_env, read_query_list, stable_hash, write_jsonl


def find_event_log(app_name: str, eventlog_dir: Path, since: float, timeout: int = 5) -> Path | None:
    """
    Finds the Spark event log for a given app_name. 
    Retries for 'timeout' seconds to account for log flushing lag.
    """
    start_wait = time.time()
    while time.time() - start_wait < timeout:
        # Sort by mtime descending to check newest logs first
        try:
            candidates = sorted(eventlog_dir.glob("app-*"), key=lambda path: path.stat().st_mtime, reverse=True)
        except OSError:
            candidates = []

        for path in candidates:
            # allow some clock drift or lag (since - 60 seconds)
            if path.stat().st_mtime < since - 60:
                continue
            try:
                with path.open("r", encoding="utf-8") as handle:
                    # App name is usually in the first few lines
                    for _ in range(30):
                        line = handle.readline()
                        if not line:
                            break
                        if app_name in line:
                            return path
            except (PermissionError, UnicodeDecodeError):
                continue
        time.sleep(1)
    return None


def parse_event_log(path: Path) -> dict:
    peak_memory = 0
    spill_bytes = 0
    cpu_time_millis = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("Event") != "SparkListenerTaskEnd":
                    continue
                
                metrics = event.get("Task Metrics", {})
                # Use max for peak memory across all tasks
                peak_memory = max(peak_memory, metrics.get("Peak Execution Memory", 0))
                spill_bytes += metrics.get("Memory Bytes Spilled", 0)
                spill_bytes += metrics.get("Disk Bytes Spilled", 0)
                # CPU time is in nanoseconds in the event log
                cpu_time_millis += int(metrics.get("Executor CPU Time", 0) / 1_000_000)
    except (PermissionError, OSError) as e:
        print(f"Error reading event log {path}: {e}")
        return {
            "peak_memory_bytes": 0,
            "spill_bytes": 0,
            "cpu_time_millis": 0,
        }
    return {
        "peak_memory_bytes": peak_memory,
        "spill_bytes": spill_bytes,
        "cpu_time_millis": cpu_time_millis,
    }


def parse_spark_time(stdout: str, stderr: str = "") -> float | None:
    """Parses 'Time taken: X.XXX seconds' from Spark stdout or stderr."""
    combined = stdout + "\n" + stderr
    # Find all matches and take the last one (usually the query time, others might be 'USE' statements)
    matches = re.findall(r"Time taken:\s+([\d.]+)\s+seconds", combined)
    if matches:
        return float(matches[-1])
    return None


def run_query(env: dict, query_file: Path, app_name: str) -> subprocess.CompletedProcess[str]:
    sql_text = query_file.read_text(encoding="utf-8")
    wrapped_sql = (
        f"USE {env['SPARK_CATALOG']}.{env['SPARK_SCHEMA']};\n"
        f"{sql_text.rstrip()}\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".sql",
        encoding="utf-8",
        delete=False,
        dir=ROOT,
    ) as handle:
        handle.write(wrapped_sql)
        host_query_file = Path(handle.name)

    container_query = f"/opt/benchmark/{host_query_file.name}"
    command = [
        "docker",
        "cp",
        str(host_query_file),
        f"{env['SPARK_CONTAINER']}:{container_query}",
    ]
    copy_result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, check=False)
    if copy_result.returncode != 0:
        try:
            host_query_file.unlink(missing_ok=True)
        except OSError:
            pass
        return copy_result

    spark_command = [
        "docker",
        "exec",
        env["SPARK_CONTAINER"],
        "spark-sql",
        "--conf",
        f"spark.app.name={app_name}",
        "--conf",
        "spark.sql.shuffle.partitions=8",
        "--conf",
        f"spark.sql.defaultCatalog={env['SPARK_CATALOG']}",
        "-f",
        container_query,
    ]
    
    timeout_seconds = int(env.get("QUERY_TIMEOUT_SECONDS", 1800))
    try:
        result = subprocess.run(spark_command, capture_output=True, text=True, cwd=ROOT, check=False, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(spark_command, 124, e.stdout.decode() if e.stdout else "", f"Query timed out after {timeout_seconds}s\n{e.stderr.decode() if e.stderr else ''}")

    cleanup = subprocess.run(
        ["docker", "exec", env["SPARK_CONTAINER"], "rm", "-f", container_query],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if cleanup.returncode != 0 and result.returncode == 0:
        result = subprocess.CompletedProcess(
            result.args,
            1,
            result.stdout,
            f"{result.stderr}\nFailed to remove temp SQL file: {cleanup.stderr}".strip(),
        )

    try:
        host_query_file.unlink(missing_ok=True)
    except OSError:
        pass

    return result


def parse_spark_rows(stdout: str, stderr: str = "") -> list[list[str]]:
    """
    Parses spark-sql output into a list of rows.
    Uses stdout for data and ignores known metadata/log patterns.
    """
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    data_rows = []
    
    # Patterns that, if present anywhere in the line, mark it as non-data
    metadata_patterns = ["Time taken:", "Fetched", "row(s)", "SLF4J:", "WARN", "INFO", "ERROR", "DEBUG"]
    # Prefixes for log lines
    log_prefixes = ("::", "Spark Web UI", "Spark master:", "Setting", "Ivy", "The jars", "resolving", "confs:", "found", "resolution", "modules", "retrieving", "artifacts", "org.apache")

    for line in lines:
        # Skip if any metadata pattern is present
        if any(p in line for p in metadata_patterns):
            continue
        # Skip if it starts with a log prefix
        if line.startswith(log_prefixes):
            continue
        # Skip date-prefixed log lines (e.g., 24/04/27 10:20:30)
        if len(line) > 10 and line[2] == "/" and line[5] == "/" and " " in line[:11]:
            continue
            
        data_rows.append(line.split("\t"))
        
    return data_rows


def main() -> None:
    env = load_env()
    query_files = read_query_list(env)
    warmups = int(env["WARMUP_RUNS"])
    runs = int(env["RUNS"])
    eventlog_dir = ROOT / env["SPARK_EVENTLOG_DIR"]

    records = []
    raw_dir = ROOT / env["RESULTS_DIR"] / "raw"
    ensure_dir(raw_dir)

    output_file = raw_dir / "spark_results.jsonl"
    # Clear file at start
    output_file.write_text("", encoding="utf-8")

    try:
        for query_file in query_files:
            query_name = query_file.stem
            for run_index in range(1, warmups + runs + 1):
                is_warmup = run_index <= warmups
                measured_run = 0 if is_warmup else run_index - warmups
                app_name = f"benchmark-{query_name}-run-{run_index}"
                started_wall = time.perf_counter()
                started_epoch = time.time()
                
                completed = run_query(env, query_file, app_name)
                elapsed_wall = time.perf_counter() - started_wall
                
                # Try to parse pure query time from spark output (check both stdout and stderr)
                engine_time = parse_spark_time(completed.stdout, completed.stderr)
                
                event_log = find_event_log(app_name, eventlog_dir, started_epoch)
                metrics = parse_event_log(event_log) if event_log else {
                    "peak_memory_bytes": 0,
                    "spill_bytes": 0,
                    "cpu_time_millis": 0,
                }
                
                if not event_log and completed.returncode == 0:
                    print(f"  Warning: Event log not found for {app_name}")

                status = "success" if completed.returncode == 0 else "failed"
                result_rows = parse_spark_rows(completed.stdout, completed.stderr)
                
                # Final query time: prefer engine time if parsed, otherwise use wall time
                query_time = engine_time if engine_time is not None else elapsed_wall

                record = {
                    "engine": "spark",
                    "query_name": query_name,
                    "run_type": "warmup" if is_warmup else "measured",
                    "run_number": measured_run,
                    "query_id": app_name,
                    "status": status,
                    "query_time_seconds": round(query_time, 3),
                    "throughput_qps": round(1 / query_time, 6) if query_time > 0 else 0,
                    "peak_memory_bytes": metrics["peak_memory_bytes"],
                    "spill_bytes": metrics["spill_bytes"],
                    "cpu_time_millis": metrics["cpu_time_millis"],
                    "result_hash": stable_hash(result_rows),
                    "row_count": len(result_rows),
                    "error_message": completed.stderr.strip() if status == "failed" else "",
                }
                records.append(record)
                
                # Save incrementally
                with output_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")

                mem_mb = metrics["peak_memory_bytes"] / (1024 * 1024)
                print(f"Spark {query_name} run {run_index} -> {status} (Query: {query_time:.2f}s, Mem: {mem_mb:.1f}MB)")
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user. Partial results saved to", output_file)
    
    print(f"Benchmark finished. Total records: {len(records)}")


if __name__ == "__main__":
    main()
