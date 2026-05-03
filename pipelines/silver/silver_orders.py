import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Cleans and deduplicates order data for the Silver layer."""
    print(f"Transforming {source_table} to {target_table}...")

    # 1. Create table with explicit schema
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {target_table} (
            order_id BIGINT,
            user_id BIGINT,
            status STRING,
            gender STRING,
            created_at TIMESTAMP,
            source_updated_at TIMESTAMP,
            returned_at TIMESTAMP,
            shipped_at TIMESTAMP,
            delivered_at TIMESTAMP,
            num_of_item INT,
            updated_at TIMESTAMP
        ) USING iceberg
        PARTITIONED BY (days(created_at))
    """)

    # 2. Read from Bronze
    df_bronze = spark.read.table(source_table)

    # 3. Cleansing and metadata
    df_silver = (
        df_bronze.select(
            col("order_id").cast("long"),
            col("user_id").cast("long"),
            "status",
            "gender",
            col("created_at").cast("timestamp"),
            col("source_updated_at").cast("timestamp"),
            col("returned_at").cast("timestamp"),
            col("shipped_at").cast("timestamp"),
            col("delivered_at").cast("timestamp"),
            col("num_of_item").cast("int")
        )
        .withColumn("updated_at", current_timestamp())
        .dropDuplicates(["order_id"])
    )

    # 4. Write to Silver Iceberg
    (
        df_silver.writeTo(target_table)
        .append()
    )
    
    print(f"Transformation of orders completed.")

if __name__ == "__main__":
    # Sync configurations with pipelines/example/spark_hive_minio_test.py
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")
    HIVE_METASTORE_URI = os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083")

    spark = (
        SparkSession.builder
        .appName("Silver-Transform-Orders")
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

    source = "catalog_iceberg.bronze.orders"
    target = "catalog_iceberg.silver.orders"
    
    transform_table(spark, source, target)
    
    spark.stop()
