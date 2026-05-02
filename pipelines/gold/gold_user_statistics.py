import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, count, max, current_timestamp, round

def aggregate_user_statistics(spark: SparkSession, target_table: str) -> None:
    """Aggregates comprehensive user statistics (orders, spend, events)."""
    print(f"Aggregating user statistics into {target_table}...")

    # 1. Create table with explicit schema
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {target_table} (
            user_id BIGINT,
            total_orders LONG,
            total_items_purchased LONG,
            total_spend DOUBLE,
            total_events LONG,
            last_order_at TIMESTAMP,
            last_event_at TIMESTAMP,
            updated_at TIMESTAMP
        ) USING iceberg
        TBLPROPERTIES (
            'write.format.default'='parquet',
            'write.distribution-mode'='hash'
        )
    """)
    spark.sql(f"ALTER TABLE {target_table} WRITE ORDERED BY user_id")

    # 2. Read from Silver
    users_df = spark.read.table("catalog_iceberg.silver.users")
    orders_df = spark.read.table("catalog_iceberg.silver.orders")
    items_df = spark.read.table("catalog_iceberg.silver.order_items")
    events_df = spark.read.table("catalog_iceberg.silver.events")

    # 3. Aggregate Orders and Spend
    # Join items with orders to get user_id for spend
    order_metrics = (
        items_df.alias("i")
        .join(orders_df.alias("o"), col("i.order_id") == col("o.order_id"))
        .groupBy("o.user_id")
        .agg(
            count("o.order_id").alias("total_orders"), # Note: This counts line items, but we want orders. 
            # Better: countDistinct(o.order_id) or group by order first.
            sum("i.sale_price").alias("total_spend")
        )
    )
    
    # Accurate order count and last order date
    order_summary = (
        orders_df.groupBy("user_id")
        .agg(
            count("order_id").alias("total_orders"),
            sum("num_of_item").alias("total_items_purchased"),
            max("created_at").alias("last_order_at")
        )
    )

    # 4. Aggregate Events
    events_agg = (
        events_df.groupBy("user_id")
        .agg(
            count("id").alias("total_events"),
            max("created_at").alias("last_event_at")
        )
    )

    # 5. Join everything together
    # Start with users as the base
    final_df = (
        users_df.select("id").alias("u")
        .join(order_summary.alias("os"), col("u.id") == col("os.user_id"), "left")
        .join(order_metrics.select("user_id", "total_spend").alias("om"), col("u.id") == col("om.user_id"), "left")
        .join(events_agg.alias("e"), col("u.id") == col("e.user_id"), "left")
        .select(
            col("u.id").alias("user_id"),
            col("os.total_orders").fill(0).alias("total_orders"),
            col("os.total_items_purchased").fill(0).alias("total_items_purchased"),
            round(col("om.total_spend"), 2).fill(0.0).alias("total_spend"),
            col("e.total_events").fill(0).alias("total_events"),
            col("os.last_order_at"),
            col("e.last_event_at"),
            current_timestamp().alias("updated_at")
        )
    )
    
    # Note: fill() is not a direct column method in Spark SQL in this way, using coalesce
    from pyspark.sql.functions import coalesce, lit
    
    final_df = (
        users_df.select(col("id").alias("user_id"))
        .join(order_summary, "user_id", "left")
        .join(order_metrics.select("user_id", "total_spend"), "user_id", "left")
        .join(events_agg, "user_id", "left")
        .select(
            "user_id",
            coalesce(col("total_orders"), lit(0)).alias("total_orders"),
            coalesce(col("total_items_purchased"), lit(0)).alias("total_items_purchased"),
            round(coalesce(col("total_spend"), lit(0.0)), 2).alias("total_spend"),
            coalesce(col("total_events"), lit(0)).alias("total_events"),
            "last_order_at",
            "last_event_at",
            current_timestamp().alias("updated_at")
        )
    )

    # 6. Write to Gold Iceberg
    (
        final_df.writeTo(target_table)
        .append()
    )
    
    print(f"Aggregation of user_statistics completed.")

if __name__ == "__main__":
    # Sync configurations with pipelines/example/spark_hive_minio_test.py
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")
    HIVE_METASTORE_URI = os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083")

    spark = (
        SparkSession.builder
        .appName("Gold-Agg-User-Statistics")
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

    target = "catalog_iceberg.gold.user_statistics"
    
    aggregate_user_statistics(spark, target)
    
    spark.stop()
