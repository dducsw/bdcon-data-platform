# Real-Time theLook eCommerce Data Generator

A real-time data generator for theLook eCommerce platform. Unlike static datasets, this tool generates continuous, real-time event streams directly into a PostgreSQL database, making it ideal for testing Change Data Capture (CDC) pipelines (e.g., Debezium, Kafka) and event-driven architectures.

## ⚙️ Core Features

- **Production-Level Data Integrity**: Guarantees strict referential integrity across all tables (Users -> Orders -> Order Items -> Products/Inventory).
- **Atomic Transactions**: Groups related records (e.g., order, items, inventory allocations, clickstream events) into single atomic database commits to prevent orphaned data.
- **Probabilistic Side Tasks**: Simulates realistic e-commerce behaviors including new account creation, anonymous browsing (ghost events), and order status progression (Processing -> Shipped -> Delivered -> Returned).

## 🚀 Usage

Ensure you have installed the required dependencies from `requirements.txt` and activated your virtual environment.

### 1. Using Makefile (Recommended)

Run the generator easily using predefined `make` commands:

- **Clean & Seed**: Truncates the database, loads base CSV catalogs (products, distribution centers), and seeds 1000 initial users before generating live data.
  ```bash
  make reset-seed-gendata
  ```
- **Start Generator**: Starts generating data with 1000 seeded users (assumes the DB schema is empty but exists).
  ```bash
  make gendata
  ```
- **Resume Generator**: Resumes generating data on top of your existing dataset without creating an initial batch of 1000 users.
  ```bash
  make resume-gendata
  ```

### 2. Using Python CLI

Run the script manually to customize generation parameters, such as QPS and database credentials:

```bash
python thelook-ecomm/generator.py \
  --db-host localhost \
  --db-port 5433 \
  --db-user db_user \
  --db-password db_password \
  --db-name thelook_db \
  --db-schema demo \
  --avg-qps 5 \
  --init-num-users 1000 \
  --max-iter -1
```

### 3. Generating Only Clickstream Events

If you only want to generate high-throughput clickstream events (without progressing orders or modifying inventory), you can use the dedicated `generate_events_only.py` script. This is especially useful for load-testing Kafka or event analytics pipelines.

```bash
python thelook-ecomm/generate_events_only.py \
  --db-host localhost \
  --db-port 5433 \
  --db-user db_user \
  --db-password db_password \
  --db-name thelook_db \
  --db-schema demo \
  --avg-qps 20 \
  --publish-kafka
```

**Key Parameters for Full Generation:**
- `--avg-qps`: Target simulated events per second.
- `--max-iter`: Stop after N iterations (use `-1` for infinite loop).
- `--init-num-users`: Number of users to seed at startup.
- `--user-create-prob` / `--order-update-prob` / `--ghost-create-prob`: Probabilities (0.0 to 1.0) for side tasks like user creation, order updates, and ghost events.

### 4. Publishing to Kafka (Local vs Kubernetes)

When running the generator locally with `--publish-kafka`, you might encounter a **Kafka DNS resolution error** (e.g., `DNS lookup failed for data-platform-kafka-broker-pool-0...`).

**Why this happens:**
Even if you port-forward the Kafka bootstrap server (`localhost:9092`), Kafka brokers return their internal Kubernetes DNS names as their "Advertised Listeners". Your local machine cannot resolve these internal K8s hostnames.

**The Solution:**
The simplest and most robust way to run the generator with Kafka publishing is to run it **inside the Kubernetes cluster** using a temporary pod, so it can natively resolve the Kafka internal DNS:

1. **Create a temporary runner pod:**
   ```bash
   kubectl run datagen-runner --image=python:3.10-slim --restart=Never -n data-platform -- sleep 3600
   kubectl wait --for=condition=Ready pod/datagen-runner -n data-platform --timeout=60s
   ```
2. **Copy the datagen directory into the pod:**
   ```bash
   kubectl cp . data-platform/datagen-runner:/app
   ```
3. **Install dependencies and run:**
   Since the pod is a raw python image, install the required packages the first time, then run your desired script.

   **First time running (with dependency installation):**
   ```bash
   kubectl exec -it datagen-runner -n data-platform -- bash -c "pip install kafka-python sqlalchemy psycopg2-binary faker typing-extensions && python /app/thelook-ecomm/generator.py --publish-kafka --bootstrap-servers data-platform-kafka-kafka-bootstrap:9092 --db-host postgres-source --db-port 5432 --db-user db_user --db-password db_password --db-name thelook_db --db-schema demo"
   ```

   **Subsequent runs (skip pip install):**
   Once the pod has the dependencies installed, you can run the scripts directly:

   *To run the Full Generator:*
   ```bash
   kubectl exec -it datagen-runner -n data-platform -- python /app/thelook-ecomm/generator.py --publish-kafka --bootstrap-servers data-platform-kafka-kafka-bootstrap:9092 --db-host postgres-source --db-port 5432 --db-user db_user --db-password db_password --db-name thelook_db --db-schema demo
   ```

   *To run ONLY Clickstream Events:*
   ```bash
   kubectl exec -it datagen-runner -n data-platform -- python /app/thelook-ecomm/generate_events_only.py --publish-kafka --bootstrap-servers data-platform-kafka-kafka-bootstrap:9092 --db-host postgres-source --db-port 5432 --db-user db_user --db-password db_password --db-name thelook_db --db-schema demo
   ```