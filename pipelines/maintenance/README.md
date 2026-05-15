# Iceberg Table Maintenance Guide

Tài liệu này hướng dẫn chi tiết về các hoạt động bảo trì bảng (Table Maintenance) cho hệ thống Data Lakehouse sử dụng Apache Iceberg. Việc bảo trì định kỳ là cực kỳ quan trọng để đảm bảo hiệu suất truy vấn cao và tối ưu hóa chi phí lưu trữ trên MinIO.

## 1. Tổng quan các tác vụ bảo trì

Dữ liệu trong Iceberg được lưu trữ dưới dạng các file Parquet bất biến. Qua thời gian, các Job Ingestion sẽ tạo ra hàng nghìn file nhỏ (Small Files) và hàng trăm bản sao lịch sử (Snapshots). Nếu không được xử lý, chúng sẽ làm chậm Spark khi phải quét metadata.

Script `iceberg_maintenance.py` thực hiện 4 tác vụ chính:
1. **Compaction**: Gom các file nhỏ thành các file lớn tối ưu.
2. **Snapshot Expiration**: Xóa lịch sử cũ để giải phóng dung lượng.
3. **Manifest Rewriting**: Tối ưu hóa file danh mục metadata.
4. **Orphan File Removal**: Xóa các file "rác" không thuộc về bảng nào.

---

## 2. Chi tiết các Procedure & Cấu hình nâng cao

### 2.1 Compaction (`rewrite_data_files`)
Tác vụ này đọc các file nhỏ và ghi lại thành các file lớn hơn (thường là 128MB hoặc 256MB).

**Các tham số quan trọng:**
* `target-file-size-bytes`: Kích thước file đích (mặc định ~512MB). Khuyên dùng: `268435456` (256MB).
* `min-input-files`: Số lượng file tối thiểu để kích hoạt compaction (mặc định 5).
* `strategy`: 
    * `binpack`: Chỉ gom file (nhanh, ít tốn tài nguyên).
    * `sort`: Sắp xếp lại dữ liệu khi gom (giúp Data Skipping cực tốt).
* `sort_order`: Cấu hình Z-Order để tối ưu truy vấn đa chiều.

**Ví dụ gọi thủ công nâng cao:**
```sql
CALL catalog_iceberg.system.rewrite_data_files(
  table => 'silver.events',
  strategy => 'sort',
  sort_order => 'zorder(user_id, session_id)',
  options => map(
    'target-file-size-bytes', '268435456',
    'min-input-files', '10'
  )
)
```

### 2.2 Expire Snapshots (`expire_snapshots`)
Mỗi khi bạn ghi dữ liệu, Iceberg tạo ra 1 Snapshot mới. Mặc định Iceberg giữ lại tất cả.

**Các tham số quan trọng:**
* `older_than`: Xóa các snapshot trước thời điểm này.
* `retain_last`: Số lượng snapshot tối thiểu luôn phải giữ lại (để tránh lỗi nếu có Job đang đọc).

**Khuyên dùng:** Giữ lại snapshots trong 7 ngày gần nhất hoặc tối thiểu 10 bản ghi cuối cùng.

### 2.3 Remove Orphan Files (`remove_orphan_files`)
Đôi khi Job bị crash giữa chừng, các file Parquet đã được ghi xuống MinIO nhưng chưa kịp commit vào Metadata. Những file này gọi là "mồ côi".

**Tham số:**
* `older_than`: Chỉ xóa các file mồ côi đã tồn tại lâu hơn X thời gian (mặc định 3 ngày) để tránh xóa nhầm các file đang được ghi bởi các Job đang chạy.

---

## 3. Lịch trình bảo trì khuyến nghị (Best Practices)

| Tác vụ | Tần suất | Lưu ý |
| :--- | :--- | :--- |
| **Compaction (Binpack)** | Sau mỗi Job Ingest lớn | Giúp truy vấn Silver/Gold nhanh ngay lập tức. |
| **Compaction (Z-Order)** | Hàng tuần | Tốn tài nguyên tính toán nhưng tăng tốc truy vấn cực lớn. |
| **Expire Snapshots** | Hàng ngày | Giúp MinIO không bị đầy dung lượng. |
| **Remove Orphan Files** | Hàng tuần | Dọn dẹp rác tồn đọng. |

## 4. Cách chạy Script bảo trì

Bạn có thể chạy script bằng `spark-submit`:

```bash
spark-submit \
  --master k8s://https://<kubernetes-api> \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.catalog_iceberg=org.apache.iceberg.spark.SparkCatalog \
  docker-dev/pipelines/maintenance/iceberg_maintenance.py
```

*Lưu ý: Luôn đảm bảo không có Job ghi dữ liệu lớn nào đang chạy đồng thời vào cùng một bảng khi thực hiện `rewrite_data_files` với chiến lược `sort` để tránh xung đột tài nguyên.*
