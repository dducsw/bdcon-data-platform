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
        
        # Kích hoạt Hive
        .enableHiveSupport()
        .getOrCreate()
    )
    
    # Giảm bớt log rác
    spark.sparkContext.setLogLevel("WARN")

    try:
        print("✅ SparkSession Initialized!")
        
        # --- TEST 1: HIVE METASTORE X MINIO ---
        print("\n--- Test 1: Tạo Database & Bảng qua Hive Metastore ---")
        spark.sql("CREATE DATABASE IF NOT EXISTS test_db")
        spark.sql("USE test_db")
        
        # --- TEST 2: GHI DỮ LIỆU ---
        print("\n--- Test 2: Ghi dữ liệu mẫu xuống MinIO ---")
        data = [("Alice", 25, "Data Engineer"), 
                ("Bob", 30, "Data Scientist"), 
                ("Charlie", 28, "DevOps")]
        columns = ["Name", "Age", "Role"]
        
        df = spark.createDataFrame(data, columns)
        print("Dữ liệu đầu vào:")
        df.show()

        table_name = "spark_minio_test"
        table_path = f"s3a://{S3_BUCKET}/test_db/{table_name}"
        
        print(f"Đang ghi Parquet vào: {table_path} ...")
        # Ghi đè bảng nếu đã tồn tại
        spark.sql(f"DROP TABLE IF EXISTS {table_name}")
        df.write.mode("overwrite") \
          .format("parquet") \
          .option("path", table_path) \
          .saveAsTable(table_name)
          
        print("✅ Ghi thành công!")

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
