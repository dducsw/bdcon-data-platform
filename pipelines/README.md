# Data Ingestion & Transformation Pipelines

Hệ thống pipeline dữ liệu được thiết kế theo kiến trúc **Medallion Architecture** (Bronze -> Silver -> Gold) chạy trên nền tảng **Spark on Kubernetes (GKE)** và lưu trữ dưới định dạng **Apache Iceberg**.

## 1. Kiến trúc tổng quan

```text
    [ Local Laptop ]           [ Kubernetes (GKE) Cluster ]
    +--------------+           +--------------------------+
    |  Datagen     | --(pf)--> |  Postgres DB (Source)    |
    | (Generator)  | --(pf)--> |  Kafka Cluster (Events)  |
    +--------------+           +------------+-------------+
                                            |
                                   (Spark Ingestion)
                                            v
                               +------------+-------------+
                               |    Bronze Layer (Raw)    |
                               +------------+-------------+
                                            |
                                   (Cleaning/Deduplicate)
                                            v
                               +------------+-------------+
                               |   Silver Layer (Curated) |
                               +------------+-------------+
                                            |
                                   (Aggregation/Joins)
                                            v
                               +------------+-------------+
                               |    Gold Layer (Business) |
                               +--------------------------+
                                  (Stored in Iceberg/S3)
```

---

## 2. Luồng thực thi (Execution Flow)

### Bước 1: Khởi tạo hạ tầng (Source Infrastructure)
Trước khi chạy pipeline, cần triển khai database nguồn và Kafka trong cụm:
```bash
kubectl apply -f pipelines/ingestion/postgres.yaml
kubectl apply -f pipelines/ingestion/kafka.yaml
```

### Bước 2: Kết nối dữ liệu từ Local
Sử dụng port-forward để `datagen` (chạy tại máy local) có thể ghi dữ liệu vào K8s:
```bash
# Terminal 1: Forward Postgres
kubectl port-forward svc/postgres-source 5433:5432 -n data-platform

# Terminal 2: Forward Kafka
kubectl port-forward svc/data-platform-kafka-kafka-bootstrap 9092:9092 -n data-platform
```

### Bước 3: Thực thi các tầng Pipeline (Medallion)

#### 🥉 Tầng Bronze (Raw Data)
Kéo dữ liệu thô từ Postgres (JDBC) và Kafka (Streaming) vào Iceberg.
- **Job ví dụ**: `kubectl apply -f pipelines/bronze/spark-ingest-users.yaml`
- **Tối ưu**: Dữ liệu được phân vùng theo ngày (`days(created_at)`).

#### 🥈 Tầng Silver (Cleaned & Deduplicated)
Làm sạch, ép kiểu và loại bỏ trùng lặp dữ liệu.
- **Job ví dụ**: `kubectl apply -f pipelines/silver/spark-transform-users.yaml`
- **Tối ưu**: 
    - **Bloom Filter**: Bật cho `session_id` (events) và `email` (users) để tra cứu nhanh.
    - **Sort Order**: Sắp xếp vật lý theo `user_id`, `order_id` để tối ưu phép JOIN.

#### 🥇 Tầng Gold (Business & Aggregated)
Tổng hợp dữ liệu phục vụ báo cáo và phân tích.
- **Job ví dụ**: `kubectl apply -f pipelines/gold/spark-agg-user-statistics.yaml`
- **Sản phẩm**: Bảng `user_statistics`, `sales_performance`.

---

## 3. Quản lý và Giám sát
- **Kiểm tra trạng thái job**: `kubectl get sparkapplication -n data-platform`
- **Xem log thực thi**: `kubectl logs -f <driver-pod-name> -n data-platform`
- **Truy vấn kết quả**: Sử dụng Trino kết nối vào catalog `catalog_iceberg`.

## 4. Các kỹ thuật tối ưu hóa đã áp dụng
- **Hidden Partitioning**: Tiết kiệm dung lượng và tăng tốc filter mà không cần thêm cột phụ.
- **Write Distribution (Hash)**: Tránh tình trạng "small files" khi ghi dữ liệu phân vùng lớn.
- **Parquet Bloom Filters**: Tối ưu hóa các truy vấn lọc chính xác (Point lookup).
