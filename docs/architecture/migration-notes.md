# Migration Notes

## Active Layout

- terraform/envs/dev is the active Terraform entrypoint.
- k8s/base and k8s/overlays/dev are the active Kubernetes entrypoints.
- helm-values/*/dev.yaml are the active Helm values.
- scripts/bootstrap, scripts/deploy, scripts/verify, and scripts/cleanup are the active script groups.

## Legacy But Temporarily Retained

The following paths are kept only to support rollback while migration is being validated. New changes should not reference them.

- k8s/postgres, k8s/minio, k8s/redis, k8s/kafka, k8s/hive-metastore, k8s/gravitino, k8s/spark, k8s/superset, k8s/ingress, k8s/trino, k8s/airflow
- nested duplicates under k8s/base/** such as postgres/postgres, spark/spark, build/build, setup/setup
- duplicate script copies at the top level of scripts/

## Guidance

If you need to rollback, prefer switching references back at the entrypoint files rather than editing both new and legacy trees in parallel.

