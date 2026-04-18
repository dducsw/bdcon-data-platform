@echo off
cd /d %~dp0

echo 📦 Creating default namespace "data-platform"...
kubectl create namespace data-platform --dry-run=client -o yaml | kubectl apply -f -

echo 📦 Installing Strimzi Kafka Operator (Helm)...
helm repo add strimzi https://strimzi.io/charts/
helm repo update
helm upgrade --install strimzi-kafka-operator strimzi/strimzi-kafka-operator --namespace strimzi-system --create-namespace --set watchNamespaces="{data-platform}" --wait
echo ✅ Strimzi Kafka Operator installed.

echo 📦 Installing External Secrets Operator (ESO)...
helm repo add external-secrets https://charts.external-secrets.io
helm repo update
helm upgrade --install external-secrets external-secrets/external-secrets --namespace external-secrets --create-namespace --wait
echo ✅ External Secrets Operator installed.

echo 📦 Installing Cilium Ingress Controller...
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx --namespace ingress-nginx --create-namespace --set controller.service.type=LoadBalancer --set controller.ingressClassResource.name=cilium --wait

echo 📦 Installing Kube-Prometheus-Stack...
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace --set grafana.service.type=ClusterIP --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false --wait
echo ✅ Kube-Prometheus-Stack installed.

echo 📦 Installing Apache Airflow (KubernetesExecutor)...
helm repo add apache-airflow https://airflow.apache.org
helm repo update
REM Delete stuck airflow-logs PVC if it exists in Pending state, so it can be recreated cleanly
kubectl delete pvc airflow-logs -n data-platform --ignore-not-found
helm upgrade --install airflow apache-airflow/airflow --namespace data-platform --create-namespace -f ../k8s/airflow/airflow-values.yaml --wait --timeout 10m
echo ✅ Apache Airflow installed.

echo 📦 Installing Apache Spark Kubernetes Operator...
helm repo add kubeflow https://kubeflow.github.io/spark-operator
helm repo update
helm upgrade spark-operator kubeflow-spark/spark-operator  --namespace data-platform   --values k8s\spark\setup\spark-operator-values.yaml --wait --timeout 180s
echo ✅ Apache Spark Kubernetes Operator installed.


echo 📦 Installing Trino Cluster (Official Helm Chart)...
helm repo add trino https://trinodb.github.io/charts/
helm repo update
helm upgrade --install trino trino/trino --namespace data-platform --create-namespace -f ../k8s/trino/trino-values.yaml --wait
echo ✅ Trino installed.

echo.
echo 🎉 All Helm charts and operators are ready. Now apply Kustomize:
echo    kubectl apply -k k8s/
