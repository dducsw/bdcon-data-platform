# 🤝 Partner / Developer Setup Guide

Welcome to the **Data Platform Kubernetes Cluster**. This guide will help you configure your local environment to connect to the cluster, verify the workloads, and access the core data services.

> **Note:** You must have been granted at least the **Editor** IAM role on the GCP project before proceeding.

---

## 1. Prerequisites

You will need the following tools installed on your local machine:
1. **[Google Cloud CLI (gcloud)](https://cloud.google.com/sdk/docs/install)**: Required for authenticating with GCP.
2. **[kubectl](https://kubernetes.io/docs/tasks/tools/)**: The Kubernetes command-line tool.
3. **[Helm](https://helm.sh/docs/intro/install/)** *(Optional)*: For modifying chart deployments.

---

## 2. Authenticate & Connect to the Cluster

Since the cluster is already provisioned and running, you only need to authenticate your CLI and fetch the cluster credentials.

1. **Login to your Google Cloud account:**
   ``bash
   gcloud auth login
   ``

2. **Set the default project:**
   ``bash
   gcloud config set project k8s-data-platform-1879
   ``

3. **Fetch the Kubernetes cluster credentials:**
   ``bash
   gcloud container clusters get-credentials data-platform-cluster --zone asia-east1-a --project k8s-data-platform-1879
   ``

---

## 3. Verify Cluster Access

Check if you can communicate with the cluster and view the running pods in the data-platform namespace:

`ash
kubectl get pods -n data-platform
`

You should see an output with applications like irflow, 	rino, spark, minio, kafka, and superset in a Running state.

---

## 4. Accessing Core Services (Port-Forwarding)

Because this cluster is private and secure, all services run internally. To access their Web UIs locally, you need to use kubectl port-forward.

Open separate terminal windows for the services you want to access:

### 🪣 MinIO (S3 Object Storage)
`ash
kubectl port-forward svc/minio-console 9001:9001 -n data-platform
`
- **URL**: [http://localhost:9001](http://localhost:9001)
- **User**: minioadmin
- **Pass**: minioadmin123

### 🚀 Trino (Distributed SQL Query Engine)
`ash
kubectl port-forward svc/trino 8080:8080 -n data-platform
`
- **URL**: [http://localhost:8080](http://localhost:8080)
- **Username**: dmin (No password required)

### 📊 Apache Superset (BI & Dashboards)
`ash
kubectl port-forward svc/superset 8088:8088 -n data-platform
`
- **URL**: [http://localhost:8088](http://localhost:8088)
- **User**: dmin
- **Pass**: dmin

### 🌪️ Apache Airflow (Workflow Orchestration)
`ash
kubectl port-forward svc/airflow-webserver 8080:8080 -n data-platform
`
*(Note: If port 8080 is blocked by Trino, use a different local port like 8081:8080)*
- **URL**: [http://localhost:8080](http://localhost:8080)
- **User / Pass**: Check with the project owner or Kubernetes secret.

### 🐘 Gravitino (Data Catalog REST)
`ash
kubectl port-forward svc/gravitino 9090:9090 -n data-platform
`
- **URL**: [http://localhost:9090](http://localhost:9090)

---

## 5. Working with Spark

The cluster uses the **Spark Kubernetes Operator**. You can submit jobs declaratively via YAML manifests rather than using traditional spark-submit.

To submit a test job (e.g., Spark Pi):
`ash
kubectl apply -f k8s/base/platform-services/spark/spark-pi-example.yaml -n data-platform
`

To view the status of your jobs:
`ash
kubectl get sparkapplication -n data-platform
`

To tail the logs of your Spark Driver:
`ash
kubectl logs -f spark-pi-driver -n data-platform
`

---

## 6. Development Workflow

- **Kubernetes Manifests**: Stored in k8s/base/.
- **Helm Configurations**: Override files are found in helm-values/ (e.g., Trino, Airflow).
- **Applying Changes**: After modifying infrastructure code, simply run:
  `ash
  kubectl apply -k k8s/overlays/dev/
  `

If you encounter any issues, refer to the documents inside the docs/runbooks/ directory for troubleshooting and architectural details. Happy building! 🚀
