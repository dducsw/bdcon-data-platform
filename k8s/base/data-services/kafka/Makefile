NAMESPACE ?= data-platform

.PHONY: \
	apply delete status create-topic delete-topic help

help:
	@echo "Makefile commands for Kafka (Strimzi):"
	@echo "  make apply           - Deploy the Kafka KRaft cluster"
	@echo "  make delete          - Delete the Kafka cluster"
	@echo "  make status          - Check Kafka cluster status"
	@echo "  make create-topic    - Create the 'buswaypoints' topic"
	@echo "  make delete-topic    - Delete the 'buswaypoints' topic"

apply:
	@set -e; \
	printf '\033[1;33mApplying Kafka Cluster via Strimzi...\033[0m\n'; \
	kubectl apply -f kafka-cluster.yaml -n $(NAMESPACE); \
	printf '\033[1;32mKafka Cluster applied.\033[0m\n'

delete:
	@set -e; \
	printf '\033[1;31mDeleting Kafka Cluster...\033[0m\n'; \
	kubectl delete -f kafka-cluster.yaml -n $(NAMESPACE) || true; \
	printf '\033[1;32mKafka Cluster deleted.\033[0m\n'

status:
	@kubectl get kafka data-platform-kafka -n $(NAMESPACE) -w

create-topic:
	@set -e; \
	printf '\033[1;33mCreating Kafka Topic...\033[0m\n'; \
	kubectl apply -f kafka-topic.yaml -n $(NAMESPACE); \
	printf '\033[1;32mTopic created.\033[0m\n'

delete-topic:
	@set -e; \
	printf '\033[1;31mDeleting Kafka Topic...\033[0m\n'; \
	kubectl delete -f kafka-topic.yaml -n $(NAMESPACE) || true; \
	printf '\033[1;32mTopic deleted.\033[0m\n'
