from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

from common import ROOT, ensure_dir, load_env, read_query_list, stable_hash, write_jsonl


def find_event_log(app_name: str, eventlog_dir: Path, since: float) -> Path | None:
    candidates = sorted(eventlog_dir.glob("app-*"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        if path.stat().st_mtime < since - 2:
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                for _ in range(20):
                    line = handle.readline()
                    if not line:
                        break
                    if app_name in line:
                        return path
        except UnicodeDecodeError:
            continue
    return None


def parse_event_log(path: Path) -> dict:
    peak_memory = 0
    spill_bytes = 0
    cpu_time_millis = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            if event.get("Event") != "SparkListenerTaskEnd":
                continue
            metrics = event.get("Task Metrics", {})
            peak_memory = max(peak_memory, metrics.get("Peak Execution Memory", 0))
            spill_bytes += metrics.get("Memory Bytes Spilled", 0)
            spill_bytes += metrics.get("Disk Bytes Spilled", 0)
            cpu_time_millis += int(metrics.get("Executor CPU Time", 0) / 1_000_000)
    return {
        "peak_memory_bytes": peak_memory,
        "spill_bytes": spill_bytes,
        "cpu_time_millis": cpu_time_millis,
    }


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

    command = [
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
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, check=False)

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


def main() -> None:
    env = load_env()
    query_files = read_query_list(env)
    warmups = int(env["WARMUP_RUNS"])
    runs = int(env["RUNS"])
    eventlog_dir = ROOT / env["SPARK_EVENTLOG_DIR"]

    records = []
    raw_dir = Path(env["RESULTS_DIR"]) / "raw"
    ensure_dir(raw_dir)

    for query_file in query_files:
        query_name = query_file.stem
        for run_index in range(1, warmups + runs + 1):
            is_warmup = run_index <= warmups
            measured_run = 0 if is_warmup else run_index - warmups
            app_name = f"benchmark-{query_name}-run-{run_index}"
            started_wall = time.perf_counter()
            started_epoch = time.time()
            completed = run_query(env, query_file, app_name)
            elapsed = time.perf_counter() - started_wall
            event_log = find_event_log(app_name, eventlog_dir, started_epoch)
            metrics = parse_event_log(event_log) if event_log else {
                "peak_memory_bytes": 0,
                "spill_bytes": 0,
                "cpu_time_millis": 0,
            }
            status = "success" if completed.returncode == 0 else "failed"
            stdout_lines = [
                line
                for line in completed.stdout.splitlines()
                if line.strip() and not line.startswith("Time taken:")
            ]
            records.append(
                {
                    "engine": "spark",
                    "query_name": query_name,
                    "run_type": "warmup" if is_warmup else "measured",
                    "run_number": measured_run,
                    "query_id": app_name,
                    "status": status,
                    "query_time_seconds": round(elapsed, 3),
                    "throughput_qps": round(1 / elapsed, 6) if elapsed > 0 else 0,
                    "peak_memory_bytes": metrics["peak_memory_bytes"],
                    "spill_bytes": metrics["spill_bytes"],
                    "cpu_time_millis": metrics["cpu_time_millis"],
                    "result_hash": stable_hash(stdout_lines),
                    "row_count": max(len(stdout_lines) - 1, 0),
                    "error_message": completed.stderr.strip(),
                }
            )
            print(f"Spark {query_name} run {run_index} -> {status}")

    output = raw_dir / "spark_results.jsonl"
    write_jsonl(output, records)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
