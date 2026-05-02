$ErrorActionPreference = "Stop"

$NAMESPACE = "data-platform"

Write-Host "Installing Strimzi Kafka Operator (Helm)..." -ForegroundColor Cyan
helm repo add strimzi https://strimzi.io/charts/
helm repo update

helm upgrade --install strimzi-kafka-operator strimzi/strimzi-kafka-operator --namespace strimzi-system --create-namespace --set watchNamespaces="{data-platform}" --wait

Write-Host "Strimzi Kafka Operator installed." -ForegroundColor Green

Write-Host "Installing External Secrets Operator (ESO)..." -ForegroundColor Cyan
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

helm upgrade --install external-secrets external-secrets/external-secrets --namespace external-secrets --create-namespace --wait

Write-Host "External Secrets Operator installed." -ForegroundColor Green

Write-Host "Installing Cilium Ingress Controller..." -ForegroundColor Cyan
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx --namespace ingress-nginx --create-namespace --set controller.service.type=LoadBalancer --set controller.ingressClassResource.name=cilium --wait

Write-Host "Installing Kube-Prometheus-Stack..." -ForegroundColor Cyan
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace --set grafana.service.type=ClusterIP --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false --wait

Write-Host "Kube-Prometheus-Stack installed." -ForegroundColor Green

Write-Host "Installing Apache Airflow (KubernetesExecutor)..." -ForegroundColor Cyan
helm repo add apache-airflow https://airflow.apache.org
helm repo update
helm upgrade --install airflow apache-airflow/airflow --namespace $NAMESPACE --create-namespace -f ../../helm-values/airflow/dev.yaml --wait

Write-Host "Apache Airflow installed." -ForegroundColor Green

Write-Host "Installing Kubeflow Spark Operator..." -ForegroundColor Cyan
helm repo add spark-operator https://kubeflow.github.io/spark-operator
helm repo update spark-operator
helm upgrade --install spark-operator spark-operator/spark-operator --namespace $NAMESPACE --create-namespace --values ../../k8s/base/platform-services/spark/setup/spark-operator-values.yaml --wait

Write-Host "Kubeflow Spark Operator installed." -ForegroundColor Green

Write-Host "Installing Trino Cluster (Official Helm Chart)..." -ForegroundColor Cyan
helm repo add trino https://trinodb.github.io/charts/
helm repo update
helm upgrade --install trino trino/trino --namespace $NAMESPACE --create-namespace -f ../../helm-values/trino/dev.yaml --wait

Write-Host "Trino installed." -ForegroundColor Green

Write-Host ""
Write-Host "All Helm charts and operators are ready. Now apply Kustomize:" -ForegroundColor Magenta
Write-Host "   kubectl apply -k k8s/base" -ForegroundColor Yellow
