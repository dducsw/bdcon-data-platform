from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, max, current_timestamp

def aggregate_data(spark: SparkSession, target_table: str) -> None:
    """Aggregates user engagement data for the Gold layer."""
    print(f"Aggregating data into {target_table}...")

    # 1. Create table with explicit schema
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {target_table} (
            user_id BIGINT,
            event_count LONG,
            last_event_at TIMESTAMP,
            updated_at TIMESTAMP
        ) USING iceberg
    """)

    # 2. Read from Silver
    events_df = spark.read.table("catalog_iceberg.silver.events")

    # 3. Aggregate
    gold_df = (
        events_df.groupBy("user_id")
        .agg(
            count("*").alias("event_count"),
            max("created_at").alias("last_event_at")
        )
        .withColumn("updated_at", current_timestamp())
    )

    # 4. Write to Gold Iceberg
    (
        gold_df.writeTo(target_table)
        .append()
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
