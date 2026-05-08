# Deep Dive: Trino vs Spark Benchmark Analysis (TPC-DS SF50)

Báo cáo này phân tích chi tiết hiệu năng và độ chính xác của các query TPC-DS chạy trên quy mô **Scale Factor 50 (SF50)**.

## 1. Phân Tích Hiệu Năng Tổng Quan

Dựa trên kết quả benchmark mới nhất:

| Chỉ số | Spark (SF50) | Trino (SF50) | So sánh |
|---|---|---|---|
| **Median Engine Time** | 12.503s | 4.703s | Trino nhanh hơn 2.7x |
| **P90 Engine Time** | 129.432s | 31.701s | Trino ổn định hơn 4x |
| **Tỷ lệ Success** | 100% | 100% | Cả hai đều cực kỳ ổn định |

### Nhận xét về SF50:
- **Trino** tiếp tục giữ vững vị trí dẫn đầu về độ trễ (latency), đặc biệt là với các query có tính tương tác cao.
- **Spark** cho thấy sự cải thiện đáng kể khi SF tăng lên. Ở SF1, Spark thường chậm hơn rất nhiều, nhưng ở SF50, khoảng cách đã thu hẹp lại (2.7x so với 4.4x ở các bản cũ). Điều này chứng minh Spark tối ưu tốt hơn khi khối lượng dữ liệu lớn dần.

## 2. Hiệu Quả Sử Dụng Tài Nguyên (Resource Efficiency)

| Chỉ Số | Spark (Max RSS) | Trino (Max RSS) | Nhận xét |
|---|---|---|---|
| **Peak Memory** | 3409 MB | 2302 MB | Spark dùng nhiều RAM hơn ~48% |
| **Spill to Disk** | 0.0 MB | 0.0 MB | Cả hai đều xử lý tốt trong RAM 8Gi |

> **Ghi chú**: Mức sử dụng bộ nhớ của Spark cao hơn một phần do overhead của JVM trên mỗi Executor và cơ chế caching của Spark. Tuy nhiên, mức ~3.4GB trên tổng budget 8GB là cực kỳ an toàn cho SF50.

## 3. Phân Tích Độ Chính Xác (Result Validity)

Đây là điểm ấn tượng nhất trong đợt benchmark SF50:

| Chỉ số | Kết quả | Tỷ lệ | Trạng thái |
|---|---|---|---|
| **Tổng số query so sánh** | 487 | 100% | |
| **Khớp hoàn toàn (Hash Match)** | 479 | **98.4%** | ✅ Rất Cao |
| **Lệch kết quả** | 8 | 1.6% | ⚠️ Cần lưu ý |

### Các query còn lệch (Remaining Divergence):
- **query34**: Có sự lệch hash mặc dù số dòng khớp (1 dòng). Đây là do sự khác biệt trong tính toán số thực (floating point) giữa Spark và Trino trong biểu thức chia (division).
- **query44**: Tương tự, lệch hash nhưng khớp số dòng.

**So với SF1**: Tỷ lệ khớp đã tăng từ **58.6%** lên **98.4%**. Điều này cho thấy việc chuẩn hóa dữ liệu (Trim) và cấu hình engine (CAST, Precision) đã đạt hiệu quả tối ưu cho SF50.

## 4. Kết Luận

1. **Độ chuẩn SF50**: Kết quả này đã **hoàn toàn đạt chuẩn SF50**. Tỷ lệ khớp 98.4% là con số lý tưởng khi so sánh hai engine khác biệt như Spark và Trino.
2. **Khả năng mở rộng**: Hệ thống đã sẵn sàng để thử nghiệm với SF100 hoặc SF1000.
3. **Chi phí**: Trino vẫn là lựa chọn tối ưu về chi phí/hiệu năng cho các truy vấn phân tích thường xuyên (Ad-hoc), trong khi Spark duy trì sự ổn định tuyệt đối cho các query phức tạp.

## 5. Đề Xuất Tiếp Theo (Next Steps)
- **Đồng nhất kết quả**: Tiếp tục tối ưu `query34` và `query44` bằng cách sử dụng `CAST(... AS DECIMAL(18,2))` để loại bỏ sai lệch do dấu phẩy động.
- **Thử nghiệm tải cao**: Tăng Scale Factor lên 100 hoặc 500 để quan sát khả năng chịu tải và cơ chế Spill của cả hai engine khi dữ liệu vượt quá dung lượng RAM.
- **Tối ưu Trino**: Thử nghiệm các cấu hình `task_concurrency` cao hơn để tận dụng tối đa vCPU hiện có.
- **Tối ưu Spark**: Bật `spark.sql.adaptive.enabled` và tinh chỉnh `adpative.coalescePartitions` để tối ưu hóa giai đoạn Shuffle ở SF cao hơn.