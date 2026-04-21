from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, LongType, TimestampType

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Transforms raw event data from Bronze to Silver layer."""
    print(f"Transforming {source_table} to {target_table}...")

    # 1. Define JSON Schema based on Datagen Event model
    schema = StructType([
        StructField("id", LongType(), True),
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
        StructField("created_at", StringType(), True)
    ])

    # 2. Read from Bronze
    df_bronze = spark.read.table(source_table)

    # 3. Transform: Parse JSON and normalize timestamps
    df_silver = (
        df_bronze
        .withColumn("data", from_json(col("value"), schema))
        .select("data.*")
        .withColumn("created_at", col("created_at").cast(TimestampType()))
    )

    # 4. Write to Silver Iceberg
    (
        df_silver.writeTo(target_table)
        .createOrReplace()
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
