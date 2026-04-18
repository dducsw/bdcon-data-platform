# Post-Refactor Verification Checklist

Use this checklist after any structural refactor of Terraform, Kustomize, Helm values, or service layout.

## Terraform

- `cd terraform/envs/dev`
- `terraform init`
- `terraform plan -var-file=terraform.tfvars`
- expected result: `No changes` for an already-reconciled cluster
- `terraform state list`
- expected result: state addresses use `module.network`, `module.nat`, `module.gke`

## Cluster Connectivity

- `kubectl get nodes -o wide`
- expected result: all nodes `Ready`

- `kubectl get pods -A`
- expected result: platform pods `Running`, jobs may be `Completed`

## Kubernetes Manifests

- `kubectl apply -k k8s/overlays/dev --dry-run=server`
- expected result: command succeeds without schema errors

- `make verify-layout`
- expected result: layout check passes

## Kafka / Strimzi

- `kubectl get kafka,kafkanodepool,kafkatopic -n data-platform`
- expected result:
  - Kafka `Ready=True`
  - node pools show desired replicas and node IDs

- `kubectl get svc -n data-platform | findstr /I kafka`
- expected result:
  - `data-platform-kafka-kafka-bootstrap`
  - `data-platform-kafka-kafka-brokers`

- `kubectl get pod -n data-platform | findstr /I kafka`
- expected result:
  - controller pods `Running`
  - broker pods `Running`
  - entity operator `Running`
  - `kafka-exporter` `Running`

## Core Platform

- PostgreSQL `Running`
- MinIO pods `Running`
- Gravitino `Running`
- Hive Metastore `Running`
- Redis `Running`
- Trino coordinator and workers `Running`
- Superset `Running`
- Airflow core pods `Running`

## Observability

- Prometheus pods `Running`
- Grafana pod `Running`
- `ServiceMonitor` resources apply cleanly in server dry-run

## Known Good Runtime Snapshot

Last verified end-to-end: `2026-04-18`

At that point:

- Terraform apply was no-op
- Kustomize dev overlay server dry-run passed
- Kafka version `4.1.1` reconciled successfully on Strimzi `0.51.0`
- `kafka-exporter` recovered and reached `Running`
