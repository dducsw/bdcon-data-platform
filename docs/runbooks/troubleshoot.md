# Troubleshooting Runbook

This runbook captures the issues that were actually observed during the refactor validation on 2026-04-18.

## 1. Terraform Wants To Recreate The Cluster

Symptom:

- `terraform plan` shows existing VPC, subnet, NAT, cluster, and node pools as `destroy`
- new module resources appear as `create`

Cause:

- state still points to the old root resource addresses
- config now uses `module.network`, `module.nat`, and `module.gke`

Fix:

Use `terraform state mv` to migrate state addresses before applying.

Example mapping:

```bash
terraform state mv google_compute_network.vpc module.network.google_compute_network.vpc
terraform state mv google_compute_subnetwork.subnet module.network.google_compute_subnetwork.subnet
terraform state mv google_compute_router.router module.nat.google_compute_router.router
terraform state mv google_compute_router_nat.nat module.nat.google_compute_router_nat.nat
terraform state mv google_container_cluster.primary module.gke.google_container_cluster.primary
terraform state mv google_container_node_pool.infra_pool module.gke.google_container_node_pool.infra_pool
terraform state mv google_container_node_pool.compute_pool module.gke.google_container_node_pool.compute_pool
terraform state mv google_container_node_pool.query_pool module.gke.google_container_node_pool.query_pool
```

Expected result after migration:

- `terraform plan -var-file=terraform.tfvars`
- `No changes`

## 2. Kafka Does Not Reconcile

Symptom:

- `kubectl get kafka -n data-platform` shows not ready
- no Kafka bootstrap service exists
- Strimzi logs show `UnsupportedKafkaVersionException`

Observed root cause:

- Strimzi operator version: `0.51.0`
- manifest used Kafka `3.8.0`
- operator supports only `4.1.0`, `4.1.1`, `4.2.0`

Fix:

- switch CR API to `kafka.strimzi.io/v1`
- use Kafka `4.1.1`
- use metadata version `4.1-IV0`

## 3. kafka-exporter Stuck In Init

Symptom:

- exporter pod stays `Init:0/1`

Observed root causes:

1. Kafka was not healthy yet, so the bootstrap service did not exist
2. exporter was waiting on the wrong service name

Correct bootstrap target:

```text
data-platform-kafka-kafka-bootstrap.data-platform.svc:9092
```

## 4. Useful Live Debug Commands

```bash
kubectl get pods -A
kubectl get svc -n data-platform | findstr /I kafka
kubectl get kafka,kafkanodepool,kafkatopic -n data-platform
kubectl describe kafka data-platform-kafka -n data-platform
kubectl logs -n strimzi-system deploy/strimzi-cluster-operator --tail=200
kubectl apply -k k8s/overlays/dev --dry-run=server
```
