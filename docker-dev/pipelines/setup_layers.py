from pyspark.sql import SparkSession

def initialize_namespaces(spark: SparkSession) -> None:
    """Creates the medallion architecture namespaces in the Iceberg catalog."""
    catalog = "catalog_iceberg"
    layers = ["bronze", "silver", "gold"]
    
    for layer in layers:
        print(f"Creating namespace: {catalog}.{layer}")
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {catalog}.{layer}")
    
    print("Listing namespaces in catalog:")
    spark.sql(f"SHOW NAMESPACES IN {catalog}").show()

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("Setup-Medallion-Layers")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")
    
    initialize_namespaces(spark)
    
    spark.stop()
