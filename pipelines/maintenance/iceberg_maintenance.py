from pyspark.sql import SparkSession
import sys

def maintain_table(spark, table_name, strategy="binpack", sort_order=None):
    """
    Performs optimized Iceberg maintenance.
    
    Args:
        spark: SparkSession
        table_name: Fully qualified table name
        strategy: 'binpack' (default) or 'sort'
        sort_order: SQL string for sort order, e.g., 'zorder(col1, col2)'
    """
    print(f"\n--- Maintenance Start: {table_name} ---")
    
    # Configuration options for compaction
    # target-file-size-bytes: 256MB
    # min-input-files: 5 files
    options = "map('target-file-size-bytes', '268435456', 'min-input-files', '5')"
    
    # 1. Compact data files with specific strategy
    print(f"[{table_name}] Compacting data files (Strategy: {strategy})...")
    if strategy == "sort" and sort_order:
        rewrite_query = f"""
            CALL catalog_iceberg.system.rewrite_data_files(
                table => '{table_name}',
                strategy => 'sort',
                sort_order => '{sort_order}',
                options => {options}
            )
        """
    else:
        rewrite_query = f"""
            CALL catalog_iceberg.system.rewrite_data_files(
                table => '{table_name}',
                strategy => 'binpack',
                options => {options}
            )
        """
    spark.sql(rewrite_query)
    
    # 2. Expire old snapshots (Keep last 10 snapshots)
    print(f"[{table_name}] Expiring snapshots...")
    spark.sql(f"CALL catalog_iceberg.system.expire_snapshots(table => '{table_name}', retain_last => 10)")
    
    # 3. Rewrite manifest files
    print(f"[{table_name}] Rewriting manifests...")
    spark.sql(f"CALL catalog_iceberg.system.rewrite_manifests(table => '{table_name}')")
    
    # 4. Remove orphan files (older than 3 days)
    print(f"[{table_name}] Removing orphan files...")
    spark.sql(f"CALL catalog_iceberg.system.remove_orphan_files(table => '{table_name}')")
    
    print(f"--- Maintenance Completed: {table_name} ---\n")

if __name__ == "__main__":
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")
    HIVE_METASTORE_URI = os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083")

    spark = (
        SparkSession.builder
        .appName("Iceberg-Maintenance-Advanced")
        .config("hive.metastore.uris", HIVE_METASTORE_URI)
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .enableHiveSupport()
        .getOrCreate()
    )
    
    # Define table-specific maintenance strategies
    maintenance_config = [
        {"table": "catalog_iceberg.bronze.events", "strategy": "binpack"},
        {"table": "catalog_iceberg.silver.events", "strategy": "binpack"},
        {"table": "catalog_iceberg.silver.users", "strategy": "binpack"},
        {"table": "catalog_iceberg.silver.orders", "strategy": "binpack"},
        {"table": "catalog_iceberg.silver.order_items", "strategy": "binpack"},
        {"table": "catalog_iceberg.gold.sessions", "strategy": "binpack"},
        {"table": "catalog_iceberg.gold.user_statistics", "strategy": "binpack"}
    ]
    
    for cfg in maintenance_config:
        table = cfg["table"]
        try:
            if spark.catalog.tableExists(table):
                maintain_table(
                    spark, 
                    table, 
                    strategy=cfg.get("strategy", "binpack"), 
                    sort_order=cfg.get("sort_order")
                )
            else:
                print(f"Table {table} does not exist. Skipping.")
        except Exception as e:
            print(f"FAILED to maintain {table}: {str(e)}")
            
    spark.stop()
