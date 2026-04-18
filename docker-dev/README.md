# Docker Dev Lakehouse

Thu muc `docker-dev/` la local development stack dung de mo phong cac thanh phan du lieu cot loi truoc khi dua workload len Kubernetes. Muc tieu la giu cho phan cau hinh o day gan voi `k8s/` nhat co the, tap trung vao 4 khoi chinh:

- Spark de xu ly batch va streaming.
- Kafka de ingest su kien va pipeline real-time.
- Hive Metastore de lam catalog metadata cho Iceberg.
- Trino de query interactive tren cung mot lakehouse.

Gravitino da duoc loai khoi local stack nay de `docker-dev` di sat hon huong trien khai tren cluster.

## Architecture

![Data Lakehouse Architecture](assets/architecture.png)

Luong chinh trong `docker-dev`:

1. Kafka nhan event dau vao.
2. Spark doc/ghi du lieu va materialize bang Iceberg.
3. Hive Metastore quan ly metadata cho Iceberg.
4. Trino query cung data lake tren MinIO.
5. Postgres luu metadata backend cho Hive Metastore.
6. Superset giu vai tro kham pha va xem du lieu o local.

Stack local nay duoc giu gon de phuc vu phat trien va test pipeline:

- Spark gom 1 master va 1 worker.
- Khong bao gom Redis, Prometheus, Grafana hay cac exporter monitoring.
- Tap trung vao data path chinh: Kafka -> Spark -> Iceberg/MinIO -> Trino/Superset.

## Naming convention

De viec migrate code tu Docker sang cluster don gian hon, `docker-dev` dang co mot bo ten co dinh cho Hive Metastore flow:

- Bucket: `iceberg`
- Warehouse: `s3a://iceberg/lakehouse`
- Catalog: `hive`
- Schema mac dinh cho vi du: `schema_iceberg`
- Hive Metastore URI: `thrift://hive-metastore:9083`

Neu viet them pipeline moi trong `docker-dev`, nen giu dung naming nay de khi dua sang k8s chi can doi endpoint hoac secret, khong phai doi ten bang/schema/catalog.

## Thu muc quan trong

- `docker-compose.yml`: orchestration local stack.
- `infrastructure/spark`: Dockerfile, init script, Spark config.
- `infrastructure/hive-metastore`: image va config cua Hive Metastore.
- `infrastructure/trino`: catalog Trino tro vao Hive Metastore.
- `pipelines/`: code xu ly mau de chay local roi dua sang k8s workloads.
- `setup/`: script khoi tao schema/catalog ban dau.

## Cach dung nhanh

```bash
cd docker-dev
docker compose up --detach --build
```

Khoi tao schema Iceberg:

```bash
docker exec -it spark-master spark-sql -f /opt/spark/apps/setup/create_schema.sql
```

Chay pipeline mau:

```bash
docker exec -it spark-master python /opt/spark/apps/pipelines/example/create_example_table.py
```

## Mapping sang Kubernetes

`docker-dev` duoc to chuc de map thang sang `k8s/`:

- Spark local map sang `k8s/base/platform-services/spark/`.
- Hive Metastore local map sang `k8s/base/data-services/hive-metastore/`.
- Kafka local map sang `k8s/base/data-services/kafka/`.
- Trino local map sang `helm-values/trino/` va cac tai lieu deploy lien quan.

Neu can them service cho local, uu tien giu ten bien, endpoint va thu muc config tuong dong voi `k8s/` de luc tach image/manifests sang cluster se it phai doi lai nhat.
