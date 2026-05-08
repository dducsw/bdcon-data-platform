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
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from kubernetes import client, config

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


# ─── Low-level HTTP helpers ───────────────────────────────────────────────────

_DEFAULT_TIMEOUT_S = 60   # per individual HTTP request (not query timeout)


def _post(url: str, body: str, headers: dict, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url=url,
                data=body.encode("utf-8"),
                headers={"Content-Type": "text/plain; charset=utf-8", **headers},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, ConnectionError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 ** attempt)
    return {}


def _get(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=_DEFAULT_TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, ConnectionError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 ** attempt)
    return {}


def _delete(url: str) -> None:
    req = urllib.request.Request(url=url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception:
        pass   # best-effort cancellation


# --- K8s Cluster-wide Memory Sampler ------------------------------------------

class K8sClusterMemorySampler(threading.Thread):
    """
    Polls Kubernetes Metrics API to get the instantaneous sum of memory 
    usage across all pods matching a label selector.
    """
    def __init__(self, namespace: str, label_selector: str, interval: float = 1.0):
        super().__init__()
        self.namespace = namespace
        self.label_selector = label_selector
        self.interval = interval
        self.stop_event = threading.Event()
        self.peak_memory_bytes = 0
        
        try:
            config.load_incluster_config()
        except:
            try:
                config.load_kube_config()
            except:
                self.api = None
                return
        self.api = client.CustomObjectsApi()

    def _parse_mem(self, mem_str: str) -> int:
        if not mem_str: return 0
        if mem_str.endswith("Ki"): return int(mem_str[:-2]) * 1024
        if mem_str.endswith("Mi"): return int(mem_str[:-2]) * 1024 * 1024
        if mem_str.endswith("Gi"): return int(mem_str[:-2]) * 1024 * 1024 * 1024
        try:
            return int(mem_str.rstrip("nukmGTP")) 
        except:
            return 0

    def run(self):
        if not self.api: return
        while not self.stop_event.is_set():
            try:
                res = self.api.list_namespaced_custom_object(
                    group="metrics.k8s.io",
                    version="v1beta1",
                    namespace=self.namespace,
                    plural="pods",
                    label_selector=self.label_selector
                )
                
                current_total = 0
                for item in res.get("items", []):
                    for container in item.get("containers", []):
                        usage = container.get("usage", {}).get("memory", "0")
                        current_total += self._parse_mem(usage)
                
                if current_total > self.peak_memory_bytes:
                    self.peak_memory_bytes = current_total
            except:
                pass
            time.sleep(self.interval)

    def stop(self) -> int:
        self.stop_event.set()
        if self.is_alive():
            self.join(timeout=2.0)
        return self.peak_memory_bytes


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
    
    # Crash-resume: Load existing results to skip completed queries
    existing_results = load_jsonl(output_file)
    completed_queries = {r["query_name"] for r in existing_results if r["run_type"] == "measured"}
    if completed_queries:
        print(f"Found {len(completed_queries)} queries already completed in {output_file.name}. Resuming...")
    else:
        # Only truncate if we are starting fresh (optional, but safer to append by default)
        if not output_file.exists():
            output_file.write_text("", encoding="utf-8")


    # Verify worker count
    try:
        # Use system.runtime.nodes as /v1/node may return 404 in some Trino versions/configs
        sql_check = "SELECT count(*) FROM system.runtime.nodes WHERE coordinator = false AND state = 'active'"
        initial = submit_query(sql_check, env, "worker-check")
        rows, _, _ = poll_until_done(initial, 30)
        workers_count = rows[0][0] if rows else 0
        
        print(f"Trino cluster: {workers_count} active workers found.")
        if workers_count != 2:
            print(f"WARNING: Expected 2 workers, but found {workers_count}. Results may be inconsistent.")
    except Exception as e:
        print(f"Warning: Could not verify worker count: {e}")

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
                v_start = time.perf_counter()
                
                # Start RSS sampler for Trino workers
                ns = env.get("K8S_NAMESPACE", "data-platform")
                selector = "app.kubernetes.io/component=worker"
                v_sampler = K8sClusterMemorySampler(ns, selector)
                v_sampler.start()
                
                v_query_resp = submit_query(sql_full, env, f"val-{query_name}")
                v_rows, v_stats, v_qid = poll_until_done(v_query_resp, timeout_s)
                v_wall = time.perf_counter() - v_start
                v_rss_peak = v_sampler.stop()
                
                v_hash = stable_hash(v_rows) if v_rows else ""
                
                v_record = make_record(
                    engine="trino",
                    query_name=query_name,
                    run_type="validation",
                    run_number=1,
                    query_id=v_qid,
                    status="success" if v_rows else "failed",
                    wall_time_seconds=v_wall,
                    engine_internal_time=(v_stats.get("elapsedTimeMillis", 0) / 1000.0),
                    peak_memory_bytes=max(v_rss_peak, _safe_int(v_stats, "peakTotalMemoryBytes", "peakMemoryBytes")),
                    spill_bytes=_safe_int(v_stats, "spilledBytes"),
                    cpu_time_millis=_safe_int(v_stats, "cpuTimeMillis"),
                    result_hash=v_hash,
                    row_count=len(v_rows),
                )
                append_jsonl(output_file, v_record)
                print(f"    Validation: hash={v_hash[:8]}, rows={len(v_rows)}")

                # Phase 2: Measured Runs
            sql_perf = sql_full
            if env.get("WRAP_COUNT", "false").lower() == "true":
                sql_perf = f"SELECT COUNT(*) FROM (\n{sql_full}\n)"

            for run_index in range(1, warmups + runs + 1):
                is_warmup = run_index <= warmups
                run_number = 0 if is_warmup else run_index - warmups
                run_label = f"warmup-{run_index}" if is_warmup else f"run-{run_number}"
                source = f"tpcds-benchmark-{query_name}-{run_label}"

                # Start RSS sampler for Trino workers
                ns = env.get("K8S_NAMESPACE", "data-platform")
                selector = "app.kubernetes.io/component=worker"
                sampler = K8sClusterMemorySampler(ns, selector)
                sampler.start()

                client_start = time.perf_counter()
                status = "success"
                error_message = ""
                rows: list = []
                stats: dict = {}
                query_id = "N/A"

                try:
                    query_resp = submit_query(sql_perf, env, source)
                    rows, stats, query_id = poll_until_done(query_resp, timeout_s)
                except Exception as exc:
                    status = "failed"
                    error_message = str(exc)[:2000]

                client_wall = time.perf_counter() - client_start
                peak_rss_bytes = sampler.stop()

                # Canonical wall_time is client-side perf_counter (E2E).
                # Store server-side reported time in engine_internal_time for debugging.
                server_ms = stats.get("elapsedTimeMillis")
                server_wall = (server_ms / 1000.0) if server_ms is not None else 0.0

                # Priority: Sampler RSS > peakTotalMemoryBytes > peakMemoryBytes
                reported_peak = _safe_int(stats, "peakTotalMemoryBytes", "peakMemoryBytes")
                final_peak = max(peak_rss_bytes, reported_peak)

                record = make_record(
                    engine="trino",
                    query_name=query_name,
                    run_type="warmup" if is_warmup else "measured",
                    run_number=run_number,
                    query_id=query_id,
                    status=status,
                    wall_time_seconds=client_wall,
                    engine_internal_time=server_wall,
                    peak_memory_bytes=final_peak,
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
                    f"→ {status}  wall={client_wall:.2f}s  "
                    f"mem={mem_mb}MB  "
                    f"spill={record['spill_bytes']//1024}KB"
                    + (f"\n  ERROR: {record['error_message']}" if status != "success" else "")
                )

    except KeyboardInterrupt:
        print("\nInterrupted — partial results saved.")

    print(f"\nDone. Results: {output_file}")


if __name__ == "__main__":
    main()