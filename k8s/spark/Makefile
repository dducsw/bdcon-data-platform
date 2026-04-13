NAMESPACE ?= data-platform
REGISTRY ?= REGISTRY
SPARK_IMAGE ?= $(REGISTRY)/spark:3.5.5

.PHONY: build-image push-image submit-pi delete-pi check-status get-jobs logs-pi help

build-image:
	@set -e; \
	printf '\033[1;33mBuilding Spark custom Docker image...\033[0m\n'; \
	docker build -t $(SPARK_IMAGE) \
		--build-arg PYTHON_VERSION=3.12.3 \
		--build-arg SPARK_VERSION=3.5.5 \
		--build-arg SPARK_SCALA_VERSION=3.5_2.12 \
		--build-arg ICEBERG_VERSION=1.10.0 \
		--build-arg POSTGRESQL_JAR_VERSION=42.7.5 \
		--build-arg HADOOP_AWS_JAR_VERSION=3.3.1 \
		--build-arg AWS_JAVA_SDK_BUNDLE_JAR_VERSION=1.12.367 \
		--build-arg AWS_SDK_V2_VERSION=2.25.11 \
		--build-arg KAFKA_VERSION=3.9.0 \
		--build-arg SPARK_KAFKA_VERSION=3.5.5 \
		-f build/Dockerfile ../../; \
	printf '\033[1;32mSpark image built.\033[0m\n'

push-image:
	@set -e; \
	printf '\033[1;33mPushing Spark image...\033[0m\n'; \
	docker push $(SPARK_IMAGE); \
	printf '\033[1;32mImage pushed.\033[0m\n'

submit-pi:
	@set -e; \
	printf '\033[1;33mSubmitting Spark Pi example...\033[0m\n'; \
	kubectl apply -f spark-pi-example.yaml -n $(NAMESPACE); \
	printf '\033[1;32mJob submitted.\033[0m\n'

delete-pi:
	@set -e; \
	printf '\033[1;33mDeleting Spark Pi example...\033[0m\n'; \
	kubectl delete -f spark-pi-example.yaml -n $(NAMESPACE) || true; \
	printf '\033[1;32mJob deleted.\033[0m\n'

check-status:
	@set -e; \
	printf '\033[1;33mChecking Spark pods...\033[0m\n'; \
	kubectl get pods -l spark-role=driver -n $(NAMESPACE)

get-jobs:
	@set -e; \
	printf '\033[1;33mListing Spark jobs...\033[0m\n'; \
	kubectl get sparkapplication -n $(NAMESPACE)

logs-pi:
	@set -e; \
	printf '\033[1;33mGetting driver logs...\033[0m\n'; \
	kubectl logs -n $(NAMESPACE) -f spark-pi-driver

help:
	@echo "Spark Makefile commands:"
	@echo "  make build-image     - Build Spark custom Docker image"
	@echo "  make push-image      - Push Spark Docker image to REGISTRY"
	@echo "  make submit-pi       - Submit Spark Pi example job"
	@echo "  make delete-pi       - Delete Spark Pi example job"
	@echo "  make check-status    - View running Spark driver pods"
	@echo "  make get-jobs        - List SparkApplication CRDs"
	@echo "  make logs-pi         - Follow logs for the Spark Pi job"

