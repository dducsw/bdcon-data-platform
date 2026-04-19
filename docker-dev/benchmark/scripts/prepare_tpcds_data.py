from __future__ import annotations

import json
import urllib.error
import urllib.request

from common import load_env


TPCDS_TABLES = [
    "call_center",
    "catalog_page",
    "catalog_returns",
    "catalog_sales",
    "customer",
    "customer_address",
    "customer_demographics",
    "date_dim",
    "household_demographics",
    "income_band",
    "inventory",
    "item",
    "promotion",
    "reason",
    "ship_mode",
    "store",
    "store_returns",
    "store_sales",
    "time_dim",
    "warehouse",
    "web_page",
    "web_returns",
    "web_sales",
    "web_site",
]


def execute_statement(sql: str, env: dict) -> None:
    request = urllib.request.Request(
        url=f"{env['TRINO_BASE_URL']}/v1/statement",
        data=sql.encode("utf-8"),
        headers={
            "X-Trino-User": env["TRINO_USER"],
            "X-Trino-Catalog": env["TRINO_CATALOG"],
            "X-Trino-Schema": env["TRINO_SCHEMA"],
            "X-Trino-Source": f"{env['TRINO_SOURCE']}-prepare",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))

    next_uri = payload.get("nextUri")
    while next_uri:
        with urllib.request.urlopen(next_uri, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("error"):
            message = payload["error"].get("message", "Unknown Trino error")
            raise RuntimeError(message)
        next_uri = payload.get("nextUri")


def main() -> None:
    env = load_env()
    create_schema = (
        f"CREATE SCHEMA IF NOT EXISTS {env['TRINO_CATALOG']}.{env['TRINO_SCHEMA']}"
    )
    execute_statement(create_schema, env)

    for table in TPCDS_TABLES:
        drop_sql = f"DROP TABLE IF EXISTS {env['TRINO_CATALOG']}.{env['TRINO_SCHEMA']}.{table}"
        create_sql = (
            f"CREATE TABLE {env['TRINO_CATALOG']}.{env['TRINO_SCHEMA']}.{table} AS "
            f"SELECT * FROM {env['TPCDS_SOURCE_CATALOG']}.{env['TPCDS_SOURCE_SCHEMA']}.{table}"
        )
        print(f"Materializing {table}...")
        execute_statement(drop_sql, env)
        try:
            execute_statement(create_sql, env)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Failed to create table {table}: {exc.read().decode('utf-8')}") from exc

    print(
        f"TPC-DS dataset from {env['TPCDS_SOURCE_CATALOG']}.{env['TPCDS_SOURCE_SCHEMA']} "
        f"is ready in Iceberg schema {env['TRINO_CATALOG']}.{env['TRINO_SCHEMA']}."
    )


if __name__ == "__main__":
    main()
