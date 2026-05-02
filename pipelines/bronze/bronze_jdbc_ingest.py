import os
import argparse
from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp

def ingest_jdbc_to_iceberg(spark: SparkSession, source_table: str, target_table: str, schema_ddl: str) -> None:
    """Ingests data from a PostgreSQL table to an Iceberg table using JDBC."""
    db_host = os.getenv("DB_HOST", "postgres")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "thelook_db")
    db_user = os.getenv("DB_USER", "db_user")
    db_password = os.getenv("DB_PASSWORD", "db_password")
    db_schema = os.getenv("DB_SCHEMA", "demo")
    
    jdbc_url = f"jdbc:postgresql://{db_host}:{db_port}/{db_name}"

    print(f"Ingesting {db_schema}.{source_table} from Postgres to {target_table}...")

    # 1. Create table if not exists using provided DDL
    if schema_ddl:
        spark.sql(f"CREATE TABLE IF NOT EXISTS {target_table} ({schema_ddl}) USING iceberg")

    # 2. Read from Postgres
    df = (
        spark.read
        .format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", f"{db_schema}.{source_table}")
        .option("user", db_user)
        .option("password", db_password)
        .option("driver", "org.postgresql.Driver")
        .load()
    )
    
    # 3. Add metadata and rename business updated_at
    if "updated_at" in df.columns:
        df = df.withColumnRenamed("updated_at", "source_updated_at")
    
    df_transformed = df.withColumn("load_at", current_timestamp())
    
    # 4. Write to Iceberg
    (
        df_transformed.writeTo(target_table)
        .append()
    )
    
    print(f"Ingestion of {source_table} completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-table", required=True)
    parser.add_argument("--target-table", required=True)
    parser.add_argument("--schema-ddl", default="")
    args = parser.parse_args()

    # Sync configurations with pipelines/example/spark_hive_minio_test.py
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")
    HIVE_METASTORE_URI = os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083")

    spark = (
        SparkSession.builder
        .appName(f"Bronze-Ingest-{args.source_table}")
        .config("hive.metastore.uris", HIVE_METASTORE_URI)
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", 
                "org.apache.hadoop.fs.s3a.EnvironmentVariableCredentialsProvider")
        .enableHiveSupport()
        .getOrCreate()
    )
    
    spark.sparkContext.setLogLevel("ERROR")

    ingest_jdbc_to_iceberg(spark, args.source_table, args.target_table, args.schema_ddl)
    
    spark.stop()
