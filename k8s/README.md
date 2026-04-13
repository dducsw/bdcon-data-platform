# Data Platform on Kubernetes 🌊

Thư mục `k8s/` chứa toàn bộ cấu hình (manifests) để triển khai Data Platform theo kiến trúc Cloud-Native trên cluster Kubernetes. Quá trình triển khai chủ yếu sử dụng **Kustomize** để gom và quản lý vòng đời tài nguyên.

## Mục lục
- [Kiến trúc Tổng thể](#kiến-trúc-tổng-thể)
- [Cơ sở lưu trữ & Database](#cơ-sở-lưu-trữ--database)
- [Siêu dữ liệu (Catalog Layer)](#siêu-dữ-liệu-catalog-layer)
- [Xử lý Phân tán (Compute Layer)](#xử-lý-phân-tán-compute-layer)
- [Phân phối Dữ liệu (Streaming Layer)](#phân-phối-dữ-liệu-streaming-layer)
- [Truy vấn & Trực quan (Query & BI Layer)](#truy-vấn--trực-quan-query--bi-layer)
- [Bảo trì & Giám sát (Observability Layer)](#bảo-trì--giám-sát-observability-layer)
- [Hướng dẫn Deploy Nhanh](#hướng-dẫn-deploy-nhanh)

---

## Kiến trúc Tổng thể

Toàn bộ nền tảng hệ thống được cấp phát độc lập trên namespace `data-platform`. Cấu trúc Ingress điều phối lưu lượng đến các Node thông qua các internal domain:
- `trino.data.local`: Hệ thống Query Trino.
- `superset.data.local`: Nền tảng phân tích Superset.
- `grafana.data.local`: Bảng điều khiển giám sát Metric.
- `airflow.data.local`: Nền tảng điều phối dữ liệu Airflow.

*(**Lưu ý:** Các dự án như Trino và Airflow được cài từ Helm Chart bên ngoài thông qua scripts, nhưng khai báo Routing Ingress vẫn được liên kết thống nhất tại cấu trúc kustomize).*

## Cơ sở lưu trữ & Database
1. **PostgreSQL**: StatefulSet, đóng vai trò Metadata Data Storage cốt lõi cho Catalog (Hive/Gravitino) cũng như lưu trữ config/state của công cụ BI.
2. **MinIO**: StatefulSet cung cấp giải pháp lưu trữ lõi cho Object-Storage (S3-compatible API), đóng vai trò Data Lake/Lakehouse. Một khởi tạo Job sẽ cấu trúc sẵn bucket `iceberg` cho nền tảng.
3. **Redis**: In-memory Cache Layer phục vụ các Session, Exporter, làm Message Broker cho tiến trình Celery từ BI hoặc Orchestrator.

## Siêu dữ liệu (Catalog Layer)
Lọc, trích lục, quản lý phiên bản siêu dữ liệu trên Lakehouse:
1. **Gravitino**: Iceberg REST Catalog Manager chạy luồng REST API tương thích Iceberg giúp kiểm soát schema.
2. **Hive Metastore**: Dịch vụ Thrift Metastore Server ở cổng `9083`, giao tiếp cross chéo MinIO & Postgres cho các tiến trình truyền thống cần metadata Hadoop chuẩn.

## Xử lý Phân tán (Compute Layer)
**Apache Spark Operator CRDs**: Thư mục cung cấp RBAC Role/Binding (`spark-rbac.yaml`) và `ConfigMap` cho phép cluster Kubernetes tự khởi tạo phiên bản động của môi trường chạy Spark data processing/streaming job. Kèm theo một App Pipeline mẫu (`spark-pi-example.yaml`).

## Phân phối Dữ liệu (Streaming Layer)
**Apache Kafka**: Tích hợp với **Strimzi Operator** qua CRDs định cấu hình cụm Kafka Cluster và Topic, đóng vai trò Backbone truyền/nhận các Event & Telemetry theo thời gian thực phân tán.

## Truy vấn & Trực quan (Query & BI Layer)
1. **Superset**: Trực quan số liệu BI Dashboard, cho phép build Chart biểu đồ nối trực tiếp với tầng Trino Query Engine bằng PostgreSQL Metadata.
2. **Trino (qua Helm)**: Distributed SQL Query Engine tốc độ MPP xử lý Analytics quy mô lớn.

## Bảo trì & Giám sát (Observability Layer)
Tích hợp mạnh mẽ với `Kube-Prometheus-Stack`, tầng theo dõi bao gồm:
- Tự động Exporter tài nguyên (VD: `grafana-exporters.yaml` mở port `9308` cho Kafka, Redis).
- `service-monitors.yaml`: Service Monitor CRD giúp Prometheus Operator tự thu thập và cào số liệu thông qua Labels mà không cần chỉnh config Prometheus thủ công.

---

## Hướng dẫn Deploy Nhanh

Đường viền chung của Project đã được đóng gói thành một `Kustomization` file gốc.

**(1) Triển khai các phụ thuộc từ bên thứ 3:**
Đảm bảo bạn đã cái sẵn Helm Charts cho NGINX Ingress Controller / Airflow / Trino / Prometheus Operator thông qua scripts trong hạ tầng. 

**(2) Khởi tạo / Cập nhật Kubernetes Manifest trực tiếp:**
```bash
# Kiểm tra tổng thể các rendering Object YAML không có syntax/link error:
kubectl kustomize ./k8s

# Apply toàn bộ thay đổi hệ thống vào cụm qua kubectl kustomize tích hợp:
kubectl apply -k ./k8s
```

*(Hãy chắc chắn đã thay đổi / replace định danh `REGISTRY` thành URL Repo cá nhân của bạn trên các files Deployments trước khi đẩy lên CI/CD).*
