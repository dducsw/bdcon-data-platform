# Giải thuật Kalman Filter cho Dữ liệu Bus GPS trong Kiến trúc Lakehouse

Tài liệu này hướng dẫn cách tiếp cận và hiện thực giải thuật Kalman Filter nhằm làm mượt (smoothing) dữ liệu GPS (tọa độ `x`, `y`) của xe buýt (`BusWayPoint`). Đồng thời, định hướng cách tích hợp quá trình làm mượt này vào kiến trúc Data Lakehouse.

## 1. Mục tiêu của Kalman Filter đối với Bus GPS

Dữ liệu GPS thu thập từ các xe buýt thường gặp hiện tượng nhiễu (noise) do mất tín hiệu, phản xạ tòa nhà cao tầng, hoặc sai số thiết bị.
Kalman Filter là một giải thuật tối ưu giúp:
- **Ước lượng trạng thái (State Estimation)**: Dự đoán vị trí thực tế của xe dựa trên vị trí đo được và vận tốc.
- **Làm mượt quỹ đạo (Trajectory Smoothing)**: Loại bỏ các điểm GPS bị nhảy vọt (outliers), tạo ra quỹ đạo di chuyển liền mạch.

Trạng thái (State) của xe buýt tại một thời điểm $t$ có thể được mô hình hóa gồm:
- Vị trí: $x$ (Longitude), $y$ (Latitude)
- Vận tốc: $v_x$, $v_y$

## 2. Tích hợp Kalman Filter vào Kiến trúc Lakehouse (Medallion Architecture)

Trong dự án Lakehouse (sử dụng MinIO + Iceberg + Spark + Gravitino), việc làm mượt dữ liệu qua Kalman Filter sẽ đóng vai trò như một **Data Transformation Step** chuyển đổi từ lớp Bronze sang Silver.

### 2.1. Bronze Layer (Raw Data)
- **Nguồn:** Dữ liệu streaming từ Kafka (đã được parse từ protobuf `BusWayPoint`).
- **Lưu trữ:** Apache Iceberg table (ví dụ: `system.bronze.buswaypoint`).
- **Đặc điểm:** Chứa nguyên bản các tọa độ $x$, $y$, $speed$, và $datetime$ chưa qua xử lý, có thể lẫn nhiễu.

### 2.2. Silver Layer (Cleaned & Smoothed Data)
- **Xử lý:** Một Spark Streaming (Micro-batch) hoặc một Batch Job định kì sẽ đọc dữ liệu từ bảng Bronze, nhóm (group by) theo từng `vehicle` (biển số xe buýt), và sắp xếp theo `datetime`.
- **Áp dụng Kalman Filter:** Sử dụng **Pandas UDF (Grouped Map)** trong PySpark. Mỗi partition tương ứng với 1 xe sẽ đi qua hàm Kalman Filter của Python (sử dụng thư viện `pykalman` hoặc tự code numpy) để tính toán lại giá trị $x$ và $y$.
- **Lưu trữ:** Apache Iceberg table (ví dụ: `system.silver.buswaypoint_smoothed`).
- **Đặc điểm:** Tọa độ GPS đã mượt mà, sẵn sàng phục vụ cho việc tính toán quãng đường, vận tốc trung bình, hoặc hiển thị lên bản đồ (Superset).

### 2.3. Gold Layer (Analytics & Serving)
- **Xử lý:** Aggregate dữ liệu từ bảng Silver để tính toán các metric nghiệp vụ (mật độ xe, thời gian kẹt xe, lộ trình di chuyển phổ biến).
- **Phục vụ (Serving):** Đưa dữ liệu qua Trino để Superset truy vấn, hoặc đưa vào Redis để frontend gọi API real-time.

## 3. Khuyến nghị Kỹ thuật khi triển khai với PySpark

1. **Windowing & Grouping:** Dữ liệu GPS cần được sắp xếp theo thời gian mới có thể chạy Kalman Filter chính xác. Do đó, cần partition data theo `vehicle` và sort theo `datetime`.
2. **Pandas Pandas UDF (`applyInPandas`):** Vì PySpark thao tác trên các phân tán, ta gom toàn bộ hành trình của một chiếc xe buýt trong khoảng thời gian (ví dụ: 1 giờ hoặc 1 ngày) thành một Pandas DataFrame, sau đó áp dụng thuật toán Kalman Filter cục bộ (local computation) trên DataFrame đó rồi trả về kết quả.
3. **Thư viện Python:** Cài đặt package `pykalman` (`pip install pykalman`) trên các worker node (hoặc trong image Docker Spark) để tránh tự hard-code ma trận, giảm thiểu lỗi toán học. Hoặc tự implement bằng NumPy để tối ưu dependencies.

*(Xem file `notebooks/kalman_filter_bus_gps.ipynb` để tham khảo mã nguồn PySpark)*
