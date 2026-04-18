# Spark Operator trên GKE - Quá trình Cấu hình & Hiện trạng Kiến trúc (18/04/2026)

Tài liệu này mô tả chi tiết quá trình khắc phục các sự cố của Spark Operator khi chạy trên Google Kubernetes Engine (GKE), cùng với cấu trúc cấu hình và thiết kế hiện tại của dự án. 

## 1. Các sự cố đã xử lý và Giải pháp

Trong quá trình deploy và submit Spark Job `spark-minio-test-job`, chúng ta đã gặp một loạt các vấn đề đặc thù của kiến trúc K8s kết hợp MinIO (S3A) và Hive Metastore (HMS). Dưới đây là cách chúng được xử lý:

### 1.1 Webhook Volumes bị vô hiệu hoá (Ignored Volumes & VolumeMounts)
- **Vấn đề**: Thông thường, cấu hình `volumes` và `volumeMounts` ở spec CRD `SparkApplication` sẽ được dịch tự động bởi Mutating Admission Webhook của Spark Operator. Tuy nhiên, webhook này bị `disable: true` trong values của cluster để giảm phụ thuộc `cert-manager`. Do đó, YAML không thể mount `ConfigMap` chứa script python thẳng vào pod.
- **Giải pháp**: Thay vì ép mount `ConfigMap`, script test `spark_hive_minio_test.py` được **upload thẳng vào MinIO** (`datalake/scripts/...`). Sau đó, manifest đọc file trực tiếp thông qua URI `s3a://datalake/scripts/spark_hive_minio_test.py`.

### 1.2 Lỗi ClassNotFound đối với S3A Credential Provider
- **Vấn đề**: Các file cấu hình cũ sử dụng `org.apache.hadoop.fs.s3a.EnvironmentVariableCredentialsProvider` cho cấu hình xác thực S3 bằng biến môi trường. Class này không hợp lệ và gây crash driver/operator ở môi trường hiện tại.
- **Giải pháp**: 
  1. Gỡ bỏ tuỳ chọn credentials provider khỏi `hadoopConf` và mã nguồn Python. 
  2. Bổ sung trực tiếp `fs.s3a.access.key` và `fs.s3a.secret.key` vào `hadoopConf` để Controller (operator) có thể đọc S3, tải file Script.
  3. Quá trình chạy trong driver tự nhận biết credentials qua default chain nhờ các biến môi trường được inject từ K8s Secret.

### 1.3 Thiếu thư mục Cache của Ivy (`/nonexistent`)
- **Vấn đề**: Để đọc từ MinIO, hệ thống dùng `--packages org.apache.hadoop:hadoop-aws:3.3.4...`. Quá trình download diễn ra trong Kubernetes nhưng user đang chạy không có quyền vào thư mục `HOME` ngầm định (`/nonexistent`), làm Spark-Submit thất bại không cấp thư mục cache cho Ivy (công cụ package manager).
- **Giải pháp**: Bố trí `spark.jars.ivy: "/tmp/.ivy2"` trong `sparkConf`. Thư mục `/tmp` luôn được cho phép ghi ngẫu nhiên ở phần lớn Container Image.

### 1.4 Thiếu quyền RBAC để xoá tài nguyên (Driver Cleanup Failed)
- **Vấn đề**: Sau khi Spark test chạy thành công, bản thân quá trình dọn dẹp Executor và các ConfigMaps bị văng lỗi `Forbidden: User cannot deletecollection`.
- **Giải pháp**: Bổ sung động từ API (`verbs: ["*"]` hoặc ít nhất `["deletecollection"]`) trên các đối tượng `pods`, `services`, `configmaps`, `persistentvolumeclaims` vào file định tuyến phân quyền `k8s/spark/spark-rbac.yaml`. 

### 1.5 Database Metastore ghi sang Local thay vì MinIO
- **Vấn đề**: Khi tạo database qua Spark SQL `CREATE DATABASE...`, thông báo lỗi báo Spark cố tạo `/opt/spark/work-dir/...` (Local Container OS) do Hive Metastore quay về mặc định.
- **Giải pháp**: Trói buộc `spark.sql.warehouse.dir: "s3a://datalake/warehouse"` bên trong manifest config.

---

## 2. Kiến trúc & Cấu hình Thực thi Hiện tại

Luồng hoạt động của job Spark tích hợp Data Platform này dựa vào **Apache Spark Operator**. Quy trình diễn ra như sau:

1. **Khởi tạo và Quản trị MinIO & Hive**: Backend lưu trữ chính là cụm MinIO (`datalake`). Schema và tables được theo dõi thông qua Hive-metastore (`thrift://hive-metastore:9083`).
2. **Spark Operator Controller**: Nhận Custom Resource `SparkApplication` mà người dùng submit qua API (file `pipelines/spark_test_job.yaml`).
3. **Download Script**: Controller (Operator) đọc `hadoopConf` bên trong manifest để xác thực và download script `.py` phân tích đầu tiên từ `s3a://`.
4. **Driver & Executor Pod Allocation**: 
   - K8s cấp phát một **Driver Pod** (`apache/spark:3.5.0` Image). Nhờ `deletecollection` Roles, Driver giữ quyền tuyệt đối với Executor của nó.
   - Khi có Job chạy qua SparkContext, Driver yêu cầu Kubernetes Scheduler cấp **Executor Pod(s)** trên Node nhóm (Pool).
5. **Đồng bộ Dependencies (Hadoop AWS S3A)**: Thông qua tính năng `spark.jars.packages`, Spark tải trực tiếp driver/SDK để kết nối qua chuẩn mạng S3 tương thích.

### Thành phần File Cấu Hình Quan Trọng

* `pipelines/spark_test_job.yaml`: Bản mô tả thiết kế `SparkApplication` CRD. Cấu hình cấp cores/coreLimit phù hợp LimitRange.
* `pipelines/spark_hive_minio_test.py`: Tập lệnh thực chiến Pyspark (Tạo DB, Xử lý data, Save Table Parquet qua `s3a`). Mọi credentials được đọc qua biến môi trường để đảm bảo độ bảo mật.
* `k8s/spark/spark-rbac.yaml`: Cấp Namespace Privilege Roles cho Operator và Spark Application. Truy cập APIs dọn tài nguyên.
* `k8s/spark/setup/spark-operator-values.yaml`: Helm config cho cài đặt Spark Operator. Khai báo `spark.jobNamespaces` hỗ trợ theo dõi `data-platform`. Kèm theo các Tolerations/NodeSelector.

---

## 3. Quy trình thực thi thủ công nhanh (Quick-start Makefile)

Dự án có sẵn config rỗng trong file root `Makefile` để đơn giản hoá vòng đời testing của bạn. 

1. Đẩy script lên MinIO `s3a://datalake/scripts`:
   *(Mặc định đã thực hiện thủ công bằng command hoặc upload qua console MinIO UI ở bước hiện tại)*

2. Submit và chạy Spark Job:
   ```bash
   make spark-submit
   ```

3. Dõi theo chuỗi vòng lặp Driver Logs:
   ```bash
   make spark-logs
   ```
   *Tip: Khi nhận được Log line "ALL TESTS PASSED!", bài toán hoàn tất.*

4. Thu hồi Job cũ để dọn dẹp Cluster:
   ```bash
   make spark-delete
   ```
