import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, col

def ingest_jdbc_to_iceberg(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Ingests data from a PostgreSQL table to an Iceberg table using JDBC."""
    db_host = os.getenv("DB_HOST", "postgres")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "thelook_ecommerce")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    
    jdbc_url = f"jdbc:postgresql://{db_host}:{db_port}/{db_name}"

    print(f"Ingesting {source_table} from Postgres to {target_table}...")

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
            load_at TIMESTAMP
        ) USING iceberg
        PARTITIONED BY (days(created_at))
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
        .option("fetchsize", "10000")
        .load()
    )
    
    # 3. Add metadata and repartition
    if "updated_at" in df.columns:
        df = df.withColumnRenamed("updated_at", "source_updated_at")
        
    df_transformed = (
        df.withColumn("load_at", current_timestamp())
        .repartition(4)
    )
    
    (
        df_transformed.writeTo(target_table)
        .createOrReplace()
    )
    
    print(f"Ingestion of {source_table} completed.")

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Bronze-Ingest-Users")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    source = "users"
    target = "catalog_iceberg.bronze.users"
    
    ingest_jdbc_to_iceberg(spark, source, target)
    
    spark.stop()
