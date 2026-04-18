#!/bin/bash

# This script initializes the Kafka topics needed for the project.
# It uses docker exec to run the kafka-topics.sh script inside the kafka container.

KAFKA_CONTAINER="kafka"
BOOTSTRAP_SERVER="localhost:9092"

TOPICS=(
    "buswaypoint_json"
)

echo "Checking Kafka container status..."
if ! docker ps | grep -q "$KAFKA_CONTAINER"; then
    echo "Error: Kafka container '$KAFKA_CONTAINER' is not running!"
    echo "Please start your docker-compose environment first."
    exit 1
fi

echo "Creating Kafka topics..."

for topic in "${TOPICS[@]}"; do
    echo "-> Creating topic: $topic"
    docker exec "$KAFKA_CONTAINER" /opt/kafka/bin/kafka-topics.sh \
        --create \
        --if-not-exists \
        --topic "$topic" \
        --bootstrap-server "$BOOTSTRAP_SERVER" \
        --partitions 2 \
        --replication-factor 2
done

echo ""
echo "List of current topics:"
docker exec "$KAFKA_CONTAINER" /opt/kafka/bin/kafka-topics.sh \
    --list \
    --bootstrap-server "$BOOTSTRAP_SERVER"

echo ""
echo "Done!"
