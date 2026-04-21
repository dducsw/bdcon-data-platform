from pyspark.sql import SparkSession
from pyspark.sql.functions import col

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Cleans and deduplicates product data for the Silver layer."""
    print(f"Transforming {source_table} to {target_table}...")

    # 1. Read from Bronze
    df_bronze = spark.read.table(source_table)

    # 2. Cleansing and type enforcement
    df_silver = (
        df_bronze.select(
            col("id").cast("long"),
            col("cost").cast("double"),
            "category",
            "name",
            "brand",
            col("retail_price").cast("double"),
            "department",
            "sku",
            col("distribution_center_id").cast("long")
        )
        .dropDuplicates(["id"])
    )

    # 3. Write to Silver Iceberg
    (
        df_silver.writeTo(target_table)
        .createOrReplace()
    )
    
    print(f"Transformation of products completed.")

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Silver-Transform-Products")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    source = "catalog_iceberg.bronze.products"
    target = "catalog_iceberg.silver.products"
    
    transform_table(spark, source, target)
    
    spark.stop()
