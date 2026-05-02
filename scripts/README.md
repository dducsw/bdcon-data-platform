# Scripts Utility - K8s Data Platform

Thư mục này chứa các script hỗ trợ quản lý vòng đời, cài đặt và kiểm tra hệ thống Data Platform trên Kubernetes (GKE).

## 📂 Cấu trúc thư mục

| Thư mục | Mục đích |
| :--- | :--- |
| `bootstrap/` | Cài đặt các Operator, Helm charts và cấu hình ban đầu. |
| `cleanup/` | Các script dọn dẹp tài nguyên và tắt cluster an toàn để tiết kiệm chi phí. |
| `deploy/` | Hỗ trợ quá trình triển khai và lập lịch cho cluster. |
| `verify/` | Các công cụ kiểm tra dữ liệu, producer/consumer mẫu cho Kafka. |

---

## 🚀 Chi tiết các tập lệnh

### 🛠️ 1. Bootstrap (Khởi tạo hệ thống)

Nhóm script này được sử dụng sau khi cluster K8s đã sẵn sàng (sau khi chạy Terraform).

*   **`install_helm_charts.sh`**: Tự động cài đặt các thành phần cốt lõi qua Helm:
    *   Strimzi Kafka Operator
    *   External Secrets Operator (ESO)
    *   Cilium Ingress Controller (hoặc NGINX Ingress)
    *   Kube-Prometheus-Stack (Prometheus & Grafana)
    *   Apache Airflow (KubernetesExecutor)
    *   Apache Spark Operator
    *   Trino Cluster
    *   *Cách dùng:* `chmod +x install_helm_charts.sh && ./install_helm_charts.sh`
*   **`init_kafka_topics.sh`**: Khởi tạo nhanh các Kafka topic cần thiết bằng cách truy cập vào pod Kafka broker.
    *   *Cách dùng:* `./init_kafka_topics.sh`
*   **`get_helm.sh`**: Script tiện ích để cài đặt Helm binary nếu máy chưa có.

### 🧹 2. Cleanup (Dọn dẹp & Tiết kiệm chi phí)

Khi không sử dụng platform (ví dụ: ban đêm hoặc cuối tuần), bạn nên sử dụng các script này để đưa chi phí compute về 0 mà không cần xóa cluster.

*   **`stop_cluster_vms_safe.ps1` (Khuyên dùng)**: Script PowerShell thông minh thực hiện các bước:
    1. Xóa các PodDisruptionBudgets (để không chặn việc drain node).
    2. Scale down các deployment (Airflow, Trino, Spark, v.v.) về 0.
    3. Tắt Kafka theo đúng trình tự (Entity Operator -> Broker -> Controller).
    4. Scale down các statefulset (MinIO, Postgres, Redis).
    5. Resize tất cả Node Pools của GKE về 0.
    *   *Cách dùng:* `powershell ./stop_cluster_vms_safe.ps1`
*   **`stop_cluster_vms.ps1`**: Phiên bản đơn giản hơn của script trên.

### 🚢 3. Deploy (Triển khai)

*   **`gke_schedule.sh`**: Script hỗ trợ quản lý trạng thái cluster (Start/Stop) để tự động hóa việc bật/tắt tài nguyên theo giờ làm việc (ví dụ: 14:00 - 22:00 ICT).
    *   *Cách dùng:*
        *   `./scripts/deploy/gke_schedule.sh start`: Bật toàn bộ dịch vụ (Postgres, MinIO, Kafka, Trino, Airflow).
        *   `./scripts/deploy/gke_schedule.sh stop`: Tắt toàn bộ dịch vụ về 0 replicas.

### 🔍 4. Verify (Kiểm tra & Tiện ích)

Dùng để test luồng dữ liệu end-to-end.

*   **`json_producer.py`**: Python script để đẩy dữ liệu JSON mẫu vào Kafka topic.
*   **`read_topic.py`**: Đọc dữ liệu từ Kafka topic để kiểm tra.
*   **`kafka_to_redis.py`**: Script mẫu minh họa việc tiêu thụ dữ liệu từ Kafka và lưu vào Redis.
    *   *Lưu ý:* Cài đặt dependencies trước khi dùng: `pip install -r verify/requirements.txt`

---

## 📋 Yêu cầu hệ thống

Để chạy các script này, máy của bạn cần cài đặt:
- **Google Cloud SDK (`gcloud`)**: Đã login và set đúng project.
- **`kubectl`**: Đã kết nối tới cluster (`gcloud container clusters get-credentials ...`).
- **Helm v3**: Dành cho các script bootstrap.
- **PowerShell 7+**: Nếu sử dụng các script trong thư mục `cleanup/`.
- **Python 3.9+**: Dành cho các script trong thư mục `verify/`.

## ⚠️ Lưu ý quan trọng

1.  **Quyền thực thi**: Trên Linux/macOS, hãy nhớ cấp quyền thực thi cho các file `.sh`:
    ```bash
    chmod +x scripts/**/*.sh
    ```
2.  **Thứ tự thực hiện**: Luôn chạy Terraform trước khi chạy các script trong `bootstrap/`.
3.  **Khôi phục hệ thống**: Sau khi đã chạy `stop_cluster_vms_safe.ps1`, để bật lại hệ thống, bạn chỉ cần chạy lại `terraform apply` hoặc dùng lệnh gcloud để resize node pools lên số lượng mong muốn.
