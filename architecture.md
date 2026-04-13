# Modern Data Platform on GKE (Architecture Overview)

This document describes the high-level architecture of the data platform deployed on Google Kubernetes Engine (GKE).

## 1. Infrastructure Layer

*   **Cluster**: Private GKE Cluster located in `asia-east1` (Taiwan).
*   **Networking**:
    *   **VPC-Native**: Dedicated VPC with secondary ranges for Pods and Services.
    *   **Private Nodes**: All worker nodes have only internal IP addresses.
    *   **Cloud NAT**: Provides outbound internet access for nodes (e.g., pulling images).
    *   **Dataplane V2**: Powered by Cilium (eBPF) for enhanced networking and security.
*   **Security**:
    *   **Workload Identity**: Map K8s Service Accounts to GCP IAM Roles without managing JSON keys.
    *   **External Secrets Operator (ESO)**: Automatically syncs secrets from Google Secret Manager to K8s Secrets.

## 2. Storage & Metadata Layer

*   **Object Storage (MinIO)**: High-performance, S3-compatible storage used as the primary Data Lake storage.
*   **Relational Database (PostgreSQL)**: Centralized metadata storage for Hive Metastore, Airflow, and Superset.
*   **Unified Catalog (Gravitino)**: Provides a single metadata lakehouse for managing disparate data sources.
*   **Hive Metastore**: Standard catalog for Trino and Spark integration.

## 3. Compute & Orchestration Layer

*   **Orchestration (Apache Airflow)**: Manages ETL/ELT pipelines. Configured to use KubernetesExecutor for scalability.
*   **Query Engine (Trino)**: Distributed SQL engine for ultra-fast queries across MinIO and other sources.
*   **Batch Processing (Apache Spark)**: Managed via the Spark-on-K8s Operator for efficient resource utilization.
*   **Streaming (Kafka)**: Managed via Strimzi Operator using KRaft mode (No Zookeeper).

## 4. Visualization & Observability

*   **Visualization (Apache Superset)**: Modern BI platform for data exploration and dashboarding.
*   **Monitoring**: 
    *   Prometheus/Grafana stack (managed via Helm).
    *   Custom ServiceMonitors for each component.

## 5. Deployment Model

The platform is managed using a hybrid approach:
*   **Infrastructure as Code (Terraform)**: For GKE, VPC, NAT, and IAM.
*   **Kubernetes Manifests (Kustomize)**: For core platform services and configurations.
*   **Helm**: For complex deployments like Airflow, Trino, and Monitoring.

---
## Node Pool Configuration (Logical Segregation)

| Pool Name | Machine Type | Role / Workload |
| :--- | :--- | :--- |
| **infra-pool** | n2-standard-8 | Postgres, MinIO, Redis (Stateful/Heavy) |
| **compute-pool** | e2-highmem-4 | Airflow, Spark Drivers/Executors |
| **query-pool** | e2-highmem-4 | Trino Workers, Superset, Grafana |

> [!NOTE]
> Currently, for cost optimization, the pools are configured with **autoscaling (min 0)** to allow complete hibernation when not in use.
