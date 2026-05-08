"""
common.py — shared utilities for the TPC-DS benchmark harness.

Key design decisions:
- wall_time_seconds is the canonical latency field for BOTH engines.
  Trino provides server-side elapsedTimeMillis; Spark uses perf_counter.
  Both are end-to-end query time as seen from the caller.
- stable_hash sorts rows before hashing so non-deterministic result ordering
  from either engine does not cause false validation mismatches.
- normalize_value rounds floats to 4 dp so minor floating-point differences
  between SparkSQL and Trino do not inflate the mismatch count.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Iterable, List

# Repository root — two levels above this file (benchmark/scripts/common.py)
ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = ROOT / "benchmark"


# ─── Configuration ────────────────────────────────────────────────────────────

def load_env() -> dict:
    """
    Load benchmark.env; environment variables override file values so that
    Kubernetes Job env-vars (TRINO_BASE_URL, RESULTS_DIR …) take precedence.
    """
    env_path = BENCHMARK_ROOT / "config" / "benchmark.env"
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    # Environment variables win over file values.
    for key in list(values):
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_query_list(env: dict) -> List[Path]:
    query_list = ROOT / env["QUERY_LIST"]
    base_dir = query_list.parent
    files: List[Path] = []
    for line in query_list.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        p = base_dir / name
        if not p.exists():
            raise FileNotFoundError(f"Query file not found: {p}")
        files.append(p)
    return files


# ─── Result normalisation & hashing ──────────────────────────────────────────

def normalize_value(val: object) -> str:
    """
    Deterministic string form of a cell value.
    - NULL / None → "NULL"
    - Numeric     → 4 decimal places (avoids float precision divergence)
    - String      → stripped
    """
    if val is None:
        return "NULL"
    
    # Try to parse as float for numeric normalization
    try:
        f_val = float(val)
        if math.isnan(f_val):
            return "NULL"
        if math.isinf(f_val):
            return "INF" if f_val > 0 else "-INF"
        # Round to 4 decimal places for stable comparison
        return "{:.4f}".format(round(f_val, 4))
    except (ValueError, TypeError):
        pass

    s = str(val).strip()
    if not s or s.upper() in ("NULL", "NONE"):
        return "NULL"
    return s


def stable_hash(rows: Iterable) -> str:
    """
    Order-independent MD5 of a result set.
    Rows are normalised then *sorted* so that non-deterministic ordering
    in Spark or Trino does not produce false hash mismatches.
    
    We attempt a 'smart' sort: numeric values are compared numerically
    to avoid lexicographical issues (e.g., "9" > "10").
    """
    def sort_key(row):
        # Convert each cell to a tuple (is_numeric, numeric_val, string_val)
        key = []
        for cell in row:
            try:
                f = float(cell)
                key.append((0, f, ""))
            except (ValueError, TypeError):
                key.append((1, 0.0, str(cell)))
        return key

    normalised = [[normalize_value(cell) for cell in row] for row in rows]
    try:
        # Try sorting using the smart key
        normalised.sort(key=sort_key)
    except Exception:
        # Fallback to JSON-based sort if schema is inconsistent
        normalised.sort(key=lambda r: json.dumps(r, sort_keys=True))
        
    payload = json.dumps(normalised, sort_keys=True, ensure_ascii=True)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


# ─── I/O helpers ─────────────────────────────────────────────────────────────

# Canonical field names written by BOTH benchmark scripts.
# wall_time_seconds  = end-to-end elapsed time (seconds, float) — THE latency metric.
# throughput_qps     = 1 / wall_time_seconds for successful queries.
# peak_memory_bytes  = engine-reported peak RSS / heap during the query.
# spill_bytes        = data spilled to disk (0 if none).
# cpu_time_millis    = CPU time consumed (best-effort; 0 if unavailable).
RESULT_FIELDS = [
    "engine",
    "query_name",
    "run_type",        # "warmup" | "measured"
    "run_number",      # 0 for warmups, 1..N for measured runs
    "query_id",
    "status",          # "success" | "failed"
    "wall_time_seconds",
    "engine_internal_time",
    "throughput_qps",
    "peak_memory_bytes",
    "spill_bytes",
    "cpu_time_millis",
    "result_hash",
    "row_count",
    "error_message",
]


def make_record(
    *,
    engine: str,
    query_name: str,
    run_type: str,
    run_number: int,
    query_id: str,
    status: str,
    wall_time_seconds: float,
    engine_internal_time: float = 0.0,
    peak_memory_bytes: int = 0,
    spill_bytes: int = 0,
    cpu_time_millis: int = 0,
    result_hash: str = "",
    row_count: int = 0,
    error_message: str = "",
) -> dict:
    """
    Build a canonical result record. Both run_spark_benchmark.py and
    run_trino_benchmark.py call this — guarantees identical schema.
    """
    safe_wall = max(wall_time_seconds, 1e-9)
    return {
        "engine": engine,
        "query_name": query_name,
        "run_type": run_type,
        "run_number": run_number,
        "query_id": query_id,
        "status": status,
        "wall_time_seconds": round(wall_time_seconds, 3),
        "engine_internal_time": round(engine_internal_time, 3),
        "throughput_qps": round(1.0 / safe_wall, 6) if status == "success" else 0.0,
        "peak_memory_bytes": int(peak_memory_bytes),
        "spill_bytes": int(spill_bytes),
        "cpu_time_millis": int(cpu_time_millis),
        "result_hash": result_hash,
        "row_count": int(row_count),
        "error_message": error_message,
    }


def append_jsonl(path: Path, record: dict) -> None:
    """Append a single record to a JSONL file (incremental, crash-safe)."""
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=True) + "\n")


def write_jsonl(path: Path, records: List[dict]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=True) + "\n")


def load_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_results_df() -> "pd.DataFrame":
    """
    Utility for notebooks: loads both engines' raw results into a single pandas DataFrame.
    Globs for *_results.jsonl files in the raw directory.
    """
    import pandas as pd
    env = load_env()
    results_dir_val = env.get("RESULTS_DIR", "benchmark/results")
    results_root = ROOT / results_dir_val
    raw_dir = results_root / "raw"
    
    print(f"DEBUG: Searching for results in: {raw_dir.resolve()}")
    
    records = []
    if raw_dir.exists():
        files = list(raw_dir.glob("*_results*.jsonl"))
        print(f"DEBUG: Found {len(files)} files: {[f.name for f in files]}")
        for path in files:
            # Try to infer engine from filename if not in record
            engine_hint = "spark" if "spark" in path.name.lower() else "trino" if "trino" in path.name.lower() else "unknown"
            file_records = load_jsonl(path)
            for r in file_records:
                if "engine" not in r:
                    r["engine"] = engine_hint
            records.extend(file_records)
    
    df = pd.DataFrame(records)
    if not df.empty:
        # Ensure numeric types
        for col in ["wall_time_seconds", "engine_internal_time", "peak_memory_bytes", "throughput_qps"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Canonical latency: use internal time if available, else wall time
        df["latency_s"] = df.apply(
            lambda r: r["engine_internal_time"] if r.get("engine_internal_time", 0) > 0 else r.get("wall_time_seconds", 0),
            axis=1
        )
    return df