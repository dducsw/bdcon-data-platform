from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

from common import ROOT, ensure_dir, load_env, write_csv


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_summary(records: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for record in records:
        if record["run_type"] != "measured":
            continue
        grouped[record["engine"]].append(record)

    summary = []
    for engine, rows in grouped.items():
        successes = [row for row in rows if row["status"] == "success"]
        # Handle both old and new field names
        total_runtime = sum(row.get("wall_time_seconds", row.get("query_time_seconds", 0)) for row in rows)
        success_runtime = sum(row.get("wall_time_seconds", row.get("query_time_seconds", 0)) for row in successes)
        
        runtimes = sorted(row.get("wall_time_seconds", row.get("query_time_seconds", 0)) for row in successes)
        median_value = statistics.median(runtimes) if runtimes else 0
        
        summary.append(
            {
                "engine": engine,
                "total_queries": len(rows),
                "success_count": len(successes),
                "failure_count": len(rows) - len(successes),
                "success_rate": round(len(successes) / len(rows), 4) if rows else 0,
                "total_runtime_seconds": round(total_runtime, 3),
                "median_query_time_seconds": round(median_value, 3),
                # Throughput is total successful queries / total time taken for them
                "avg_throughput_qps": round(len(successes) / success_runtime, 6) if success_runtime > 0 else 0,
                "max_peak_memory_bytes": max((row["peak_memory_bytes"] for row in successes), default=0),
                "total_spill_bytes": sum(row["spill_bytes"] for row in successes),
                "total_cpu_time_millis": sum(row["cpu_time_millis"] for row in successes),
            }
        )
    return summary


def build_validation(records: list[dict]) -> list[dict]:
    pair_map = defaultdict(dict)
    for record in records:
        if record["run_type"] != "measured" or record["status"] != "success":
            continue
        key = (record["query_name"], record["run_number"])
        pair_map[key][record["engine"]] = record

    rows = []
    for (query_name, run_number), engines in sorted(pair_map.items()):
        spark = engines.get("spark")
        trino = engines.get("trino")
        if not spark or not trino:
            continue
        rows.append(
            {
                "query_name": query_name,
                "run_number": run_number,
                "spark_hash": spark["result_hash"],
                "trino_hash": trino["result_hash"],
                "matches": spark["result_hash"] == trino["result_hash"],
            }
        )
    return rows


def main() -> None:
    env = load_env()
    results_root = ROOT / env["RESULTS_DIR"]
    raw_dir = results_root / "raw"
    merged_dir = results_root / "merged"
    reports_dir = results_root / "reports"
    ensure_dir(merged_dir)
    ensure_dir(reports_dir)

    records = load_jsonl(raw_dir / "spark_results.jsonl") + load_jsonl(raw_dir / "trino_results.jsonl")
    if not records:
        raise SystemExit("No raw benchmark results found. Run Spark and Trino benchmarks first.")

    fieldnames = [
        "engine",
        "query_name",
        "run_type",
        "run_number",
        "query_id",
        "status",
        "query_time_seconds",
        "throughput_qps",
        "peak_memory_bytes",
        "spill_bytes",
        "cpu_time_millis",
        "result_hash",
        "row_count",
        "error_message",
    ]
    write_csv(merged_dir / "benchmark_results.csv", records, fieldnames)

    summary = build_summary(records)
    write_csv(reports_dir / "summary.csv", summary, list(summary[0].keys()) if summary else [])

    validation = build_validation(records)
    write_csv(reports_dir / "validation.csv", validation, list(validation[0].keys()) if validation else [])

    # Detailed Per-Query Comparison
    query_stats = defaultdict(lambda: {"spark": None, "trino": None})
    for record in records:
        if record["run_type"] != "measured" or record["status"] != "success":
            continue
        # Average across runs for the table
        engine = record["engine"]
        qname = record["query_name"]
        t = record.get("wall_time_seconds", record.get("query_time_seconds", 0))
        if query_stats[qname][engine] is None:
            query_stats[qname][engine] = []
        query_stats[qname][engine].append(t)

    dataset_info = f"Dataset: {env.get('TRINO_CATALOG', 'iceberg')}.{env.get('TRINO_SCHEMA', 'tpcds')}"
    lines = [
        "# TPC-DS Benchmark Summary Report",
        "",
        f"- **Dataset**: `{dataset_info}`",
        f"- **Runs**: {env.get('WARMUP_RUNS')} warmup, {env.get('RUNS')} measured",
        "",
        "## Engine Performance Summary",
        "",
        "| Engine | Success Rate | Total Time | Median Time | Avg QPS | Max Peak Mem | Total Spill |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in summary:
        lines.append(
            f"| {row['engine']} | {row['success_rate']*100:.1f}% | {row['total_runtime_seconds']}s | {row['median_query_time_seconds']}s | {row['avg_throughput_qps']:.3f} | {row['max_peak_memory_bytes']/(1024*1024):.1f} MB | {row['total_spill_bytes']/(1024*1024):.1f} MB |"
        )

    lines.extend(["", "## Validation Result Summary", ""])
    matched = sum(1 for row in validation if row["matches"])
    total_val = len(validation)
    percent = (matched / total_val * 100) if total_val > 0 else 0
    lines.append(f"- **Total Result Matching**: {matched}/{total_val} ({percent:.1f}%)")

    if total_val > matched:
        lines.extend(["", "### Mismatched Queries (Sample)", "", "| Query | Run | Spark Hash | Trino Hash |", "|---|---|---|---|"])
        for v in [row for row in validation if not row["matches"]][:10]:
            lines.append(f"| {v['query_name']} | {v['run_number']} | `{v['spark_hash'][:8]}` | `{v['trino_hash'][:8]}` |")

    lines.extend(["", "## Per-Query Comparison (Average Time in Seconds)", "", "| Query | Trino (s) | Spark (s) | Ratio (S/T) |", "|---|---|---|---|"])
    for qname in sorted(query_stats.keys())[:20]: # Limit to top 20 for readability
        t_vals = query_stats[qname]["trino"]
        s_vals = query_stats[qname]["spark"]
        if t_vals and s_vals:
            t_avg = statistics.mean(t_vals)
            s_avg = statistics.mean(s_vals)
            ratio = s_avg / t_avg if t_avg > 0 else 0
            lines.append(f"| {qname} | {t_avg:.3f} | {s_avg:.3f} | {ratio:.1f}x |")

    (reports_dir / "summary_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {(reports_dir / 'summary_report.md')}")


if __name__ == "__main__":
    main()
