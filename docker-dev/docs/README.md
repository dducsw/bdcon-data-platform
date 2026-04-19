# Data Lakehouse Setup Guide

This project provides a local, dockerized Data Lakehouse environment using Apache Spark, Gravitino, MinIO, and PostgreSQL.

## Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop) and Docker Compose must be installed on your machine.

## Getting Started

Follow these steps to initialize the environment and run a demo data pipeline.

### 1. Start the Environment

Start all the required services in the background using Docker Compose:

```bash
docker compose up -d
```

This will spin up several containers, including `spark-master`, `spark-worker-1`, `spark-worker-2`, `gravitino`, `minio`, `postgres`, and monitoring tools. Wait a few moments for all services, especially Gravitino and PostgreSQL, to be fully operational.

### 2. Initialize the Metalake and Catalog

Initialize the Gravitino Metalake and the Iceberg catalog to establish the connection with MinIO (acting as our S3-compatible storage):

```bash
docker exec gravitino bash /tmp/common/init_metalake_catalog.sh
```

### 3. Create the Database Schema

Create the necessary schema (`schema_iceberg`) within the Spark catalog:

```bash
docker exec spark-master spark-sql -f /opt/spark/apps/setup/create_schema.sql
```

### 4. Run the Demo Data Pipeline

Run the example PySpark pipeline to create a sample Iceberg table (`table_iceberg`) and write data to it:

```bash
docker exec spark-master spark-submit /opt/spark/apps/pipelines/create_example_table.py
```

## Verifying the Results

Once the pipeline completes successfully, the data will be stored physically in the MinIO `lakehouse` bucket. You can verify the data using the MinIO UI (accessible at `http://localhost:9000` with default credentials `minioadmin` / `minioadmin123`) or by running queries against the `catalog_iceberg.schema_iceberg.table_iceberg` table in Spark.
