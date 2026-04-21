from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp
from pyspark.sql.types import TimestampType

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Transforms raw event data from Bronze to Silver layer."""
    print(f"Transforming {source_table} to {target_table}...")

    # 1. Create table with explicit schema and partitioning
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
    """)

    # 2. Read from Bronze
    df_bronze = spark.read.table(source_table)

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

    # 4. Write to Silver Iceberg
    (
        df_silver.writeTo(target_table)
        .append()
    )
    
    print(f"Transformation of events completed.")

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
