import json
import logging
from kafka import KafkaProducer
from src.models import Event

class KafkaEventPublisher:
    def __init__(self, bootstrap_servers: str, topic_prefix: str):
        self.bootstrap_servers = bootstrap_servers
        self.topic_prefix = topic_prefix
        
        logging.info(f"Initializing Kafka producer connecting to {self.bootstrap_servers}")
        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            # Add retries and acknowledgments for robust delivery
            retries=5,
            acks='all'
        )
        self.topic = self.topic_prefix
        logging.info(f"Kafka publisher ready. Target topic: {self.topic}")

    def publish(self, event: Event):
        import dataclasses
        try:
            # We can use the event ID or user ID as the routing key
            key = str(event.user_id) if getattr(event, 'user_id', None) else str(getattr(event, 'session_id', ''))
            payload = dataclasses.asdict(event) if dataclasses.is_dataclass(event) else getattr(event, '__dict__', {})
            
            self.producer.send(
                topic=self.topic,
                key=key,
                value=payload
            )
            # We don't block here (don't call .get()) to keep the generator fast.
            # The producer will send batches asynchronously.
        except Exception as e:
            logging.error(f"Failed to publish event to Kafka: {e}")

    def close(self):
        if self.producer:
            self.producer.flush()
            self.producer.close()
