from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    LongType,
    DoubleType,
    TimestampType,
)

# User Schema
USER_SCHEMA = StructType([
    StructField("id", LongType(), False),
    StructField("first_name", StringType(), True),
    StructField("last_name", StringType(), True),
    StructField("email", StringType(), True),
    StructField("age", IntegerType(), True),
    StructField("gender", StringType(), True),
    StructField("street_address", StringType(), True),
    StructField("postal_code", StringType(), True),
    StructField("city", StringType(), True),
    StructField("state", StringType(), True),
    StructField("country", StringType(), True),
    StructField("latitude", DoubleType(), True),
    StructField("longitude", DoubleType(), True),
    StructField("traffic_source", StringType(), True),
    StructField("created_at", TimestampType(), True),
    StructField("updated_at", TimestampType(), True),
])

# Order Schema
ORDER_SCHEMA = StructType([
    StructField("order_id", LongType(), False),
    StructField("user_id", LongType(), True),
    StructField("status", StringType(), True),
    StructField("gender", StringType(), True),
    StructField("created_at", TimestampType(), True),
    StructField("updated_at", TimestampType(), True),
    StructField("returned_at", TimestampType(), True),
    StructField("shipped_at", TimestampType(), True),
    StructField("delivered_at", TimestampType(), True),
    StructField("num_of_item", IntegerType(), True),
])

# Order Item Schema
ORDER_ITEM_SCHEMA = StructType([
    StructField("id", LongType(), False),
    StructField("order_id", LongType(), True),
    StructField("user_id", LongType(), True),
    StructField("product_id", LongType(), True),
    StructField("inventory_item_id", LongType(), True),
    StructField("status", StringType(), True),
    StructField("created_at", TimestampType(), True),
    StructField("updated_at", TimestampType(), True),
    StructField("shipped_at", TimestampType(), True),
    StructField("delivered_at", TimestampType(), True),
    StructField("returned_at", TimestampType(), True),
    StructField("sale_price", DoubleType(), True),
])

# Product Schema
PRODUCT_SCHEMA = StructType([
    StructField("id", LongType(), False),
    StructField("cost", DoubleType(), True),
    StructField("category", StringType(), True),
    StructField("name", StringType(), True),
    StructField("brand", StringType(), True),
    StructField("retail_price", DoubleType(), True),
    StructField("department", StringType(), True),
    StructField("sku", StringType(), True),
    StructField("distribution_center_id", LongType(), True),
])

# Event Schema (Kafka Payload)
EVENT_SCHEMA = StructType([
    StructField("id", LongType(), False),
    StructField("user_id", LongType(), True),
    StructField("sequence_number", IntegerType(), True),
    StructField("session_id", StringType(), True),
    StructField("ip_address", StringType(), True),
    StructField("city", StringType(), True),
    StructField("state", StringType(), True),
    StructField("postal_code", StringType(), True),
    StructField("browser", StringType(), True),
    StructField("traffic_source", StringType(), True),
    StructField("uri", StringType(), True),
    StructField("event_type", StringType(), True),
    StructField("created_at", TimestampType(), True),
])

# Distribution Center Schema
DISTRIBUTION_CENTER_SCHEMA = StructType([
    StructField("id", LongType(), False),
    StructField("name", StringType(), True),
    StructField("latitude", DoubleType(), True),
    StructField("longitude", DoubleType(), True),
])

# Inventory Item Schema
INVENTORY_ITEM_SCHEMA = StructType([
    StructField("id", LongType(), False),
    StructField("product_id", LongType(), True),
    StructField("created_at", TimestampType(), True),
    StructField("sold_at", TimestampType(), True),
    StructField("cost", DoubleType(), True),
    StructField("product_category", StringType(), True),
    StructField("product_name", StringType(), True),
    StructField("product_brand", StringType(), True),
    StructField("product_retail_price", DoubleType(), True),
    StructField("product_department", StringType(), True),
    StructField("product_sku", StringType(), True),
    StructField("product_distribution_center_id", LongType(), True),
])

# DDL Strings for JDBC customSchema
USER_SCHEMA_DDL = "id BIGINT, first_name STRING, last_name STRING, email STRING, age INT, gender STRING, street_address STRING, postal_code STRING, city STRING, state STRING, country STRING, latitude DOUBLE, longitude DOUBLE, traffic_source STRING, created_at TIMESTAMP, updated_at TIMESTAMP"
ORDER_SCHEMA_DDL = "order_id BIGINT, user_id BIGINT, status STRING, gender STRING, created_at TIMESTAMP, updated_at TIMESTAMP, returned_at TIMESTAMP, shipped_at TIMESTAMP, delivered_at TIMESTAMP, num_of_item INT"
ORDER_ITEM_SCHEMA_DDL = "id BIGINT, order_id BIGINT, user_id BIGINT, product_id BIGINT, inventory_item_id BIGINT, status STRING, created_at TIMESTAMP, updated_at TIMESTAMP, shipped_at TIMESTAMP, delivered_at TIMESTAMP, returned_at TIMESTAMP, sale_price DOUBLE"
PRODUCT_SCHEMA_DDL = "id BIGINT, cost DOUBLE, category STRING, name STRING, brand STRING, retail_price DOUBLE, department STRING, sku STRING, distribution_center_id BIGINT"
DISTRIBUTION_CENTER_SCHEMA_DDL = "id BIGINT, name STRING, latitude DOUBLE, longitude DOUBLE"
INVENTORY_ITEM_SCHEMA_DDL = "id BIGINT, product_id BIGINT, created_at TIMESTAMP, sold_at TIMESTAMP, cost DOUBLE, product_category STRING, product_name STRING, product_brand STRING, product_retail_price DOUBLE, product_department STRING, product_sku STRING, product_distribution_center_id BIGINT"
