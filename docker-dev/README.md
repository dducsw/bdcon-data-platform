#  Modern Data Lakehouse with Apache Iceberg

A production-grade, containerized Data Lakehouse environment featuring Apache Iceberg, Spark Cluster, Kafka, Trino, and Gravitino REST Catalog. Built with modern data engineering best practices and optimized for local development and testing.

## 📐 Architecture

![Data Lakehouse Architecture](assets/architecture.png)

The architecture follows a layered approach:
- **Ingestion Layer**: Apache Kafka for real-time data streaming
- **Compute Layer**: Apache Spark cluster (1 Master + 2 Workers) for distributed processing
- **Query Layer**: Trino for fast, interactive SQL analytics
- **Catalog Layer**: Apache Gravitino as the Iceberg REST catalog service
- **Table Format**: Apache Iceberg for ACID transactions and time travel
- **File Format**: Apache Parquet for efficient columnar storage
- **Storage Layer**: MinIO (S3-compatible) for scalable object storage
- **Observability**: Grafana and Prometheus for metrics and monitoring

## ✨ Key Features

- **🔄 ACID Transactions**: Full ACID support via Apache Iceberg with snapshot isolation
- **⚡ Distributed Processing**: Spark cluster with 1 master and 2 worker nodes
- **🎯 Multi-Engine Access**: Query data using Spark SQL, Trino, or PySpark notebooks
- **📊 Real-time Ingestion**: Kafka cluster (3-node KRaft) for streaming data pipelines
- **🔍 Unified Catalog**: Gravitino REST catalog for centralized metadata management
- **📈 Built-in Monitoring**: Prometheus metrics with Grafana dashboards
- **🐳 Fully Dockerized**: One-command deployment with Docker Compose
- **🔐 S3-Compatible Storage**: MinIO for cost-effective data lake storage

## 🛠 Technology Stack

| Component | Version | Purpose |
|-----------|---------|---------|
| **Apache Spark** | 3.5.5 | Distributed data processing engine |
| **Apache Iceberg** | 1.10.0 | Open table format for huge analytic datasets |
| **Apache Gravitino** | 1.1.0 | REST catalog service for lakehouse metadata |
| **Apache Kafka** | 3.9.0 | Distributed event streaming platform |
| **Trino** | 471 | Fast distributed SQL query engine |
| **MinIO** | 2025-09-07 | S3-compatible object storage |
| **PostgreSQL** | 16 | Catalog backend database |
| **Grafana** | 12.1.0 | Metrics visualization |
| **Prometheus** | 3.5.1 | Metrics collection and alerting |
| **Python** | 3.12.3 | Runtime for PySpark applications |
| **Java** | 17 | Runtime for JVM-based services |

## 🚀 Quick Start

### Prerequisites
- Docker Engine 20.10+ with Docker Compose
- At least 8GB RAM available for containers
- Ports available: 8080, 8090, 8888, 9091, 3000, 9000, 5432

### 1. Clone and Start

```bash
# Clone the repository
git clone https://github.com/dducsw/mp252.git
cd mp252

# Start all services
docker compose up --detach --build
```

2. **Initialize Schema**:
   ```shell
   docker exec -it spark-master spark-sql -f /opt/spark/apps/setup/create_schema.sql
   ```

3. **Run the Medallion Pipeline**:
   The project includes a complete Medallion architecture pipeline. You can run individual layers or the entire pipeline using `make`:
   ```bash
   # Run everything (Bronze -> Silver -> Gold)
   make pipeline-all

   # Or run layer by layer
   make pipeline-bronze
   make pipeline-silver
   make pipeline-gold
   ```

4. **Using Notebooks**:
   - Access **JupyterLab** at `http://localhost:8888`.
   - Your notebooks are saved in the `notebooks/` directory.
   - To start a PySpark session in a notebook:
     ```python
     from pyspark.sql import SparkSession
     spark = SparkSession.builder.getOrCreate()
     ```

## 🔍 Querying Data
You can query tables using either Spark or Trino:

**Spark SQL:**
```shell
docker exec -it spark-master spark-sql
SELECT * FROM catalog_iceberg.hive.table_iceberg;
```

**Trino CLI:**
```shell
docker exec -it trino trino --catalog catalog_iceberg --schema schema_iceberg
SELECT * FROM table_iceberg;
```

### 🏮 Medallion Data Architecture

The pipeline implements a standard Medallion architecture with explicit schema enforcement and optimized Iceberg partitioning:

| Layer | Purpose | Partitioning | Metadata Columns |
|-------|---------|--------------|------------------|
| **Bronze** | Raw data from Source | `days(created_at)` | `source_updated_at`, `load_at` |
| **Silver** | Cleaned & Deduplicated | `days(created_at)` | `source_updated_at`, `updated_at` |
| **Gold** | Aggregated & Analytics-ready | Business Logic | `updated_at` |

**Verification in Trino:**
```sql
-- Check Bronze users
SELECT id, source_updated_at, load_at FROM catalog_iceberg.bronze.users LIMIT 10;

-- Check Silver users
SELECT id, source_updated_at, updated_at FROM catalog_iceberg.silver.users LIMIT 10;
```

### 🕸️ Apache Airflow Orchestration

![Airflow DAGs](../assets/dag0.png)

The project leverages **Apache Airflow 3.1** to orchestrate the PySpark Medallion pipelines. To achieve maximum efficiency and prevent cluster resource contention, we implemented a **Hybrid Pipeline Architecture** (Lambda/Kappa approach):

- ⚡ **Near Real-Time (NRT) Pipeline** (`lakehouse_nrt_events_pipeline`): Runs every **5 minutes**. Focuses strictly on high-velocity streaming data (`events`), moving it from Bronze (Kafka Streaming Batch) -> Silver -> Gold (User Sessions & Engagement).
- 🕒 **Batch Transactional Pipeline** (`lakehouse_batch_transactional_pipeline`): Runs every **30 minutes**. Focuses on core transactional data ingested from PostgreSQL (`users`, `orders`, `products`, etc.).

**Key Highlights:**
1. **Parallel Execution**: Tables are processed in parallel (e.g., `bronze_users >> silver_users`, `bronze_orders >> silver_orders`), ensuring fast throughput without waiting for unrelated tables.
2. **Precise Dependencies**: The Gold layer tasks only wait for the *specific* Silver tables they need (e.g., `gold_sessions` only waits for `silver_events`), drastically reducing end-to-end latency.
3. **Resource Management**: Spark jobs are assigned to a dedicated Airflow Pool (`spark_pool=3`) to prevent cluster memory exhaustion (OOM) by capping parallel Spark-Submits.

## Benchmarking Spark vs Trino

The repository includes a starter benchmark harness under [benchmark/](benchmark/README.md) to compare Spark and Trino on the same `TPC-DS SF5` dataset and collect:

- `query_time`
- `throughput`
- `peak_memory`
- `spill_bytes`
- `cpu_time`
- `success_fail_rate`

For the local `16 GB` Docker budget, the engines are also capped internally:

- Spark: `driver.memory=1g`, `executor.instances=1`, `executor.cores=2`, `executor.memory=1536m`, `executor.memoryOverhead=512m`
- Trino: `-Xmx2G`, `query.max-memory-per-node=768MB`, `query.max-memory=768MB`, `query.max-total-memory=1536MB`

Run sequence:

```shell
make benchmark-prepare
make benchmark-spark
make benchmark-trino
make benchmark-report
```

Or:

```shell
make benchmark-all
```

## 📁 Project Structure

```
Project
│
├── 📄 docker-compose.yml              # Main orchestration file for all services
├── 📄 .env                            # Environment variables and version configurations
├── 📄 README.md                       # Project documentation
├── 📄 .gitignore                      # Git ignore patterns
│
├── 📁 airflow/                        # Apache Airflow Orchestration
│   └── 📁 dags/                       # Airflow DAG definitions (NRT, Batch, Maintenance)
│
├── 📁 assets/                         # Documentation assets
│
├── 📁 infrastructure/                 # Service-specific configurations
│   │
│   ├── 📁 common/                     # Shared initialization scripts
│   │
│   ├── 📁 gravitino/                  # Apache Gravitino REST Catalog
│   │
│   ├── 📁 spark/                      # Apache Spark Cluster
│   │
│   ├── 📁 trino/                      # Trino Query Engine
│   │
│   ├── 📁 kafka/                      # Apache Kafka 
│   │
│   ├── 📁 minio/                      # MinIO S3-Compatible Storage
│   │
│   ├── 📁 postgres/                   # PostgreSQL Metadata Store
│   │
│   ├── 📁 grafana/                    # Grafana Monitoring
│   │
│   └── 📁 prometheus/                 # Prometheus Metrics Collection
│
├── 📁 notebooks/                      # Jupyter Notebooks
│   └── (Your interactive PySpark notebooks)
│
├── 📁 pipelines/                      # Data Processing Pipelines
│   ├── 📁 bronze/                     # Raw Data Ingestion (JDBC, Kafka)
│   ├── 📁 silver/                     # Data Cleaning & Deduplication
│   ├── 📁 gold/                       # Aggregations & Business Logic
│   ├── 📁 maintenance/                # Iceberg Snapshot & Optimization
│   └── 📁 utils/                      # Shared logic (Audit, Watermarks)
│
├── 📁 scripts/                        # Utility Scripts
│
└── 📁 setup/                          # Initial Setup Scripts
    └── create_schema.sql              # Database schema initialization
```


**⭐ Star this repository if you find it helpful!**

*Enhanced and maintained by [dducsw](https://github.com/dducsw). Based on the original project by [marcellinus-witarsah](https://github.com/marcellinus-witarsah/local-data-lakehouse-iceberg).*


