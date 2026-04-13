# Trino Query Engine

This directory contains configuration for deploying Trino via the **Official Trino Helm Chart**.

## Overview
Trino is deployed as the distributed SQL query engine for our data platform. It connects to the Hive Metastore (for raw data) and Gravitino (for Iceberg REST data) to query MinIO/S3.

## Files
- `trino-values.yaml`: Contains the Helm overrides for Trino. It configures the JVM memory, limits Spot VM tolerations (`role=query`), and dynamically injects `hive` and `iceberg` catalogs.

## Usage
Use the `Makefile` to quickly manage the Trino installation.

```bash
# Install Trino
make install

# Check status
make status

# Upgrade (apply changes to trino-values.yaml)
make upgrade

# Uninstall
make uninstall
```
