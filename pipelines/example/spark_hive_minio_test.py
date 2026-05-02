import os
from pyspark.sql import SparkSession

def main():
    # Các cấu hình mặc định (có thể được ghi đè bằng Biến môi trường nếu chạy trên Airflow/K8s)
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    HIVE_METASTORE_URI = os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083")
    
    # Bucket S3 lưu trữ dữ liệu (đảm bảo bạn đã tạo bucket này trên MinIO)
    S3_BUCKET = "datalake"

    print("🚀 Initializing SparkSession...")
    spark = (
        SparkSession.builder
        .appName("Test-Spark-Hive-MinIO")
        
        # 1. Cấu hình Hive Metastore
        .config("hive.metastore.uris", HIVE_METASTORE_URI)
        
        # 2. Cấu hình MinIO (S3A) thay cho HDFS
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")      # Quan trọng với MinIO
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") # MinIO chạy HTTP nội bộ
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        
        # 3. Cấu hình Apache Iceberg
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkSessionCatalog")
        .config("spark.sql.catalog.spark_catalog.type", "hive")
        .config("spark.sql.catalog.catalog_iceberg", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.catalog_iceberg.type", "hive")
        .config("spark.sql.catalog.catalog_iceberg.uri", HIVE_METASTORE_URI)
        .config("spark.sql.catalog.catalog_iceberg.warehouse", f"s3a://{S3_BUCKET}/warehouse")
        
        # Kích hoạt Hive
        .enableHiveSupport()
        .getOrCreate()
    )
    
    # Giảm bớt log rác
    spark.sparkContext.setLogLevel("WARN")

    try:
        print("✅ SparkSession with Iceberg Initialized!")
        
        # --- TEST 1: HIVE METASTORE X MINIO ---
        print("\n--- Test 1: Tạo Database & Bảng Iceberg ---")
        # Sử dụng catalog_iceberg để tạo database
        spark.sql("CREATE DATABASE IF NOT EXISTS catalog_iceberg.test_db")
        
        # --- TEST 2: GHI DỮ LIỆU ICEBERG ---
        print("\n--- Test 2: Ghi dữ liệu Iceberg xuống MinIO ---")
        data = [("Alice", 25, "Data Engineer"), 
                ("Bob", 30, "Data Scientist"), 
                ("Charlie", 28, "DevOps")]
        columns = ["Name", "Age", "Role"]
        
        df = spark.createDataFrame(data, columns)
        
        # Tên bảng Iceberg đầy đủ (Catalog.Database.Table)
        table_name = "catalog_iceberg.test_db.spark_iceberg_test"
        
        print(f"Đang ghi Iceberg vào: {table_name} ...")
        # Ghi bằng phương thức v2 writeTo
        df.writeTo(table_name).createOrReplace()
          
        print("✅ Ghi Iceberg thành công!")

        # --- TEST 3: ĐỌC DỮ LIỆU ---
        print("\n--- Test 3: Truy vấn lại dữ liệu bằng Spark SQL (đọc từ Hive -> MinIO) ---")
        read_df = spark.sql(f"SELECT * FROM {table_name} WHERE Age > 25")
        read_df.show()

        print("🎉 TẤT CẢ TEST ĐÃ PASS!")

    except Exception as e:
        print("❌ LỖI TRONG QUÁ TRÌNH CHẠY:", str(e))
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
