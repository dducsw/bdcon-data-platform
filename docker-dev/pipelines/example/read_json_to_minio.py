import os
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, 
    FloatType, DoubleType, BooleanType
)

from pyspark.sql.functions import current_timestamp, from_unixtime, to_timestamp, to_date, col, from_json

def stream_kafka_to_iceberg(spark: SparkSession, table_name: str) -> None:
    # Define schema for the nested BusWayPoint based on ufms.proto
    bus_way_point_schema = StructType([
        StructField("vehicle", StringType(), True),
        StructField("driver", StringType(), True),
        StructField("speed", FloatType(), True),
        StructField("datetime", IntegerType(), True),
        StructField("x", DoubleType(), True),
        StructField("y", DoubleType(), True),
        StructField("z", FloatType(), True),
        StructField("heading", FloatType(), True),
        StructField("ignition", BooleanType(), True),
        StructField("aircon", BooleanType(), True),
        StructField("door_up", BooleanType(), True),
        StructField("door_down", BooleanType(), True),
        StructField("sos", BooleanType(), True),
        StructField("working", BooleanType(), True),
        StructField("analog1", FloatType(), True),
        StructField("analog2", FloatType(), True)
    ])
    
    # Define root schema
    root_schema = StructType([
        StructField("msgType", StringType(), True),
        StructField("msgBusWayPoint", bus_way_point_schema, True)
    ])
    
    # Read the JSON file (it's an array of objects, so multiline=True)
    df_kafka = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "kafka:29092")
        .option("subscribe", "bus_gps_json")
        .option("startingOffsets", "latest")
        .load()
    )
    
    df_json = df_kafka.selectExpr("CAST(value AS STRING) as json")

    # Flatten the struct so it maps well to a tabular Iceberg table
    df = df_json.select(
        from_json(col("json"), root_schema).alias("data")
    ).select("data.*")    

    df_flattened = df.select("msgType", "msgBusWayPoint.*")

    # Convert epoch datetime to Spark timestamp and extract Date for partitioning
    df_with_ts = (
        df_flattened
        .withColumn("timestamp", to_timestamp(from_unixtime("datetime")))
        .withColumn("date", to_date(from_unixtime("datetime")))
        .withColumn("load_at", current_timestamp())
    )
    
    # Write to Iceberg with partitioning using the native date field
    query = (
        df_with_ts
        .writeStream
        .format("parquet")
        .outputMode("append")
        .option("path", "s3a://iceberg/bus_way_points")
        .option("checkpointLocation", "s3a://iceberg/checkpoints/bus_way_points")
        .partitionBy("date")
        .start()
    )

    query.awaitTermination()

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("KafkaJsonToMinIO")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    table_name = "catalog_iceberg.bus_bronze.bus_way_points"
    
    stream_kafka_to_iceberg(spark, table_name)
