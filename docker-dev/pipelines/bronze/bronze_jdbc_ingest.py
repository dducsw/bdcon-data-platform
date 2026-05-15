import os
import sys
import argparse
import time
from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp

def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-table", required=True)
    parser.add_argument("--target-table", required=True)
    parser.add_argument("--schema-ddl", default="")
    args = parser.parse_args()

    source_table = args.source_table
    target_table = args.target_table

    # Configs
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")
    HIVE_METASTORE_URI = os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083")
    DB_HOST = os.getenv("DB_HOST", "postgres-source")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "thelook_db")
    DB_USER = os.getenv("DB_USER", "db_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "db_password")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "demo")
    
    jdbc_url = f"jdbc:postgresql://{DB_HOST}:{DB_PORT}/{DB_NAME}"

    log("🚀 Initializing SparkSession...")
    spark = (
        SparkSession.builder
        .appName(f"Bronze-Ingest-{source_table}")
        .config("hive.metastore.uris", HIVE_METASTORE_URI)
        # S3A / MinIO config
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
        # S3A Fast Upload: stream trực tiếp, không buffer trên disk → tránh hang
        .config("spark.hadoop.fs.s3a.fast.upload", "true")
        .config("spark.hadoop.fs.s3a.fast.upload.buffer", "bytebuffer")
        .config("spark.hadoop.fs.s3a.multipart.size", "67108864")
        .config("spark.hadoop.fs.s3a.multipart.threshold", "67108864")
        # Connection timeouts: fail fast thay vì hang vô thời hạn
        .config("spark.hadoop.fs.s3a.connection.timeout", "30000")
        .config("spark.hadoop.fs.s3a.connection.establish.timeout", "5000")
        .config("spark.hadoop.fs.s3a.attempts.maximum", "3")
        # Magic committer: tránh staging committer deadlock với MinIO (non-AWS S3)
        .config("spark.hadoop.fs.s3a.committer.name", "magic")
        .config("spark.hadoop.fs.s3a.committer.magic.enabled", "true")
        .config("spark.sql.sources.commitProtocolClass",
                "org.apache.spark.internal.io.cloud.PathOutputCommitProtocol")
        .config("spark.sql.parquet.output.committer.class",
                "org.apache.spark.internal.io.cloud.BindingParquetOutputCommitter")
        # Iceberg catalog config
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkSessionCatalog")
        .config("spark.sql.catalog.spark_catalog.type", "hive")
        .config("spark.sql.catalog.catalog_iceberg", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.catalog_iceberg.type", "hive")
        .config("spark.sql.catalog.catalog_iceberg.uri", HIVE_METASTORE_URI)
        .config("spark.sql.catalog.catalog_iceberg.warehouse", "s3a://iceberg/lakehouse")
        # Tối ưu: ít shuffle partitions cho dataset vừa
        .config("spark.sql.shuffle.partitions", "4")
        .enableHiveSupport()
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    log("✅ SparkSession with Iceberg Initialized!")

    try:
        log(f"--- Ingesting {DB_SCHEMA}.{source_table} to {target_table} ---")

        # 0. Đảm bảo database tồn tại trong catalog trước khi ghi
        target_parts = target_table.split(".")
        if len(target_parts) == 3:
            catalog_name, db_name, _ = target_parts
            log(f"Ensuring database {catalog_name}.{db_name} exists...")
            spark.sql(f"CREATE DATABASE IF NOT EXISTS {catalog_name}.{db_name}")
            log(f"Database {catalog_name}.{db_name} ready.")

        # 1. Read from JDBC
        log(f"Reading from JDBC: {jdbc_url} ...")
        df = (
            spark.read
            .format("jdbc")
            .option("url", jdbc_url)
            .option("dbtable", f"{DB_SCHEMA}.{source_table}")
            .option("user", DB_USER)
            .option("password", DB_PASSWORD)
            .option("driver", "org.postgresql.Driver")
            .option("fetchsize", "10000")
            .load()
        )
        log(f"Read {df.count()} rows from {DB_SCHEMA}.{source_table}")

        # Add metadata
        if "updated_at" in df.columns:
            df = df.withColumnRenamed("updated_at", "source_updated_at")
        df_transformed = df.withColumn("load_at", current_timestamp())

        # 2. Repartition để kiểm soát số file ghi ra MinIO
        df_transformed = df_transformed.repartition(4)

        # 3. Write to Iceberg
        log(f"Writing to Iceberg: {target_table} ...")
        df_transformed.writeTo(target_table).createOrReplace()
        log("✅ Ingestion completed successfully!")

    except Exception as e:
        log(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        log("Stopping Spark Session.")
        spark.stop()

if __name__ == "__main__":
    main()
