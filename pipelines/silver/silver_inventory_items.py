import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Cleans and deduplicates inventory items data for the Silver layer."""
    print(f"Transforming {source_table} to {target_table}...")

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

    # 4. Write to Silver Iceberg
    (
        df_silver.writeTo(target_table)
        .append()
    )
    
    print(f"Transformation of inventory_items completed.")

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
