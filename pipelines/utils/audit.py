import uuid
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType, TimestampType

def init_audit_table(spark: SparkSession):
    """Ensures the audit table exists in the Gold layer."""
    audit_table = "catalog_iceberg.gold.pipeline_audit"
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {audit_table} (
            run_id STRING,
            pipeline_name STRING,
            source_table STRING,
            target_table STRING,
            source_count LONG,
            target_count LONG,
            status STRING,
            error_message STRING,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration_seconds DOUBLE
        ) USING iceberg
        PARTITIONED BY (days(start_time))
    """)

def log_audit(spark: SparkSession, pipeline_name: str, source: str, target: str, 
              source_cnt: int, target_cnt: int, status: str, start_ts: datetime, 
              error: str = None):
    """Records pipeline execution metadata to the Iceberg audit table."""
    end_ts = datetime.now()
    duration = (end_ts - start_ts).total_seconds()
    
    schema = StructType([
        StructField("run_id", StringType(), False),
        StructField("pipeline_name", StringType(), False),
        StructField("source_table", StringType(), True),
        StructField("target_table", StringType(), True),
        StructField("source_count", LongType(), True),
        StructField("target_count", LongType(), True),
        StructField("status", StringType(), False),
        StructField("error_message", StringType(), True),
        StructField("start_time", TimestampType(), False),
        StructField("end_time", TimestampType(), False),
        StructField("duration_seconds", DoubleType(), True)
    ])
    
    data = [(
        str(uuid.uuid4()),
        pipeline_name,
        source,
        target,
        source_cnt,
        target_cnt,
        status,
        error,
        start_ts,
        end_ts,
        duration
    )]
    
    df = spark.createDataFrame(data, schema)
    df.writeTo("catalog_iceberg.gold.pipeline_audit").append()
    print(f"[{datetime.now()}] Audit: {pipeline_name} finished with status {status}")
