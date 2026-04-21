from pyspark.sql import SparkSession
from pyspark.sql.functions import col

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Cleans and deduplicates user data for the Silver layer."""
    print(f"Transforming {source_table} to {target_table}...")

    # 1. Read from Bronze
    df_bronze = spark.read.table(source_table)

    # 2. Cleansing and type enforcement
    df_silver = (
        df_bronze.select(
            col("id").cast("long"),
            "first_name",
            "last_name",
            "email",
            col("age").cast("int"),
            "gender",
            "street_address",
            "postal_code",
            "city",
            "state",
            "country",
            col("latitude").cast("double"),
            col("longitude").cast("double"),
            "traffic_source",
            col("created_at").cast("timestamp"),
            col("updated_at").cast("timestamp")
        )
        .dropDuplicates(["id"])
    )

    # 3. Write to Silver Iceberg
    (
        df_silver.writeTo(target_table)
        .createOrReplace()
    )
    
    print(f"Transformation of users completed.")

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Silver-Transform-Users")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    source = "catalog_iceberg.bronze.users"
    target = "catalog_iceberg.silver.users"
    
    transform_table(spark, source, target)
    
    spark.stop()
