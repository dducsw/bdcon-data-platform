# Redis over Real-time Bus GPS Dashboard Serving Layer

## Introduction
This document outlines the architecture and implementation details of using Redis as the primary serving layer for the Real-time Bus GPS Dashboard. The objective of this serving layer is to ingest high-throughput, low-latency streaming data from Kafka and serve it efficiently to client applications (e.g., a live map dashboard).

## Architecture Overview
The data flow follows a standard real-time streaming pipeline:

1.  **Data Source:** Bus GPS coordinates and telemetry data (speed, ignition, aircon, etc.) are generated and ingested.
2.  **Message Broker (Kafka):** Raw events are published to a Kafka topic (`buswaypoint_json`), acting as a durable buffer and streaming platform.
3.  **Stream Processor / Consumer:** A Python consumer script (`kafka_to_redis.py`) constantly listens to the Kafka topic.
4.  **Serving Layer (Redis):** The consumer processes the events and pushes them into Redis using specific data structures optimized for different querying patterns.
5.  **Client Dashboard:** The front-end application queries Redis to render the live positions of all active buses and historical trails if needed.

## Redis Data Structures
To fully leverage Redis's capabilities for this specific use case, we utilize two distinct data structures:

### 1. Redis Streams (`XADD`)
-   **Key:** `buswaypoint_stream`
-   **Purpose:** To store the continuous time-series flow of bus waypoint events.
-   **Usage:** 
    -   Ideal for event sourcing and pub/sub patterns.
    -   Clients can subscribe to this stream using `XREAD` or `XREADGROUP` to receive real-time updates as they happen, effectively creating a live feed.
    -   The stream is capped (e.g., `maxlen=100000`) to prevent infinite memory growth, ensuring only the most recent events are kept in the hot memory layer.

### 2. Redis Hashes (`HSET`)
-   **Key Pattern:** `buswaypoint_latest:<vehicle_id>`
-   **Purpose:** To store the absolute latest known state (location, speed, etc.) of each individual vehicle.
-   **Usage:**
    -   When a dashboard first loads, it doesn't necessarily need the entire history; it just needs to know *where every bus is right now*.
    -   Hashes provide $\mathcal{O}(1)$ time complexity for lookups. A client can quickly fetch the latest state of a specific bus using `HGETALL buswaypoint_latest:<vehicle_id>`, or fetch all active buses using pattern matching (e.g., `SCAN` with `MATCH buswaypoint_latest:*`).
    -   This structure is highly optimized for the "current state" view.

## Why Redis?
-   **In-Memory Speed:** Redis operates entirely in memory, offering sub-millisecond read and write latencies, which is crucial for a smooth real-time dashboard experience.
-   **Tailored Data Structures:** Features like Streams and Hashes explicitly solve the dual problem of tracking history (Streams) and tracking the current state (Hashes) without complex relational joins.
-   **Scalability:** Redis can handle tens of thousands of operations per second, easily matching the high throughput of IoT GPS data.

## Implementation Details
The synchronization from Kafka to Redis is handled by the `KafkaToRedisConsumer` Python application.

Key features of the implementation include:
-   **Graceful Shutdown:** Ensures no data is left hanging during intentional restarts.
-   **Checkpointing:** Periodically saves the consumer's offset to disk (e.g., every 500 messages). If the pipeline crashes, it resumes from the exact last saved offset, preventing data duplication or loss.
-   **Batch Processing:** The consumer fetches data in batches from Kafka to optimize network I/O, but pushes to Redis individually for absolute real-time availability.

## Conclusion
By utilizing Redis as the serving layer bridging Kafka and the front-end dashboard, the architecture achieves a highly performant, scalable, and resilient solution for tracking thousands of moving buses in real-time.
