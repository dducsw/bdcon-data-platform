Có, **spark submit được**, nhưng trong cluster này hướng đúng hơn là:

- dùng **Spark Operator**
- nộp job bằng **`SparkApplication` CRD**
- thay vì tự chạy `spark-submit` thủ công từ máy local

**Cách chạy chuẩn trong project này**
Repo hiện đã có sẵn flow này:
- manifest ví dụ: [k8s/base/platform-services/spark/spark-pi-example.yaml](/D:/Projects/k8s-data-platform/k8s/base/platform-services/spark/spark-pi-example.yaml)
- lệnh hỗ trợ trong [Makefile](/D:/Projects/k8s-data-platform/Makefile)

Bạn chạy:
```bash
make spark-submit
```

Theo dõi:
```bash
make spark-watch
make spark-logs
```

Xóa job:
```bash
make spark-delete
```

**Spark submit có dùng được không?**
Có, nhưng nên hiểu 2 kiểu:

1. `spark-submit` kiểu truyền thống
- chạy lệnh `spark-submit` trực tiếp
- cần một nơi để chạy lệnh đó, image phù hợp, config K8s đầy đủ
- phức tạp hơn với repo hiện tại

2. `SparkApplication` qua Spark Operator
- thực chất là “submit job lên K8s” theo kiểu declarative
- hợp với cluster này hơn
- dễ version control hơn
- dễ lặp lại hơn

Với project của bạn, mình khuyên dùng cách số 2.

**Muốn chạy chương trình Spark riêng của bạn**
Bạn có 2 hướng:

1. Dùng file Python/JAR đã nằm trong image hoặc ở object storage
- sửa `spark-pi-example.yaml`
- đổi `mainApplicationFile`
- đổi args, resources, image

2. Tạo một `SparkApplication` mới
- ví dụ `my-job.yaml`
- rồi:
```bash
kubectl apply -f my-job.yaml -n data-platform
```

**Điều kiện để job chạy được**
- Spark Operator đang chạy
- image Spark có đủ dependencies
- file app của bạn phải truy cập được:
  - trong image
  - hoặc qua S3/MinIO
  - hoặc volume/config phù hợp
- service account / RBAC cho Spark đã đúng

**Tóm lại**
- Có thể “spark submit”
- Nhưng trong cluster này, cách đúng là **submit qua Spark Operator bằng `SparkApplication`**
- `make spark-submit` là entrypoint thuận nhất hiện giờ

Nếu bạn muốn, mình có thể làm tiếp ngay:
1. rà runtime Spark Operator hiện tại và xác nhận flow submit đang chạy được
2. tạo cho bạn một mẫu `SparkApplication` mới để chạy chương trình Spark riêng của bạn