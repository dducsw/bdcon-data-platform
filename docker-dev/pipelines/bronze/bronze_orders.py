import os
from pyspark.sql import SparkSession
from schemas import ORDER_SCHEMA_DDL

def ingest_jdbc_to_iceberg(spark: SparkSession, source_table: str, target_table: str, schema_ddl: str = None) -> None:
    """Ingests data from a PostgreSQL table to an Iceberg table using JDBC."""
    db_host = os.getenv("DB_HOST", "postgres")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "fh_dev")
    db_user = os.getenv("DB_USER", "db_user")
    db_password = os.getenv("DB_PASSWORD", "db_password")
    
    jdbc_url = f"jdbc:postgresql://{db_host}:{db_port}/{db_name}"

    print(f"Ingesting {source_table} from Postgres to {target_table}...")

    # 1. Read from Postgres
    reader = (
        spark.read
        .format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", f"public.{source_table}")
        .option("user", db_user)
        .option("password", db_password)
        .option("driver", "org.postgresql.Driver")
    )
    
    if schema_ddl:
        reader = reader.option("customSchema", schema_ddl)
    
    df = reader.load()

    # 2. Write to Iceberg
    (
        df.writeTo(target_table)
        .createOrReplace()
    )
    
    print(f"Ingestion of {source_table} completed.")

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Bronze-Ingest-Orders")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    source = "orders"
    target = "catalog_iceberg.bronze.orders"
    
    ingest_jdbc_to_iceberg(spark, source, target, ORDER_SCHEMA_DDL)
    
    spark.stop()
