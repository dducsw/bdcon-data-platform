import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, count, date_trunc, current_timestamp

def aggregate_data(spark: SparkSession, target_table: str) -> None:
    """Aggregates sales performance data for the Gold layer."""
    print(f"Aggregating data into {target_table}...")

    # 1. Create table with explicit schema and partitioning
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {target_table} (
            order_date TIMESTAMP,
            product_category STRING,
            total_revenue DOUBLE,
            total_items_sold LONG,
            updated_at TIMESTAMP
        ) USING iceberg
        PARTITIONED BY (days(order_date))
        TBLPROPERTIES (
            'write.format.default'='parquet',
            'write.distribution-mode'='hash'
        )
    """)
    spark.sql(f"ALTER TABLE {target_table} WRITE ORDERED BY product_category")

    # 2. Read from Silver
    orders_df = spark.read.table("catalog_iceberg.silver.orders")
    items_df = spark.read.table("catalog_iceberg.silver.order_items")
    products_df = spark.read.table("catalog_iceberg.silver.products")

    # 3. Join and Aggregate
    gold_df = (
        items_df.alias("i")
        .join(orders_df.alias("o"), col("i.order_id") == col("o.order_id"))
        .join(products_df.alias("p"), col("i.product_id") == col("p.id"))
        .select(
            date_trunc("day", col("o.created_at")).alias("order_date"),
            col("p.category").alias("product_category"),
            col("i.sale_price")
        )
        .groupBy("order_date", "product_category")
        .agg(
            sum("sale_price").alias("total_revenue"),
            count("*").alias("total_items_sold")
        )
        .withColumn("updated_at", current_timestamp())
        .orderBy("order_date", "product_category")
    )

    # 4. Write to Gold Iceberg
    (
        gold_df.writeTo(target_table)
        .append()
    )
    
    print(f"Aggregation of sales_performance completed.")

if __name__ == "__main__":
    # Sync configurations with pipelines/example/spark_hive_minio_test.py
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")
    HIVE_METASTORE_URI = os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083")

    spark = (
        SparkSession.builder
        .appName("Gold-Agg-Sales-Performance")
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

    target = "catalog_iceberg.gold.sales_performance"
    
    aggregate_data(spark, target)
    
    spark.stop()
