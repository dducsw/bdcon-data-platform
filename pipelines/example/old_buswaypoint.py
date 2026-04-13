from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, upper, current_timestamp, size, trim, lit, split, regexp_replace

# Khởi tạo SparkSession với Iceberg
spark = SparkSession.builder \
    .appName("ReadBusWayPointStream") \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.iceberg.type", "rest") \
    .config("spark.sql.catalog.iceberg.uri", "http://iceberg-rest:8181") \
    .config("spark.sql.catalog.iceberg.warehouse", "s3a://lake/") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.sql.catalog.iceberg.cache-enabled", "false") \
    .config("spark.cores.max", "2") \
    .config("spark.executor.cores", "1") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")
# Tạo bảng iceberg.silver.buswaypoint
spark.sql("CREATE NAMESPACE IF NOT EXISTS iceberg.silver")
spark.sql("""
    CREATE TABLE IF NOT EXISTS iceberg.silver.buswaypoint (
        vehicle STRING,
        driver STRING,
        driver_name STRING,
        speed FLOAT,
        datetime TIMESTAMP,
        x DOUBLE,
        y DOUBLE,
        z FLOAT,
        heading DOUBLE,
        ignition BOOLEAN,
        aircon BOOLEAN,
        door_up BOOLEAN,
        door_down BOOLEAN,
        sos BOOLEAN,
        working BOOLEAN,
        analog1 DOUBLE,
        analog2 DOUBLE,
        update_at TIMESTAMP
    ) USING iceberg
    PARTITIONED BY (day(datetime))
""")
print("Create table 'iceberg.silver.buswaypoint' success")
# Đọc streaming từ bảng buswaypoint từ bronze layer
print("Read Bus Way Point Stream:")
buswaypoint_df = spark.readStream \
    .format("iceberg") \
    .table("iceberg.bronze.buswaypoint")

# Normalize driver field (trim, replace full-width semicolon) then split
cleaned_driver = regexp_replace(trim(col("driver")), "; ", ";")
driver_parts = split(cleaned_driver, ";")
# Clean và Transform 
transformed_df = buswaypoint_df \
    .withColumn("heading", when(col("heading").isNull(), -1.0).otherwise(col("heading").cast("float"))) \
    .withColumn("ignition", when(col("ignition").isNull(), False).otherwise(True)) \
    .withColumn("aircon", when(col("aircon").isNull(), False).otherwise(True)) \
    .withColumn("door_up", when(col("door_up").isNull(), False).otherwise(True)) \
    .withColumn("door_down", when(col("door_down").isNull(), False).otherwise(True)) \
    .withColumn("sos", when(col("sos").isNull(), False).otherwise(True)) \
    .withColumn("working", when(col("working").isNull(), False).otherwise(True)) \
    .withColumn("analog1", when(col("analog1").isNull(), -1.0).otherwise(col("analog1").cast("float"))) \
    .withColumn("analog2", when(col("analog2").isNull(), -1.0).otherwise(col("analog2").cast("float"))) \
    .withColumn("vehicle", upper(col("vehicle"))) \
    .withColumn("speed", when(col("speed").isNull(), -1).otherwise(col("speed"))) \
    .withColumn("update_at", current_timestamp()) \
    .withColumn("driver",when(col("driver").isNull() | (trim(col("driver")) == ""), lit(None)).when(size(driver_parts) >= 1, trim(driver_parts.getItem(0))).otherwise(trim(col("driver"))))\
    .withColumn("driver_name",when(col("driver").isNull() | (trim(col("driver")) == ""), lit(None)).when(size(driver_parts) >= 2, trim(driver_parts.getItem(1))).otherwise(lit(None)))    # Cần fix lại driver 800136000842;NGUYEN LE TAN DAT

# Select only the necessary columns before writing to the silver table
selected_columns = [
    "vehicle", "driver", "driver_name", "speed", "datetime", "x", "y", "z", "heading", 
    "ignition", "aircon", "door_up", "door_down", "sos", "working", 
    "analog1", "analog2", "update_at"
]

transformed_df = transformed_df.select(*selected_columns)

print("Starting streaming transformation and write to iceberg.silver.buswaypoint...")

def write_batch_to_iceberg(batch_df, batch_id):
    print("Start write")
    rec_count = batch_df.count()
    print(f"[DEBUG] Batch {batch_id}: received {rec_count} records. Showing up to 20 rows:")
    batch_df.show(20, truncate=False)


# Ghi dữ liệu streaming vào bảng silver.buswaypoint với foreachBatch và ghi log
def write_batch_to_iceberg(batch_df, batch_id):
    print("Start write")
    rec_count = batch_df.count()
    print(f"[DEBUG] Batch {batch_id}: received {rec_count} records.")
    # Show main rows
    batch_df.show(20, truncate=False)
    # Additional debug: compute driver_parts on the batch and show them to investigate split issues
    if rec_count > 0:
        batch_df.write \
            .format("iceberg") \
            .mode("append") \
            .option("path", "s3a://lake/silver/buswaypoint") \
            .saveAsTable("iceberg.silver.buswaypoint")

query = transformed_df.writeStream \
    .foreachBatch(write_batch_to_iceberg) \
    .outputMode("append") \
    .option("checkpointLocation", "s3a://lake/silver/buswaypoint/_checkpoints") \
    .start()

print("Streaming write started. Awaiting termination...")

query.awaitTermination()