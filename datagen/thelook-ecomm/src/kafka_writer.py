import json
import logging
import dataclasses
import datetime
from typing import List, Union, Any
from kafka import KafkaProducer

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
)

class DataSerializer(json.JSONEncoder):
    """Custom JSON encoder for dataclasses and datetime objects."""
    def default(self, obj: Any) -> Any:
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)

class KafkaWriter:
    def __init__(
        self,
        bootstrap_servers: str,
        topic_prefix: str,
        topic: str = None,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic_prefix = topic_prefix
        self.topic = topic
        self.producer = None
        self._connect()

    def _connect(self):
        try:
            logging.info(f"Connecting to Kafka at {self.bootstrap_servers}...")
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, cls=DataSerializer).encode("utf-8"),
                acks=1,
                retries=3,
                linger_ms=10,
                api_version=(3, 6, 0)
            )
            logging.info("Kafka connection established.")
        except Exception as e:
            logging.error(f"Failed to connect to Kafka: {e}")
            self.producer = None

    def send(self, data: List[Any], table: str = "events"):
        """Sends a list of objects to a Kafka topic."""
        if self.producer is None:
            # Attempt to reconnect
            self._connect()
            if self.producer is None:
                logging.warning("Kafka producer not available. Skipping message send.")
                return

        topic = self.topic or f"{self.topic_prefix}.{table}"
        try:
            for item in data:
                self.producer.send(topic, item)
            # We don't flush every time for performance, but we rely on linger_ms
            logging.debug(f"Sent {len(data)} messages to Kafka topic {topic}")
        except Exception as e:
            logging.error(f"Error sending messages to Kafka: {e}")

    def close(self):
        if self.producer:
            logging.info("Closing Kafka producer...")
            self.producer.flush()
            self.producer.close()
            logging.info("Kafka producer closed.")
