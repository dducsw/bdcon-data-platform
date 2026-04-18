-- TheLook E-Commerce Database Schema
-- Matches the schema defined in ingest_csv.py

CREATE DATABASE thelook_ecommerce;

DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS inventory_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS distribution_centers CASCADE;

-- Distribution Centers
CREATE TABLE distribution_centers (
    id BIGINT PRIMARY KEY,
    name TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);

-- Products
-- updated_at is used by dbt SCD2 snapshot (snap_products.sql)
CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    cost DOUBLE PRECISION,
    category TEXT,
    name TEXT,
    brand TEXT,
    retail_price DOUBLE PRECISION,
    department TEXT,
    sku TEXT,
    distribution_center_id BIGINT,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    age INT,
    gender TEXT,
    state TEXT,
    street_address TEXT,
    postal_code TEXT,
    city TEXT,
    country TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    traffic_source TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Orders
CREATE TABLE orders (
    order_id BIGINT PRIMARY KEY,
    user_id BIGINT,
    status TEXT,
    gender TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    returned_at TIMESTAMP WITHOUT TIME ZONE,
    shipped_at TIMESTAMP WITHOUT TIME ZONE,
    delivered_at TIMESTAMP WITHOUT TIME ZONE,
    num_of_item INT
);

-- Inventory Items
CREATE TABLE inventory_items (
    id BIGINT PRIMARY KEY,
    product_id BIGINT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    sold_at TIMESTAMP WITHOUT TIME ZONE,
    cost DOUBLE PRECISION,
    product_category TEXT,
    product_name TEXT,
    product_brand TEXT,
    product_retail_price DOUBLE PRECISION,
    product_department TEXT,
    product_sku TEXT,
    product_distribution_center_id BIGINT
);

-- Order Items
CREATE TABLE order_items (
    id BIGINT PRIMARY KEY,
    order_id BIGINT,
    user_id BIGINT,
    product_id BIGINT,
    inventory_item_id BIGINT,
    status TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    shipped_at TIMESTAMP WITHOUT TIME ZONE,
    delivered_at TIMESTAMP WITHOUT TIME ZONE,
    returned_at TIMESTAMP WITHOUT TIME ZONE,
    sale_price DOUBLE PRECISION
);

-- Events
CREATE TABLE events (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    sequence_number INT,
    session_id TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    ip_address TEXT,
    city TEXT,
    state TEXT,
    postal_code TEXT,
    browser TEXT,
    traffic_source TEXT,
    uri TEXT,
    event_type TEXT
);


