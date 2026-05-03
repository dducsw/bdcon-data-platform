import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, current_timestamp
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    LongType,
)

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
    kafka_bootstrap_servers = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "data-platform-kafka-kafka-bootstrap:9092",
    )
    checkpoint_location = f"s3a://iceberg/checkpoints/{table_name.replace('.', '_')}"

    print(f"Streaming from {topic_name} to {table_name}...")

    spark.sql("CREATE DATABASE IF NOT EXISTS catalog_iceberg.bronze")

    # Create table if not exists
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

    df_kafka = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers)
        .option("subscribe", topic_name)
        .option("startingOffsets", "earliest")
        .load()
    )

    df_transformed = (
        df_kafka.select(
            col("key").cast("string"),
            from_json(col("value").cast("string"), EVENT_SCHEMA).alias("data"),
            col("timestamp")
        ).select("data.*", "timestamp")
        .withColumn("load_at", current_timestamp())
    )

    query = (
        df_transformed.writeStream
        .format("iceberg")
        .outputMode("append")
        .trigger(availableNow=True)
        .option("checkpointLocation", checkpoint_location)
        .toTable(table_name)
    )

    query.awaitTermination()

if __name__ == "__main__":
    # Sync configurations with pipelines/example/spark_hive_minio_test.py
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")
    HIVE_METASTORE_URI = os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083")

    spark = (
        SparkSession.builder
        .appName("Bronze-Ingest-Events-Streaming")
        .config("hive.metastore.uris", HIVE_METASTORE_URI)
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .enableHiveSupport()
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    topic = os.getenv("KAFKA_TOPIC", "click-events")
    target_table = "catalog_iceberg.bronze.events"
    
    stream_kafka_to_iceberg(spark, topic, target_table)
    
    spark.stop()
