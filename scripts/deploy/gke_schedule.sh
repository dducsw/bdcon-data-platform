#!/bin/bash
# ====================================================================
# GKE Auto-scale Scheduling Script (14:00 - 22:00 ICT)
# ====================================================================
# Usage: ./scripts/deploy/gke_schedule.sh [start|stop]
# Description:
#   Scales K8s workloads up/down so GKE Cluster Autoscaler can
#   adjust node counts.
# ====================================================================

set -euo pipefail

ACTION="${1:-}"
NAMESPACE="data-platform"

if [ "$ACTION" == "start" ]; then
  echo "[$(date '+%H:%M:%S')] Khởi động Data Platform (14:00)..."

  # --- Step 1: Stateful storage layer ---
  echo "  [1/5] Starting storage layer: PostgreSQL + MinIO (4 nodes)..."
  kubectl scale statefulset postgres --replicas=1 -n "$NAMESPACE"
  kubectl scale statefulset minio --replicas=4 -n "$NAMESPACE"

  echo "  Chờ PostgreSQL sẵn sàng..."
  kubectl rollout status statefulset/postgres -n "$NAMESPACE" --timeout=120s

  # --- Step 2: Catalog & metadata layer ---
  echo "  [2/5] Starting catalog layer: Gravitino + Hive Metastore + Redis..."
  kubectl scale deployment gravitino --replicas=1 -n "$NAMESPACE"
  kubectl scale statefulset hive-metastore redis --replicas=1 -n "$NAMESPACE"

  # --- Step 3: Kafka (Strimzi) ---
  echo "  [3/5] Starting Kafka KRaft cluster..."
  kubectl scale kafkanodepool controller-pool --replicas=1 -n "$NAMESPACE"
  sleep 15
  kubectl scale kafkanodepool broker-pool --replicas=2 -n "$NAMESPACE"

  # --- Step 4: Compute layer (Trino via Helm) ---
  echo "  [4/5] Starting compute layer: Trino (via Helm upgrade)..."
  helm upgrade trino trino/trino \
    --namespace "$NAMESPACE" \
    --reuse-values \
    --set server.workers=2 \
    --wait

  # --- Step 5: UI & Airflow ---
  echo "  [5/5] Starting UI & Airflow..."
  kubectl scale deployment superset --replicas=1 -n "$NAMESPACE"
  # Airflow KubernetesExecutor will spin up pods on demand, but we scale webserver/scheduler
  kubectl scale deployment airflow-webserver airflow-scheduler --replicas=1 -n "$NAMESPACE"

  echo "Lệnh scale đã hoàn tất."

elif [ "$ACTION" == "stop" ]; then
  echo "[$(date '+%H:%M:%S')] Tat Data Platform (22:00)..."

  echo "  Dung Airflow & UI..."
  kubectl scale deployment airflow-webserver airflow-scheduler superset --replicas=0 -n "$NAMESPACE"

  echo "  Dừng Trino (via Helm scale down)..."
  helm upgrade trino trino/trino \
    --namespace "$NAMESPACE" \
    --reuse-values \
    --set server.workers=0

  echo "  Dung Kafka..."
  kubectl scale kafkanodepool broker-pool --replicas=0 -n "$NAMESPACE"
  sleep 10
  kubectl scale kafkanodepool controller-pool --replicas=0 -n "$NAMESPACE"

  echo "  Dừng catalog layer..."
  kubectl scale deployment gravitino --replicas=0 -n "$NAMESPACE"
  kubectl scale statefulset hive-metastore redis --replicas=0 -n "$NAMESPACE"

  echo "  Dừng storage layer..."
  kubectl scale statefulset minio postgres --replicas=0 -n "$NAMESPACE"

  echo "Tất cả workloads đã được scale về 0."

else
  echo "Usage: $0 [start|stop]"
  exit 1
fi
