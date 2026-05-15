from pyspark.sql import SparkSession
from pyspark.sql.functions import max as spark_max
from datetime import datetime

def get_watermark(spark: SparkSession, pipeline_name: str):
    """Retrieves the last processed watermark for a pipeline."""
    watermark_table = "catalog_iceberg.gold.pipeline_watermarks"
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {watermark_table} (
            pipeline_name STRING,
            last_watermark TIMESTAMP,
            updated_at TIMESTAMP
        ) USING iceberg
    """)
    
    df = spark.sql(f"SELECT last_watermark FROM {watermark_table} WHERE pipeline_name = '{pipeline_name}'")
    row = df.first()
    # If no watermark exists, return a very old date
    return row['last_watermark'] if row else datetime(1970, 1, 1)

def update_watermark(spark: SparkSession, pipeline_name: str, watermark_value):
    """Updates the watermark for a pipeline using MERGE for idempotency."""
    watermark_table = "catalog_iceberg.gold.pipeline_watermarks"
    
    data = [(pipeline_name, watermark_value, datetime.now())]
    df = spark.createDataFrame(data, ["pipeline_name", "last_watermark", "updated_at"])
    df.createOrReplaceTempView("source_watermark")
    
    spark.sql(f"""
        MERGE INTO {watermark_table} t
        USING source_watermark s
        ON t.pipeline_name = s.pipeline_name
        WHEN MATCHED THEN
            UPDATE SET 
                t.last_watermark = s.last_watermark,
                t.updated_at = s.updated_at
        WHEN NOT MATCHED THEN
            INSERT (pipeline_name, last_watermark, updated_at)
            VALUES (s.pipeline_name, s.last_watermark, s.updated_at)
    """)
