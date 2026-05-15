import sys
import os
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.audit import init_audit_table, log_audit

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Cleans and deduplicates inventory items data for the Silver layer with idempotency."""
    start_ts = datetime.now()
    pipeline_name = "Silver-Inventory-Items"
    
    print(f"Transforming {source_table} to {target_table}...")
    
    try:
        init_audit_table(spark)
        
        # 1. Create table with explicit schema
        spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {target_table} (
                id BIGINT,
                product_id BIGINT,
                created_at TIMESTAMP,
                sold_at TIMESTAMP,
                cost DOUBLE,
                product_category STRING,
                product_name STRING,
                product_brand STRING,
                product_retail_price DOUBLE,
                product_department STRING,
                product_sku STRING,
                product_distribution_center_id BIGINT,
                updated_at TIMESTAMP
            ) USING iceberg
            PARTITIONED BY (days(created_at))
        """)

        # 2. Read from Bronze
        df_bronze = spark.read.table(source_table)
        source_cnt = df_bronze.count()

        # 3. Transform and metadata
        df_silver = (
            df_bronze.select(
                col("id").cast("long"),
                col("product_id").cast("long"),
                col("created_at").cast("timestamp"),
                col("sold_at").cast("timestamp"),
                col("cost").cast("double"),
                "product_category",
                "product_name",
                "product_brand",
                col("product_retail_price").cast("double"),
                "product_department",
                "product_sku",
                col("product_distribution_center_id").cast("long")
            )
            .withColumn("updated_at", current_timestamp())
            .dropDuplicates(["id"])
        )
        target_cnt = df_silver.count()

        # 4. Upsert (Merge) into Silver Iceberg
        df_silver.createOrReplaceTempView("source_inventory")
        
        spark.sql(f"""
            MERGE INTO {target_table} t
            USING source_inventory s
            ON t.id = s.id
            WHEN MATCHED THEN
                UPDATE SET *
            WHEN NOT MATCHED THEN
                INSERT *
        """)
        
        log_audit(spark, pipeline_name, source_table, target_table, source_cnt, target_cnt, "SUCCESS", start_ts)
        print(f"Transformation of inventory_items completed.")

    except Exception as e:
        log_audit(spark, pipeline_name, source_table, target_table, 0, 0, "FAILED", start_ts, str(e))
        raise e

if __name__ == "__main__":
    # Sync configurations with pipelines/example/spark_hive_minio_test.py
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")
    HIVE_METASTORE_URI = os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083")

    spark = (
        SparkSession.builder
        .appName("Silver-Transform-Inventory-Items")
        .config("hive.metastore.uris", HIVE_METASTORE_URI)
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .enableHiveSupport()
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    source = "catalog_iceberg.bronze.inventory_items"
    target = "catalog_iceberg.silver.inventory_items"
    
    transform_table(spark, source, target)
    
    spark.stop()
