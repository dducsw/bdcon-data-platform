# Deploy Platform Runbook

This runbook reflects the current repository layout and the verified runtime state of the dev cluster.

## Primary Entrypoints

- Terraform: `terraform/envs/dev`
- Kustomize base: `k8s/base`
- Kustomize overlay: `k8s/overlays/dev`
- Helm values: `helm-values/*/dev.yaml`

## Standard Deployment Flow

### 1. Reconcile Infrastructure

```bash
make tf-init
make tf-plan
make tf-apply
```

### 2. Bootstrap Helm Operators

```bash
make bootstrap-operators
```

### 3. Apply Platform Manifests

```bash
make k8s-dev
```

If you want server-side validation first:

```bash
kubectl apply -k k8s/overlays/dev --dry-run=server
```

## Verified Runtime Snapshot

The live cluster checked on 2026-04-18 is healthy with these key components running:

- Airflow
- PostgreSQL
- MinIO
- Gravitino
- Hive Metastore
- Redis
- Spark operator
- Kafka via Strimzi
- Kafka exporter
- Trino
- Superset
- External Secrets
- Prometheus / Grafana

## Kafka Details

The working Kafka setup currently uses:

- `Kafka` CR API: `kafka.strimzi.io/v1`
- `KafkaNodePool` CR API: `kafka.strimzi.io/v1`
- `KafkaTopic` CR API: `kafka.strimzi.io/v1`
- Kafka version: `4.1.1`
- Metadata version: `4.1-IV0`
- Bootstrap service: `data-platform-kafka-kafka-bootstrap.data-platform.svc`

The `kafka-exporter` deployment must point to that bootstrap service name.

## Health Checks

```bash
kubectl get nodes -o wide
kubectl get pods -A
kubectl get kafka,kafkanodepool,kafkatopic -n data-platform
```

## Success Criteria

- all nodes are `Ready`
- Terraform plan is `No changes`
- Kustomize server dry-run succeeds
- `Kafka` CR reports `Ready=True`
- `kafka-exporter` is `Running`
