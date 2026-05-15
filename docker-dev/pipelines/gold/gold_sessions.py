import sys
import os
from datetime import datetime
from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import (
    col, min, max, count, unix_timestamp, first, 
    current_timestamp, when, sum, row_number
)

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.audit import init_audit_table, log_audit

def aggregate_data(spark: SparkSession, target_table: str) -> None:
    """Aggregates event data into sessions for the Gold layer with advanced metrics."""
    start_ts = datetime.now()
    pipeline_name = "Gold-Sessions-Advanced"
    source_table = "catalog_iceberg.silver.events"
    
    print(f"Aggregating sessions into {target_table}...")
    
    try:
        # Initialize audit table
        init_audit_table(spark)
        
        # 1. Create table with explicit schema if not exists
        spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {target_table} (
                session_id STRING,
                user_id BIGINT,
                session_start TIMESTAMP,
                session_end TIMESTAMP,
                duration_seconds LONG,
                event_count LONG,
                landing_page STRING,
                exit_page STRING,
                is_converted BOOLEAN,
                ip_address STRING,
                city STRING,
                state STRING,
                browser STRING,
                traffic_source STRING,
                updated_at TIMESTAMP
            ) USING iceberg
            PARTITIONED BY (days(session_start))
            TBLPROPERTIES (
                'write.format.default'='parquet',
                'write.distribution-mode'='hash'
            )
        """)
        spark.sql(f"ALTER TABLE {target_table} WRITE ORDERED BY session_id")

        # 2. Read from Silver
        events_df = spark.read.table(source_table)
        source_cnt = events_df.count()

        # 3. Enrich events with purchase flag
        enriched_events = events_df.withColumn(
            "is_purchase", when(col("event_type") == "purchase", 1).otherwise(0)
        )

        # 4. Define Window to identify landing and exit pages
        window_first = Window.partitionBy("session_id").orderBy("created_at", "id")
        window_last = Window.partitionBy("session_id").orderBy(col("created_at").desc(), col("id").desc())

        # 5. Extract landing/exit and first event attributes
        session_lifecycle = (
            enriched_events.withColumn("rank_first", row_number().over(window_first))
            .withColumn("rank_last", row_number().over(window_last))
            .filter((col("rank_first") == 1) | (col("rank_last") == 1))
            .groupBy("session_id")
            .agg(
                first(when(col("rank_first") == 1, col("uri"))).alias("landing_page"),
                first(when(col("rank_last") == 1, col("uri"))).alias("exit_page"),
                first(when(col("rank_first") == 1, col("ip_address"))).alias("ip_address"),
                first(when(col("rank_first") == 1, col("city"))).alias("city"),
                first(when(col("rank_first") == 1, col("state"))).alias("state"),
                first(when(col("rank_first") == 1, col("browser"))).alias("browser"),
                first(when(col("rank_first") == 1, col("traffic_source"))).alias("traffic_source")
            )
        )

        # 6. Basic aggregations
        sessions_metrics = (
            enriched_events.groupBy("session_id", "user_id")
            .agg(
                min("created_at").alias("session_start"),
                max("created_at").alias("session_end"),
                count("*").alias("event_count"),
                sum("is_purchase").alias("purchase_count")
            )
        )

        # 7. Combine everything
        final_sessions = (
            sessions_metrics.join(session_lifecycle, "session_id")
            .withColumn("is_converted", col("purchase_count") > 0)
            .withColumn(
                "duration_seconds",
                unix_timestamp(col("session_end")) - unix_timestamp(col("session_start"))
            )
            .withColumn("updated_at", current_timestamp())
            .select(
                "session_id", "user_id", "session_start", "session_end", "duration_seconds",
                "event_count", "landing_page", "exit_page", "is_converted",
                "ip_address", "city", "state", "browser", "traffic_source", "updated_at"
            )
        )

        # 8. Upsert (Merge) into Iceberg Table
        final_sessions.createOrReplaceTempView("source_sessions")
        target_cnt = final_sessions.count()
        
        spark.sql(f"""
            MERGE INTO {target_table} t
            USING source_sessions s
            ON t.session_id = s.session_id
            WHEN MATCHED THEN
                UPDATE SET *
            WHEN NOT MATCHED THEN
                INSERT *
        """)
        
        log_audit(spark, pipeline_name, source_table, target_table, source_cnt, target_cnt, "SUCCESS", start_ts)
        print(f"Upsert of sessions into {target_table} completed.")

    except Exception as e:
        log_audit(spark, pipeline_name, source_table, target_table, 0, 0, "FAILED", start_ts, str(e))
        raise e

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Gold-Agg-Sessions-Advanced")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    target = "catalog_iceberg.gold.sessions"
    
    aggregate_data(spark, target)
    
    spark.stop()
