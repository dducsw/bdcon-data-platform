from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from common import ensure_dir, load_env, write_csv


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
        total_runtime = sum(row["query_time_seconds"] for row in rows)
        median_runtime = sorted(row["query_time_seconds"] for row in successes)
        median_value = 0
        if median_runtime:
            median_value = median_runtime[len(median_runtime) // 2]
        summary.append(
            {
                "engine": engine,
                "total_queries": len(rows),
                "success_count": len(successes),
                "failure_count": len(rows) - len(successes),
                "success_rate": round(len(successes) / len(rows), 4) if rows else 0,
                "total_runtime_seconds": round(total_runtime, 3),
                "median_query_time_seconds": median_value,
                "avg_throughput_qps": round(sum(row["throughput_qps"] for row in successes) / len(successes), 6) if successes else 0,
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
        rows.append(
            {
                "query_name": query_name,
                "run_number": run_number,
                "spark_hash": spark["result_hash"] if spark else "",
                "trino_hash": trino["result_hash"] if trino else "",
                "matches": bool(spark and trino and spark["result_hash"] == trino["result_hash"]),
            }
        )
    return rows


def main() -> None:
    env = load_env()
    raw_dir = Path(env["RESULTS_DIR"]) / "raw"
    merged_dir = Path(env["RESULTS_DIR"]) / "merged"
    reports_dir = Path(env["RESULTS_DIR"]) / "reports"
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

    lines = [
        "# Benchmark Summary",
        "",
        "Dataset: TPC-DS SF5 materialized to Iceberg schema `catalog_iceberg.benchmark_tpcds`.",
        "",
        "## Engine Summary",
        "",
    ]
    for row in summary:
        lines.extend(
            [
                f"- {row['engine']}: success_rate={row['success_rate']}, total_runtime_seconds={row['total_runtime_seconds']}, median_query_time_seconds={row['median_query_time_seconds']}, avg_throughput_qps={row['avg_throughput_qps']}, max_peak_memory_bytes={row['max_peak_memory_bytes']}, total_spill_bytes={row['total_spill_bytes']}, total_cpu_time_millis={row['total_cpu_time_millis']}",
            ]
        )
    lines.extend(["", "## Validation", ""])
    matched = sum(1 for row in validation if row["matches"])
    lines.append(f"- matching query results: {matched}/{len(validation)}")

    (reports_dir / "summary_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {(reports_dir / 'summary_report.md')}")


if __name__ == "__main__":
    main()
