# Benchmark Harness

This folder contains the minimum benchmark harness to compare Spark and Trino on the same `TPC-DS SF5` dataset inside `docker-dev`.

## What it does

1. Uses Trino's `tpcds.sf5` catalog to materialize shared `TPC-DS SF5` tables into Iceberg schema `catalog_iceberg.benchmark_tpcds`.
2. Runs the same SQL query set on Spark and Trino.
3. Collects the six core metrics:
   - `query_time`
   - `throughput`
   - `peak_memory`
   - `spill_bytes`
   - `cpu_time`
   - `success_fail_rate`
4. Writes raw outputs, merged CSV, and a Markdown summary report.

## Run order

```powershell
make benchmark-prepare
make benchmark-spark
make benchmark-trino
make benchmark-report
```

Or run everything:

```powershell
make benchmark-all
```

## Output layout

- `results/raw/` raw per-query records for each engine
- `results/merged/benchmark_results.csv` merged benchmark rows
- `results/reports/summary_report.md` high-level summary

## Notes

- The starter suite uses six representative SQL queries under `queries/tpcds_sf5/`.
- You can replace `query_list.txt` with a larger TPC-DS query set later without changing the runners.
- Spark metrics are parsed from Spark event logs under `infrastructure/spark/logs/`.
- Trino metrics are collected from the Trino statement API.
