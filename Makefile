.PHONY: help \
	up-streaming up-lakehouse up-all start-streaming start-lakehouse start-all \
	down stop restart \
	init-kafka-topics list-kafka-topics read-kafka-topic install \
	k8s-deploy k8s-dev k8s-diff k8s-status k8s-pods k8s-logs k8s-start k8s-stop \
	tf-init tf-validate tf-plan tf-apply tf-destroy tf-fmt \
	secrets-create


# ================================================================
# Variables
# ================================================================

NAMESPACE       ?= data-platform
SERVICE         ?= spark-master      # Override with: make k8s-logs SERVICE=trino-coordinator
KAFKA_CONTAINER  = kafka
BOOTSTRAP_SERVER = localhost:9092
PYTHON          ?= python3

# Service Groups (Docker Compose — local dev)
STREAMING_SERVICES = kafka kafka-exporter redis redis-exporter prometheus grafana cadvisor spark-master spark-worker-1 spark-worker-2
LAKEHOUSE_SERVICES = gravitino postgres minio minio-client trino superset spark-master spark-worker-1 spark-worker-2


# ================================================================
# Help
# ================================================================
help:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════╗"
	@echo "║          K8s Data Platform — Makefile Help           ║"
	@echo "╠══════════════════════════════════════════════════════╣"
	@echo "║  KUBERNETES                                          ║"
	@echo "║  make k8s-deploy   — Apply all manifests (base)     ║"
	@echo "║  make k8s-dev      — Apply dev overlay              ║"
	@echo "║  make k8s-diff     — Dry-run diff (what will change)║"
	@echo "║  make k8s-status   — Show all pod statuses          ║"
	@echo "║  make k8s-pods     — Watch pods live (-w)           ║"
	@echo "║  make k8s-logs     — Tail logs (SERVICE=name)       ║"
	@echo "║  make k8s-start    — Scale up workloads (14:00)     ║"
	@echo "║  make k8s-stop     — Scale down workloads (22:00)   ║"
	@echo "╠══════════════════════════════════════════════════════╣"
	@echo "║  TERRAFORM                                           ║"
	@echo "║  make tf-init      — terraform init                  ║"
	@echo "║  make tf-validate  — terraform validate              ║"
	@echo "║  make tf-plan      — terraform plan                  ║"
	@echo "║  make tf-apply     — terraform apply                 ║"
	@echo "║  make tf-destroy   — terraform destroy               ║"
	@echo "║  make tf-fmt       — terraform fmt -recursive        ║"
	@echo "╠══════════════════════════════════════════════════════╣"
	@echo "║  SECRETS SETUP (run once after cluster creation)     ║"
	@echo "║  make secrets-create — Push secrets to GCP SM        ║"
	@echo "╠══════════════════════════════════════════════════════╣"
	@echo "║  DOCKER COMPOSE (local dev)                          ║"
	@echo "║  make up-all       — Start all Docker services       ║"
	@echo "║  make down         — Stop and remove containers      ║"
	@echo "║  make init-kafka-topics — Create Kafka topics        ║"
	@echo "╚══════════════════════════════════════════════════════╝"
	@echo ""


# ================================================================
# Kubernetes
# ================================================================

k8s-deploy:
	@echo "🚀 Deploying all manifests (base)..."
	kubectl apply -k k8s/

k8s-dev:
	@echo "🚀 Deploying with dev overlay (reduced resources)..."
	kubectl apply -k k8s/overlays/dev/

k8s-diff:
	@echo "🔍 Previewing changes (dry-run)..."
	kubectl diff -k k8s/ || true

k8s-status:
	@echo "📊 Pod status in namespace: $(NAMESPACE)"
	kubectl get pods,svc,pvc -n $(NAMESPACE)

k8s-pods:
	@echo "👀 Watching pods (Ctrl+C to exit)..."
	kubectl get pods -n $(NAMESPACE) -w

k8s-logs:
	@echo "📋 Tailing logs for: $(SERVICE)"
	kubectl logs -f deployment/$(SERVICE) -n $(NAMESPACE) --tail=100

k8s-start:
	@echo "▶️  Starting cluster workloads..."
	./scripts/gke_schedule.sh start

k8s-stop:
	@echo "⏹️  Stopping cluster workloads..."
	./scripts/gke_schedule.sh stop


# ================================================================
# Terraform
# ================================================================

tf-init:
	@echo "🔧 Initializing Terraform..."
	cd terraform && terraform init

tf-validate:
	@echo "✅ Validating Terraform configuration..."
	cd terraform && terraform validate

tf-plan:
	@echo "📋 Planning Terraform changes..."
	cd terraform && terraform plan -var-file=terraform.tfvars

tf-apply:
	@echo "⚠️  Applying Terraform changes..."
	cd terraform && terraform apply -var-file=terraform.tfvars

tf-destroy:
	@echo "💣 Destroying Terraform-managed infrastructure..."
	cd terraform && terraform destroy -var-file=terraform.tfvars

tf-fmt:
	@echo "🎨 Formatting Terraform files..."
	cd terraform && terraform fmt -recursive


# ================================================================
# Spark Operator (Kubeflow spark-operator v2.5.0)
# ================================================================
SPARK_REGISTRY  ?= gcr.io/k8s-data-platform-1879
SPARK_IMAGE     ?= $(SPARK_REGISTRY)/spark:3.5.5
SPARK_APP       ?= k8s/spark/spark-pi-example.yaml   # Override: make spark-submit SPARK_APP=path/to/app.yaml

spark-operator-install:
	@echo "🚀 Installing Spark Kubernetes Operator..."
	helm repo add spark-operator https://kubeflow.github.io/spark-operator 2>/dev/null || true
	helm repo update spark-operator
	helm install spark-operator spark-operator/spark-operator \
		--namespace $(NAMESPACE) \
		--values k8s/spark/setup/spark-operator-values.yaml
	@echo "✅ spark-operator installed. Check: make spark-operator-status"

spark-operator-upgrade:
	@echo "⬆️  Upgrading Spark Kubernetes Operator..."
	helm upgrade spark-operator spark-operator/spark-operator \
		--namespace $(NAMESPACE) \
		--values k8s/spark/setup/spark-operator-values.yaml
	@echo "✅ spark-operator upgraded."

spark-operator-status:
	@echo "📊 Spark Operator status:"
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=spark-operator
	@echo ""
	@echo "📋 SparkApplications:"
	@kubectl get sparkapplication -n $(NAMESPACE) 2>/dev/null || echo "  (no SparkApplications found)"

spark-operator-logs:
	@echo "📋 Spark Operator controller logs:"
	kubectl logs -n $(NAMESPACE) -l app.kubernetes.io/name=spark-operator -f --tail=100

spark-build-image:
	@echo "🔨 Building Spark Docker image..."
	cd k8s/spark && docker build -t $(SPARK_IMAGE) \
		--build-arg PYTHON_VERSION=3.12.3 \
		--build-arg SPARK_VERSION=3.5.5 \
		--build-arg SPARK_SCALA_VERSION=3.5_2.12 \
		--build-arg ICEBERG_VERSION=1.10.0 \
		--build-arg POSTGRESQL_JAR_VERSION=42.7.5 \
		--build-arg HADOOP_AWS_JAR_VERSION=3.3.1 \
		--build-arg AWS_JAVA_SDK_BUNDLE_JAR_VERSION=1.12.367 \
		--build-arg KAFKA_VERSION=3.9.0 \
		--build-arg SPARK_KAFKA_VERSION=3.5.5 \
		-f build/Dockerfile ../../
	@echo "✅ Image built: $(SPARK_IMAGE)"

spark-push-image:
	@echo "📤 Pushing Spark image to GCR..."
	gcloud auth configure-docker --quiet
	docker push $(SPARK_IMAGE)
	@echo "✅ Image pushed: $(SPARK_IMAGE)"

spark-submit:
	@echo "🚀 Submitting SparkApplication: $(SPARK_APP)"
	kubectl apply -f $(SPARK_APP) -n $(NAMESPACE)
	@echo "👀 Watch status: make spark-watch"

spark-delete:
	@echo "🗑️  Deleting SparkApplication: $(SPARK_APP)"
	kubectl delete -f $(SPARK_APP) -n $(NAMESPACE) --ignore-not-found

spark-watch:
	@echo "👀 Watching SparkApplications (Ctrl+C to exit)..."
	kubectl get sparkapplication -n $(NAMESPACE) -w

spark-logs:
	@echo "📋 Spark driver logs:"
	kubectl logs -n $(NAMESPACE) -l spark-role=driver -f --tail=100

spark-jobs:
	@echo "📋 All SparkApplications:"
	kubectl get sparkapplication -n $(NAMESPACE) -o wide


# ================================================================
# Secrets Bootstrap (run once after cluster is created)
# ================================================================

secrets-create:
	@echo "🔐 Creating secrets in GCP Secret Manager..."
	@echo "  ⚠️  This will prompt for values. Replace placeholders with real passwords."
	@read -p "  MinIO root user [minioadmin]: " minio_user; \
	 minio_user=$${minio_user:-minioadmin}; \
	 gcloud secrets create minio-root-user --data-file=- <<< "$$minio_user" || \
	 gcloud secrets versions add minio-root-user --data-file=- <<< "$$minio_user"
	@read -sp "  MinIO root password: " minio_pass; echo; \
	 gcloud secrets create minio-root-password --data-file=- <<< "$$minio_pass" || \
	 gcloud secrets versions add minio-root-password --data-file=- <<< "$$minio_pass"
	@read -p "  Postgres user [postgres]: " pg_user; \
	 pg_user=$${pg_user:-postgres}; \
	 gcloud secrets create postgres-user --data-file=- <<< "$$pg_user" || \
	 gcloud secrets versions add postgres-user --data-file=- <<< "$$pg_user"
	@read -sp "  Postgres password: " pg_pass; echo; \
	 gcloud secrets create postgres-password --data-file=- <<< "$$pg_pass" || \
	 gcloud secrets versions add postgres-password --data-file=- <<< "$$pg_pass"
	@read -p "  Postgres database [catalog_metastore_db]: " pg_db; \
	 pg_db=$${pg_db:-catalog_metastore_db}; \
	 gcloud secrets create postgres-db --data-file=- <<< "$$pg_db" || \
	 gcloud secrets versions add postgres-db --data-file=- <<< "$$pg_db"
	@echo "  Generating Superset secret key..."
	@python -c "import secrets; print(secrets.token_hex(32))" | \
	 gcloud secrets create superset-secret-key --data-file=- 2>/dev/null || \
	 python -c "import secrets; print(secrets.token_hex(32))" | \
	 gcloud secrets versions add superset-secret-key --data-file=-
	@echo "✅ Secrets created in GCP Secret Manager."


# ================================================================
# Docker Compose (local dev)
# ================================================================

up-streaming:
	@echo "Starting Streaming & Real-time services..."
	docker-compose up -d $(STREAMING_SERVICES)

start-streaming:
	docker-compose start $(STREAMING_SERVICES)

up-lakehouse:
	@echo "Starting Lakehouse services..."
	docker-compose up -d $(LAKEHOUSE_SERVICES)

start-lakehouse:
	docker-compose start $(LAKEHOUSE_SERVICES)

up-all:
	@echo "Starting all services..."
	docker-compose up -d

start-all:
	docker-compose start

down:
	@echo "Stopping and removing all containers..."
	docker-compose down

stop:
	docker-compose stop

restart:
	docker-compose restart

init-kafka-topics:
	@echo "Creating Kafka topics..."
	@if ! docker ps | grep -q $(KAFKA_CONTAINER); then \
		echo "Error: $(KAFKA_CONTAINER) container is not running!"; exit 1; \
	fi
	@docker exec $(KAFKA_CONTAINER) /opt/kafka/bin/kafka-topics.sh \
		--create --if-not-exists \
		--topic buswaypoint_json \
		--bootstrap-server $(BOOTSTRAP_SERVER) \
		--partitions 2 \
		--replication-factor 1
	@echo "Kafka topics created."

list-kafka-topics:
	@docker exec $(KAFKA_CONTAINER) /opt/kafka/bin/kafka-topics.sh \
		--list --bootstrap-server $(BOOTSTRAP_SERVER)

read-kafka-topic:
	@if [ -z "$(TOPIC)" ]; then \
		echo "Error: specify topic using TOPIC=name"; exit 1; \
	fi
	@$(PYTHON) scripts/read_topic.py $(TOPIC)

install:
	pip install -r requirements.txt
