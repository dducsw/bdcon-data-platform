from __future__ import annotations

import json
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, ensure_dir, load_env, read_query_list, stable_hash, write_jsonl


def fmt_bytes(b: int) -> str:
    """Format bytes into human-readable string."""
    if b <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


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


def print_summary(records: list[dict]) -> None:
    """Print a summary table at the end of the benchmark run."""
    measured = [r for r in records if r["run_type"] == "measured" and r["status"] == "success"]
    if not measured:
        return

    by_query = defaultdict(list)
    for r in measured:
        by_query[r["query_name"]].append(r)

    print("\n" + "=" * 80)
    print("  TRINO BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"{'Query':<12} {'Avg (s)':>8} {'Min (s)':>8} {'Max (s)':>8} {'Rows':>8} {'Peak Mem':>10} {'CPU (s)':>8}")
    print("-" * 80)

    total_avg = 0
    total_cpu = 0
    for qname in sorted(by_query.keys()):
        query_records = by_query[qname]
        times = [r["query_time_seconds"] for r in query_records]
        avg_t = sum(times) / len(times)
        total_avg += avg_t
        row_count = query_records[0]["row_count"]
        peak_mem = max(r["peak_memory_bytes"] for r in query_records)
        cpu_ms = sum(r["cpu_time_millis"] for r in query_records) / len(query_records)
        total_cpu += cpu_ms
        print(f"{qname:<12} {avg_t:>8.2f} {min(times):>8.2f} {max(times):>8.2f} {row_count:>8} {fmt_bytes(peak_mem):>10} {cpu_ms/1000:>8.1f}")

    print("-" * 80)
    total_time = sum(r["query_time_seconds"] for r in measured)
    all_measured = [r for r in records if r["run_type"] == "measured"]
    print(f"{'TOTAL':<12} {total_avg:>8.2f}")
    print(f"  Total measured time:   {total_time:.2f}s")
    print(f"  Total CPU time (avg):  {total_cpu/1000:.1f}s")
    print(f"  CPU efficiency:        {total_cpu/1000/total_avg:.1f}x (CPU/Wall)")
    print(f"  Success rate:          {len(measured)}/{len(all_measured)} queries")
    print("=" * 80)


def main() -> None:
    env = load_env()
    query_files = read_query_list(env)
    warmups = int(env["WARMUP_RUNS"])
    runs = int(env["RUNS"])
    total_queries = len(query_files)

    records = []
    raw_dir = ROOT / env["RESULTS_DIR"] / "raw"
    ensure_dir(raw_dir)

    timeout_seconds = int(env.get("QUERY_TIMEOUT_SECONDS", 1800))

    print("=" * 60)
    print("  TRINO TPC-DS BENCHMARK")
    print("=" * 60)
    print(f"  URL:     {env['TRINO_BASE_URL']}")
    print(f"  Catalog: {env['TRINO_CATALOG']}.{env['TRINO_SCHEMA']}")
    print(f"  Queries: {total_queries}")
    print(f"  Warmups: {warmups}, Measured: {runs}")
    print(f"  Timeout: {timeout_seconds}s")
    print(f"  Started: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)
    print()

    benchmark_start = time.perf_counter()
    try:
        for q_idx, query_file in enumerate(query_files, 1):
            sql = query_file.read_text(encoding="utf-8").strip()
            if sql.endswith(";"):
                sql = sql[:-1].rstrip()
            
            if str(env.get("WRAP_COUNT", "false")).lower() == "true":
                sql = f"SELECT COUNT(*) FROM (\n{sql}\n)"
                
            query_name = query_file.stem
            print(f"[{q_idx}/{total_queries}] {query_name}")

            for run_index in range(1, warmups + runs + 1):
                is_warmup = run_index <= warmups
                measured_run = 0 if is_warmup else run_index - warmups
                run_label = "warmup" if is_warmup else f"run {measured_run}"
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
                server_elapsed_ms = stats.get("elapsedTimeMillis")
                # Use wall-clock time consistently (same methodology as Spark)
                query_time_seconds = elapsed_wall
                server_time_seconds = server_elapsed_ms / 1000.0 if server_elapsed_ms is not None else None

                peak_mem = stat(stats, "peakMemoryBytes", "peakUserMemoryBytes")
                cpu_ms = stat(stats, "cpuTimeMillis")
                spill = stat(stats, "spilledBytes")

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
                        "server_time_seconds": round(server_time_seconds, 3) if server_time_seconds is not None else None,
                        "peak_memory_bytes": peak_mem,
                        "spill_bytes": spill,
                        "cpu_time_millis": cpu_ms,
                        "result_hash": stable_hash(rows),
                        "row_count": len(rows),
                        "error_message": error_message,
                    }
                )

                status_icon = "✓" if status == "success" else "✗"
                server_delta = ""
                if server_time_seconds is not None:
                    delta = query_time_seconds - server_time_seconds
                    server_delta = f" | overhead: {delta*1000:.0f}ms"
                mem_str = f" | mem: {fmt_bytes(peak_mem)}" if peak_mem > 0 else ""
                cpu_str = f" | cpu: {cpu_ms/1000:.1f}s" if cpu_ms > 0 else ""
                rows_str = f" | rows: {len(rows)}" if rows else ""
                print(f"  {status_icon} {run_label}: {query_time_seconds:.2f}s{rows_str}{mem_str}{cpu_str}{server_delta}")

                if status == "failed":
                    print(f"    Error: {error_message}")
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user. Saving partial results...")

    output = raw_dir / "trino_results.jsonl"
    write_jsonl(output, records)

    benchmark_elapsed = time.perf_counter() - benchmark_start
    print(f"\nFinished: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Total wall time (incl. warmup): {benchmark_elapsed:.1f}s")

    print_summary(records)
    print(f"\nWrote {output}")


if __name__ == "__main__":
    main()
