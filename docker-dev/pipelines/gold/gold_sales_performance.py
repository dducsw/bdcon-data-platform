from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, count, date_trunc

def aggregate_data(spark: SparkSession, target_table: str) -> None:
    """Aggregates sales performance data for the Gold layer."""
    print(f"Aggregating data into {target_table}...")

    # 1. Read from Silver
    orders_df = spark.read.table("catalog_iceberg.silver.orders")
    items_df = spark.read.table("catalog_iceberg.silver.order_items")
    products_df = spark.read.table("catalog_iceberg.silver.products")

    # 2. Join and Aggregate
    # Daily sales performance by product category
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
        .orderBy("order_date", "product_category")
    )

    # 3. Write to Gold Iceberg
    (
        gold_df.writeTo(target_table)
        .createOrReplace()
    )
    
    print(f"Aggregation of sales_performance completed.")

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
