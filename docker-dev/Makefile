.PHONY: init-kafka-topics list-kafka-topics read-kafka-topic help up-streaming up-lakehouse up-all down stop restart install benchmark-prepare benchmark-spark benchmark-trino benchmark-report benchmark-all


KAFKA_CONTAINER = kafka
BOOTSTRAP_SERVER = localhost:9092
PYTHON ?= python3

# Service Groups
STREAMING_SERVICES = kafka spark-master spark-worker-1
LAKEHOUSE_SERVICES = gravitino postgres minio minio-client trino superset spark-master spark-worker-1

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
	@echo "  make read-kafka-topic TOPIC=name [GROUP=group_id] - Read messages from a specific Kafka topic"
	@echo "  make install                     - Install Python dependencies"
	@echo "  make benchmark-prepare          - Materialize TPC-DS SF5 tables into Iceberg"
	@echo "  make benchmark-spark            - Run Spark benchmark suite"
	@echo "  make benchmark-trino            - Run Trino benchmark suite"
	@echo "  make benchmark-report           - Merge raw benchmark results into a report"
	@echo "  make benchmark-all              - Prepare data, run both engines, and build report"
	@echo "  make pipeline-bronze            - Run all Bronze layer ingestion scripts"
	@echo "  make pipeline-silver            - Run all Silver layer transformation scripts"
	@echo "  make pipeline-gold              - Run all Gold layer aggregation scripts"
	@echo "  make pipeline-all               - Run full Medallion pipeline (Bronze -> Silver -> Gold)"

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
	@echo "Creating Kafka topics (buswaypoint_json, click_events)..."
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
	@docker exec $(KAFKA_CONTAINER) /opt/kafka/bin/kafka-topics.sh \
		--create --if-not-exists \
		--topic click_events \
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
	@$(PYTHON) scripts/verify/read_topic.py $(TOPIC) $(GROUP)

benchmark-prepare:
	@$(PYTHON) benchmark/scripts/prepare_tpcds_data.py

benchmark-spark:
	@$(PYTHON) benchmark/scripts/run_spark_benchmark.py

benchmark-trino:
	@$(PYTHON) benchmark/scripts/run_trino_benchmark.py

benchmark-report:
	@$(PYTHON) benchmark/scripts/build_report.py

benchmark-all: benchmark-prepare benchmark-spark benchmark-trino benchmark-report

# ================================================================
# Data Pipeline (Medallion Architecture)
# ================================================================
SPARK_MASTER = spark-master
PYTHONPATH_ENV = /opt/spark/apps/pipelines

pipeline-bronze:
	@echo "🚀 Running Bronze Layer Ingestion..."
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/bronze/bronze_users.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/bronze/bronze_orders.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/bronze/bronze_order_items.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/bronze/bronze_products.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/bronze/bronze_distribution_centers.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/bronze/bronze_inventory_items.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/bronze/bronze_events.py
	@echo "✅ Bronze layer completed."

pipeline-silver:
	@echo "🚀 Running Silver Layer Transformation..."
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/silver/silver_users.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/silver/silver_orders.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/silver/silver_order_items.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/silver/silver_products.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/silver/silver_events.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/silver/silver_distribution_centers.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/silver/silver_inventory_items.py
	@echo "✅ Silver layer completed."

pipeline-gold:
	@echo "🚀 Running Gold Layer Aggregation..."
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/gold/gold_sales_performance.py
	docker exec -e PYTHONPATH=$(PYTHONPATH_ENV) $(SPARK_MASTER) python /opt/spark/apps/pipelines/gold/gold_user_engagement.py
	@echo "✅ Gold layer completed."

pipeline-all: pipeline-bronze pipeline-silver pipeline-gold
	@echo "🎯 Full Medallion Pipeline executed successfully!"
