from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Cleans and deduplicates inventory items data for the Silver layer."""
    print(f"Transforming {source_table} to {target_table}...")

    # 1. Create table with explicit schema and partitioning
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {target_table} (
            id BIGINT,
            product_id BIGINT,
            created_at TIMESTAMP,
            sold_at TIMESTAMP,
            cost DOUBLE,
            product_category STRING,
            product_name STRING,
            product_brand STRING,
            product_retail_price DOUBLE,
            product_department STRING,
            product_sku STRING,
            product_distribution_center_id BIGINT,
            updated_at TIMESTAMP
        ) USING iceberg
        PARTITIONED BY (days(created_at))
    """)

    # 2. Read from Bronze
    df_bronze = spark.read.table(source_table)

    # 3. Transform and metadata
    df_silver = (
        df_bronze.select(
            col("id").cast("long"),
            col("product_id").cast("long"),
            col("created_at").cast("timestamp"),
            col("sold_at").cast("timestamp"),
            col("cost").cast("double"),
            "product_category",
            "product_name",
            "product_brand",
            col("product_retail_price").cast("double"),
            "product_department",
            "product_sku",
            col("product_distribution_center_id").cast("long")
        )
        .withColumn("updated_at", current_timestamp())
        .dropDuplicates(["id"])
    )

    # 4. Write to Silver Iceberg
    (
        df_silver.writeTo(target_table)
        .append()
    )
    
    print(f"Transformation of inventory_items completed.")

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Silver-Transform-Inventory-Items")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    source = "catalog_iceberg.bronze.inventory_items"
    target = "catalog_iceberg.silver.inventory_items"
    
    transform_table(spark, source, target)
    
    spark.stop()
