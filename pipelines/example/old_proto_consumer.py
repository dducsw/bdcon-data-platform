from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, from_unixtime, current_timestamp
from pyspark.sql.protobuf.functions import from_protobuf
from pyspark.storagelevel import StorageLevel


# Khởi tạo SparkSession với Iceberg + Kafka + MinIO
spark = SparkSession.builder \
    .appName("ProtoKafkaIcebergConsumer") \
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

KAFKA_BOOTSTRAP = "kafka-broker-1:29092"
TOPIC = "bus_gps_protobuf"

# Decode protobuf payload
kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP) \
    .option("subscribe", TOPIC) \
    .option("startingOffsets", "earliest") \
    .option("failOnDataLoss", "false") \
    .load()

value_df = kafka_df.selectExpr("CAST(value AS BINARY) AS raw_bytes")
decoded_df = value_df.withColumn(
    "decoded",
    from_protobuf(
        col("raw_bytes"),
        messageName="UFMS.BaseMessage",
        descFilePath="data/ufms.desc"
    )
).select("decoded.*")
decoded_df.printSchema()


# Phân loại theo msgType và ghi vào các bảng Iceberg
bronze_tables = {
    "MsgType_BusWayPoint": "iceberg.bronze.buswaypoint",
    "MsgType_WayPoint": "iceberg.bronze.waypoint",
    "MsgType_StudentCheckInPoint": "iceberg.bronze.studentcheckin",
    "MsgType_RegVehicle": "iceberg.bronze.regvehicle",
    "MsgType_RegDriver": "iceberg.bronze.regdriver",
    "MsgType_RegCompany": "iceberg.bronze.regcompany",
    "MsgType_BusTicketPoint": "iceberg.bronze.busticketpoint",
    "MsgType_BusTicketStartEndPoint": "iceberg.bronze.busticketstartend",
    "MsgType_BusWayPointBatch": "iceberg.bronze.buswaypointbatch"
}

def write_batch_to_iceberg(batch_df, batch_id):
    print("Start write")
    batch_df.persist(StorageLevel.MEMORY_AND_DISK)
    
    try:
        if batch_df.isEmpty():
            return

        rec_count = batch_df.count()
        print(f"[DEBUG] Batch {batch_id}: received {rec_count} records. Showing up to 10 rows:")
        batch_df.show(10, truncate=False)

        # Correctly filter and select fields based on message type enums
        df_buswaypoint = batch_df.filter(col("msgType") == "MsgType_BusWayPoint") \
            .select("msgBusWayPoint.*") \
            .withColumn("datetime", from_unixtime(col("datetime")).cast("timestamp"))  # Explicitly cast to TIMESTAMP

        df_waypoint = batch_df.filter(col("msgType") == "MsgType_WayPoint") \
            .select("msgWayPoint.*") \
            .withColumn("datetime", from_unixtime(col("datetime")).cast("timestamp"))  # Explicitly cast to TIMESTAMP

        df_buswaypoints = batch_df.filter(col("msgType") == "MsgType_BusWayPoints") \
            .selectExpr("explode(msgBusWayPoints.Events) as event") \
            .select("event.*") \
            .withColumn("datetime", from_unixtime(col("datetime")).cast("timestamp"))  # Explicitly cast to TIMESTAMP

        df_buswaypointbatch = batch_df.filter(col("msgType") == "MsgType_BusWayPointBatch") \
            .select("msgBusWayPointBatch.*")

        df_studentcheckin = batch_df.filter(col("msgType") == "MsgType_StudentCheckInPoint") \
            .select("msgStudentCheckInPoint.*")

        df_regvehicle = batch_df.filter(col("msgType") == "MsgType_RegVehicle") \
            .select("msgRegVehicle.*")

        df_regdriver = batch_df.filter(col("msgType") == "MsgType_RegDriver") \
            .select("msgRegDriver.*")

        df_regcompany = batch_df.filter(col("msgType") == "MsgType_RegCompany") \
            .select("msgRegCompany.*")

        df_busticketpoint = batch_df.filter(col("msgType") == "MsgType_BusTicketPoint") \
            .select("msgBusTicketPoint.*")

        df_busticketstartend = batch_df.filter(col("msgType") == "MsgType_BusTicketStartEndPoint") \
            .select("msgBusTicketStartEndPoint.*")

        # Write each filtered DataFrame to its corresponding Iceberg table with commit options
        if not df_buswaypoint.isEmpty():
            df_buswaypoint \
                .withColumn("load_at", current_timestamp()) \
                .writeTo("iceberg.bronze.buswaypoint") \
                .option("commit.manifest.min-count-to-merge", "1") \
                .option("write.metadata.metrics.default", "full") \
                .append()
                
        if not df_waypoint.isEmpty():
            df_waypoint \
                .withColumn("load_at", current_timestamp()) \
                .writeTo("iceberg.bronze.waypoint") \
                .option("commit.manifest.min-count-to-merge", "1") \
                .option("write.metadata.metrics.default", "full") \
                .append()
                
        if not df_buswaypoints.isEmpty():
            df_buswaypoints \
                .withColumn("load_at", current_timestamp()) \
                .writeTo("iceberg.bronze.buswaypoint") \
                .option("commit.manifest.min-count-to-merge", "1") \
                .option("write.metadata.metrics.default", "full") \
                .append()
                
        if not df_buswaypointbatch.isEmpty():
            df_buswaypointbatch \
                .withColumn("load_at", current_timestamp()) \
                .writeTo("iceberg.bronze.buswaypointbatch") \
                .option("commit.manifest.min-count-to-merge", "1") \
                .option("write.metadata.metrics.default", "full") \
                .append()
                
        if not df_studentcheckin.isEmpty():
            df_studentcheckin \
                .withColumn("load_at", current_timestamp()) \
                .writeTo("iceberg.bronze.studentcheckin") \
                .option("commit.manifest.min-count-to-merge", "1") \
                .option("write.metadata.metrics.default", "full") \
                .append()
                
        if not df_regvehicle.isEmpty():
            df_regvehicle \
                .withColumn("load_at", current_timestamp()) \
                .writeTo("iceberg.bronze.regvehicle") \
                .option("commit.manifest.min-count-to-merge", "1") \
                .option("write.metadata.metrics.default", "full") \
                .append()
                
        if not df_regdriver.isEmpty():
            df_regdriver \
                .withColumn("load_at", current_timestamp()) \
                .writeTo("iceberg.bronze.regdriver") \
                .option("commit.manifest.min-count-to-merge", "1") \
                .option("write.metadata.metrics.default", "full") \
                .append()
                
        if not df_regcompany.isEmpty():
            df_regcompany \
                .withColumn("load_at", current_timestamp()) \
                .writeTo("iceberg.bronze.regcompany") \
                .option("commit.manifest.min-count-to-merge", "1") \
                .option("write.metadata.metrics.default", "full") \
                .append()
                
        if not df_busticketpoint.isEmpty():
            df_busticketpoint \
                .withColumn("load_at", current_timestamp()) \
                .writeTo("iceberg.bronze.busticketpoint") \
                .option("commit.manifest.min-count-to-merge", "1") \
                .option("write.metadata.metrics.default", "full") \
                .append()
                
        if not df_busticketstartend.isEmpty():
            df_busticketstartend \
                .withColumn("load_at", current_timestamp()) \
                .writeTo("iceberg.bronze.busticketstartend") \
                .option("commit.manifest.min-count-to-merge", "1") \
                .option("write.metadata.metrics.default", "full") \
                .append()
                
    finally:
        batch_df.unpersist()

print("Starting streaming query...")
query = decoded_df.writeStream \
    .foreachBatch(write_batch_to_iceberg) \
    .option("checkpointLocation", "s3a://lake/checkpoints/bus_gps_protobuf") \
    .trigger(processingTime="5 seconds") \
    .start()

query.awaitTermination()