from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, date_trunc, countDistinct

def aggregate_data(spark: SparkSession, target_table: str) -> None:
    """Aggregates user engagement data for the Gold layer."""
    print(f"Aggregating data into {target_table}...")

    # 1. Read from Silver
    events_df = spark.read.table("catalog_iceberg.silver.events")

    # 2. Aggregate: Daily active users and event distribution
    gold_df = (
        events_df
        .select(
            date_trunc("day", col("created_at")).alias("event_date"),
            "user_id",
            "session_id",
            "event_type"
        )
        .groupBy("event_date")
        .agg(
            countDistinct("user_id").alias("daily_active_users"),
            countDistinct("session_id").alias("total_sessions"),
            count("*").alias("total_events")
        )
        .orderBy("event_date")
    )

    # 3. Write to Gold Iceberg
    (
        gold_df.writeTo(target_table)
        .createOrReplace()
    )
    
    print(f"Aggregation of user_engagement completed.")

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Gold-Agg-User-Engagement")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    target = "catalog_iceberg.gold.user_engagement"
    
    aggregate_data(spark, target)
    
    spark.stop()
