# Data Platform Infrastructure Review

## 1. Kiến trúc và Tổ chức Project (k8s folder)
**Đánh giá:**
- **Ưu điểm:** Cấu trúc phân lớp rõ ràng (Foundation, Storage, Database, Catalog, Compute, Streaming, Query, Cache, Observability). Sử dụng `kustomization.yaml` giúp quản lý triển khai một cách hệ thống.
- **Tình trạng hiện tại:** Các component (Postgres, Minio, Hive Metastore, Kafka, Spark) được định nghĩa đầy đủ, bao phủ toàn bộ pipeline dữ liệu.

## 2. Các điểm cần cải tiến (Recommendations for Production)
Dựa trên best practices cho hệ thống Data Platform Kubernetes:

1. **Quản lý Tài nguyên & Spot Instances:**
   - Các workloads chưa có cấu hình **Node Affinity/Selector** và **Tolerations** rõ ràng cho Spot VMs.
   - Resource `requests` và `limits` cần được tune chính xác cho từng component (ví dụ: Spark executor, Trino worker nên chạy trên Spot VMs, trong khi Postgres, Minio, Kafka phải nằm trên On-Demand VMs).

2. **Khả năng chịu lỗi (High Availability & Resilience):**
   - **Pod Disruption Budgets (PDB):** Cần đảm bảo PDB được cấu hình cho tất cả các Core components để tránh gián đoạn khi node update hoặc Spot VM bị thu hồi (preempted).
   - Replica counts của StatefulSets nên >= 3 (như Kafka, Minio) cho môi trường HA.

3. **Bảo mật và Quản lý Secret:**
   - Folder `secrets/` có thể chứa hard-coded manifests. Nên cân nhắc chuyển sang **External Secrets Operator** (tích hợp GCP Secret Manager) hoặc **SealedSecrets** để tránh lưu trữ secret plaintext trong Git.

4. **Triển khai tự động (GitOps):**
   - Thay vì dùng `kubectl apply -k`, nên đưa ArgoCD hoặc FluxCD vào để đồng bộ tự động từ Git.

5. **Storage & Persistent Volumes:**
   - Stateful workload hiện tại sử dụng StorageClass mặc định. Khi chạy trên cloud, nên explicit định nghĩa `storageClassName` (vd: `premium-rwo` trên GKE) cho DB/Message Queue để đạt IOPS cao.
