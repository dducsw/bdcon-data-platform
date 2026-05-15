import sys
import os
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.audit import init_audit_table, log_audit

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Cleans and deduplicates order item data for the Silver layer with idempotency."""
    start_ts = datetime.now()
    pipeline_name = "Silver-Order-Items"
    
    print(f"Transforming {source_table} to {target_table}...")
    
    try:
        init_audit_table(spark)
        
        # 1. Create table with explicit schema
        spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {target_table} (
                id BIGINT,
                order_id BIGINT,
                user_id BIGINT,
                product_id BIGINT,
                inventory_item_id BIGINT,
                status STRING,
                created_at TIMESTAMP,
                source_updated_at TIMESTAMP,
                shipped_at TIMESTAMP,
                delivered_at TIMESTAMP,
                returned_at TIMESTAMP,
                sale_price DOUBLE,
                updated_at TIMESTAMP
            ) USING iceberg
            PARTITIONED BY (days(created_at))
            TBLPROPERTIES (
                'write.format.default'='parquet',
                'write.distribution-mode'='hash'
            )
        """)
        spark.sql(f"ALTER TABLE {target_table} WRITE ORDERED BY order_id, product_id")

        # 2. Read from Bronze
        df_bronze = spark.read.table(source_table)
        source_cnt = df_bronze.count()

        # 3. Cleansing and metadata
        df_silver = (
            df_bronze.select(
                col("id").cast("long"),
                col("order_id").cast("long"),
                col("user_id").cast("long"),
                col("product_id").cast("long"),
                col("inventory_item_id").cast("long"),
                "status",
                col("created_at").cast("timestamp"),
                col("source_updated_at").cast("timestamp"),
                col("shipped_at").cast("timestamp"),
                col("delivered_at").cast("timestamp"),
                col("returned_at").cast("timestamp"),
                col("sale_price").cast("double")
            )
            .withColumn("updated_at", current_timestamp())
        )
        target_cnt = df_silver.count()

        # 4. Upsert (Merge) into Silver Iceberg
        df_silver.createOrReplaceTempView("source_order_items")
        
        spark.sql(f"""
            MERGE INTO {target_table} t
            USING source_order_items s
            ON t.id = s.id
            WHEN MATCHED THEN
                UPDATE SET *
            WHEN NOT MATCHED THEN
                INSERT *
        """)
        
        log_audit(spark, pipeline_name, source_table, target_table, source_cnt, target_cnt, "SUCCESS", start_ts)
        print(f"Transformation of order_items completed.")

    except Exception as e:
        log_audit(spark, pipeline_name, source_table, target_table, 0, 0, "FAILED", start_ts, str(e))
        raise e

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Silver-Transform-Order-Items")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    source = "catalog_iceberg.bronze.order_items"
    target = "catalog_iceberg.silver.order_items"
    
    transform_table(spark, source, target)
    
    spark.stop()
