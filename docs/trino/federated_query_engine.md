kubectl exec -it deployment/trino-coordinator -n data-platform -- trino --catalog iceberg_hive --execute "SHOW SCHEMAS;"


kubectl exec -i deployment/trino-coordinator -n data-platform -- trino --execute "SHOW CATALOGS;"


kubectl exec -i deployment/trino-coordinator -n data-platform -- trino --execute "SHOW CATALOGS;"
May 03, 2026 3:00:44 PM org.jline.utils.Log logr
WARNING: Unable to create a system terminal, creating a dumb terminal (enable debug logging for more information)
"catalog_iceberg"
"hive"
"iceberg_hive"
"kafka"
"postgres_source"
"system"
"tpcds"
"tpch"


kubectl exec -it deployment/trino-coordinator -n data-platform -- trino --execute "SELECT catalog_name,connector_name FROM system.metadata.catalogs"


Tôi đã cấu hình thành công các Catalog vào Trino. Bây giờ, chúng ta có thể thực hiện sức mạnh lớn nhất của Trino: **Truy vấn hợp nhất (Federated Query)** trên nhiều nguồn dữ liệu khác nhau.

Dưới đây là các ví dụ truy vấn từ cơ bản đến nâng cao (kết hợp các nguồn):

### 1. Truy vấn từng nguồn đơn lẻ (Single Source)

#### A. Query trực tiếp từ Postgres Source (Dữ liệu gốc)
Kiểm tra danh sách người dùng mới nhất trong cơ sở dữ liệu vận hành:
```sql
SELECT id, first_name, last_name, email, country 
FROM postgres_source.demo.users 
ORDER BY id DESC 
LIMIT 10;
```

#### B. Query từ Kafka (Dữ liệu Real-time)
Xem các sự kiện clickstream đang đổ về từ Topic `click-events` (qua mapping layer của Trino):
```sql
SELECT id, user_id, session_id, event_type, uri, timestamp 
FROM kafka.default.click_events 
ORDER BY timestamp DESC 
LIMIT 10;
```

#### C. Query từ Data Lakehouse (Dữ liệu Lớp Bronze - Iceberg)
Kiểm tra dữ liệu đã được Spark ingest và lưu trữ tối ưu dưới dạng Iceberg:
```sql
SELECT count(*) as total_events, event_type 
FROM iceberg_hive.bronze.events 
GROUP BY event_type;
```

---

### 2. Truy vấn kết hợp (Federated Queries)

#### A. Join Postgres (User Info) với Kafka (Real-time Events)
Đây là trường hợp cực kỳ hữu ích để làm **Real-time Enrichment**. Chúng ta lấy thông tin user từ Postgres để biết ai đang thực hiện hành động trên web ngay lúc này:
```sql
SELECT 
    k.timestamp, 
    u.first_name, 
    u.last_name, 
    u.email, 
    k.event_type, 
    k.uri
FROM kafka.default.click_events k
JOIN postgres_source.demo.users u ON k.user_id = u.id
ORDER BY k.timestamp DESC
LIMIT 20;
```

#### B. Kiểm tra sự sai lệch dữ liệu giữa Source (Postgres) và Lakehouse (Iceberg)
Dùng để kiểm tra xem quá trình Ingestion của Spark có bỏ lỡ record nào không (Data Validation):
```sql
SELECT 
    (SELECT count(*) FROM postgres_source.demo.orders) as source_count,
    (SELECT count(*) FROM iceberg_hive.bronze.orders) as lakehouse_count,
    ((SELECT count(*) FROM postgres_source.demo.orders) - (SELECT count(*) FROM iceberg_hive.bronze.orders)) as missing_records;
```

#### C. Phân tích hành trình khách hàng (Postgres + Iceberg)
Kết hợp thông tin đơn hàng (đã chốt - trong Postgres) với hành vi duyệt web lịch sử (trong Lakehouse) để xem khách hàng đã xem bao nhiêu sản phẩm trước khi mua:
```sql
SELECT 
    o.user_id,
    u.email,
    count(e.id) as total_views_in_lakehouse,
    count(distinct o.id) as total_orders_in_postgres
FROM postgres_source.demo.orders o
JOIN postgres_source.demo.users u ON o.user_id = u.id
JOIN iceberg_hive.bronze.events e ON o.user_id = e.user_id
WHERE e.event_type = 'product'
GROUP BY o.user_id, u.email
HAVING count(distinct o.id) > 1
ORDER BY total_views_in_lakehouse DESC;
```

---

### Cách thực hiện từ Terminal:
Bạn có thể chạy trực tiếp bằng lệnh `kubectl exec` như sau:

```powershell
# Ví dụ chạy câu lệnh Join giữa Kafka và Postgres
kubectl exec -it deployment/trino-coordinator -n data-platform -- trino --execute "
SELECT k.timestamp, u.email, k.event_type 
FROM kafka.default.click_events k 
JOIN postgres_source.demo.users u ON k.user_id = u.id 
LIMIT 10;"
```

Bạn có muốn tôi xây dựng một Dashboard hoặc một script kiểm tra tự động (Validation Script) dựa trên các câu query này không?



trino:demo> SELECT status, round(sum(sale_price), 2) as total_revenue
         -> FROM postgres_source.demo.order_items
         -> GROUP BY status
         -> ORDER BY total_revenue DESC;
         ->
   status   | total_revenue 
------------+---------------
 Shipped    |    3251045.56 
 Complete   |    2634432.21 
 Processing |    2241298.62 
 Cancelled  |    1604482.06 
 Returned   |    1126418.41 
(5 rows)

Query 20260503_151046_00024_vd2bv, FINISHED, 2 nodes
Splits: 16 total, 16 done (100.00%)
3.99 [183K rows, 802B] [45.8K rows/s, 201B/s]


