import sys
import os
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, count, date_trunc, current_timestamp

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.audit import init_audit_table, log_audit

def aggregate_data(spark: SparkSession, target_table: str) -> None:
    """Aggregates sales performance data for the Gold layer with idempotency."""
    start_ts = datetime.now()
    pipeline_name = "Gold-Sales-Performance"
    source_desc = "silver.orders, silver.order_items, silver.products"
    
    print(f"Aggregating data into {target_table}...")
    
    try:
        init_audit_table(spark)
        
        # 1. Create table with explicit schema and partitioning
        spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {target_table} (
                order_date TIMESTAMP,
                product_category STRING,
                total_revenue DOUBLE,
                total_items_sold LONG,
                updated_at TIMESTAMP
            ) USING iceberg
            PARTITIONED BY (days(order_date))
            TBLPROPERTIES (
                'write.format.default'='parquet',
                'write.distribution-mode'='hash'
            )
        """)
        spark.sql(f"ALTER TABLE {target_table} WRITE ORDERED BY product_category")

        # 2. Read from Silver
        orders_df = spark.read.table("catalog_iceberg.silver.orders")
        items_df = spark.read.table("catalog_iceberg.silver.order_items")
        products_df = spark.read.table("catalog_iceberg.silver.products")
        source_cnt = orders_df.count() # Using orders as primary source count

        # 3. Join and Aggregate
        gold_df = (
            items_df.alias("i")
            .join(orders_df.alias("o"), col("i.order_id") == col("o.order_id"))
            .join(products_df.alias("p"), col("i.product_id") == col("p.id"))
            .select(
                date_trunc("day", col("o.created_at")).alias("order_date"),
                col("p.category").alias("product_category"),
                col("i.sale_price")
            )
            .groupBy("order_date", "product_category")
            .agg(
                sum("sale_price").alias("total_revenue"),
                count("*").alias("total_items_sold")
            )
            .withColumn("updated_at", current_timestamp())
        )
        target_cnt = gold_df.count()

        # 4. Upsert (Merge) into Gold Iceberg
        gold_df.createOrReplaceTempView("source_sales")
        
        spark.sql(f"""
            MERGE INTO {target_table} t
            USING source_sales s
            ON t.order_date = s.order_date AND t.product_category = s.product_category
            WHEN MATCHED THEN
                UPDATE SET *
            WHEN NOT MATCHED THEN
                INSERT *
        """)
        
        log_audit(spark, pipeline_name, source_desc, target_table, source_cnt, target_cnt, "SUCCESS", start_ts)
        print(f"Aggregation of sales_performance completed.")

    except Exception as e:
        log_audit(spark, pipeline_name, source_desc, target_table, 0, 0, "FAILED", start_ts, str(e))
        raise e

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Gold-Agg-Sales-Performance")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    target = "catalog_iceberg.gold.sales_performance"
    
    aggregate_data(spark, target)
    
    spark.stop()
