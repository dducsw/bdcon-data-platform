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

**Key Parameters:**
- `--avg-qps`: Target simulated events per second.
- `--max-iter`: Stop after N iterations (use `-1` for infinite loop).
- `--init-num-users`: Number of users to seed at startup.
- `--user-create-prob` / `--order-update-prob` / `--ghost-create-prob`: Probabilities (0.0 to 1.0) for side tasks like user creation, order updates, and ghost events.