import sys
import os
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, max, current_timestamp

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.audit import init_audit_table, log_audit

def aggregate_data(spark: SparkSession, target_table: str) -> None:
    """Aggregates user engagement data for the Gold layer with idempotency."""
    start_ts = datetime.now()
    pipeline_name = "Gold-User-Engagement"
    source_table = "catalog_iceberg.silver.events"
    
    print(f"Aggregating data into {target_table}...")
    
    try:
        init_audit_table(spark)
        
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
        events_df = spark.read.table(source_table)
        source_cnt = events_df.count()

        # 3. Aggregate
        gold_df = (
            events_df.groupBy("user_id")
            .agg(
                count("*").alias("event_count"),
                max("created_at").alias("last_event_at")
            )
            .withColumn("updated_at", current_timestamp())
        )
        target_cnt = gold_df.count()

        # 4. Upsert (Merge) into Gold Iceberg
        gold_df.createOrReplaceTempView("source_engagement")
        
        spark.sql(f"""
            MERGE INTO {target_table} t
            USING source_engagement s
            ON t.user_id = s.user_id
            WHEN MATCHED THEN
                UPDATE SET *
            WHEN NOT MATCHED THEN
                INSERT *
        """)
        
        log_audit(spark, pipeline_name, source_table, target_table, source_cnt, target_cnt, "SUCCESS", start_ts)
        print(f"Aggregation of user_engagement completed.")

    except Exception as e:
        log_audit(spark, pipeline_name, source_table, target_table, 0, 0, "FAILED", start_ts, str(e))
        raise e

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
