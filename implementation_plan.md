# K8s Data Platform — Architecture & Deployment Guide

> Tài liệu này mô tả kiến trúc hiện tại, các công nghệ đang dùng, và hướng dẫn đầy đủ để provisioning và deploy platform lên GKE.

---

## 🏗️ Tổng Quan Kiến Trúc

Platform được xây dựng theo mô hình **Data Lakehouse** trên Google Kubernetes Engine (GKE), với:

- **Infrastructure-as-Code** bằng Terraform (GKE cluster + VPC)
- **Manifests** quản lý qua Kustomize (base + overlays)
- **Secrets** không bao giờ lưu trong Git — dùng **External Secrets Operator** kéo từ **GCP Secret Manager**
- **Chi phí tối ưu** bằng Spot VMs (2/3 node pools) và script tắt/bật theo giờ

```
┌─────────────────────────────────────────────────────────────────────┐
│              GKE Cluster — data-platform-cluster                    │
│              GKE Control Plane (managed, miễn phí)                  │
│                                                                     │
│  ┌──────────────────────┬───────────────────┬─────────────────────┐ │
│  │   infra-pool         │   compute-pool    │   query-pool        │ │
│  │   On-demand          │   Spot            │   Spot              │ │
│  │   e2-highmem-4       │   e2-highmem-4    │   e2-highmem-4      │ │
│  │   role=infra         │   role=compute    │   role=query        │ │
│  ├──────────────────────┼───────────────────┼─────────────────────┤ │
│  │ PostgreSQL           │ Spark Application │ Spark Application   │ │
│  │ MinIO pod-0          │ Trino Worker-0    │ Trino Worker-1      │ │
│  │ Gravitino            │ Kafka Broker-0    │ Kafka Broker-1      │ │
│  │ Hive Metastore       │ MinIO pod-1       │ MinIO pod-2         │ │
│  │ Spark Operator       │                   │ Superset            │ │
│  │ Trino Coordinator    │                   │                     │ │
│  │ Kafka Controller     │                   │                     │ │
│  │ Redis                │                   │                     │ │
│  └──────────────────────┴───────────────────┴─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> GCP quản lý Control Plane (API server, etcd, scheduler) miễn phí. Ba VM bên trên **đều là worker nodes** — không cần tốn VM cho K8s master.

> [!NOTE]
> **Spot VM** có thể bị GCP thu hồi bất cứ lúc nào. Redis và PostgreSQL được đặt trên On-demand (infra-pool) để tránh mất trạng thái và session. Tất cả workload Spot đều có `PodDisruptionBudget` và `tolerations` phù hợp.

---

## 🛠️ Stack Công Nghệ

### Infrastructure Layer
| Tool | Version | Mục đích |
|------|---------|---------|
| **Terraform** | ≥ 1.5 | Provisioning GKE cluster, VPC, Cloud NAT |
| **GKE** | Release Channel: REGULAR | Managed Kubernetes |
| **Kustomize** | Built-in kubectl | Quản lý manifest (base + overlays) |
| **Helm** | Latest | Cài Strimzi, ESO, kube-prometheus-stack |

### Secrets Management
| Tool | Mục đích |
|------|---------|
| **GCP Secret Manager** | Lưu trữ tất cả credentials (MinIO, Postgres, Superset key) |
| **External Secrets Operator (ESO)** | Sync secrets từ GCP SM → K8s Secrets |
| **Workload Identity** | Pods tự xác thực với GCP API (không cần SA key file) |

### Data Platform Services
| Layer | Service | Image | Node |
|-------|---------|-------|------|
| **Object Storage** | MinIO 3-node distributed | `minio/minio:RELEASE.2025-09-07...` | all (spread) |
| **Metadata DB** | PostgreSQL 16 | `postgres:16` | infra |
| **Catalog** | Apache Gravitino 1.1 | `REGISTRY/gravitino:1.1.0` | infra |
| **Metastore** | Hive Metastore 3.1.2 | `REGISTRY/hive-metastore:3.1.2` | infra |
| **Compute** | Apache Spark 3.5.5 | `REGISTRY/spark:3.5.5` | Managed by Apache Operator |
| **Query** | Trino 471 | `trinodb/trino:471` | Managed by Official Helm Chart |
| **Streaming** | Kafka (Strimzi KRaft) | Managed by Strimzi Operator | infra + spot |
| **Cache** | Redis 7.2 | `redis:7.2-bookworm` | infra (On-demand) |
| **Visualization** | Apache Superset | `REGISTRY/superset:latest` | query (Spot) |
| **Monitoring** | kube-prometheus-stack | Helm chart | query |

### Networking
| Component | Chi tiết |
|-----------|----------|
| **VPC** | Dedicated VPC `data-platform-cluster-vpc` (không dùng `default`) |
| **Subnet** | `10.10.0.0/20` + secondary ranges: pods `10.20.0.0/16`, services `10.30.0.0/20` |
| **Cloud NAT** | Private nodes (không có public IP) vẫn pull được images |
| **Ingress** | Cilium Ingress Controller |
| **NetworkPolicy** | Default-deny, allowlist per service pair |

---

## 💰 Chi Phí Ước Tính

| Machine | Loại | Đơn giá/h | Giờ/ngày | Chi phí/tháng |
|---------|------|-----------|----------|---------------|
| `e2-highmem-4` x1 | On-demand (infra) | ~$0.17/h | 8h | ~$41 |
| `e2-highmem-4` x2 | Spot (compute+query) | ~$0.04/h | 8h | ~$20 |
| **Persistent Disk** (150Gi total) | pd-balanced | — | — | ~$7 |
| **Total** | | | | **~$68/tháng** |

> Tính với 8 giờ/ngày (14:00–22:00), 30 ngày/tháng. Nếu để 24/7, chi phí x3 (~$370/tháng).

---

## 📁 Cấu Trúc Thư Mục

```
k8s-data-platform/
├── terraform/                    ← GKE provisioning (Terraform IaC)
│   ├── backend.tf                ← GCS remote state
│   ├── providers.tf              ← Google provider
│   ├── variables.tf              ← Input variables (no defaults for project_id)
│   ├── main.tf                   ← GKE cluster + 3 node pools
│   ├── network.tf                ← VPC, Subnet, Cloud Router, NAT
│   ├── outputs.tf                ← Cluster endpoint, connect command
│   ├── terraform.tfvars.example  ← Template (copy → terraform.tfvars)
│   └── terraform.tfvars          ← (git-ignored) real values
│
├── k8s/                          ← Kubernetes manifests (Kustomize base)
│   ├── kustomization.yaml        ← Thứ tự apply + namespace: data-platform
│   ├── 00-namespace.yaml
│   ├── common/
│   │   ├── secret-store.yaml     ← ESO ClusterSecretStore + K8s SA (Workload Identity)
│   │   ├── resource-quota.yaml   ← ResourceQuota + LimitRange
│   │   └── network-policy.yaml   ← Default-deny + allowlist rules
│   ├── secrets/
│   │   ├── minio-secret.yaml     ← ExternalSecret → "minio-secret"
│   │   ├── postgres-secret.yaml  ← ExternalSecret → "postgres-secret"
│   │   ├── spark-minio-secret.yaml  ← ExternalSecret → "spark-minio-secret"
│   │   └── superset-secret.yaml  ← ExternalSecret → "superset-secret"
│   ├── storage/                  ← PersistentVolumeClaims (GCE PD)
│   ├── postgres/                 ← StatefulSet, Service, init ConfigMap
│   ├── minio/                    ← StatefulSet (3 replicas), Services, bucket Job
│   ├── gravitino/                ← Deployment, ConfigMap, Service
│   ├── hive-metastore/           ← StatefulSet, ConfigMap, Service
│   ├── spark/
│   │   ├── configmap.yaml        ← spark-defaults.conf
│   │   ├── spark-rbac.yaml       ← ServiceAccount + Role cho Driver
│   │   └── spark-pi-example.yaml ← Resource SparkApplication (Apache Operator)
│   ├── kafka/                    ← Strimzi KafkaNodePool + Kafka CRD
│   ├── trino/
│   │   └── trino-values.yaml     ← Official Helm Chart values
│   ├── redis/                    ← StatefulSet (infra node, On-demand)
│   ├── pdb/                      ← PodDisruptionBudgets (7 PDBs)
│   ├── monitoring/               ← ServiceMonitors (requires kube-prometheus-stack)
│   ├── superset/                 ← Deployment + Service
│   ├── ingress/                  ← Cilium Ingress rules
│   └── overlays/
│       └── dev/
│           └── kustomization.yaml ← Patch replicas + resources nhỏ hơn cho dev
│
├── scripts/
│   ├── gke_schedule.sh           ← Scale cluster up (14:00) / down (22:00)
│   ├── install_helm_charts.sh    ← Cài Strimzi, ESO, kube-prometheus-stack
│   └── init_kafka_topics.sh      ← Tạo Kafka topics sau khi cluster start
│
└── Makefile                      ← Tất cả lệnh phổ biến (k8s-deploy, tf-plan, v.v.)
```

---

## 🔐 Kiến Trúc Secrets (ESO + GCP Secret Manager)

```
GCP Secret Manager          External Secrets Operator       K8s Secrets
────────────────────        ─────────────────────────       ───────────
minio-root-user      ──┐
minio-root-password  ──┤── ExternalSecret: minio-secret ──► Secret: minio-secret
                        │                                    (dùng bởi MinIO pods)
                        │
minio-root-user      ──┤── ExternalSecret: spark-minio ───► Secret: spark-minio-secret
minio-root-password  ──┘                                    (dùng bởi Spark envFrom)

postgres-user        ──┐
postgres-password    ──┤── ExternalSecret: postgres    ────► Secret: postgres-secret
postgres-db          ──┘                                    (dùng bởi Postgres, Hive)

superset-secret-key  ──── ExternalSecret: superset    ────► Secret: superset-secret
                                                            (dùng bởi Superset env)
```

**Flow xác thực ESO → GCP:**
```
ESO Pod ──(Workload Identity)──► GCP SA: eso-sa@ ──► Secret Manager API
```

Pods không bao giờ biết GCP credentials. ESO dùng Workload Identity của K8s SA được annotate với GCP SA.

---

## 🚀 Hướng Dẫn Deploy Lần Đầu (Full Setup)

### Bước 0 — Prerequisites

```bash
# Kiểm tra các tool cần thiết
gcloud version          # >= 450.0
terraform version       # >= 1.5.0
kubectl version --client
helm version            # >= 3.12

# Xác thực với GCP
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### Bước 1 — Tạo GCS Bucket cho Terraform State

```bash
# Tạo bucket (thực hiện 1 lần duy nhất)
gsutil mb -p YOUR_PROJECT_ID -l asia-southeast1 gs://YOUR_PROJECT_ID-tfstate

# Bật versioning để khôi phục state nếu cần
gsutil versioning set on gs://YOUR_PROJECT_ID-tfstate
```

Sau đó cập nhật `terraform/backend.tf`:
```hcl
backend "gcs" {
  bucket = "YOUR_PROJECT_ID-tfstate"   # ← sửa tại đây
  prefix = "k8s-data-platform/state"
}
```

### Bước 2 — Cấu Hình Terraform

```bash
cd terraform

# Copy example và điền giá trị thực
cp terraform.tfvars.example terraform.tfvars
```

Sửa `terraform.tfvars`:
```hcl
project_id   = "your-actual-project-id"
region       = "asia-southeast1"
zone         = "asia-southeast1-a"
cluster_name = "data-platform-cluster"
```

### Bước 3 — Provision GKE Cluster

```bash
# Từ thư mục gốc dự án
make tf-init        # terraform init (kết nối GCS backend)
make tf-validate    # kiểm tra cú pháp
make tf-plan        # xem những gì sẽ được tạo
make tf-apply       # tạo cluster (~10-15 phút)
```

Kết quả: GKE cluster với 3 node pools (ban đầu mỗi pool 1 node).

### Bước 4 — Kết Nối kubectl

```bash
# Lấy lệnh connect từ Terraform output
terraform -chdir=terraform output connect_command

# Chạy lệnh đó, ví dụ:
gcloud container clusters get-credentials data-platform-cluster \
  --zone asia-southeast1-a --project your-project-id

# Xác nhận
kubectl get nodes -o wide
# Expected: 3 nodes với role labels từ Terraform
```

### Bước 5 — Cài Helm Charts (Operators & Monitoring)

```bash
# Cài tất cả operators cần thiết
./scripts/install_helm_charts.sh

# Script cài:
# 1. Strimzi Operator (quản lý Kafka KRaft)
# 2. External Secrets Operator (ESO)
# 3. kube-prometheus-stack (Prometheus + Grafana)
# 4. NGINX / Cilium Ingress Controller (nếu cần)
```

Kiểm tra:
```bash
kubectl get pods -n strimzi-operator
kubectl get pods -n external-secrets
kubectl get pods -n monitoring
```

### Bước 6 — Tạo Secrets trong GCP Secret Manager

```bash
# Cách 1: Dùng Makefile target (có interactive prompt)
make secrets-create

# Cách 2: Thủ công
gcloud secrets create minio-root-user     --data-file=- <<< "minioadmin"
gcloud secrets create minio-root-password --data-file=- <<< "YourStrongPassword123!"
gcloud secrets create postgres-user       --data-file=- <<< "postgres"
gcloud secrets create postgres-password   --data-file=- <<< "YourPGPassword123!"
gcloud secrets create postgres-db         --data-file=- <<< "catalog_metastore_db"

# Superset secret key (generate ngẫu nhiên)
python -c "import secrets; print(secrets.token_hex(32))" | \
  gcloud secrets create superset-secret-key --data-file=-
```

### Bước 7 — Cấu Hình ESO: Bind Workload Identity

```bash
PROJECT_ID=your-project-id

# Tạo GCP Service Account cho ESO
gcloud iam service-accounts create eso-sa \
  --display-name="External Secrets Operator"

# Cấp quyền đọc Secret Manager
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:eso-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Bind K8s ServiceAccount với GCP SA (Workload Identity)
gcloud iam service-accounts add-iam-policy-binding \
  eso-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:${PROJECT_ID}.svc.id.goog[data-platform/eso-sa]"
```

Sau đó sửa `k8s/common/secret-store.yaml` — thay `PROJECT_ID` bằng giá trị thực:
```bash
# Thay toàn bộ placeholder PROJECT_ID trong file
sed -i "s/PROJECT_ID/$PROJECT_ID/g" k8s/common/secret-store.yaml
```

### Bước 8 — Build & Push Custom Images lên Artifact Registry

Các service dùng custom image (có tag `REGISTRY/...`) cần được build và push:

```bash
REGISTRY="asia-southeast1-docker.pkg.dev/${PROJECT_ID}/data-platform"

# Tạo Artifact Registry repository (1 lần)
gcloud artifacts repositories create data-platform \
  --repository-format=docker \
  --location=asia-southeast1

# Configure Docker auth
gcloud auth configure-docker asia-southeast1-docker.pkg.dev

# Build và push từng image
cd k8s/spark/build
docker build -t ${REGISTRY}/spark:3.5.5 .
docker push ${REGISTRY}/spark:3.5.5

cd k8s/gravitino/build
docker build -t ${REGISTRY}/gravitino:1.1.0 .
docker push ${REGISTRY}/gravitino:1.1.0

# ... tương tự cho hive-metastore và superset
```

Sau đó thay `REGISTRY` trong các manifest:
```bash
# Thay tất cả placeholder REGISTRY trong k8s/ folder
find k8s/ -name "*.yaml" -exec \
  sed -i "s|REGISTRY|${REGISTRY}|g" {} \;
```

### Bước 9 — Deploy Platform

```bash
# Option A: Base manifest (production-like, replicas đầy đủ)
make k8s-deploy

# Option B: Dev overlay (replicas nhỏ hơn, phù hợp học/test)
make k8s-dev

# Theo dõi quá trình khởi động
make k8s-pods
# hoặc
kubectl get pods -n data-platform -w
```

Thứ tự khởi động (Kustomize đảm bảo):
```
ESO SecretStore → Namespace → ExternalSecrets
→ ResourceQuota + NetworkPolicy
→ PVCs
→ PostgreSQL + MinIO
→ Gravitino + Hive Metastore  (init container chờ postgres/minio)
→ Spark + Kafka
→ Trino                        (init container chờ gravitino/minio)
→ Redis
→ HPA + PDB
→ Monitoring ServiceMonitors
→ Superset + Ingress
```

### Bước 10 — Tạo Kafka Topics

```bash
# Sau khi Kafka cluster READY
./scripts/init_kafka_topics.sh
```

---

## 📅 Vận Hành Hàng Ngày (Cost Scheduling)

Platform được thiết kế để **chỉ chạy 8 giờ/ngày** (14:00–22:00 ICT) để tiết kiệm chi phí.

### Scale Up (14:00 ICT)

```bash
./scripts/gke_schedule.sh start
# hoặc
make k8s-start
```

Script thực hiện theo thứ tự:
1. Scale PostgreSQL + MinIO → 3 replicas
2. Chờ PostgreSQL ready
3. Scale Gravitino + Hive Metastore + Redis
4. Scale Kafka controller → broker
5. Scale Spark + Trino
6. Scale Superset

### Scale Down (22:00 ICT)

```bash
./scripts/gke_schedule.sh stop
# hoặc
make k8s-stop
```

Script dập workloads theo thứ tự **ngược lại** (UI → compute → kafka → catalog → storage). GKE Cluster Autoscaler sẽ thu hồi Spot nodes trong ~10-15 phút sau khi pods về 0.

### Tự Động Hóa với Crontab

```bash
# Trên máy local hoặc Cloud Shell (luôn bật)
# Chỉnh múi giờ: ICT = UTC+7
crontab -e

# Thêm 2 dòng sau
0 7 * * 1-5  cd /path/to/k8s-data-platform && ./scripts/gke_schedule.sh start  >> /tmp/gke.log 2>&1
0 15 * * 1-5 cd /path/to/k8s-data-platform && ./scripts/gke_schedule.sh stop   >> /tmp/gke.log 2>&1
```

---

## 🌐 Truy Cập Các UI

Sau khi deploy, các service được expose qua Ingress (cần thêm `/etc/hosts` hoặc DNS):

```bash
# Lấy External IP của Ingress Controller
kubectl get svc -n kube-system | grep ingress

# Thêm vào /etc/hosts (thay <INGRESS_IP>)
echo "<INGRESS_IP>  trino.data.local superset.data.local grafana.data.local airflow.data.local" \
  | sudo tee -a /etc/hosts
```

| Service | URL | Credentials |
|---------|-----|-------------|
| **Trino UI** | http://trino.data.local | No auth (dev) |
| **Superset** | http://superset.data.local | admin / từ GCP Secret Manager |
| **Grafana** | http://grafana.data.local | admin / prom-operator |
| **MinIO Console** | `kubectl port-forward svc/minio 9001:9001 -n data-platform` | Từ GCP Secret Manager |
| **Spark Master UI** | `kubectl port-forward svc/spark-master 8080:8080 -n data-platform` | No auth |

---

## 🔍 Monitoring & Debugging

### Kiểm Tra Trạng Thái

```bash
make k8s-status                              # pods + svc + pvc tổng quan
kubectl get pods -n data-platform -o wide    # xem pod đang chạy ở node nào
kubectl top nodes                            # CPU/RAM mỗi node
kubectl top pods -n data-platform            # CPU/RAM mỗi pod

# Kiểm tra ESO đã sync secrets thành công chưa
kubectl get externalsecrets -n data-platform
kubectl describe externalsecret minio-secret -n data-platform

# Kiểm tra HPA
kubectl get hpa -n data-platform
```

### Xem Logs

```bash
make k8s-logs SERVICE=trino-coordinator
make k8s-logs SERVICE=spark-master
make k8s-logs SERVICE=gravitino

# Logs của Kafka (Strimzi)
kubectl logs -n data-platform -l strimzi.io/name=data-platform-kafka-broker-pool -f
```

### Debug Pod Không Start

```bash
# Xem events của pod
kubectl describe pod <pod-name> -n data-platform

# Check init container logs
kubectl logs <pod-name> -n data-platform -c wait-for-postgres
```

---

## 📊 Resource Allocation (e2 series: 16-32 GB RAM mỗi node)

| Node | Service | CPU Request | Memory Request |
|------|---------|-------------|----------------|
| **infra** | PostgreSQL | 500m | 1Gi |
| **infra** | MinIO pod-0 | 500m | 1Gi |
| **infra** | Gravitino | 500m | 2Gi |
| **infra** | Hive Metastore | 500m | 1Gi |
| **infra** | Spark Master | 500m | 1Gi |
| **infra** | Trino Coordinator | 1000m | 4Gi |
| **infra** | Kafka Controller | 500m | 1Gi |
| **infra** | Redis | 250m | 512Mi |
| | **Tổng Infra** | **~4.25 CPU** | **~11.5 Gi** |
| **compute** | Spark Worker-0 | 2000m | 8Gi |
| **compute** | Trino Worker-0 | 1000m | 4Gi |
| **compute** | Kafka Broker-0 | 500m | 2Gi |
| **compute** | MinIO pod-1 | 500m | 1Gi |
| | **Tổng Compute** | **~4 CPU** | **~15 Gi** |
| **query** | Spark Worker-1 | 2000m | 8Gi |
| **query** | Trino Worker-1 | 1000m | 4Gi |
| **query** | Kafka Broker-1 | 500m | 2Gi |
| **query** | MinIO pod-2 | 500m | 1Gi |
| **query** | Superset | 500m | 1Gi |
| | **Tổng Query** | **~4.5 CPU** | **~16 Gi** |

> Mỗi node dành ~1-1.5 CPU và ~2-3 GB cho OS, kubelet, và DaemonSets. Headroom đủ cho HPA scale thêm 1-2 pods trước khi Cluster Autoscaler thêm node mới.

---

## ⚠️ Lưu Ý Quan Trọng

> [!WARNING]
> **Trước khi deploy production**: Đổi tất cả `minioadmin` / `postgres` / placeholder passwords thành passwords mạnh trong GCP Secret Manager.

> [!IMPORTANT]
> **Build custom images**: Các manifest có `image: REGISTRY/...` sẽ **fail** cho đến khi bạn build và push images lên Artifact Registry (Bước 8). Images custom gồm: `spark`, `gravitino`, `hive-metastore`, `superset`.

> [!NOTE]
> **Kafka TLS**: Kafka internal listener hiện để `tls: false` cho dev. Để production, bật TLS và dùng SCRAM-SHA-512 authentication cho external listener.

> [!TIP]
> **Dev Overlay**: Dùng `make k8s-dev` thay `make k8s-deploy` để giảm replicas Spark/Trino về 1 và giảm resource requests — phù hợp khi học và test mà không cần full performance.
