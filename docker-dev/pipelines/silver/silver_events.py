import sys
import os
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, max as spark_max
from pyspark.sql.types import TimestampType

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.audit import init_audit_table, log_audit
from utils.watermark import get_watermark, update_watermark

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Transforms raw event data from Bronze to Silver layer with Incremental Loading."""
    start_ts = datetime.now()
    pipeline_name = "Silver-Events"
    
    print(f"Transforming {source_table} to {target_table}...")
    
    try:
        init_audit_table(spark)
        
        # Get last watermark
        last_watermark = get_watermark(spark, pipeline_name)
        print(f"Processing data created after: {last_watermark}")

        # 1. Create table with explicit schema
        spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {target_table} (
                id BIGINT,
                user_id BIGINT,
                sequence_number INT,
                session_id STRING,
                ip_address STRING,
                city STRING,
                state STRING,
                postal_code STRING,
                browser STRING,
                traffic_source STRING,
                uri STRING,
                event_type STRING,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            ) USING iceberg
            PARTITIONED BY (days(created_at))
            TBLPROPERTIES (
                'write.format.default'='parquet',
                'write.distribution-mode'='hash',
                'write.parquet.bloom-filter-enabled.column.session_id'='true'
            )
        """)
        spark.sql(f"ALTER TABLE {target_table} WRITE ORDERED BY user_id, session_id, event_type")

        # 2. Read from Bronze and filter by Watermark
        df_bronze = spark.read.table(source_table).filter(col("created_at") > last_watermark)
        source_cnt = df_bronze.count()

        if source_cnt == 0:
            print("No new data to process.")
            return

        # 3. Transform: Normalize timestamps and deduplicate
        df_silver = (
            df_bronze.select(
                "id", "user_id", "sequence_number", "session_id", "ip_address",
                "city", "state", "postal_code", "browser", "traffic_source",
                "uri", "event_type",
                col("created_at").cast(TimestampType())
            )
            .withColumn("updated_at", current_timestamp())
            .dropDuplicates(["id"])
        )
        target_cnt = df_silver.count()
        
        # Calculate new watermark
        new_watermark = df_silver.select(spark_max("created_at")).first()[0]

        # 4. Upsert (Merge) into Silver Iceberg
        df_silver.createOrReplaceTempView("source_events")
        
        spark.sql(f"""
            MERGE INTO {target_table} t
            USING source_events s
            ON t.id = s.id
            WHEN MATCHED THEN
                UPDATE SET *
            WHEN NOT MATCHED THEN
                INSERT *
        """)
        
        # Update watermark table
        update_watermark(spark, pipeline_name, new_watermark)
        
        log_audit(spark, pipeline_name, source_table, target_table, source_cnt, target_cnt, "SUCCESS", start_ts)
        print(f"Transformation of events completed.")

    except Exception as e:
        log_audit(spark, pipeline_name, source_table, target_table, 0, 0, "FAILED", start_ts, str(e))
        raise e

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Silver-Transform-Events")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    source = "catalog_iceberg.bronze.events"
    target = "catalog_iceberg.silver.events"
    
    transform_table(spark, source, target)
    
    spark.stop()
