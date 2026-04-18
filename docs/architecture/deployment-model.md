# Deployment Model

The repository uses a hybrid deployment model:

- Terraform for cloud infrastructure
- Kustomize for first-party Kubernetes manifests
- Helm values for third-party platform components

## Active Entrypoints

- Terraform: `terraform/envs/dev`
- Kustomize base: `k8s/base`
- Kustomize dev overlay: `k8s/overlays/dev`
- Helm values: `helm-values/airflow/dev.yaml`, `helm-values/trino/dev.yaml`

## Runtime-Verified State

Verified on 2026-04-18:

- Terraform module migration is complete
- remote state now uses `module.*` addresses
- `terraform apply` completes with `0 added, 0 changed, 0 destroyed`
- `kubectl apply -k k8s/overlays/dev --dry-run=server` succeeds

## Deployment Sequence

1. Reconcile infra with Terraform.
2. Bootstrap Helm-managed operators.
3. Apply Kustomize overlay.
4. Verify cluster health.

## Operational Assumptions

- this is a dev/lab cluster
- all node pools are Spot-backed
- short interruptions are acceptable
- recovery and reproducibility matter more than HA guarantees
