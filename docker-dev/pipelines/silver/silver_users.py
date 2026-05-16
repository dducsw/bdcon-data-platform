import sys
import os
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.audit import init_audit_table, log_audit

def transform_table(spark: SparkSession, source_table: str, target_table: str) -> None:
    """Cleans and deduplicates user data for the Silver layer with idempotency."""
    start_ts = datetime.now()
    pipeline_name = "Silver-Users"
    
    print(f"Transforming {source_table} to {target_table}...")
    
    try:
        init_audit_table(spark)
        
        # 1. Create table with explicit schema (SCD Type 2)
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
                updated_at TIMESTAMP,
                is_active BOOLEAN,
                valid_from TIMESTAMP,
                valid_to TIMESTAMP
            ) USING iceberg
            PARTITIONED BY (days(created_at))
            TBLPROPERTIES (
                'write.format.default'='parquet',
                'write.parquet.bloom-filter-enabled.column.email'='true'
            )
        """)

        # 2. Read from Bronze
        df_bronze = spark.read.table(source_table)
        source_cnt = df_bronze.count()

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
        target_cnt = df_silver.count()

        # 4. Upsert (Merge) into Silver Iceberg using SCD Type 2
        df_silver.createOrReplaceTempView("source_users")
        
        spark.sql(f"""
            MERGE INTO {target_table} t
            USING (
                -- 1. New records to insert (merge_key = NULL to force NOT MATCHED)
                -- Includes brand new IDs AND new versions of changed IDs
                SELECT 
                    NULL as merge_key, 
                    s.*, 
                    true as is_active, 
                    current_timestamp() as valid_from, 
                    cast(null as timestamp) as valid_to
                FROM source_users s
                LEFT JOIN {target_table} t ON s.id = t.id AND t.is_active = true
                WHERE t.id IS NULL OR s.source_updated_at > t.source_updated_at
                
                UNION ALL
                
                -- 2. Old records to expire (merge_key = id to force MATCHED)
                SELECT 
                    s.id as merge_key, 
                    s.*, 
                    false as is_active, 
                    t.valid_from as valid_from, 
                    current_timestamp() as valid_to
                FROM source_users s
                JOIN {target_table} t ON s.id = t.id AND t.is_active = true
                WHERE s.source_updated_at > t.source_updated_at
            ) s
            ON t.id = s.merge_key AND t.is_active = true
            
            WHEN MATCHED THEN
                UPDATE SET 
                    is_active = false, 
                    valid_to = s.valid_to
                    
            WHEN NOT MATCHED THEN
                INSERT (id, first_name, last_name, email, age, gender, street_address, postal_code, city, state, country, latitude, longitude, traffic_source, created_at, source_updated_at, updated_at, is_active, valid_from, valid_to)
                VALUES (s.id, s.first_name, s.last_name, s.email, s.age, s.gender, s.street_address, s.postal_code, s.city, s.state, s.country, s.latitude, s.longitude, s.traffic_source, s.created_at, s.source_updated_at, s.updated_at, s.is_active, s.valid_from, s.valid_to)
        """)
        
        log_audit(spark, pipeline_name, source_table, target_table, source_cnt, target_cnt, "SUCCESS", start_ts)
        print(f"Transformation of users completed.")

    except Exception as e:
        log_audit(spark, pipeline_name, source_table, target_table, 0, 0, "FAILED", start_ts, str(e))
        raise e

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
