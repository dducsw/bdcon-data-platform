from pyspark.sql import SparkSession
from pyspark.sql.functions import col

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Cleans and deduplicates order items data for the Silver layer."""
    print(f"Transforming {source_table} to {target_table}...")

    # 1. Read from Bronze
    df_bronze = spark.read.table(source_table)

    # 2. Cleansing and type enforcement
    df_silver = (
        df_bronze.select(
            col("id").cast("long"),
            col("order_id").cast("long"),
            col("user_id").cast("long"),
            col("product_id").cast("long"),
            col("inventory_item_id").cast("long"),
            "status",
            col("sale_price").cast("double"),
            col("created_at").cast("timestamp"),
            col("updated_at").cast("timestamp"),
            col("returned_at").cast("timestamp"),
            col("shipped_at").cast("timestamp"),
            col("delivered_at").cast("timestamp")
        )
        .dropDuplicates(["id"])
    )

    # 3. Write to Silver Iceberg
    (
        df_silver.writeTo(target_table)
        .createOrReplace()
    )
    
    print(f"Transformation of order_items completed.")

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
