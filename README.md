# 🌊 Modern Data Platform on Kubernetes (Lakehouse)

[![Stack](https://img.shields.io/badge/Stack-Lakehouse-blue.svg)](#-technology-stack)
[![Cloud](https://img.shields.io/badge/Cloud-GKE-blue.svg)](#-infrastructure--cost-optimization)
[![Cost](https://img.shields.io/badge/Strategy-100%25_Spot_Instances-green.svg)](#-infrastructure--cost-optimization)

A comprehensive, cost-optimized Modern Data Platform built on **Google Kubernetes Engine (GKE)**. This project implements a full-stack, open-source data infrastructure managed via **Terraform**, optimized for high-scale processing using a **100% Spot Instances** strategy and **GKE Autoscaler** to reduce infrastructure costs by **70%**.

---

## 🏛️ Architecture & Key Highlights

The platform leverages a **Lakehouse architecture**, combining the cost-efficiency and flexibility of a Data Lake with the performance and ACID guarantees of a Data Warehouse.

### 🚀 Key Achievements:
- **Infrastructure as Code (IaC)**: Fully automated deployment using **Terraform**, managing a cluster of 3 VMs with specialized node pools (Compute for Spark, Query for Trino).
- **Extreme Cost Optimization**: Achieved a **70% cost reduction** compared to standard instances through aggressive Spot Instance utilization and horizontal pod autoscaling.
- **Advanced ETL Pipelines**: Implemented a complete **Medallion Architecture** (Bronze, Silver, Gold) supporting E-commerce analytics, product performance, and real-time clickstream behavior.
- **Rigorous Benchmarking**: Executed **TPC-DS (Scale Factor 50, 50GB)** benchmarks to evaluate Trino and Apache Spark on query latency and resource utilization.

### Core Design Principles:
- **Decoupled Compute & Storage**: Independent scaling of processing power (Spark/Trino) and data storage (MinIO/S3).
- **Open Standards**: Built entirely on open-source technologies (Iceberg, Spark, Trino, Kafka).
- **Reliability & Idempotency**: Advanced data pipelines featuring **Audit Layer**, **Watermark logic**, and **Iceberg MERGE INTO** for zero data loss and guaranteed idempotency.

---

## 🛠️ Technology Stack

| Layer | Component | Description |
| :--- | :--- | :--- |
| **Storage** | [MinIO](https://min.io/) | S3-compatible Object Storage for raw and processed data. |
| **Table Format** | [Apache Iceberg](https://iceberg.apache.org/) | High-performance open table format for huge analytic datasets. |
| **Catalog** | [Gravitino](https://gravitino.apache.org/) | Iceberg REST Catalog for unified metadata management. |
| **Processing** | [Apache Spark](https://spark.apache.org/) | Batch and streaming processing via Spark-on-K8s Operator. |
| **Streaming** | [Apache Kafka](https://kafka.apache.org/) | Real-time event streaming managed by Strimzi Operator. |
| **SQL Engine** | [Trino](https://trino.io/) | Distributed SQL query engine for ad-hoc analytics. |
| **Orchestration** | [Apache Airflow](https://airflow.apache.org/) | Workflow management for complex data pipelines. |
| **BI & Viz** | [Apache Superset](https://superset.apache.org/) | Modern data exploration and dashboarding platform. |
| **Monitoring** | [Prometheus](https://prometheus.io/) & [Grafana](https://grafana.com/) | Full-stack observability and alerting. |

---

## 📂 Repository Structure

The repository is strictly organized to separate infrastructure logic from application manifests and operational documentation.

```bash
k8s-data-platform/
├── assets/                  # Diagrams, images, and static resources
├── datagen/                 # Custom data generators for testing and demos
├── docs/                    # 📚 Deep documentation, ADRs, and Runbooks
│   ├── architecture/        
│   ├── decisions/           
│   └── runbooks/            
├── docker-dev/              # 🐳 Standalone Docker Compose environment for local testing
├── helm-values/             # Standardized Helm chart configurations
├── k8s/                     # Kubernetes manifests (Kustomize based)
│   ├── base/                
│   └── overlays/            
├── notebooks/               # Data exploration and research notebooks
├── pipelines/               # Data transformation logic (Bronze/Silver/Gold)
├── terraform/               # Infrastructure as Code for Cloud resources
└── scripts/                 # Utility scripts for platform management
```

---

## 📖 Documentation Index

For detailed guides, please refer to the following documentation sub-folders:

### 📚 [Project Report](BigData_Assignment_Report.pdf)
- **Technical Report**: Comprehensive documentation of the platform's design, implementation, and benchmarking results.

### 📐 [Architecture Docs](docs/architecture/)
- [Deployment Model](docs/architecture/deployment-model.md): Physical and logical component layout.
- [Node Pool Strategy](docs/architecture/node-pool-strategy.md): Detailed explanation of Spot Instance utilization.
- [Platform Overview](docs/architecture/overview.md): High-level system design.

### 📜 [Decision Records (ADRs)](docs/decisions/)
- Understand why specific technologies and patterns were chosen.

### 🚀 [Data Pipelines](pipelines/)
- [Medallion Architecture](pipelines/README.md): Bronze, Silver, and Gold layer implementation.
- [Advanced Features](pipelines/README.md#3-các-tính-năng-nâng-cao-advanced-features): Idempotency, Audit Layer, and Watermark logic.
- [Iceberg Maintenance](pipelines/maintenance/README.md): Guide for compaction and snapshot expiration.

### 🛠️ [Operational Runbooks](docs/runbooks/)
- [Setup Guide](SETUP.md): Initial deployment instructions.
- [Scaling Guide](docs/runbooks/scaling.md): Instructions for resizing the cluster.
- [Backup & Recovery](docs/runbooks/backup.md): Data protection procedures.

---

## 🐳 Local Development Environment (docker-dev)

For rapid local development, prototyping, and pipeline testing without deploying to Kubernetes, we provide a fully containerized standalone environment using **Docker Compose**.

Located in the [`docker-dev/`](docker-dev/) directory, this environment perfectly mirrors the production stack (Spark, Iceberg, Trino, Airflow, Kafka, MinIO). It allows you to run, orchestrate, and debug the **Medallion Pipelines)** locally.

**Quick Start for Local Dev:**
```bash
cd docker-dev
docker compose up -d --build
```
> 👉 **See the [docker-dev README](docker-dev/README.md)** for detailed instructions, Airflow DAG architectures, and local Trino benchmarking guides.

---

## ⚡ Quick Start (Kubernetes)

### 1. Prerequisites
- Google Cloud Account (GCP)
- `gcloud`, `kubectl`, `terraform`, and `helm` installed.

### 2. Infrastructure Deployment
Navigate to the `terraform/` directory and apply the configuration to provision the GKE cluster:
```bash
terraform init
terraform apply
```

### 3. Platform Installation
Use the provided setup script to deploy all components:
```bash
./scripts/deploy-platform.sh
```

---

## 💰 Infrastructure & Cost Optimization

This platform is engineered for **minimal cloud bill**:
- **Spot Instances**: Using Preemptible VMs for all workloads.
- **Auto-Scaling**: GKE Cluster Autoscaler automatically resizes based on demand.
- **Storage Tiering**: Efficient data lifecycle management in MinIO.

For a detailed breakdown of the cost strategy, see [Node Pool Strategy](docs/architecture/node-pool-strategy.md).

---

---

## 👥 Team & Acknowledgments

This project was developed by a team of students from **Ho Chi Minh City University of Technology (HCMUT - Bach Khoa)**, and members of the **BigData Club, HCMUT**.

| Name | Student ID (MSSV) | Class |
| :--- | :--- | :--- |
| **Lê Đình Đức** | 2310774 | L01 |
| **Ngô Ngọc Tuấn Anh** | 2210078 | L01 |
| **Nguyễn Văn Công Thành** | 2313133 | L01 |
| **Nguyễn Phúc Nhân** | 2312438 | L01 |

---

## 🤝 Contributing
Contributions are welcome! Please read our [Contribution Guidelines](docs/CONTRIBUTING.md) and check our [Development Workflow](docs/runbooks/development.md).
