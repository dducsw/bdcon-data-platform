import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable, List


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = ROOT / "benchmark"


def load_env() -> dict:
    env_path = BENCHMARK_ROOT / "config" / "benchmark.env"
    values = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_query_list(env: dict) -> List[Path]:
    query_list = ROOT / env["QUERY_LIST"]
    base_dir = query_list.parent
    files = []
    for line in query_list.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        files.append(base_dir / name)
    return files


def normalize_value(val) -> str:
    """
    Standardizes a value for consistent hashing across different engines.
    - Numbers are rounded to 4 decimal places.
    - NULLs and 'None' are converted to 'NULL'.
    - Strings are trimmed.
    """
    if val is None:
        return "NULL"
    
    s_val = str(val).strip()
    if s_val.upper() in ("NULL", "NONE", ""):
        return "NULL"

    # Try to handle numeric values (even if they come in as strings from Spark)
    try:
        # Check if it's a number
        f_val = float(s_val)
        # Round and format as a fixed-point string to avoid scientific notation or precision diffs
        return "{:.4f}".format(round(f_val, 4))
    except (ValueError, TypeError):
        # Not a number, return as-is
        return s_val


def stable_hash(rows: Iterable) -> str:
    """
    Computes a deterministic hash for a set of result rows.
    Normalizes types and formatting to ensure consistency across engines.
    """
    normalized_rows = []
    for row in rows:
        normalized_rows.append([normalize_value(cell) for cell in row])
    
    # Sort rows to handle non-deterministic ordering
    try:
        normalized_rows.sort()
    except TypeError:
        # Fallback for complex structures if any
        normalized_rows.sort(key=lambda x: json.dumps(x, sort_keys=True))
    
    payload = json.dumps(normalized_rows, sort_keys=True)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def write_jsonl(path: Path, records: List[dict]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
