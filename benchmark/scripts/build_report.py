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


def fmt_bytes(b: int) -> str:
    """Format bytes into human-readable string."""
    if b <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


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


def build_query_details(records: list[dict]) -> dict:
    """Build per-query stats with avg, stddev, min, max for each engine."""
    query_stats = defaultdict(lambda: {"spark": [], "trino": []})
    query_cpu = defaultdict(lambda: {"spark": [], "trino": []})
    query_mem = defaultdict(lambda: {"spark": [], "trino": []})

    for record in records:
        if record["run_type"] != "measured" or record["status"] != "success":
            continue
        engine = record["engine"]
        qname = record["query_name"]
        t = record.get("wall_time_seconds", record.get("query_time_seconds", 0))
        query_stats[qname][engine].append(t)
        query_cpu[qname][engine].append(record.get("cpu_time_millis", 0))
        query_mem[qname][engine].append(record.get("peak_memory_bytes", 0))

    return query_stats, query_cpu, query_mem


def build_cold_start_analysis(records: list[dict]) -> dict:
    """Analyze warmup vs first measured run vs subsequent runs."""
    analysis = defaultdict(lambda: {"warmup": [], "run_1": [], "run_2_plus": []})
    for record in records:
        if record["status"] != "success":
            continue
        key = (record["engine"], record["query_name"])
        t = record.get("wall_time_seconds", record.get("query_time_seconds", 0))
        if record["run_type"] == "warmup":
            analysis[key]["warmup"].append(t)
        elif record["run_number"] == 1:
            analysis[key]["run_1"].append(t)
        else:
            analysis[key]["run_2_plus"].append(t)
    return analysis


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
        "server_time_seconds",
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

    # Build per-query details
    query_stats, query_cpu, query_mem = build_query_details(records)

    # ===== Generate Markdown Report =====
    dataset_info = f"Dataset: {env.get('TRINO_CATALOG', 'iceberg')}.{env.get('TRINO_SCHEMA', 'tpcds')}"
    lines = [
        "# TPC-DS Benchmark Summary Report",
        "",
        f"- **Dataset**: `{dataset_info}`",
        f"- **Runs**: {env.get('WARMUP_RUNS')} warmup, {env.get('RUNS')} measured",
        "",
    ]

    # --- Engine Performance Summary ---
    lines.extend([
        "## Engine Performance Summary",
        "",
        "| Engine | Success Rate | Total Time | Median Time | Avg QPS | Max Peak Mem | Total CPU Time | Total Spill |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for row in summary:
        cpu_s = row['total_cpu_time_millis'] / 1000
        lines.append(
            f"| {row['engine']} "
            f"| {row['success_rate']*100:.1f}% "
            f"| {row['total_runtime_seconds']}s "
            f"| {row['median_query_time_seconds']}s "
            f"| {row['avg_throughput_qps']:.3f} "
            f"| {fmt_bytes(row['max_peak_memory_bytes'])} "
            f"| {cpu_s:.1f}s "
            f"| {fmt_bytes(row['total_spill_bytes'])} |"
        )

    # --- Validation ---
    lines.extend(["", "## Validation Result Summary", ""])
    matched = sum(1 for row in validation if row["matches"])
    total_val = len(validation)
    percent = (matched / total_val * 100) if total_val > 0 else 0
    lines.append(f"- **Total Result Matching**: {matched}/{total_val} ({percent:.1f}%)")

    if total_val > matched:
        lines.extend(["", "### Mismatched Queries (Sample)", "", "| Query | Run | Spark Hash | Trino Hash |", "|---|---|---|---|"])
        for v in [row for row in validation if not row["matches"]][:10]:
            lines.append(f"| {v['query_name']} | {v['run_number']} | `{v['spark_hash'][:8]}` | `{v['trino_hash'][:8]}` |")

    # --- Per-Query Comparison (enhanced) ---
    lines.extend([
        "",
        "## Per-Query Comparison",
        "",
        "| Query | Trino Avg (s) | Spark Avg (s) | Ratio (S/T) | Winner | Trino StdDev | Spark StdDev | Trino Peak Mem |",
        "|---|---|---|---|---|---|---|---|",
    ])

    trino_wins = 0
    spark_wins = 0

    for qname in sorted(query_stats.keys()):
        t_vals = query_stats[qname]["trino"]
        s_vals = query_stats[qname]["spark"]
        if t_vals and s_vals:
            t_avg = statistics.mean(t_vals)
            s_avg = statistics.mean(s_vals)
            ratio = s_avg / t_avg if t_avg > 0 else 0
            t_std = statistics.stdev(t_vals) if len(t_vals) > 1 else 0
            s_std = statistics.stdev(s_vals) if len(s_vals) > 1 else 0
            t_mem = max(query_mem[qname]["trino"]) if query_mem[qname]["trino"] else 0

            if ratio >= 1.1:
                winner = "🟢 Trino"
                trino_wins += 1
            elif ratio <= 0.9:
                winner = "🔴 Spark"
                spark_wins += 1
            else:
                winner = "⚪ Tie"

            lines.append(
                f"| {qname} "
                f"| {t_avg:.3f} "
                f"| {s_avg:.3f} "
                f"| {ratio:.1f}x "
                f"| {winner} "
                f"| {t_std:.3f} "
                f"| {s_std:.3f} "
                f"| {fmt_bytes(t_mem)} |"
            )

    total_queries = trino_wins + spark_wins + (len(query_stats) - trino_wins - spark_wins)
    lines.extend([
        "",
        f"**Score: Trino {trino_wins} — Spark {spark_wins} — Tie {total_queries - trino_wins - spark_wins}** "
        f"(out of {total_queries} queries)",
    ])

    # --- Cold-Start Analysis ---
    cold_analysis = build_cold_start_analysis(records)
    has_warmup = any(d["warmup"] for d in cold_analysis.values())
    if has_warmup:
        lines.extend([
            "",
            "## Cold-Start Analysis",
            "",
            "| Engine | Query | Warmup (s) | Run 1 (s) | Run 2+ Avg (s) | Warmup Overhead |",
            "|---|---|---|---|---|---|",
        ])
        for (engine, qname), data in sorted(cold_analysis.items()):
            warmup_avg = statistics.mean(data["warmup"]) if data["warmup"] else None
            run1_avg = statistics.mean(data["run_1"]) if data["run_1"] else None
            run2_avg = statistics.mean(data["run_2_plus"]) if data["run_2_plus"] else None

            if warmup_avg is not None and run2_avg is not None and run2_avg > 0:
                overhead = f"{warmup_avg / run2_avg:.1f}x"
            elif warmup_avg is not None and run1_avg is not None and run1_avg > 0:
                overhead = f"{warmup_avg / run1_avg:.1f}x"
            else:
                overhead = "N/A"

            w_str = f"{warmup_avg:.2f}" if warmup_avg is not None else "—"
            r1_str = f"{run1_avg:.2f}" if run1_avg is not None else "—"
            r2_str = f"{run2_avg:.2f}" if run2_avg is not None else "—"
            lines.append(f"| {engine} | {qname} | {w_str} | {r1_str} | {r2_str} | {overhead} |")

    # --- CPU Efficiency (Trino only) ---
    trino_measured = [r for r in records if r["engine"] == "trino" and r["run_type"] == "measured" and r["status"] == "success"]
    if trino_measured:
        lines.extend([
            "",
            "## Trino CPU Efficiency",
            "",
            "| Query | Wall Time (s) | CPU Time (s) | Parallelism | Peak Memory |",
            "|---|---|---|---|---|",
        ])
        trino_by_q = defaultdict(list)
        for r in trino_measured:
            trino_by_q[r["query_name"]].append(r)

        for qname in sorted(trino_by_q.keys()):
            recs = trino_by_q[qname]
            wall_avg = statistics.mean([r["query_time_seconds"] for r in recs])
            cpu_avg = statistics.mean([r["cpu_time_millis"] for r in recs]) / 1000
            parallelism = cpu_avg / wall_avg if wall_avg > 0 else 0
            peak_mem = max(r["peak_memory_bytes"] for r in recs)
            lines.append(
                f"| {qname} "
                f"| {wall_avg:.2f} "
                f"| {cpu_avg:.1f} "
                f"| {parallelism:.1f}x "
                f"| {fmt_bytes(peak_mem)} |"
            )

    # --- Architecture Notes ---
    lines.extend([
        "",
        "## ⚠️ Architecture Notes",
        "",
        "| Factor | Spark | Trino |",
        "|---|---|---|",
        "| **Mode** | `local[4]` (single JVM, no network) | 1 Coordinator + 2 Workers (distributed) |",
        "| **Network Overhead** | None (in-process) | Coordinator ↔ Worker ↔ MinIO |",
        "| **Node Type** | Standard | Workers on Spot Nodes |",
        "",
        "> **Note**: Spark runs in local[4] mode which eliminates all network and serialization",
        "> overhead. This gives Spark a structural advantage that is unrelated to query engine",
        "> performance. Results should be interpreted with this architectural difference in mind.",
    ])

    (reports_dir / "summary_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {(reports_dir / 'summary_report.md')}")


if __name__ == "__main__":
    main()
