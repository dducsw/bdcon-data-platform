# GKE Bootstrap Runbook

This runbook documents the current dev/lab bootstrap flow that matches the live runtime verified on 2026-04-18.

## Active Environment

- GCP project: `k8s-data-platform-1879`
- Region: `asia-east1`
- Zone: `asia-east1-a`
- Cluster: `data-platform-cluster`
- Terraform entrypoint: `terraform/envs/dev`
- Kustomize entrypoint: `k8s/overlays/dev`

## Cluster Model

The dev cluster is intentionally cost-optimized and Spot-backed across all three pools:

- `infra-pool`: `n2-standard-8`, `role=infra`, `spot=true`
- `compute-pool`: `e2-highmem-4`, `role=compute`, `spot=true`
- `query-pool`: `e2-highmem-4`, `role=query`, `spot=true`

This is acceptable for lab usage. Preemption, restart, and temporary service loss are accepted tradeoffs.

## Bootstrap Order

1. Initialize and verify Terraform.
2. Reconcile the GKE cluster and node pools.
3. Install Helm-managed operators.
4. Apply Kustomize manifests for platform services.
5. Run post-deploy verification.

## Terraform

```bash
cd terraform/envs/dev
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -auto-approve -var-file=terraform.tfvars
```

Expected result after the refactor:

- module-based state addresses are used
- `terraform plan` returns `No changes` when the cluster is already reconciled

## Operators

```bash
cd D:/Projects/k8s-data-platform
make bootstrap-operators
```

## Platform Manifests

```bash
kubectl apply -k k8s/overlays/dev
```

For validation without changes:

```bash
kubectl apply -k k8s/overlays/dev --dry-run=server
```

## Kafka Runtime Note

The current Strimzi operator in-cluster is `quay.io/strimzi/operator:0.51.0`.

The active manifests are aligned to that runtime:

- API version: `kafka.strimzi.io/v1`
- Kafka version: `4.1.1`
- Metadata version: `4.1-IV0`

Do not downgrade these fields back to `v1beta2` or Kafka `3.8.0`, or reconciliation will fail.
