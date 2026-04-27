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


def stable_hash(rows: Iterable) -> str:
    # Sort rows to handle non-deterministic ordering from distributed engines.
    # We use json.dumps as a sort key to safely handle mixed types or nested structures.
    rows_list = list(rows)
    try:
        rows_list.sort()
    except TypeError:
        # Fallback for mixed types that can't be directly compared
        rows_list.sort(key=lambda x: json.dumps(x, default=str))
    
    payload = json.dumps(rows_list, sort_keys=True, default=str)
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
