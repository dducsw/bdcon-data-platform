import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, current_timestamp
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    LongType,
    TimestampType,
)

# Define schema directly in the file as requested
EVENT_SCHEMA = StructType([
    StructField("id", LongType(), False),
    StructField("user_id", LongType(), True),
    StructField("sequence_number", IntegerType(), True),
    StructField("session_id", StringType(), True),
    StructField("ip_address", StringType(), True),
    StructField("city", StringType(), True),
    StructField("state", StringType(), True),
    StructField("postal_code", StringType(), True),
    StructField("browser", StringType(), True),
    StructField("traffic_source", StringType(), True),
    StructField("uri", StringType(), True),
    StructField("event_type", StringType(), True),
    StructField("created_at", StringType(), True),
])

def stream_kafka_to_iceberg(spark: SparkSession, topic_name: str, table_name: str) -> None:
    """Streams data from Kafka topic to an Iceberg table."""
    kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    checkpoint_location = f"file:///tmp/checkpoints/{table_name.replace('.', '_')}"

    print(f"Starting streaming ingestion from Kafka topic {topic_name} to {table_name}...")

    # 1. Create table with explicit schema and partitioning
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
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
            created_at STRING,
            timestamp TIMESTAMP,
            load_at TIMESTAMP
        ) USING iceberg
        PARTITIONED BY (days(timestamp))
    """)

    # 2. Read from Kafka
    df_kafka = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers)
        .option("subscribe", topic_name)
        .option("startingOffsets", "earliest")
        .load()
    )

    # 3. Parse JSON and add metadata
    df_transformed = (
        df_kafka.select(
            col("key").cast("string"),
            from_json(col("value").cast("string"), EVENT_SCHEMA).alias("data"),
            col("timestamp")
        ).select("data.*", "timestamp")
        .withColumn("load_at", current_timestamp())
    )

    # 4. Write to Iceberg
    query = (
        df_transformed.writeStream
        .format("iceberg")
        .outputMode("append")
        .trigger(availableNow=True)
        .option("checkpointLocation", checkpoint_location)
        .toTable(table_name)
    )

    query.awaitTermination()
    print(f"Streaming ingestion to {table_name} completed.")

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Bronze-Ingest-Events")
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin")
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    topic = "click_events"
    target_table = "catalog_iceberg.bronze.events"
    
    stream_kafka_to_iceberg(spark, topic, target_table)
    
    spark.stop()
