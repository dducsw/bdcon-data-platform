# Kafka Streaming Layer

This directory contains the custom resources to deploy and manage Apache Kafka on Kubernetes via the **Strimzi Kafka Operator**.

## Overview
We use Strimzi to manage a 3-node KRaft cluster. Strimzi handles broker provisioning, topology spread constraints across Spot VMs, rolling upgrades, and Topic generation securely.

## Prerequisites
- K8s Cluster (GKE) running.
- Strimzi Kafka Operator installed in the cluster (via `scripts/install_helm_charts.sh`).

## Files
- `kafka-cluster.yaml`: Defines the `Kafka` custom resource containing 3 combined controller/broker nodes.
- `kafka-topic.yaml`: Defines an example `KafkaTopic` custom resource (`buswaypoints`).

## Usage
Use the provided `Makefile` for quick operations.

```bash
# Apply the Kafka cluster
make apply

# Check cluster status
make status

# Create the example topic
make create-topic

# Delete the Kafka cluster
make delete
```
