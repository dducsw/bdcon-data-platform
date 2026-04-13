# Apache Airflow Orchestration

This directory contains configuration for deploying Apache Airflow via the **Official Apache Airflow Helm Chart**.

## Overview
Airflow is the central orchestrator for data pipelines. It is configured to run on Kubernetes natively, using `CeleryExecutor` (or KubernetesExecutor if configured). It will trigger Spark jobs and Trino queries automatically.

## Files
- `airflow-values.yaml`: Helm overrides mapped from your custom 3.1.6 docker-compose file. Contains configuration for DAG persistence, CeleryExecutor, and custom environment variables.

## Usage
Use the `Makefile` to quickly manage Airflow.

```bash
# Install Airflow
make install

# Forward port manually (if not using Ingress)
make port-forward

# Uninstall
make uninstall
```
