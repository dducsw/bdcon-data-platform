# 🌊 K8s Data Platform (Lakehouse)

A scalable, cost-optimized Modern Data Platform built on Kubernetes (Google Kubernetes Engine). This project provides a full-stack, open-source data infrastructure optimized for development and experimentation using a **100% Spot Instances** strategy to minimalize cloud costs.

## 🚀 Overview & Architecture

The platform integrates leading open-source data technologies into a cohesive Lakehouse architecture:

- **Storage Layer**: MinIO (S3-compatible Object Storage)
- **Table Format**: Apache Iceberg
- **Catalog & Metastore**: Gravitino (Iceberg REST Catalog) backed by PostgreSQL & Hive Metastore
- **Compute & Processing**: Apache Spark (managed via Spark Kubernetes Operator)
- **Streaming & Messaging**: Apache Kafka & Strimzi
- **Query Engine**: Trino (Distributed SQL Engine)
- **Orchestration**: Apache Airflow
- **Visualization (BI)**: Apache Superset
- **Observability**: Prometheus & Grafana

## 📁 Repository Layout

This repository has been strictly structured into distinct functional boundaries separating infrastructure, manifests, overrides, and logic:

\\\	ext
k8s-data-platform/
├── assets/                  # Diagrams, images, and static resources
├── docs/                    # Architecture records, decisions (ADRs) and runbooks
│   ├── architecture/        # Overviews, deployment models, node strategies
│   ├── decisions/           # Architectural Decision Records (ADRs)
│   └── runbooks/            # Operational guides for platform owners
├── helm-values/             # Helm chart standard configurations (dev, prod overrides)
│   ├── airflow/             # Apache Airflow definitions
│   ├── monitoring/          # Prometheus & Grafana definitions
│   ├── strimzi/             # Kafka Strimzi definitions
│   └── trino/               # Trino overrides (Worker sizing, catalogs)
├── k8s/                     # Native Kubernetes manifests via Kustomize
│   ├── base/                # Base manifests (Namespace, RBAC, Services)
│   │   ├── data-services/   # Stateful backends (Minio, Postgres, Kafka, Hive)
│   │   ├── observability/   # Prom/Grafana manifests
│   │   └── platform-services/# Compute & BI (Spark, Superset, Ingress)
│   └── overlays/            # Environment specific overlays (e.g. dev/)
├── notebooks/               # Jupyter / Exploration notebooks
├── pipelines/               # dbt models and data transformation logic
├── scripts/                 # Utility scripts grouped by phase
│   ├── bootstrap/           # Init scripts
│   ├── cleanup/             # Teardown scripts
│   ├── deploy/              # Deployment triggers
│   └── verify/              # Verification & e2e testing Python scripts
└── terraform/               # Infrastructure as Code (GCP & GKE)
    ├── envs/dev/            # Development environment instantiation
    └── modules/             # Reusable TF modules (gke, network, nat, iam)
\\\

## 🛠️ Quick Start

### For Data Engineers / Developers
If you are joining the project as a developer or partner to submit Spark jobs, explore Trino, or build Airflow DAGs, please follow the **[Partner Setup Guide (SETUP.md)](SETUP.md)**. 

### For Platform Administrators / DevOps
If you are responsible for provisioning the GCP infrastructure or deploying the Kubernetes services from scratch, refer to our operational runbooks:
1. **[Infrastructure Provisioning](docs/runbooks/bootstrap-gke.md)** (Terraform)
2. **[Platform Deployment](docs/runbooks/deploy-platform.md)** (Helm + Kustomize)

## ⚙️ Operations & Deployment Model

The dev cluster is heavily geared towards cost-savings:
- **Spot Nodes Only**: We embrace preemption by utilizing resilient deployments for Coordinators and Auto-Scaling for Workers.
- **GitOps Ready**: Infrastructure runs through modular Terraform. Kubernetes deployments are exclusively handled by kustomize and helm values.

### Common make Commands
The root Makefile provides helpful wrappers for standard operations:

\\\ash
# Infrastructure
make tf-init          # Initialize Terraform modules
make tf-plan          # Plan Infrastructure changes

# Deployments
make bootstrap-operators # Install essential CRDs (e.g., Spark Operator)
make k8s-dev             # Apply the K8s Dev Overlay (MinIO, Spark, Postgres...)

# Diagnostics
make k8s-status       # Verify StatefulSets and Deployments
make verify-layout    # Validate the repository structure
\\\

---
*Built for learning, scalability, and resilience on Kubernetes! ⎈*
