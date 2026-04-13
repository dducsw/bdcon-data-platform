# Hướng dẫn tạo và cấu hình GKE Cluster với Spot VMs

Tài liệu này hướng dẫn cách tạo một Standard Google Kubernetes Engine (GKE) cluster bao gồm một Node Pool cố định (On-Demand) cho các Database/Core Services và một Spot Node Pool (với 2 VMs) dành cho các Computation Workloads (như Spark, Trino workers) nhằm tiết kiệm chi phí.

## Yêu cầu trước khi bắt đầu
- Cài đặt `gcloud` CLI và đã auth (`gcloud auth login`).
- Đã cài đặt `kubectl` (`gcloud components install kubectl`).
- Project trên GCP đã được kích hoạt thanh toán (billing) và API `container.googleapis.com`.

## 1. Khởi tạo các biến môi trường
Mở terminal và set các biến sau:
```bash
export PROJECT_ID="<your-gcp-project-id>"
export REGION="asia-southeast1" # Có thể đổi thành us-central1 v.v.
export ZONE="asia-southeast1-a"
export CLUSTER_NAME="data-platform-cluster"
```

## 2. Tạo GKE Cluster (Node Pool mặc định - On-Demand)
Các services dạng stateful (Database PostgreSQL, Lưu trữ trạng thái MinIO, Kafka brokers, Core Control Plane) **vô cùng nhạy cảm** với sự gián đoạn. Do đó, chúng ta cần chạy các pod này trên Node Pool mặc định dùng On-Demand VM.

```bash
gcloud container clusters create $CLUSTER_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --num-nodes=1 \
    --machine-type=e2-standard-4 \
    --disk-size=100GB \
    --node-labels="env=production,workload=stateful" \
    --enable-ip-alias \
    --release-channel="stable"
```
*Lưu ý: Lệnh trên sẽ tạo một Node Pool mặc định tên là `default-pool` chạy xuyên suốt với 1 node trên mỗi Zone trong Region (Tổng cộng 3 nodes nếu bạn chọn region-based cluster).*

## 3. Thêm Spot Node Pool (2 VMs - Cho Spark/Trino Compute)
Bây giờ, tạo một Node Pool thứ 2 chuyên dụng cho Spark Executors, Airflow workers, hoặc Trino workers. Nhờ cờ `--spot`, chúng ta sẽ mua được Spot Instance rẻ hơn tới 60-90%.

```bash
gcloud container node-pools create compute-spot-pool \
    --cluster=$CLUSTER_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --machine-type=e2-standard-8 \
    --num-nodes=2 \
    --spot \
    --disk-size=100GB \
    --node-labels="env=production,workload=compute" \
    --node-taints="cloud.google.com/gke-spot=true:NoSchedule" \
    --enable-autoscaling --min-nodes=0 --max-nodes=4
```
*Giải thích:*
- `--spot`: Yêu cầu Spot Instances từ GCP.
- `--node-taints`: Thêm Taint `cloud.google.com/gke-spot=true:NoSchedule` ngăn ngừa các Pod không mong muốn nhảy vào node Spot (nếu không được chỉ định Tolerate).

## 4. Lấy Config `kubectl`
Sinh kubeconfig cho cluster mới:
```bash
gcloud container clusters get-credentials $CLUSTER_NAME \
    --region=$REGION \
    --project=$PROJECT_ID
```

## 5. Cấu hình Pod Deployment Lên Spot Node Pool
Sau khi cluster có 2 Spot nodes, bạn cần chỉ định cho các Workload (ví dụ Spark hoặc Trino) cấu hình tương ứng để chúng chủ động deploy lên con Spot này. 

Dưới đây là một ví dụ về khai báo `tolerations` và `nodeSelector` thêm vào Pod spec (`deployment.yaml` của Stateful/Trino/Spark).

```yaml
spec:
  # Ép Pod chạy trên Node có label này
  nodeSelector:
    workload: compute
  
  # Được phép vượt qua ranh giới của Spot Taint
  tolerations:
  - key: "cloud.google.com/gke-spot"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
```

## 6. Xử lý kịch bản GKE Graceful Termination
Spot Instances có thể bị lấy lại (Preempt) sau 24h hoặc bất cứ lúc nào Google cần tài nguyên với cảnh báo trước khoảng 30s. Bạn hãy đảm bảo Pod Disruption Budgets (PDBs) đã được khai báo cẩn thận cho Data Services đang chạy và Workload của bạn có cơ chế auto restart graceful shutdown (Mặc định GKE Node Termination Handler sẽ tiếp quản sự kiện này).
