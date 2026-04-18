# Hướng Dẫn Cài Đặt Data Platform trên GKE (Spot & On-Demand VMs)

Tài liệu này hướng dẫn cách sử dụng Terraform để tự động cấp phát tài nguyên trên Google Kubernetes Engine (GKE) và tiến hành cài đặt nền tảng Data Platform (chuẩn hoá Spark & Trino).

---

## 1. Kiến Trúc Cấu Hình (Terraform)
Chúng ta sẽ tạo ra một GKE Cluster bao gồm 2 nhóm máy chủ (Node Pool):
1. **`master-pool` (1 On-Demand Node)**: Chuyên dụng cho Spark Master, Trino Coordinator và các Statefull Service (như PostgreSQL, Metastore, Zookeeper, v.v.). Label: `role=master`.
2. **`worker-pool` (2 Spot Nodes)**: Dành riêng cho Spark Worker và Trino Worker nhằm tối ưu chi phí (giảm tới 90%). Spot nodes sẽ tự động có Taint `cloud.google.com/gke-spot=true:NoSchedule` và Label `role=worker`.

> [!NOTE]
> Mặc định kiến trúc này đảm bảo các Worker (không lưu trạng thái) có thể bị thu hồi (preempted) để tiết kiệm chi phí, trong khi Core Master luôn hoạt động xuyên suốt 24/7.

---

## 2. Triển Khai Hạ Tầng GKE Với Terraform

**Yêu cầu:** Máy bạn đã cài sẵn `gcloud` CLI (đã login auth) và `terraform`.

### Bước 2.1: Khởi tạo biến môi trường
Di chuyển vào thư mục terraform:
```bash
cd terraform
```

Chỉnh sửa file `variables.tf` để chắc chắn:
- `project_id`: Trùng với project của bạn trên GCP.
- `region`, `zone`: Vị trí đặt server (mặc định asia-southeast1-a).

### Bước 2.2: Chạy Terraform
```bash
terraform init
terraform plan
terraform apply
```
Gõ `yes` và nhấn Enter khi được yêu cầu xác nhận. Quá trình tạo GKE có thể mất tới 10-15 phút.

### Bước 2.3: Lấy credentials của cụm GKE
Khi Terraform chạy xong, nó sẽ in ra một lệnh (output: `connect_command`), ví dụ:
```bash
gcloud container clusters get-credentials data-platform-cluster --zone asia-southeast1-a --project my-gcp-project-id
```
Chạy lệnh đó để kết nối `kubectl` đến Cluster của bạn.

---

## 3. Cài Đặt Các Helm Operator

Môi trường Kubernetes cần các Operator để quan lý việc sống/chết/scaling tự động của Spark và Data service.

Từ thư mục gốc dự án:
```bash
chmod +x scripts/install_helm_charts.sh
./scripts/install_helm_charts.sh
```
Kịch bản này sẽ cài đặt Strimzi Kafka, Spark Operator trên K8s, Trino base, Prometheus và Airflow bằng Helm.

---

## 4. Cấu Hình Điều Hướng Pod (NodeSelector & Tolerations)

Để đảm bảo Master pod chạy vào On-Demand Node và Worker pod chạy vào Spot node, bạn cần khai báo `nodeSelector` và `tolerations` vào các file cấu hình YAML (`values.yaml` của helm hoặc file manifest thông thường).

### Mẫu cho Spark Master / Trino Coordinator
Các con này MUST chạy trên On-demand (master-pool):
```yaml
nodeSelector:
  role: master
```

### Mẫu cho Spark Worker / Trino Worker
Bắt buộc chạy trên Spot VMs:
```yaml
nodeSelector:
  role: worker

# Cho phép Pod cư trú (vượt quyền Taint của Spot node)
tolerations:
  - key: "cloud.google.com/gke-spot"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
```

## 5. Áp Dụng (Apply) Manifest Lên Cluster
Cuối cùng, dùng Kustomize hoặc lệnh apply tiêu chuẩn của k8s để đẩy cấu hình của bản thân lên:
```bash
kubectl apply -k k8s/base
```
Hoặc apply specific thư mục:
```bash
helm upgrade --install trino trino/trino --namespace data-platform -f helm-values/trino/dev.yaml
kubectl apply -f k8s/base/platform-services/spark/spark-pi-example.yaml
```

> [!TIP]
> Dùng lệnh `kubectl get nodes --show-labels` để xem và xác nhận lại Label của các Node trên GKE. Dùng `kubectl get pods -o wide` để xem chính xác Pod nào đang nằm trên Node nào.

