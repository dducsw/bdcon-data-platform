# K8s Data Platform — GKE Deployment Guide

> **Platform**: Google Kubernetes Engine (GKE) + Spot VMs  
> **Topology**: 1 On-demand node + 2 Spot nodes  
> **Namespace**: `data-platform`

---

## 📐 Architecture Overview

```
GKE Cluster (managed control plane — free)
├── node-1  [role=infra]   On-demand  n2d-standard-8 (8vCPU / 32GB)
│   ├── PostgreSQL          → port 5432 (Gravitino + Hive Metastore backend)
│   ├── MinIO               → port 9000 (Object Storage)
│   ├── Gravitino           → port 8090/9001 (Iceberg REST Catalog)
│   ├── Hive Metastore ★   → port 9083 (Thrift, NEW component)
│   └── Spark Master        → port 7077/8080
│
├── node-2  [role=compute] Spot       n2d-standard-8 (8vCPU / 32GB)
│   ├── Spark Executor Pods → (Dynamically spawned by Spark K8s Operator)
│   ├── Kafka-1             → (Managed by Strimzi Operator)
│   ├── Redis               → port 6379
│   ├── Kafka Exporter      → port 9308
│   └── Redis Exporter      → port 9121
│
└── node-3  [role=query]   Spot       n2d-standard-8 (8vCPU / 32GB)
    ├── Kafka-2             → broker (spread via topologySpreadConstraints)
    ├── Trino               → (Coordinator/Worker managed via Official Helm Chart)
    ├── Prometheus          → port 9090
    ├── Grafana             → port 3000 (NodePort 30300)
    └── Superset            → port 8088 (NodePort 30889)
```

**★ Hive Metastore** is a new component not present in the Docker version. It provides Thrift-based metadata service for Trino's `hive` connector and as a secondary catalog for Spark.

---

## 🔧 Prerequisites

### 1. Tools Installation

```bash
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash
gcloud init

# Install kubectl
gcloud components install kubectl

# Install Helm (optional, for future use)
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify versions
kubectl version --client
gcloud version
```

### 2. Google Cloud Project Setup

```bash
# Set your project
export PROJECT_ID="your-gcp-project-id"
export REGION="asia-southeast1"          # Singapore — closest to Vietnam
export CLUSTER_NAME="data-platform"
export ARTIFACT_REGISTRY="$REGION-docker.pkg.dev/$PROJECT_ID/data-platform"

gcloud config set project $PROJECT_ID
gcloud config set compute/region $REGION

# Enable required APIs
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  compute.googleapis.com
```

---

## 🏗️ Step 1 — Create GKE Cluster (Option B: Mixed Node Pool)

```bash
# Create cluster with initial On-demand node pool (node-1 / infra)
gcloud container clusters create $CLUSTER_NAME \
  --region $REGION \
  --num-nodes 1 \
  --machine-type n2d-standard-8 \
  --disk-size 100GB \
  --disk-type pd-balanced \
  --node-labels role=infra \
  --release-channel regular \
  --no-enable-autoscaling

# Add Spot node pool for node-2 (compute)
gcloud container node-pools create compute-pool \
  --cluster $CLUSTER_NAME \
  --region $REGION \
  --num-nodes 1 \
  --machine-type n2d-standard-8 \
  --disk-size 100GB \
  --spot \
  --node-labels role=compute

# Add Spot node pool for node-3 (query)
gcloud container node-pools create query-pool \
  --cluster $CLUSTER_NAME \
  --region $REGION \
  --num-nodes 1 \
  --machine-type n2d-standard-8 \
  --disk-size 100GB \
  --spot \
  --node-labels role=query

# Connect kubectl to cluster
gcloud container clusters get-credentials $CLUSTER_NAME --region $REGION
```

### Verify Node Labels

```bash
kubectl get nodes --show-labels | grep role
# Expected output: each node has role=infra / role=compute / role=query
```

---

## 🐳 Step 2 — Build & Push Docker Images

The following services use **custom Docker images** that must be built and pushed to Google Artifact Registry.

### Create Artifact Registry Repository

```bash
gcloud artifacts repositories create data-platform \
  --repository-format docker \
  --location $REGION

# Authenticate Docker with Artifact Registry
gcloud auth configure-docker $REGION-docker.pkg.dev
```

### Build & Push Images

```bash
cd d:/Projects/k8s-data-platform   # Project root

# Spark image
docker build -t $ARTIFACT_REGISTRY/spark:3.5.5 \
  --build-arg PYTHON_VERSION=3.12.3 \
  --build-arg SPARK_VERSION=3.5.5 \
  --build-arg SPARK_SCALA_VERSION=3.5_2.12 \
  --build-arg ICEBERG_VERSION=1.10.0 \
  --build-arg POSTGRESQL_JAR_VERSION=42.7.5 \
  --build-arg HADOOP_AWS_JAR_VERSION=3.3.1 \
  --build-arg AWS_JAVA_SDK_BUNDLE_JAR_VERSION=1.12.367 \
  --build-arg AWS_SDK_V2_VERSION=2.25.11 \
  --build-arg KAFKA_VERSION=3.9.0 \
  --build-arg SPARK_KAFKA_VERSION=3.5.5 \
  -f infrastructure/spark/Dockerfile .
docker push $ARTIFACT_REGISTRY/spark:3.5.5

# Gravitino image
docker build -t $ARTIFACT_REGISTRY/gravitino:1.1.0 \
  --build-arg GRAVITINO_IMAGE_TAG=1.1.0 \
  --build-arg HADOOP_AWS_JAR_VERSION=3.3.1 \
  --build-arg AWS_JAVA_SDK_BUNDLE_JAR_VERSION=1.12.367 \
  --build-arg AWS_SDK_V2_VERSION=2.25.11 \
  --build-arg ICEBERG_VERSION=1.10.0 \
  -f infrastructure/gravitino/Dockerfile .
docker push $ARTIFACT_REGISTRY/gravitino:1.1.0

# Hive Metastore image (NEW)
docker build -t $ARTIFACT_REGISTRY/hive-metastore:4.0.0 \
  -f infrastructure/hive-metastore/Dockerfile \
  infrastructure/hive-metastore/
docker push $ARTIFACT_REGISTRY/hive-metastore:4.0.0

# Superset image
docker build -t $ARTIFACT_REGISTRY/superset:latest \
  -f infrastructure/superset/Dockerfile \
  infrastructure/superset/
docker push $ARTIFACT_REGISTRY/superset:latest
```

### Update Image References in Manifests

Replace `REGISTRY` placeholder in manifests with your actual registry path:

```bash
# Windows PowerShell
$REGISTRY = "$REGION-docker.pkg.dev/$PROJECT_ID/data-platform"

# Linux/Mac
export REGISTRY="$REGION-docker.pkg.dev/$PROJECT_ID/data-platform"

# Find and replace REGISTRY in all manifest files
Get-ChildItem -Path k8s -Recurse -Filter "*.yaml" | ForEach-Object {
  (Get-Content $_.FullName) -replace 'REGISTRY', $REGISTRY | Set-Content $_.FullName
}
```

---

## 🚀 Step 3 — Deploy Operators and Platform

### 3.1 Install Helm Charts, Operators, Ingress, and Airflow

We use **Spark on K8s Operator**, **Strimzi Kafka Operator**, **Trino Helm Chart**, **NGINX Ingress**, **Kube-Prometheus-Stack**, and **Airflow** for a production-grade platform.

```bash
# Run the installation script
chmod +x scripts/install_helm_charts.sh
./scripts/install_helm_charts.sh
```

### 3.2 Deploy the Data Platform (Kustomize)

Once operators are running, deploy the remaining infrastructure and CRDs:

```bash
kubectl apply -k k8s/
```

# 2. Storage PVCs
kubectl apply -f k8s/storage/

# 3. Database & Object Storage
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/minio/

# Wait for Postgres and MinIO to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n data-platform --timeout=120s
kubectl wait --for=condition=ready pod -l app=minio -n data-platform --timeout=120s

# 4. Catalog Layer — Gravitino & Hive Metastore
kubectl apply -f k8s/gravitino/
kubectl apply -f k8s/hive-metastore/

kubectl wait --for=condition=ready pod -l app=gravitino -n data-platform --timeout=180s
kubectl wait --for=condition=ready pod -l app=hive-metastore -n data-platform --timeout=180s

# 5. Compute Layer — Spark
kubectl apply -f k8s/spark/
kubectl wait --for=condition=ready pod -l app=spark-master -n data-platform --timeout=120s

# 6. Streaming Layer — Kafka
kubectl apply -f k8s/kafka/
# Wait for Strimzi to provision brokers
kubectl wait --for=condition=ready pod -l strimzi.io/name=data-platform-kafka-dual-role -n data-platform --timeout=180s

# 7. Query Layer — Trino is deployed via Helm in step 3.1

# 8. Cache Layer — Redis
kubectl apply -f k8s/redis/

# 9. Observability
kubectl apply -f k8s/monitoring/

# 10. Visualization
kubectl apply -f k8s/superset/

# 11. Resilience
kubectl apply -f k8s/pdb/
```

---

## ✅ Step 4 — Post-Deploy Verification

### Check All Pods

```bash
# All pods should be Running or Completed
kubectl get pods -n data-platform -o wide

# Check resource usage per node
kubectl top nodes
kubectl top pods -n data-platform
```

### Verify Each Service

```bash
# PostgreSQL
kubectl exec -it -n data-platform $(kubectl get pod -l app=postgres -n data-platform -o name) \
  -- psql -U postgres -c "\l"
# Expected: catalog_metastore_db AND hive_metastore_db both listed

# MinIO
kubectl exec -it -n data-platform $(kubectl get pod -l app=minio -n data-platform -o name) \
  -- mc alias set local http://localhost:9000 minioadmin minioadmin123 && mc ls local
# Expected: iceberg bucket listed

# Hive Metastore
kubectl exec -it -n data-platform hive-metastore-0 \
  -- /opt/hive/bin/schematool -dbType postgres -info
# Expected: Hive distribution version...

# Kafka (3-node cluster health)
kubectl exec -it -n data-platform kafka-0 \
  -- /opt/kafka/bin/kafka-broker-api-versions.sh \
  --bootstrap-server kafka-0.kafka-headless.data-platform.svc.cluster.local:29092
# Expected: list of broker API versions from all 3 brokers

# Trino
kubectl exec -it -n data-platform $(kubectl get pod -l app=trino-coordinator -n data-platform -o name) \
  -- trino --server http://localhost:8080 --execute "SHOW CATALOGS"
# Expected: catalog_iceberg, hive, system, tpch
```

### Access Web UIs (via NGINX Ingress)

Ensure your domain name (or `/etc/hosts`) points to the NGINX Ingress External IP:
```bash
# Get the IP of the Ingress Controller Loadbalancer
kubectl get svc -n ingress-nginx ingress-nginx-controller
```
Add to `C:\Windows\System32\drivers\etc\hosts` or `/etc/hosts`:
```
<INGRESS-IP> trino.data.local superset.data.local grafana.data.local airflow.data.local
```

| Service | URL | Background / Config |
|---|---|---|
| **Spark Master UI** | `http://<node-1-ip>:30080` | (Still NodePort) |
| **Trino UI** | `http://trino.data.local` | Ingress Route -> trino:8080 |
| **Grafana** | `http://grafana.data.local` | Ingress Route -> kube-prometheus-stack |
| **Superset** | `http://superset.data.local` | Ingress Route -> superset:8088 |
| **Airflow** | `http://airflow.data.local` | Ingress Route -> airflow:8080 |

---

## 🔒 Step 5 — Production Hardening (Recommended)

### 1. Change Default Credentials

```bash
# Update secrets with real values before first deploy
# Generate base64 values:
echo -n 'your-strong-password' | base64

# Edit secrets manifests, then apply
kubectl apply -f k8s/secrets/
```

### 2. Enable GKE Workload Identity (replace static credentials)

Instead of hardcoded MinIO credentials in ConfigMaps, use Workload Identity + GCS:
```bash
# Enable Workload Identity on cluster
gcloud container clusters update $CLUSTER_NAME \
  --workload-pool=$PROJECT_ID.svc.id.goog \
  --region $REGION
```

### 3. Enable Spot VM Auto-Recovery

Since Spot VMs can be preempted, configure PDB (already created in `k8s/pdb/pdb.yaml`). Monitor preemptions:
```bash
# Watch for node preemptions
kubectl get events -n data-platform --field-selector reason=Killing
```

---

## 🔧 Step 6 — Common Operations

### Submit a Spark Job (via Operator)

With the Spark Operator, you don't use `spark-submit`. Instead, apply a `SparkApplication` custom resource:

```bash
kubectl apply -f k8s/spark/spark-pi-example.yaml

# Check job status
kubectl get sparkapplication -n data-platform spark-pi

# View driver logs
kubectl logs -n data-platform -f spark-pi-driver
```

### Kafka Topic Management (via Strimzi)

Strimzi allows managing topics via `KafkaTopic` custom resources:

```bash
# Apply topic CRD
kubectl apply -f k8s/kafka/kafka-topic.yaml

# List topics
kubectl get kafkatopic -n data-platform
```

### Port-Forward for Local Development

```bash
# Trino local access
kubectl port-forward svc/trino 8080:8080 -n data-platform

# MinIO Console
kubectl port-forward svc/minio 9001:9001 -n data-platform

# Grafana
kubectl port-forward svc/grafana 3000:3000 -n data-platform
```

---

## 💸 Estimated GKE Costs (Monthly, Singapore Region)

| Resource | Type | Count | Est. Cost/Month |
|---|---|---|---|
| node-1 `n2d-standard-8` | On-demand | 1 | ~$200 |
| node-2 `n2d-standard-8` | Spot | 1 | ~$60 |
| node-3 `n2d-standard-8` | Spot | 1 | ~$60 |
| GKE Control Plane | Managed | Free tier | $0 |
| GCE PD (Persistent Disks) | standard | ~300GB | ~$20 |
| Egress & other | — | — | ~$10 |
| **Total** | | | **~$350/month** |

> Switch all 3 nodes to Spot to reduce to ~$180/month (higher preemption risk).

---

## 🗑️ Cleanup

```bash
# Delete all resources
kubectl delete -k k8s/

# Delete GKE cluster
gcloud container clusters delete $CLUSTER_NAME --region $REGION
```
