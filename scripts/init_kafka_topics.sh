#!/bin/bash
# ====================================================================
# Initialize Kafka Topics — K8s (Strimzi KRaft)
#
# NOTE: For GKE deployments, topics are primarily managed via
# Strimzi KafkaTopic CRDs (see k8s/kafka/kafka-topic.yaml).
# This script is for ad-hoc topic creation via kubectl exec.
# ====================================================================

set -euo pipefail

NAMESPACE="data-platform"
BOOTSTRAP_SERVER="data-platform-kafka-bootstrap:9092"

# Get a running Kafka broker pod
KAFKA_POD=$(kubectl get pods -n "$NAMESPACE" \
  -l strimzi.io/name=data-platform-kafka-broker-pool \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$KAFKA_POD" ]; then
  echo "Error: No running Kafka broker pods found in namespace '$NAMESPACE'!"
  echo "Make sure Strimzi Kafka cluster is running."
  exit 1
fi

TOPICS=(
    "buswaypoint_json"
)

echo "Creating Kafka topics via pod: $KAFKA_POD"

for topic in "${TOPICS[@]}"; do
    echo "-> Creating topic: $topic"
    kubectl exec -n "$NAMESPACE" "$KAFKA_POD" -- \
        /opt/kafka/bin/kafka-topics.sh \
        --create \
        --if-not-exists \
        --topic "$topic" \
        --bootstrap-server "$BOOTSTRAP_SERVER" \
        --partitions 3 \
        --replication-factor 2
done

echo ""
echo "List of current topics:"
kubectl exec -n "$NAMESPACE" "$KAFKA_POD" -- \
    /opt/kafka/bin/kafka-topics.sh \
    --list \
    --bootstrap-server "$BOOTSTRAP_SERVER"

echo ""
echo "Done!"
