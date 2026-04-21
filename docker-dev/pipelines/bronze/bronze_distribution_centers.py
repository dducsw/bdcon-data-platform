import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp

def ingest_jdbc_to_iceberg(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Ingests data from a PostgreSQL table to an Iceberg table using JDBC."""
    db_host = os.getenv("DB_HOST", "postgres")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "thelook_ecommerce")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    
    jdbc_url = f"jdbc:postgresql://{db_host}:{db_port}/{db_name}"

    print(f"Ingesting {source_table} from Postgres to {target_table}...")

    # 1. Create table with explicit schema (No partitioning for DC)
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {target_table} (
            id BIGINT,
            name STRING,
            latitude DOUBLE,
            longitude DOUBLE,
            load_at TIMESTAMP
        ) USING iceberg
    """)

    # 2. Read from Postgres
    df = (
        spark.read
        .format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", f"public.{source_table}")
        .option("user", db_user)
        .option("password", db_password)
        .option("driver", "org.postgresql.Driver")
        .load()
    )
    
    # 3. Add metadata and write
    df_with_metadata = df.withColumn("load_at", current_timestamp())
    
    (
        df_with_metadata.writeTo(target_table)
        .append()
    )
    
    print(f"Ingestion of {source_table} completed.")

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Bronze-Ingest-Distribution-Centers")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    source = "distribution_centers"
    target = "catalog_iceberg.bronze.distribution_centers"
    
    ingest_jdbc_to_iceberg(spark, source, target)
    
    spark.stop()
