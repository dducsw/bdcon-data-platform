from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from common import ROOT, ensure_dir, load_env, read_query_list, stable_hash, write_jsonl


def post_query(sql: str, env: dict, source: str) -> dict:
    request = urllib.request.Request(
        url=f"{env['TRINO_BASE_URL']}/v1/statement",
        data=sql.encode("utf-8"),
        headers={
            "X-Trino-User": env["TRINO_USER"],
            "X-Trino-Catalog": env["TRINO_CATALOG"],
            "X-Trino-Schema": env["TRINO_SCHEMA"],
            "X-Trino-Source": source,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def poll_query(payload: dict, timeout_seconds: int = 1800) -> tuple[list, dict]:
    rows = []
    last_payload = payload
    if payload.get("data"):
        rows.extend(payload["data"])
    next_uri = payload.get("nextUri")
    start_time = time.time()
    
    while next_uri:
        if time.time() - start_time > timeout_seconds:
            # We should try to cancel the query if it's still running
            # For now, just raise TimeoutError
            raise TimeoutError(f"Query timed out after {timeout_seconds}s")
            
        with urllib.request.urlopen(next_uri, timeout=60) as response:
            last_payload = json.loads(response.read().decode("utf-8"))
        if last_payload.get("data"):
            rows.extend(last_payload["data"])
        if last_payload.get("error"):
            raise RuntimeError(last_payload["error"].get("message", "Unknown Trino error"))
        next_uri = last_payload.get("nextUri")
    return rows, last_payload


def stat(stats: dict, *names: str, default=0):
    for name in names:
        if name in stats and stats[name] is not None:
            return stats[name]
    return default


def main() -> None:
    env = load_env()
    query_files = read_query_list(env)
    warmups = int(env["WARMUP_RUNS"])
    runs = int(env["RUNS"])

    records = []
    raw_dir = ROOT / env["RESULTS_DIR"] / "raw"
    ensure_dir(raw_dir)

    timeout_seconds = int(env.get("QUERY_TIMEOUT_SECONDS", 1800))
    try:
        for query_file in query_files:
            sql = query_file.read_text(encoding="utf-8").strip()
            if sql.endswith(";"):
                sql = sql[:-1].rstrip()
            
            if str(env.get("WRAP_COUNT", "false")).lower() == "true":
                sql = f"SELECT COUNT(*) FROM (\n{sql}\n)"
                
            query_name = query_file.stem

            for run_index in range(1, warmups + runs + 1):
                is_warmup = run_index <= warmups
                measured_run = 0 if is_warmup else run_index - warmups
                source = f"{env['TRINO_SOURCE']}-{query_name}-run-{run_index}"
                started = time.perf_counter()
                status = "success"
                error_message = ""
                
                try:
                    payload = post_query(sql, env, source)
                    query_id = payload.get("id", "")
                    rows, final_payload = poll_query(payload, timeout_seconds)
                except Exception as exc:  # noqa: BLE001
                    rows = []
                    query_id = "N/A"
                    final_payload = {}
                    status = "failed"
                    error_message = str(exc)
                else:
                    stats = final_payload.get("stats", {})

                elapsed_wall = time.perf_counter() - started
                stats = final_payload.get("stats", {}) if final_payload else {}
                server_elapsed = stats.get("elapsedTimeMillis")
                query_time_seconds = server_elapsed / 1000.0 if server_elapsed is not None else elapsed_wall

                records.append(
                    {
                        "engine": "trino",
                        "query_name": query_name,
                        "run_type": "warmup" if is_warmup else "measured",
                        "run_number": measured_run,
                        "query_id": query_id,
                        "status": status,
                        "query_time_seconds": round(query_time_seconds, 3),
                        "throughput_qps": round(1 / query_time_seconds, 6) if query_time_seconds > 0 else 0,
                        "peak_memory_bytes": stat(stats, "peakMemoryBytes", "peakUserMemoryBytes"),
                        "spill_bytes": stat(stats, "spilledBytes"),
                        "cpu_time_millis": stat(stats, "cpuTimeMillis"),
                        "result_hash": stable_hash(rows),
                        "row_count": len(rows),
                        "error_message": error_message,
                    }
                )
                print(f"Trino {query_name} run {run_index} -> {status} ({query_time_seconds:.2f}s)")
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user. Saving partial results...")

    output = raw_dir / "trino_results.jsonl"
    write_jsonl(output, records)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
