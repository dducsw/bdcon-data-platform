# K8s Data Platform

Data platform dev/lab on GKE with an intentionally cost-optimized Spot-backed cluster. The repository combines Terraform for cloud infrastructure, Kustomize for first-party Kubernetes manifests, Helm values for third-party platforms, and runbooks for bootstrap and operations.

## Repository Layout

```text
.
+- assets/
+- docs/
¦  +- architecture/
¦  +- decisions/
¦  +- runbooks/
+- helm-values/
¦  +- airflow/
¦  +- monitoring/
¦  +- strimzi/
¦  +- trino/
+- k8s/
¦  +- base/
¦  +- overlays/
+- notebooks/
+- pipelines/
+- scripts/
¦  +- bootstrap/
¦  +- cleanup/
¦  +- deploy/
¦  +- verify/
+- terraform/
   +- envs/
   +- modules/
```

## Deployment Model

- `terraform/envs/dev`: active Terraform entrypoint for the development cluster
- `terraform/modules/*`: reusable infrastructure modules
- `k8s/base`: shared Kubernetes manifests grouped by responsibility
- `k8s/overlays/dev`: development overlay and resource overrides
- `helm-values/*/dev.yaml`: values files for Helm-managed services

The dev cluster is intentionally all-Spot. This reduces cost and keeps experimentation easy, but it also means preemption, scale-to-zero, and service restarts are accepted tradeoffs.

## Common Commands

```bash
make tf-init
make tf-plan
make bootstrap-operators
make k8s-deploy
make k8s-dev
make verify-layout
```
