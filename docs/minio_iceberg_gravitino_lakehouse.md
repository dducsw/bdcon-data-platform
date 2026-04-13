# Developing a Data Lakehouse for Bus GPS Streaming

## Introduction
This document outlines the architecture and rationale for building a modern Data Lakehouse to handle real-time streaming and historical analytics of Bus GPS data. The storage layer leverages **MinIO** as the foundational object storage, **Apache Iceberg** as the open table format, and **Apache Gravitino** as the centralized metadata catalog.

## Architectural Components

### 1. Object Storage Layer: MinIO
MinIO acts as the bedrock of the Data Lakehouse. It is a high-performance, S3-compatible object storage server.

**Role in the Bus GPS Pipeline:**
- **Raw Data Hub:** All raw telemetry data (JSON/Protobuf events from Kafka) is ultimately persisted here.
- **Cost-Effective Storage:** Unlike storing massive amounts of historical GPS data in a traditional relational database (which is expensive and difficult to scale), MinIO provides highly economical long-term storage capable of holding terabytes or petabytes of data.
- **S3 Compatibility:** Since MinIO provides an S3-compatible API, compute engines like Apache Spark or Trino can read from and write to it natively without custom integrations.

### 2. Open Table Format Layer: Apache Iceberg
While MinIO stores the raw data files (typically in columnar formats like Parquet), object storage alone lacks database-like features (e.g., ACID transactions, schema evolution). Apache Iceberg bridges this gap.

**Role in the Bus GPS Pipeline:**
- **Table Abstraction:** Iceberg organizes the raw Parquet files residing in MinIO into logical "tables."
- **Streaming Ingestion & ACID Transactions:** As Spark Structured Streaming consumes the real-time GPS stream from Kafka, it continuously appends records to Iceberg tables. Iceberg ensures these rapid appends are safe and atomic (ACID properties), preventing readers from seeing partially written files.
- **Time Travel & Versioning:** Iceberg maintains snapshots of the data. If a bad batch of GPS data is ingested (e.g., due to a malfunctioning sensor), data engineers can easily "time travel" to a previous snapshot to analyze or restore the state.
- **Schema Evolution:** If a new sensor is added to the buses, Iceberg allows adding this column to the schema safely without rewriting all historical Parquet files.

### 3. Unified Metadata Catalog: Apache Gravitino
In a complex Lakehouse environment, keeping track of where data lives, what its schema is, and how it is organized across different storage systems is challenging. Gravitino acts as a high-performance, unified metadata catalog.

**Role in the Bus GPS Pipeline:**
- **Centralized Metadata Management:** Instead of managing metadata locally within Spark or relying solely on a Hive Metastore, Gravitino provides a RESTful catalog that multiple compute engines can talk to.
- **Interoperability:** Gravitino registers the Iceberg tables stored in MinIO. Consequently, when a data scientist uses a Jupyter Notebook (via Spark) to build an ML model on GPS data, and a data analyst uses Trino/Superset to build historical dashboards, both engines connect to Gravitino to retrieve the exact same table definitions and data locations.
- **REST Catalog Implementation:** Iceberg heavily relies on a catalog to track table state. Using Gravitino as the Iceberg REST Catalog provides a robust, standardized interface compared to older catalog mechanisms.

## Data Flow: From Stream to Lakehouse

1. **Ingestion:** GPS devices on buses send telemetry data to a message broker (Kafka). This acts as the high-throughput buffer.
2. **Stream Processing (Compute):** Apache Spark Structured Streaming consumes events from the Kafka topic (`buswaypoint_json` or protobuf).
3. **Storage (MinIO + Iceberg):** The Spark job transforms the data (e.g., flattens JSON) and writes it out as Parquet files to MinIO. Crucially, it commits these writes to Iceberg tables.
4. **Metadata Update (Gravitino):** The Iceberg commits are registered with the Gravitino REST Catalog, instantly making the fresh data discoverable.
5. **Analytics & BI:** Analytics tools (Trino, Superset, etc.) query Gravitino to find the Iceberg table paths in MinIO, then execute massive parallel reads across the Parquet files to generate historical routing dashboards or calculate long-term KPIs (e.g., average route speeds over the last month).

## Summary
The synergy of **MinIO (Storage)**, **Iceberg (Format)**, and **Gravitino (Catalog)** transforms passive cloud storage into a highly dynamic, transactional Data Lakehouse. This architecture confidently handles the "V"s of Big Data (Volume, Velocity) inherent in streaming Bus GPS data, while providing clean, reliable "tables" for downstream data science and BI applications.
