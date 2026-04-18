import os
from pyspark.sql import SparkSession

CATALOG_NAME = "hive"
SCHEMA_NAME = "schema_iceberg"
WAREHOUSE_BUCKET = "iceberg"
WAREHOUSE_ROOT = f"s3a://{WAREHOUSE_BUCKET}/lakehouse"


def main():
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    minio_access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
    hive_metastore_uri = os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083")

    print("Initializing SparkSession...")
    spark = (
        SparkSession.builder
        .appName("Test-Spark-Hive-MinIO")
        .config("hive.metastore.uris", hive_metastore_uri)
        .config("spark.hadoop.fs.s3a.endpoint", minio_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", minio_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", minio_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config(f"spark.sql.catalog.{CATALOG_NAME}", "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{CATALOG_NAME}.type", "hive")
        .config(f"spark.sql.catalog.{CATALOG_NAME}.uri", hive_metastore_uri)
        .config(f"spark.sql.catalog.{CATALOG_NAME}.warehouse", WAREHOUSE_ROOT)
        .config(f"spark.sql.catalog.{CATALOG_NAME}.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config(f"spark.sql.catalog.{CATALOG_NAME}.s3.endpoint", minio_endpoint)
        .config(f"spark.sql.catalog.{CATALOG_NAME}.s3.path-style-access", "true")
        .config(f"spark.sql.catalog.{CATALOG_NAME}.s3.access-key-id", minio_access_key)
        .config(f"spark.sql.catalog.{CATALOG_NAME}.s3.secret-access-key", minio_secret_key)
        .config(f"spark.sql.catalog.{CATALOG_NAME}.client.region", "us-east-1")
        .enableHiveSupport()
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    try:
        print("SparkSession initialized")

        print("\n--- Test 1: Create schema in the canonical Iceberg catalog ---")
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")

        print("\n--- Test 2: Write sample data to the canonical catalog ---")
        data = [
            ("Alice", 25, "Data Engineer"),
            ("Bob", 30, "Data Scientist"),
            ("Charlie", 28, "DevOps"),
        ]
        columns = ["Name", "Age", "Role"]

        df = spark.createDataFrame(data, columns)
        print("Input data:")
        df.show()

        table_name = f"{CATALOG_NAME}.{SCHEMA_NAME}.spark_minio_test"
        print(f"Writing Iceberg table to warehouse root {WAREHOUSE_ROOT} ...")
        spark.sql(f"DROP TABLE IF EXISTS {table_name}")
        df.writeTo(table_name).tableProperty("format-version", "2").createOrReplace()
        print("Write successful")

        print("\n--- Test 3: Read back through Hive Metastore -> MinIO ---")
        read_df = spark.sql(f"SELECT * FROM {table_name} WHERE Age > 25")
        read_df.show()

        print("\n--- Test 4: Additional Iceberg table in the same catalog/schema ---")
        iceberg_table = f"{CATALOG_NAME}.{SCHEMA_NAME}.spark_iceberg_test"
        print(f"Creating Iceberg table: {iceberg_table} ...")
        df.writeTo(iceberg_table).tableProperty("format-version", "2").createOrReplace()

        print("Data read back from Iceberg:")
        spark.sql(f"SELECT * FROM {iceberg_table}").show()

        print("\n--- Test 5: Update Iceberg data (ACID) ---")
        print("Incrementing Alice age by 1...")
        spark.sql(f"UPDATE {iceberg_table} SET Age = Age + 1 WHERE Name = 'Alice'")

        print("Data after update:")
        spark.sql(f"SELECT * FROM {iceberg_table}").show()

        print("All tests passed")

    except Exception as e:
        print("Error while running tests:", str(e))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
