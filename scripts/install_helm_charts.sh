#!/bin/bash
# ====================================================================
# Install Kubernetes Operators and Helm Charts
# run: chmod +x install_helm_charts.sh && ./install_helm_charts.sh
# ====================================================================

set -euo pipefail

NAMESPACE="data-platform"

echo "📦 Installing Strimzi Kafka Operator (Helm)..."
helm repo add strimzi https://strimzi.io/charts/
helm repo update

helm upgrade --install strimzi-kafka-operator strimzi/strimzi-kafka-operator \
  --namespace strimzi-system --create-namespace \
  --set watchNamespaces="{data-platform}" \
  --wait

echo "✅ Strimzi Kafka Operator installed."

echo "📦 Installing External Secrets Operator (ESO)..."
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

helm upgrade --install external-secrets external-secrets/external-secrets \
  --namespace external-secrets --create-namespace \
  --wait

echo "✅ External Secrets Operator installed."

echo "📦 Installing Cilium Ingress Controller..."
# Assuming GKE Dataplane V2 is enabled, we still need to enable Ingress support
# or install a standard ingress like NGINX if preferred. 
# Here we'll install NGINX Ingress as it's more common for general use-cases.
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.ingressClassResource.name=cilium \
  --wait

echo "📦 Installing Kube-Prometheus-Stack..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.service.type=ClusterIP \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --wait

echo "✅ Kube-Prometheus-Stack installed."

echo "📦 Installing Apache Airflow (KubernetesExecutor)..."
helm repo add apache-airflow https://airflow.apache.org
helm repo update
# Delete stuck airflow-logs PVC if it exists in Pending state, so it can be recreated cleanly
kubectl delete pvc airflow-logs -n "$NAMESPACE" --ignore-not-found
helm upgrade --install airflow apache-airflow/airflow \
  --namespace "$NAMESPACE" --create-namespace \
  -f ../k8s/airflow/airflow-values.yaml \
  --wait --timeout 10m

echo "✅ Apache Airflow installed."

echo "📦 Installing Apache Spark Kubernetes Operator..."
helm repo add spark https://apache.github.io/spark-kubernetes-operator
helm repo update
helm upgrade --install spark-kubernetes-operator spark/spark-kubernetes-operator \
  --namespace spark-operator --create-namespace \
  --wait

echo "✅ Apache Spark Kubernetes Operator installed."


echo "📦 Installing Trino Cluster (Official Helm Chart)..."
helm repo add trino https://trinodb.github.io/charts/
helm repo update
helm upgrade --install trino trino/trino \
  --namespace "$NAMESPACE" --create-namespace \
  -f ../k8s/trino/trino-values.yaml \
  --wait

echo "✅ Trino installed."

echo ""
echo "🎉 All Helm charts and operators are ready. Now apply Kustomize:"
echo "   kubectl apply -k k8s/"
