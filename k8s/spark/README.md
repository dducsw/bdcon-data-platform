# Spark Compute Layer

This directory contains resources for running Apache Spark jobs natively on Kubernetes using the **Spark on K8s Operator**.

## Overview
Unlike a standalone Spark cluster (Master/Worker pods always running), the Spark Operator dynamically provisions Executor pods purely when jobs are submitted and tears them down when completed. This heavily optimizes Spot VM usage.

## Files
- `configmap.yaml`: Core Spark configurations (`spark-defaults.conf`, `core-site.xml` for MinIO, `metrics.properties`). Connects Spark to Gravitino and Hive Metastore catalogs.
- `spark-rbac.yaml`: ServiceAccount and RBAC roles allowing Spark driver pods to request executor pods from the K8s API.
- `spark-pi-example.yaml`: An example `SparkApplication` custom resource executing Spark Pi.

## Usage
Use the `Makefile` to quickly manage jobs.

```bash
# Setup RBAC limits and ConfigMaps
make setup

# Submit the Spark Pi job
make submit-job

# Watch job logs
make logs

# Clean up the job
make delete-job
```
