# Bronze Layer Ingestion Pipeline

Thư mục này chứa các pipeline ingest dữ liệu từ nguồn (PostgreSQL) vào Data Lake lớp Bronze dưới định dạng **Apache Iceberg**.

## 🚀 Quy trình vận hành

### 1. Cập nhật Spark Script
Mỗi khi bạn thay đổi code Python (ví dụ `bronze_jdbc_ingest.py`), bạn cần cập nhật ConfigMap trong K8s để các Spark Job nhận được code mới nhất.

```powershell
kubectl create configmap bronze-ingest-scripts `
  --from-file=bronze_jdbc_ingest.py=pipelines/bronze/bronze_jdbc_ingest.py `
  -n data-platform --dry-run=client -o yaml | kubectl apply -f -
```

### 2. Triển khai Spark Job (Ingest)
Để bắt đầu quá trình ingest dữ liệu (ví dụ bảng `users`), hãy apply file YAML tương ứng:

```powershell
# Xóa job cũ nếu có (để chạy lại snapshot mới)
kubectl delete sparkapplication.sparkoperator.k8s.io bronze-ingest-users -n data-platform

# Chạy job mới
kubectl apply -f pipelines/bronze/spark-ingest-users.yaml -n data-platform
```

### 3. Theo dõi Log
Kiểm tra tiến trình ingest thông qua log của Driver Pod:

```powershell
kubectl logs bronze-ingest-users-driver -n data-platform -f
```

---

## 🔍 Kiểm tra dữ liệu qua Trino

Sau khi job báo `Ingestion completed successfully!`, bạn có thể kiểm tra dữ liệu ngay lập tức bằng Trino CLI.

### Truy cập Trino CLI
Tìm tên Pod Trino Coordinator:
```powershell
$TRINO_POD = kubectl get pods -n data-platform -l app=trino,component=coordinator -o name
```

### Query kiểm tra
Sử dụng catalog `iceberg_hive` để truy vấn lớp Bronze:

```powershell
# Liệt kê các bảng
kubectl exec -it $TRINO_POD -n data-platform -- trino --catalog iceberg_hive --execute "SHOW TABLES FROM bronze"

# Xem dữ liệu mẫu
kubectl exec -it $TRINO_POD -n data-platform -- trino --catalog iceberg_hive --execute "SELECT * FROM bronze.users LIMIT 10"

# Kiểm tra cấu trúc bảng Iceberg
kubectl exec -it $TRINO_POD -n data-platform -- trino --catalog iceberg_hive --execute "SHOW CREATE TABLE bronze.users"
```

---

## 🛠 Lưu ý về cấu hình (Troubleshooting)

### Warehouse Location
Toàn bộ dữ liệu lớp Bronze được lưu trữ tại: `s3a://iceberg/lakehouse/bronze.db/`

### Sửa lỗi treo (Hanging Issues)
Các job đã được tối ưu hóa với:
- **Magic Committer:** Tránh deadlock khi ghi dữ liệu lớn vào MinIO.
- **Fast Upload:** Giảm thiểu việc ghi đệm vào Disk của Pod.
- **Hive Metastore Sync:** Đảm bảo Hive Metastore đã được cấu hình đủ S3 Credentials để tránh lỗi Access Denied.

Nếu Hive Metastore thay đổi cấu hình, hãy thực hiện restart:
```powershell
kubectl rollout restart statefulset/hive-metastore -n data-platform
```

---
*Duy trì bởi: Data Platform Team*
