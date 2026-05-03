import argparse
import asyncio
import logging
import random
import re
import sys
from pathlib import Path

from faker import Faker
from sqlalchemy.exc import OperationalError, SQLAlchemyError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from src.db_writer import DataWriter
from src.id_allocator import IdAllocator
from src.models import Event, EventCategory, User, PRODUCT_MAP


logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
)


class EventsOnlySimulator:
    def __init__(self, args: argparse.Namespace, fake: Faker):
        self.args = args
        self.fake = fake
        self.writer = DataWriter(
            user=args.db_user,
            password=args.db_password,
            host=args.db_host,
            port=args.db_port,
            db_name=args.db_name,
            schema=args.db_schema,
            batch_size=args.db_batch_size,
        )
        self.user_ids = IdAllocator()
        self.event_ids = IdAllocator()
        self.clickstream_publisher = None
        if args.publish_kafka:
            from src.kafka_publisher import KafkaEventPublisher
            self.clickstream_publisher = KafkaEventPublisher(
                bootstrap_servers=args.bootstrap_servers,
                topic_prefix=args.topic_prefix,
            )

    async def initialize(self):
        await asyncio.to_thread(self.writer.create_tables_if_not_exists)
        event_max = await asyncio.to_thread(
            self.writer.select, table="events", columns=["max(id) as max_id"]
        )
        self.event_ids.seed_from_existing(event_max[0]["max_id"] if event_max else 0)
        user_max = await asyncio.to_thread(
            self.writer.select, table="users", columns=["max(id) as max_id"]
        )
        self.user_ids.seed_from_existing(user_max[0]["max_id"] if user_max else 0)
        user_count = await asyncio.to_thread(
            self.writer.select, table="users", columns=["count(*) as cnt"]
        )
        existing_users = int(user_count[0]["cnt"]) if user_count else 0
        if existing_users == 0 and self.args.init_num_users > 0:
            users = [
                User.new(
                    country=self.args.country,
                    state=self.args.state,
                    postal_code=self.args.postal_code,
                    fake=self.fake,
                )
                for _ in range(self.args.init_num_users)
            ]
            for user in users:
                user.id = self.user_ids.allocate()
            await asyncio.to_thread(
                self.writer.upsert, table="users", data=users, conflict_keys=["id"]
            )
            logging.info("Seeded %s users for events-only generation.", len(users))

    async def _publish_if_needed(self, events):
        if not self.clickstream_publisher:
            return
        for event in events:
            await asyncio.to_thread(self.clickstream_publisher.publish, event)

    async def _generate_user_session(self):
        user_rows = await asyncio.to_thread(
            self.writer.select, table="users", order_by="RANDOM()", limit=1
        )
        if not user_rows:
            logging.warning("No users available to generate authenticated events.")
            return

        user = User.from_dict(user_rows[0])
        events = Event.new(user=user, order_item=None, event_category=EventCategory.GHOST.value, fake=self.fake)
        for event in events:
            event.id = self.event_ids.allocate()
            if event.event_type in {"purchase", "cancel", "return"}:
                event.event_type = "product"
            if event.event_type == "product" and not re.match(r"^/product/\d+$", event.uri):
                product_id = random.choice(list(PRODUCT_MAP.keys()))
                event.uri = f"/product/{product_id}"

        await asyncio.to_thread(
            self.writer.upsert, table="events", data=events, conflict_keys=["id"]
        )
        await self._publish_if_needed(events)

    async def _generate_ghost_session(self):
        events = Event.new(
            user=None,
            order_item=None,
            event_category=EventCategory.GHOST.value,
            fake=self.fake,
        )
        for event in events:
            event.id = self.event_ids.allocate()
            if event.event_type in {"purchase", "cancel", "return"}:
                event.event_type = "product"
            if event.event_type == "product" and not re.match(r"^/product/\d+$", event.uri):
                product_id = random.choice(list(PRODUCT_MAP.keys()))
                event.uri = f"/product/{product_id}"
        await asyncio.to_thread(
            self.writer.upsert, table="events", data=events, conflict_keys=["id"]
        )
        await self._publish_if_needed(events)

    async def run(self):
        current_iteration = 0
        while True:
            if 0 < self.args.max_iter <= current_iteration:
                logging.info("Stopped after %s iterations.", current_iteration)
                break

            try:
                wait_time = random.expovariate(self.args.avg_qps)
                await asyncio.sleep(wait_time)

                if random.random() < self.args.ghost_ratio:
                    await self._generate_ghost_session()
                else:
                    await self._generate_user_session()
            except (SQLAlchemyError, OperationalError) as exc:
                logging.warning("Events-only generation failed on iteration %s: %s", current_iteration, exc)
                await asyncio.sleep(5)
            else:
                current_iteration += 1

    async def close(self):
        if self.writer.conn and not self.writer.conn.closed:
            await asyncio.to_thread(self.writer.close)
        if self.clickstream_publisher and hasattr(self.clickstream_publisher, 'close'):
            self.clickstream_publisher.close()


async def run_simulation(args: argparse.Namespace):
    simulator = EventsOnlySimulator(args, Faker())
    try:
        await simulator.initialize()
        await simulator.run()
    finally:
        await simulator.close()


def main():
    parser = argparse.ArgumentParser(description="Generate only clickstream events")
    parser.add_argument("--avg-qps", type=float, default=20.0, help="Average event-session generations per second.")
    parser.add_argument("--max-iter", type=int, default=-1, help="Max number of successful iterations. Default -1 for infinite.")
    parser.add_argument("--ghost-ratio", type=float, default=0.3, help="Probability of generating anonymous sessions.")
    parser.add_argument("--init-num-users", type=int, default=100, help="Seed users if users table is empty.")
    parser.add_argument("--country", default="*", help="User country.")
    parser.add_argument("--state", default="*", help="User state.")
    parser.add_argument("--postal-code", default="*", help="User postal code.")
    parser.add_argument("--db-host", default="localhost", help="Database host.")
    parser.add_argument("--db-port", type=int, default=5432, help="Database port.")
    parser.add_argument("--db-user", default="db_user", help="Database user.")
    parser.add_argument("--db-password", default="db_password", help="Database password.")
    parser.add_argument("--db-name", default="fh_dev", help="Database name.")
    parser.add_argument("--db-schema", default="public", help="Database schema.")
    parser.add_argument("--db-batch-size", type=int, default=1000)
    parser.add_argument("--publish-kafka", action="store_true", help="Publish generated events to Kafka.")
    parser.add_argument("--bootstrap-servers", type=str, default="localhost:9092", help="Bootstrap server addresses.")
    parser.add_argument("--topic-prefix", type=str, default="ecomm", help="Kafka topic prefix.")

    args = parser.parse_args()

    try:
        asyncio.run(run_simulation(args))
    except KeyboardInterrupt:
        logging.warning("Events-only generator stopped by user.")


if __name__ == "__main__":
    main()
