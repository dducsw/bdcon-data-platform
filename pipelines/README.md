# 🚀 Data Pipelines (Medallion Architecture)

Thư mục này chứa toàn bộ logic xử lý dữ liệu của nền tảng, được thiết kế theo **Kiến trúc Medallion (Bronze, Silver, Gold)**. Hệ thống hỗ trợ phân tích toàn diện cho dữ liệu E-commerce, bao gồm: **hiệu suất bán hàng (sales), sản phẩm (product performance), tồn kho (inventory)** và **hành vi người dùng (clickstream behavior analytics)**.

## 1. Mục tiêu và Nguyên tắc thiết kế
- **Medallion Architecture**: Phân tách dữ liệu thành 3 tầng (Bronze -> Silver -> Gold) để đảm bảo chất lượng dữ liệu tăng dần qua từng công đoạn.
- **Spark-on-K8s**: Sử dụng Spark Operator để chạy các Job biến đổi dữ liệu một cách linh hoạt trên Kubernetes.
- **Idempotency**: Mọi pipeline được thiết kế để có thể chạy lại bất cứ lúc nào mà không gây sai lệch dữ liệu.

## 2. Kiến trúc tổng quan

```text
    [ Source Systems ]         [ Kubernetes (GKE) Cluster ]
           |                          |
    [ Bronze Layer ] ---- ingest ----> [ Raw Data (Iceberg) ]
           |                          |
    [ Silver Layer ] -- transform --> [ Cleaned Data (Iceberg) ]
           |                          |
    [ Gold Layer ]   --- aggregate --> [ Business Views (Iceberg) ]
```

---

## 3. Các Tính năng Nâng cao (Advanced Features)

### 3.1. Chính xác & Idempotency (MERGE INTO)
Toàn bộ các layer Silver và Gold hiện đã chuyển từ cơ chế `.append()` sang **`MERGE INTO` (Upsert)**. 
- **Lợi ích**: Đảm bảo tính toàn vẹn dữ liệu (không trùng lặp) ngay cả khi chạy lại pipeline nhiều lần (Idempotency). Tự động cập nhật các thay đổi trạng thái (ví dụ: `order_status`) từ Bronze lên Silver.

### 3.2. Hạ tầng Giám sát (Audit Layer)
Hệ thống tích hợp sẵn module **Audit** tập trung tại `gold.pipeline_audit`.
- **Metadata thu thập**: ID lần chạy, tên Job, số lượng dòng vào/ra, thời gian thực thi, trạng thái (SUCCESS/FAILED) và nội dung lỗi chi tiết.
- **Observability**: Dễ dàng xây dựng Dashboard giám sát sức khỏe dữ liệu trên toàn bộ nền tảng.

### 3.3. Xử lý Tăng trưởng (Incremental Loading)
Sử dụng cơ chế **Watermark** (dựa trên cột thời gian) để chỉ xử lý dữ liệu mới phát sinh.
- **Hiệu năng**: Giảm thiểu tài nguyên tính toán và thời gian thực thi bằng cách bỏ qua các dữ liệu đã được xử lý ở các lần chạy trước.

### 3.4. Bảo trì Tự động (Maintenance Pipeline)
Iceberg đòi hỏi bảo trì định kỳ để duy trì hiệu năng cao nhất. Script `maintenance/iceberg_maintenance.py` thực hiện:
- **Compaction (Binpack)**: Gom hàng nghìn file nhỏ thành các file lớn tối ưu (256MB).
- **Snapshot Expiration**: Xóa lịch sử cũ để giải phóng dung lượng MinIO (giữ lại 10 bản gần nhất).
- **Orphan File Removal**: Tự động dọn dẹp các file rác phát sinh khi Job bị crash.

### 3.5. Phân tích Chuyên sâu (Advanced Gold Analytics)
- **Sessionization**: Pipeline `gold_sessions.py` tự động tổng hợp sự kiện thành các phiên làm việc (sessions), xác định Landing/Exit pages và theo dõi tỉ lệ chuyển đổi (Conversion tracking).

## 4. Quản lý và Giám sát
- **Kiểm tra trạng thái job**: `kubectl get sparkapplication -n data-platform`
- **Xem log thực thi**: `kubectl logs -f <driver-pod-name> -n data-platform`
- **Truy vấn kết quả**: Sử dụng Trino hoặc Spark SQL kết nối vào `catalog_iceberg`.
