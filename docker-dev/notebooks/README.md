# Jupyter Notebooks Guide

This directory contains Jupyter Notebooks configured to interact with the local Data Lakehouse environment (Spark, Iceberg, and MinIO).

## 🚀 Accessing Jupyter Lab

You don't need to install Python, PySpark, or Jupyter on your local machine. The Jupyter Lab environment is already packaged and running inside the `spark-master` Docker container.

To access the interactive environment:
1. Ensure your Docker containers are running (`docker-compose up -d`).
2. Open your web browser and navigate to: **[http://localhost:8888](http://localhost:8888)**
3. You will have direct access to all notebooks saved in this `notebooks` directory.

## 🛠️ Environment Configuration

The notebooks run seamlessly with the provided Data Lakehouse stack because the `SparkSession` in this environment is pre-configured with all necessary dependencies:
- **Apache Iceberg** extensions and REST catalog configurations (via Gravitino).
- **MinIO (S3)** connectors for reading and writing data directly to the object storage.
- **Kafka** connectors for streaming data.

### Volume Mounts
- **Notebooks (`/opt/spark/notebooks`)**: Any notebook you create, edit, or save via the `localhost:8888` interface will be automatically synced to this `notebooks` folder on your local host machine.
- **Data (`/opt/spark/apps/data`)**: The `data` folder from your repository is mounted inside the container. You can load source files (like JSON, CSV) directly from your `data` directory using local file paths in Spark (e.g., `/opt/spark/apps/data/...`).

## 📚 Included Examples

- **`read_json_to_minio.ipynb`**: Demonstrates how to read raw JSON data (`sample.json`), flatten the nested structure, convert epochs to Timestamps, and write the DataFrame into an Iceberg table in the Bronze layer (`iceberg.bus_bronze.bus_way_points`).
- **`read_data_from_bronze.ipynb`**: Demonstrates how to connect to the Iceberg catalog to read the previously written Bronze table, perform basic aggregations, and run SQL queries.
- **`benchmark_analysis.ipynb`**: (New) Visualizes TPC-DS benchmark results, comparing Spark and Trino performance (latency, memory, throughput) using Plotly charts.

## 📝 Creating New Notebooks

When creating a new notebook for PySpark processing, you can usually start with this basic initialization block to connect to the cluster:

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("My-Custom-Notebook") \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.iceberg.type", "rest") \
    .config("spark.sql.catalog.iceberg.uri", "http://gravitino:9001/api/metalakes/default/catalogs/iceberg") \
    .config("spark.sql.catalog.iceberg.warehouse", "s3a://lakehouse/") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")
```
