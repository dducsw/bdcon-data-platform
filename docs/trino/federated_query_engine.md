# Trino Federated Query Engine: Hướng dẫn Truy vấn Hợp nhất

Trino đóng vai trò là "bộ não" tính toán trong Data Platform của chúng ta, cho phép truy vấn dữ liệu từ nhiều nguồn khác nhau (Postgres, Iceberg, Kafka, ...) bằng một ngôn ngữ SQL duy nhất mà không cần di chuyển dữ liệu.

---

## 1. Kết nối vào Trino Cluster

Bạn có thể kết nối vào Trino Coordinator đang chạy trên Kubernetes bằng lệnh sau:

```powershell
# Truy cập vào CLI của Trino
kubectl exec -it deployment/trino-coordinator -n data-platform -- trino
```

Để kiểm tra các nguồn dữ liệu (Catalogs) đã được cấu hình:
```sql
SHOW CATALOGS;
```

**Các Catalog chính hiện có:**
*   `postgres_source`: Cơ sở dữ liệu vận hành (Operational DB).
*   `iceberg_hive`: Data Lakehouse (Bronze, Silver, Gold layers).
*   `tpcds` & `tpch`: Dữ liệu mẫu dùng cho Benchmark.

---

## 2. Truy vấn Đơn nguồn (Single Source Query)

Trước khi thực hiện Join, chúng ta có thể kiểm tra dữ liệu ở từng nguồn riêng biệt.

### A. Operational Database (Postgres)
Kiểm tra thông tin người dùng mới nhất:
```sql
SELECT id, first_name, last_name, email, country 
FROM postgres_source.demo.users 
ORDER BY id DESC 
LIMIT 5;
```

### B. Data Lakehouse (Iceberg - Bronze Layer)
Xem các sự kiện clickstream đã được lưu trữ trong Lakehouse:
```sql
SELECT event_type, count(*) as event_count
FROM iceberg_hive.bronze.events 
GROUP BY event_type;
```

---

## 3. Truy vấn Hợp nhất (Federated Query)

Đây là sức mạnh thực sự của Trino: Kết hợp dữ liệu từ nhiều hệ thống khác nhau.

### A. Kiểm tra sự sai lệch dữ liệu (Data Validation)
So sánh số lượng bản ghi giữa cơ sở dữ liệu gốc (Postgres) và Lakehouse (Iceberg) để đảm bảo quá trình Ingestion không bị mất mát dữ liệu.

```sql
SELECT 
    (SELECT count(*) FROM postgres_source.demo.orders) as source_count,
    (SELECT count(*) FROM iceberg_hive.bronze.orders) as lakehouse_count,
    ((SELECT count(*) FROM postgres_source.demo.orders) - (SELECT count(*) FROM iceberg_hive.bronze.orders)) as missing_records;
```

### B. Phân tích Hành trình Khách hàng (Customer Journey)
Kết hợp thông tin đơn hàng (Orders - Postgres) với hành vi duyệt web (Events - Iceberg) để tìm ra những khách hàng xem sản phẩm nhiều nhất trước khi chốt đơn.

```sql
SELECT 
    o.user_id,
    u.email,
    count(e.id) as total_views_in_lakehouse,
    count(distinct o.order_id) as total_orders_in_postgres
FROM postgres_source.demo.orders o
JOIN postgres_source.demo.users u ON o.user_id = u.id
JOIN iceberg_hive.bronze.events e ON o.user_id = e.user_id
WHERE e.event_type = 'product'
GROUP BY o.user_id, u.email
HAVING count(distinct o.order_id) > 1
ORDER BY total_views_in_lakehouse DESC
LIMIT 10;
```

---

## 4. Kết quả Thực thi Thực tế (Execution Logs)

*Cập nhật ngày: 05/05/2026*

### Kết quả Data Validation:
```text
 source_count | lakehouse_count | missing_records 
--------------+-----------------+-----------------
       126125 |          126125 |               0 
(1 row)
```

> [!TIP]
> Kết quả cho thấy dữ liệu giữa Postgres và Lakehouse hoàn toàn đồng bộ (0 record thất thoát).

### Top 10 Khách hàng tích cực nhất:
```text
 user_id |             email             | total_views_in_lakehouse | total_orders_in_postgres 
---------+-------------------------------+--------------------------+--------------------------
   44024 | brandonyoung@example.net      |                       28 |                        4 
   91215 | carriewood@example.com        |                       20 |                        4 
   20144 | williamdalton@example.net     |                       20 |                        4 
   63545 | pamelafuller@example.com      |                       20 |                        4 
   34137 | stephaniephillips@example.net |                       18 |                        3 
   95123 | stephanieray@example.net      |                       16 |                        4 
   83734 | karenjimenez@example.org      |                       16 |                        4 
   78458 | martinwarner@example.org      |                       16 |                        4 
   13421 | patriciabryant@example.org    |                       16 |                        4 
   23573 | brianramirez@example.com      |                       16 |                        4 
(10 rows)
```

---

## 5. Lưu ý khi thực hiện Federated Query
1.  **Predicate Pushdown**: Trino sẽ cố gắng đẩy các điều kiện `WHERE` xuống nguồn dữ liệu gốc để tối ưu hóa. Hãy luôn sử dụng filter nếu có thể.
2.  **Schema Drift**: Đảm bảo schema ở các nguồn không bị thay đổi đột ngột làm gãy các câu query Join.
3.  **Resource Management**: Các câu query Join lớn giữa nhiều nguồn có thể tiêu tốn nhiều bộ nhớ trên Trino Workers.

---
*Tài liệu này được tạo tự động và cập nhật dựa trên trạng thái thực tế của hệ thống.*
