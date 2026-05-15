import sys
import os
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    coalesce,
    col,
    count,
    current_timestamp,
    lit,
    max,
    round,
    sum,
)

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.audit import init_audit_table, log_audit

def aggregate_user_statistics(spark: SparkSession, target_table: str) -> None:
    """Aggregates comprehensive user statistics (orders, spend, events) with idempotency."""
    start_ts = datetime.now()
    pipeline_name = "Gold-User-Statistics"
    source_desc = "silver.users, silver.orders, silver.order_items, silver.events"
    
    print(f"Aggregating user statistics into {target_table}...")
    
    try:
        init_audit_table(spark)
        
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
        source_cnt = users_df.count()

        # 3. Aggregate Orders and Spend
        order_metrics = (
            items_df.alias("i")
            .join(orders_df.alias("o"), col("i.order_id") == col("o.order_id"))
            .groupBy("o.user_id")
            .agg(sum("i.sale_price").alias("total_spend"))
        )
        
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
        target_cnt = final_df.count()

        # 5. Upsert (Merge) into Gold Iceberg
        final_df.createOrReplaceTempView("source_user_stats")
        
        spark.sql(f"""
            MERGE INTO {target_table} t
            USING source_user_stats s
            ON t.user_id = s.user_id
            WHEN MATCHED THEN
                UPDATE SET *
            WHEN NOT MATCHED THEN
                INSERT *
        """)
        
        log_audit(spark, pipeline_name, source_desc, target_table, source_cnt, target_cnt, "SUCCESS", start_ts)
        print(f"Aggregation of user_statistics completed.")

    except Exception as e:
        log_audit(spark, pipeline_name, source_desc, target_table, 0, 0, "FAILED", start_ts, str(e))
        raise e

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Gold-Agg-User-Statistics")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    target = "catalog_iceberg.gold.user_statistics"
    
    aggregate_user_statistics(spark, target)
    
    spark.stop()
