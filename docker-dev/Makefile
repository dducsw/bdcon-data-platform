.PHONY: init-kafka-topics list-kafka-topics read-kafka-topic help up-streaming up-lakehouse up-all down stop restart install


KAFKA_CONTAINER = kafka
BOOTSTRAP_SERVER = localhost:9092
PYTHON ?= python3

# Service Groups
STREAMING_SERVICES = kafka spark-master spark-worker-1
LAKEHOUSE_SERVICES = postgres minio minio-client hive-metastore trino superset spark-master spark-worker-1

help:
	@echo "Available commands:"
	@echo "  make up-streaming                - Create and start Streaming services"
	@echo "  make start-streaming             - Start existing Streaming containers"
	@echo "  make up-lakehouse                - Create and start Lakehouse services"
	@echo "  make start-lakehouse             - Start existing Lakehouse containers"
	@echo "  make up-all                      - Create and start all services"
	@echo "  make start-all                   - Start all existing containers"
	@echo "  make down                        - Stop and remove all containers"
	@echo "  make stop                        - Stop all containers without removing them"
	@echo "  make restart                     - Restart all services"
	@echo "  make init-kafka-topics           - Create necessary Kafka topics for the project"
	@echo "  make list-kafka-topics           - List all current Kafka topics"
	@echo "  make read-kafka-topic TOPIC=name - Read messages from a specific Kafka topic"
	@echo "  make install                     - Install Python dependencies"

up-streaming:
	@echo "Starting Streaming & Real-time services (Up)..."
	docker-compose up -d $(STREAMING_SERVICES)

start-streaming:
	@echo "Starting Streaming & Real-time services (Start)..."
	docker-compose start $(STREAMING_SERVICES)

up-lakehouse:
	@echo "Starting Lakehouse services (Up)..."
	docker-compose up -d $(LAKEHOUSE_SERVICES)

start-lakehouse:
	@echo "Starting Lakehouse services (Start)..."
	docker-compose start $(LAKEHOUSE_SERVICES)

up-all:
	@echo "Starting all services (Up)..."
	docker-compose up -d

start-all:
	@echo "Starting all services (Start)..."
	docker-compose start

down:
	@echo "Stopping and removing all containers..."
	docker-compose down

stop:
	@echo "Stopping all containers..."
	docker-compose stop

restart:
	@echo "Restarting all services..."
	docker-compose restart

init-kafka-topics:
	@echo "Creating Kafka topics (buswaypoint_json)..."
	@if ! docker ps | grep -q $(KAFKA_CONTAINER); then \
		echo "Error: $(KAFKA_CONTAINER) container is not running! Start docker-compose first."; \
		exit 1; \
	fi
	@docker exec $(KAFKA_CONTAINER) /opt/kafka/bin/kafka-topics.sh \
		--create --if-not-exists \
		--topic buswaypoint_json \
		--bootstrap-server $(BOOTSTRAP_SERVER) \
		--partitions 2 \
		--replication-factor 1
	@echo "Kafka topics created successfully."

list-kafka-topics:
	@echo "Listing Kafka topics:"
	@docker exec $(KAFKA_CONTAINER) /opt/kafka/bin/kafka-topics.sh \
		--list \
		--bootstrap-server $(BOOTSTRAP_SERVER)

read-kafka-topic:
	@if [ -z "$(TOPIC)" ]; then \
		echo "Error: Please specify a topic using TOPIC=topic_name. Example: make read-kafka-topic TOPIC=buswaypoint_json"; \
		exit 1; \
	fi
	@$(PYTHON) scripts/read_topic.py $(TOPIC)
