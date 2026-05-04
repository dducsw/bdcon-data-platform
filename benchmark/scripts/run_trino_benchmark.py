"""
run_trino_benchmark.py
======================
Submits TPC-DS queries to Trino via the REST /v1/statement API and records
server-side metrics from the final payload.

Metrics collected per query (symmetric with Spark script)
----------------------------------------------------------
wall_time_seconds   stats.elapsedTimeMillis / 1000  (server-side, ms precision)
peak_memory_bytes   stats.peakUserMemoryBytes
spill_bytes         stats.spilledBytes
cpu_time_millis     stats.cpuTimeMillis
result_hash         stable_hash(rows)

If elapsedTimeMillis is absent (very fast queries that finish in the first
poll), we fall back to the client-side perf_counter delta — same as Spark.

Timeout handling
----------------
When a query exceeds QUERY_TIMEOUT_SECONDS, we send a DELETE to /v1/query/<id>
to cancel it on the server before moving on. Without cancellation, zombie
queries accumulate on the Trino cluster and interfere with subsequent runs.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from common import (
    ROOT,
    append_jsonl,
    ensure_dir,
    load_env,
    make_record,
    read_query_list,
    stable_hash,
)


# ─── Low-level HTTP helpers ───────────────────────────────────────────────────

_DEFAULT_TIMEOUT_S = 60   # per individual HTTP request (not query timeout)


def _post(url: str, body: str, headers: dict) -> dict:
    req = urllib.request.Request(
        url=url,
        data=body.encode("utf-8"),
        headers={"Content-Type": "text/plain; charset=utf-8", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=_DEFAULT_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _delete(url: str) -> None:
    req = urllib.request.Request(url=url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception:
        pass   # best-effort cancellation


# ─── Query submission & polling ───────────────────────────────────────────────

def submit_query(sql: str, env: dict, source: str) -> dict:
    """POST the SQL to /v1/statement and return the initial payload."""
    return _post(
        url=f"{env['TRINO_BASE_URL']}/v1/statement",
        body=sql,
        headers={
            "X-Trino-User": env.get("TRINO_USER", "benchmark"),
            "X-Trino-Catalog": env["TRINO_CATALOG"],
            "X-Trino-Schema": env["TRINO_SCHEMA"],
            "X-Trino-Source": source,
            # Ask Trino to report memory stats in the final response.
            "X-Trino-Client-Info": "tpcds-benchmark",
        },
    )


def poll_until_done(
    initial_payload: dict,
    timeout_s: int,
) -> tuple[list, dict, str]:
    """
    Poll nextUri until the query completes or times out.
    Returns (rows, final_stats_dict, query_id).
    Cancels the query on timeout.
    """
    rows: list = []
    payload = initial_payload
    query_id: str = payload.get("id", "")
    deadline = time.monotonic() + timeout_s

    # First payload may already contain data rows.
    if payload.get("data"):
        rows.extend(payload["data"])

    next_uri = payload.get("nextUri")
    while next_uri:
        if time.monotonic() > deadline:
            _delete(f"{payload.get('infoUri', '').rsplit('/query', 1)[0]}/v1/query/{query_id}")
            raise TimeoutError(f"Query {query_id} timed out after {timeout_s}s")

        # Back-off when Trino says "not ready yet" (no nextUri change, no data)
        time.sleep(0.05)

        try:
            payload = _get(next_uri)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Poll failed ({exc.code}): {exc.read().decode('utf-8', errors='replace')}") from exc

        if payload.get("error"):
            msg = payload["error"].get("message", "Unknown Trino error")
            failure_info = payload["error"].get("failureInfo", {})
            stack = failure_info.get("stack", [])
            detail = "\n".join(stack[:5]) if stack else ""
            raise RuntimeError(f"{msg}\n{detail}".strip())

        if payload.get("data"):
            rows.extend(payload["data"])

        next_uri = payload.get("nextUri")

    stats = payload.get("stats", {})
    return rows, stats, query_id


def _safe_int(stats: dict, *keys: str) -> int:
    for k in keys:
        v = stats.get(k)
        if v is not None:
            return int(v)
    return 0


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    env = load_env()
    query_files = read_query_list(env)
    warmups = int(env.get("WARMUP_RUNS", 1))
    runs = int(env.get("RUNS", 3))
    timeout_s = int(env.get("QUERY_TIMEOUT_SECONDS", 1800))

    results_root = Path(env.get("RESULTS_DIR", str(ROOT / "benchmark" / "results")))
    raw_dir = results_root / "raw"
    ensure_dir(raw_dir)
    output_file = raw_dir / "trino_results.jsonl"
    output_file.write_text("", encoding="utf-8")

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
                source = f"tpcds-benchmark-{query_name}-{run_label}"

                client_start = time.perf_counter()
                status = "success"
                error_message = ""
                rows: list = []
                stats: dict = {}
                query_id = "N/A"

                try:
                    initial = submit_query(sql, env, source)
                    query_id = initial.get("id", "N/A")
                    rows, stats, query_id = poll_until_done(initial, timeout_s)
                except Exception as exc:
                    status = "failed"
                    error_message = str(exc)[:2000]

                client_wall = time.perf_counter() - client_start

                # Prefer server-reported elapsed time (excludes client HTTP
                # overhead on the first round-trip); fall back to client wall.
                server_ms = stats.get("elapsedTimeMillis")
                wall = (server_ms / 1000.0) if server_ms is not None else client_wall

                record = make_record(
                    engine="trino",
                    query_name=query_name,
                    run_type="warmup" if is_warmup else "measured",
                    run_number=run_number,
                    query_id=query_id,
                    status=status,
                    wall_time_seconds=wall,
                    peak_memory_bytes=_safe_int(stats, "peakUserMemoryBytes", "peakMemoryBytes"),
                    spill_bytes=_safe_int(stats, "spilledBytes"),
                    cpu_time_millis=_safe_int(stats, "cpuTimeMillis"),
                    result_hash=stable_hash(rows) if rows else "",
                    row_count=len(rows),
                    error_message=error_message,
                )
                append_jsonl(output_file, record)
                done += 1

                mem_mb = record["peak_memory_bytes"] // 1024 // 1024
                print(
                    f"[{done}/{total_queries}] trino {query_name} {run_label} "
                    f"→ {status}  wall={wall:.2f}s  "
                    f"mem={mem_mb}MB  "
                    f"spill={record['spill_bytes']//1024}KB"
                )

    except KeyboardInterrupt:
        print("\nInterrupted — partial results saved.")

    print(f"\nDone. Results: {output_file}")


if __name__ == "__main__":
    main()