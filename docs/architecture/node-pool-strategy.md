# Node Pool Strategy

This document reflects the node-pool strategy that is actually running in the dev cluster.

## Live Pool Layout

| Pool | Machine type | Label | Spot | Intended workloads |
| --- | --- | --- | --- | --- |
| `infra-pool` | `n2-standard-8` | `role=infra` | yes | PostgreSQL, MinIO, Gravitino, Hive Metastore |
| `compute-pool` | `e2-highmem-4` | `role=compute` | yes | Spark, Redis, exporters, batch workloads |
| `query-pool` | `e2-highmem-4` | `role=query` | yes | Trino, Superset, query-facing workloads |

## Why This Is Acceptable Here

This repository targets learning, dev, and lab usage.

Accepted tradeoffs:

- preemption
- temporary pod eviction
- service restart
- scale-to-zero behavior

Not guaranteed:

- strict HA
- stable stateful uptime
- production-grade recovery targets

## Scheduling Conventions

- workloads are placed primarily with `nodeSelector.role`
- Spot-backed workloads tolerate `cloud.google.com/gke-spot=true:NoSchedule`
- controllers and stateful services are still grouped logically by pool even though the cluster is all-Spot

## Current Verification

Verified on 2026-04-18:

- all three pools exist
- all nodes are `Ready`
- workloads are successfully spread across `infra`, `compute`, and `query`
