"""
build_report.py
===============
Merges Spark and Trino JSONL result files and produces:
  - merged/benchmark_results.csv   — all raw records, unified schema
  - reports/summary.csv            — per-engine aggregate metrics
  - reports/validation.csv         — per-query hash comparison
  - reports/summary_report.md      — human-readable markdown report
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

from common import RESULT_FIELDS, ROOT, ensure_dir, load_env, load_jsonl, write_csv


# ─── Summary ──────────────────────────────────────────────────────────────────

def build_summary(records: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r["run_type"] == "measured":
            grouped[r["engine"]].append(r)

    summary = []
    for engine, rows in grouped.items():
        successes = [r for r in rows if r["status"] == "success"]
        failures  = [r for r in rows if r["status"] != "success"]

        times = [r["wall_time_seconds"] for r in successes]
        total_time = sum(r["wall_time_seconds"] for r in rows)
        success_time = sum(r["wall_time_seconds"] for r in successes)

        summary.append({
            "engine":                     engine,
            "total_queries":              len(rows),
            "success_count":              len(successes),
            "failure_count":              len(failures),
            "success_rate":               round(len(successes) / len(rows), 4) if rows else 0,
            "total_wall_time_seconds":    round(total_time, 3),
            "median_wall_time_seconds":   round(statistics.median(times), 3) if times else 0,
            "p90_wall_time_seconds":      round(sorted(times)[int(len(times) * 0.9)], 3) if times else 0,
            "avg_throughput_qps":         round(len(successes) / success_time, 6) if success_time > 0 else 0,
            "max_peak_memory_bytes":      max((r["peak_memory_bytes"] for r in successes), default=0),
            "total_spill_bytes":          sum(r["spill_bytes"] for r in successes),
            "total_cpu_time_millis":      sum(r["cpu_time_millis"] for r in successes),
        })
    return summary


# ─── Validation ───────────────────────────────────────────────────────────────

def build_validation(records: list[dict]) -> list[dict]:
    # Bucket by (query_name, run_number) → {engine: record}
    buckets: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in records:
        if r["run_type"] == "measured" and r["status"] == "success" and r["result_hash"]:
            buckets[(r["query_name"], r["run_number"])][r["engine"]] = r

    rows = []
    for (query_name, run_number), engines in sorted(buckets.items()):
        spark = engines.get("spark")
        trino = engines.get("trino")
        if not spark or not trino:
            continue
        rows.append({
            "query_name":  query_name,
            "run_number":  run_number,
            "spark_hash":  spark["result_hash"],
            "trino_hash":  trino["result_hash"],
            "spark_rows":  spark["row_count"],
            "trino_rows":  trino["row_count"],
            "matches":     spark["result_hash"] == trino["result_hash"],
        })
    return rows


# ─── Per-query comparison ─────────────────────────────────────────────────────

def build_per_query(records: list[dict]) -> list[dict]:
    """Average wall_time across measured runs for each (engine, query)."""
    buckets: dict[tuple, list[float]] = defaultdict(list)
    for r in records:
        if r["run_type"] == "measured" and r["status"] == "success":
            buckets[(r["query_name"], r["engine"])].append(r["wall_time_seconds"])

    query_names = sorted({k[0] for k in buckets})
    rows = []
    for q in query_names:
        t_times = buckets.get((q, "trino"), [])
        s_times = buckets.get((q, "spark"), [])
        if not t_times and not s_times:
            continue
        t_avg = statistics.mean(t_times) if t_times else None
        s_avg = statistics.mean(s_times) if s_times else None
        ratio = (s_avg / t_avg) if (t_avg and s_avg) else None
        rows.append({
            "query_name":         q,
            "trino_avg_wall_s":   round(t_avg, 3) if t_avg is not None else "",
            "spark_avg_wall_s":   round(s_avg, 3) if s_avg is not None else "",
            "spark_trino_ratio":  round(ratio, 2) if ratio is not None else "",
            "faster_engine":      ("trino" if (ratio or 0) > 1 else "spark") if ratio else "",
        })
    return rows


# ─── Markdown report ──────────────────────────────────────────────────────────

def build_markdown(env: dict, summary: list[dict], validation: list[dict], per_query: list[dict]) -> str:
    lines = [
        "# TPC-DS Benchmark Report: Trino vs Apache Spark",
        "",
        "## Configuration",
        "",
        f"- **Dataset**: `{env.get('TRINO_CATALOG', 'iceberg')}.{env.get('TRINO_SCHEMA', 'tpcds')}`",
        f"- **Warmup runs**: {env.get('WARMUP_RUNS', 1)}  |  **Measured runs**: {env.get('RUNS', 3)}",
        f"- **Resource budget**: 4 vCPU / 8 Gi per engine (Spark: local[4]; Trino: 1 coordinator + 1 worker)",
        f"- **Timeout**: {env.get('QUERY_TIMEOUT_SECONDS', 1800)}s per query",
        "",
        "## Engine performance summary",
        "",
        "| Engine | Queries | Success | Fail | Success % | Total time | Median | P90 | Avg QPS | Max mem | Spill |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in summary:
        max_mem_mb = r["max_peak_memory_bytes"] / 1024 / 1024
        spill_mb   = r["total_spill_bytes"] / 1024 / 1024
        lines.append(
            f"| **{r['engine']}** "
            f"| {r['total_queries']} "
            f"| {r['success_count']} "
            f"| {r['failure_count']} "
            f"| {r['success_rate']*100:.1f}% "
            f"| {r['total_wall_time_seconds']}s "
            f"| {r['median_wall_time_seconds']}s "
            f"| {r['p90_wall_time_seconds']}s "
            f"| {r['avg_throughput_qps']:.4f} "
            f"| {max_mem_mb:.0f} MB "
            f"| {spill_mb:.1f} MB |"
        )

    # Speed-up headline
    t_row = next((r for r in summary if r["engine"] == "trino"), None)
    s_row = next((r for r in summary if r["engine"] == "spark"), None)
    if t_row and s_row and t_row["median_wall_time_seconds"] > 0:
        speedup = s_row["median_wall_time_seconds"] / t_row["median_wall_time_seconds"]
        lines += [
            "",
            f"> **Trino median query time is {speedup:.1f}× {'faster' if speedup > 1 else 'slower'} than Spark** "
            f"({t_row['median_wall_time_seconds']}s vs {s_row['median_wall_time_seconds']}s).",
        ]

    # Validation
    matched = sum(1 for r in validation if r["matches"])
    total_val = len(validation)
    pct = matched / total_val * 100 if total_val else 0
    lines += [
        "",
        "## Result validation",
        "",
        f"- Comparable query runs: **{total_val}**",
        f"- Hash matches: **{matched} / {total_val}** ({pct:.1f}%)",
        "",
        "Hash mismatches are expected for queries without an explicit `ORDER BY`:",
        "Spark and Trino may return rows in different orders. "
        "The harness sorts rows before hashing, so ordering differences are eliminated.",
        "Remaining mismatches indicate genuine numeric or NULL-handling divergence.",
    ]
    if total_val > matched:
        lines += ["", "### Mismatched queries (first 10)", "", "| Query | Run | Spark rows | Trino rows | Spark hash | Trino hash |", "|---|---|---|---|---|---|"]
        for v in [r for r in validation if not r["matches"]][:10]:
            lines.append(
                f"| {v['query_name']} | {v['run_number']} "
                f"| {v['spark_rows']} | {v['trino_rows']} "
                f"| `{v['spark_hash'][:8]}` | `{v['trino_hash'][:8]}` |"
            )

    # Per-query table (top 30 by Trino time, slowest first)
    sortable = [r for r in per_query if r["trino_avg_wall_s"] != ""]
    top = sorted(sortable, key=lambda r: float(r["trino_avg_wall_s"]), reverse=True)[:30]
    if top:
        lines += [
            "",
            "## Per-query comparison (avg wall time, slowest Trino queries first)",
            "",
            "| Query | Trino (s) | Spark (s) | Spark/Trino ratio | Faster |",
            "|---|---|---|---|---|",
        ]
        for r in top:
            lines.append(
                f"| {r['query_name']} "
                f"| {r['trino_avg_wall_s']} "
                f"| {r['spark_avg_wall_s'] or '—'} "
                f"| {r['spark_trino_ratio'] or '—'} "
                f"| {r['faster_engine'] or '—'} |"
            )

    return "\n".join(lines) + "\n"


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    env = load_env()
    results_root = Path(env.get("RESULTS_DIR", str(ROOT / "benchmark" / "results")))
    raw_dir     = results_root / "raw"
    merged_dir  = results_root / "merged"
    reports_dir = results_root / "reports"
    ensure_dir(merged_dir)
    ensure_dir(reports_dir)

    records = load_jsonl(raw_dir / "spark_results.jsonl") + \
              load_jsonl(raw_dir / "trino_results.jsonl")
    if not records:
        raise SystemExit("No raw results found. Run both benchmarks first.")

    print(f"Loaded {len(records)} records.")

    write_csv(merged_dir / "benchmark_results.csv", records, RESULT_FIELDS)

    summary = build_summary(records)
    if summary:
        write_csv(reports_dir / "summary.csv", summary, list(summary[0].keys()))

    validation = build_validation(records)
    if validation:
        write_csv(reports_dir / "validation.csv", validation, list(validation[0].keys()))

    per_query = build_per_query(records)
    if per_query:
        write_csv(reports_dir / "per_query.csv", per_query, list(per_query[0].keys()))

    md = build_markdown(env, summary, validation, per_query)
    (reports_dir / "summary_report.md").write_text(md, encoding="utf-8")

    print(f"Reports written to {reports_dir}/")
    for f in sorted(reports_dir.iterdir()):
        print(f"  {f.name}  ({f.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()