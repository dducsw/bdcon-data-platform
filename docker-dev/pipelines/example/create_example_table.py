from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, IntegerType, StringType, LongType, TimestampType
from datetime import datetime

CATALOG_NAME = "hive"
SCHEMA_NAME = "schema_iceberg"
TABLE_NAME = "table_iceberg"


def create_table(spark: SparkSession) -> None:
    schema = StructType(
        [
            StructField("id", LongType(), False),
            StructField("name", StringType(), True),
            StructField("age", IntegerType(), True),
            StructField("created_datetime", TimestampType(), True),
        ]
    )

    data = [
        (1, "Alice", 30, datetime.now()),
        (2, "Bob", 25, datetime.now()),
        (3, "Charlie", 35, datetime.now()),
    ]

    (
        spark
        .createDataFrame(data, schema)
        .write.format("iceberg")
        .mode("overwrite")
        .saveAsTable(f"{CATALOG_NAME}.{SCHEMA_NAME}.{TABLE_NAME}")
    )

if __name__ == "__main__":
    
    
    spark = SparkSession.builder.appName("SparkSessionExample").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    create_table(spark)
