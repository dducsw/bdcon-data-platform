from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Cleans and deduplicates user data for the Silver layer."""
    print(f"Transforming {source_table} to {target_table}...")

    # 1. Create table with explicit schema (source_updated_at for business)
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {target_table} (
            id BIGINT,
            first_name STRING,
            last_name STRING,
            email STRING,
            age INT,
            gender STRING,
            street_address STRING,
            postal_code STRING,
            city STRING,
            state STRING,
            country STRING,
            latitude DOUBLE,
            longitude DOUBLE,
            traffic_source STRING,
            created_at TIMESTAMP,
            source_updated_at TIMESTAMP,
            updated_at TIMESTAMP
        ) USING iceberg
        PARTITIONED BY (days(created_at))
    """)

    # 2. Read from Bronze
    df_bronze = spark.read.table(source_table)

    # 3. Cleansing and metadata
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
            col("source_updated_at").cast("timestamp")
        )
        .withColumn("updated_at", current_timestamp())
        .dropDuplicates(["id"])
    )

    # 4. Write to Silver Iceberg
    (
        df_silver.writeTo(target_table)
        .append()
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
