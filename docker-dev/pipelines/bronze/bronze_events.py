import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from schemas import EVENT_SCHEMA

def stream_kafka_to_iceberg(spark: SparkSession, topic_name: str, table_name: str) -> None:
    """Streams data from Kafka topic to an Iceberg table."""
    kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    checkpoint_location = f"s3a://warehouse/checkpoints/{table_name.replace('.', '_')}"

    print(f"Starting streaming ingestion from Kafka topic {topic_name} to {table_name}...")

    # 1. Read from Kafka
    df_kafka = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers)
        .option("subscribe", topic_name)
        .option("startingOffsets", "earliest")
        .load()
    )

    # 2. Extract Value and Key, and parse the JSON payload
    df_bronze = (
        df_kafka.select(
            col("key").cast("string"),
            from_json(col("value").cast("string"), EVENT_SCHEMA).alias("data"),
            col("topic"),
            col("partition"),
            col("offset"),
            col("timestamp"),
            col("timestampType")
        ).select("key", "data.*", "topic", "partition", "offset", "timestamp", "timestampType")
    )

    # 3. Create table if not exists (using spark-sql to ensure schema)
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            key STRING,
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
            topic STRING,
            partition INT,
            `offset` BIGINT,
            timestamp TIMESTAMP,
            timestampType INT
        ) USING iceberg
        PARTITIONED BY (days(timestamp))
    """)

    # 4. Write to Iceberg
    query = (
        df_bronze.writeStream
        .format("iceberg")
        .outputMode("append")
        .trigger(processingTime="10 seconds")
        .option("path", table_name)
        .option("checkpointLocation", checkpoint_location)
        .start()
    )

    query.awaitTermination()

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Bronze-Ingest-Events")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    target_table = "catalog_iceberg.bronze.events"
    topic = "ecomm.events"
    
    stream_kafka_to_iceberg(spark, topic, target_table)
