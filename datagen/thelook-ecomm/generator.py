import argparse
import asyncio
import random
import logging
import datetime
import os
import sys
import threading
from pathlib import Path

from faker import Faker
from sqlalchemy.exc import SQLAlchemyError, OperationalError

SCRIPT_DIR = Path(__file__).resolve().parent
# Local: datagen/thelook-ecomm/generator.py  -> parents[2] = repo root
# Docker: /app/generator.py                  -> parents[0] = /app (src/ is copied here)
try:
    REPO_ROOT = SCRIPT_DIR.parents[1]  # datagen/thelook-ecomm -> repo root
    if not (REPO_ROOT / "src").exists():
        raise IndexError("src/ not found at parents[1], try script dir")
except (IndexError, OSError):
    REPO_ROOT = SCRIPT_DIR  # Docker: /app has src/ copied directly
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.db_writer import DataWriter
from src.id_allocator import IdAllocator
from src.models import User, Order, OrderItem, Event, OrderStatus, EventCategory, PRODUCT_MAP
from src.utils import generate_from_csv

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
)


class TheLookECommSimulator:
    """
    Manages the state and execution of the e-commerce data generation simulation.
    """

    def __init__(self, args: argparse.Namespace, fake: Faker):
        """Initializes the simulator and the DataWriter."""
        self.args = args
        self.fake = fake
        self.writer = DataWriter(
            user=args.db_user,
            password=args.db_password,
            host=args.db_host,
            db_name=args.db_name,
            schema=args.db_schema,
            port=args.db_port,
            batch_size=args.db_batch_size,
        )
        self.consecutive_db_errors = 0
        self.max_consecutive_errors = 3
        self._next_inventory_item_id = None
        self.product_lookup = {}
        self.user_ids = IdAllocator()
        self.order_ids = IdAllocator()
        self.order_item_ids = IdAllocator()
        self.event_ids = IdAllocator()
        self._db_lock = threading.RLock()
        self.clickstream_publisher = None
        if args.publish_kafka:
            from src.kafka_publisher import KafkaEventPublisher
            self.clickstream_publisher = KafkaEventPublisher(
                bootstrap_servers=args.bootstrap_servers,
                topic_prefix=args.topic_prefix,
            )

    def _build_product_lookup(self, products: list[dict]) -> dict[int, dict]:
        lookup = {}
        for p in products:
            pid = int(p["id"])
            lookup[pid] = {
                "cost": float(p.get("cost", 0) or 0),
                "category": p.get("category", "unknown"),
                "name": p.get("name", "unknown"),
                "brand": p.get("brand", "unknown"),
                "retail_price": float(p.get("retail_price", 0) or 0),
                "department": p.get("department", "unknown"),
                "sku": p.get("sku", "n/a"),
                "distribution_center_id": int(p.get("distribution_center_id", 0) or 0),
            }
        return lookup

    def _ensure_inventory_id_seeded(self):
        if self._next_inventory_item_id is not None:
            return
        existing = self.writer.select(
            table="inventory_items", columns=["id"], order_by="id DESC", limit=1
        )
        max_id = int(existing[0]["id"]) if existing else 0
        self._next_inventory_item_id = max_id + 1

    def _seed_allocator(self, allocator: IdAllocator, table: str, column: str):
        existing = self.writer.select(
            table=table, columns=[f"max({column}) as max_id"]
        )
        allocator.seed_from_existing(existing[0]["max_id"] if existing else 0)

    def _seed_all_allocators(self):
        self._seed_allocator(self.user_ids, "users", "id")
        self._seed_allocator(self.order_ids, "orders", "order_id")
        self._seed_allocator(self.order_item_ids, "order_items", "id")
        self._seed_allocator(self.event_ids, "events", "id")
        self._ensure_inventory_id_seeded()

    def _assign_runtime_ids(self, order: Order, order_items: list[OrderItem], events: list[Event]):
        order.order_id = self.order_ids.allocate()
        for order_item in order_items:
            order_item.id = self.order_item_ids.allocate()
            order_item.order_id = order.order_id
        for event in events:
            event.id = self.event_ids.allocate()

    def _sanitize_browsing_events(self, events: list[Event]) -> list[Event]:
        import re
        for event in events:
            event.id = self.event_ids.allocate()
            if event.event_type in {"purchase", "cancel", "return"}:
                event.event_type = "product"
            # Ensure all product events have a valid /product/{id} URI
            if event.event_type == "product" and not re.match(r"^/product/\d+$", event.uri):
                product_id = random.choice(list(PRODUCT_MAP.keys()))
                event.uri = f"/product/{product_id}"
        return events

    def _next_inventory_id(self) -> int:
        self._ensure_inventory_id_seeded()
        current = self._next_inventory_item_id
        self._next_inventory_item_id += 1
        return current

    def _new_inventory_row(self, product_id: int, created_at: datetime.datetime) -> dict:
        p = self.product_lookup[product_id]
        return {
            "id": self._next_inventory_id(),
            "product_id": product_id,
            "created_at": created_at,
            "sold_at": None,
            "cost": p["cost"],
            "product_category": p["category"],
            "product_name": p["name"],
            "product_brand": p["brand"],
            "product_retail_price": p["retail_price"],
            "product_department": p["department"],
            "product_sku": p["sku"],
            "product_distribution_center_id": p["distribution_center_id"],
        }

    def _allocate_inventory_item(self, product_id: int, sold_at: datetime.datetime) -> int:
        inv = self.writer.select(
            table="inventory_items",
            where_clause="product_id = :pid and sold_at is null",
            where_params={"pid": product_id},
            order_by="created_at ASC, id ASC",
            limit=1,
            for_update=True,
        )

        if inv:
            selected = dict(inv[0])
        else:
            # Auto-replenish inventory when no unsold unit exists.
            selected = self._new_inventory_row(product_id=product_id, created_at=sold_at)
            self.writer.upsert(
                table="inventory_items", data=[selected], conflict_keys=["id"], commit=False
            )

        selected["sold_at"] = sold_at
        self.writer.upsert(
            table="inventory_items", data=[selected], conflict_keys=["id"], commit=False
        )
        return int(selected["id"])

    def _seed_initial_inventory(self, units_per_product: int):
        if units_per_product <= 0:
            return

        existing_count = self.writer.select(
            table="inventory_items", columns=["count(*) as cnt"]
        )
        if existing_count and int(existing_count[0]["cnt"]) > 0:
            logging.info("inventory_items already populated. Skip initial seeding.")
            return

        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        inventory_rows = []
        for product_id in self.product_lookup.keys():
            for _ in range(units_per_product):
                inventory_rows.append(
                    self._new_inventory_row(product_id=product_id, created_at=now)
                )
        self.writer.upsert(
            table="inventory_items", data=inventory_rows, conflict_keys=["id"]
        )

    async def initialize(self):
        """
        Performs the one-time setup for the simulation.
        This includes creating database tables, loading initial data, and creating Kafka topics.
        """
        try:
            logging.info("Setting up database schema...")
            await asyncio.to_thread(self.writer.create_tables_if_not_exists)

            logging.info("Writing initial data...")
            products = generate_from_csv("products.csv")
            self.product_lookup = self._build_product_lookup(products)

            existing_users = await asyncio.to_thread(
                self.writer.select, table="users", columns=["count(*) as cnt"]
            )
            if int(existing_users[0]["cnt"]) == 0 and self.args.init_num_users > 0:
                init_users = [
                    User.new(
                        country=self.args.country,
                        state=self.args.state,
                        postal_code=self.args.postal_code,
                        fake=self.fake,
                    )
                    for _ in range(self.args.init_num_users)
                ]
                for user in init_users:
                    user.id = self.user_ids.allocate()
                logging.info(f"Writing {len(init_users)} initial users...")
                await asyncio.to_thread(
                    self.writer.upsert,
                    table="users",
                    data=init_users,
                    conflict_keys=["id"],
                )

            # distribution_centers phải được insert TRƯỚC products do FK constraint
            existing_distribution_centers = await asyncio.to_thread(
                self.writer.select,
                table="distribution_centers",
                columns=["count(*) as cnt"],
            )
            if int(existing_distribution_centers[0]["cnt"]) == 0:
                logging.info("Writing initial distribution centers...")
                await asyncio.to_thread(
                    self.writer.upsert,
                    table="distribution_centers",
                    data=generate_from_csv("distribution_centers.csv"),
                    conflict_keys=["id"],
                )

            existing_products = await asyncio.to_thread(
                self.writer.select, table="products", columns=["count(*) as cnt"]
            )
            if int(existing_products[0]["cnt"]) == 0:
                logging.info("Writing initial products...")
                await asyncio.to_thread(
                    self.writer.upsert,
                    table="products",
                    data=products,
                    conflict_keys=["id"],
                )

            logging.info("Writing initial inventory items...")
            await asyncio.to_thread(
                self._seed_initial_inventory, self.args.init_inventory_per_product
            )
            await asyncio.to_thread(self._seed_all_allocators)
            logging.info("Initialization successful.")
            return True
        except (SQLAlchemyError, OperationalError) as e:
            logging.critical(
                f"A fatal error occurred during initial setup. Cannot continue. Error: {e}"
            )
            return False

    def _persist_purchase_bundle(
        self,
        order: Order,
        order_items: list[OrderItem],
        purchase_events: list[Event],
    ):
        with self._db_lock:
            self._persist_purchase_bundle_locked(order, order_items, purchase_events)

    def _persist_purchase_bundle_locked(
        self,
        order: Order,
        order_items: list[OrderItem],
        purchase_events: list[Event],
    ):
        try:
            self.writer.begin()
            for order_item in order_items:
                order_item.inventory_item_id = self._allocate_inventory_item(
                    product_id=int(order_item.product_id), sold_at=order.created_at
                )

            self.writer.upsert(
                table="orders",
                data=[order],
                conflict_keys=["order_id"],
                commit=False,
            )
            self.writer.upsert(
                table="order_items",
                data=order_items,
                conflict_keys=["id"],
                commit=False,
            )
            self.writer.upsert(
                table="events",
                data=purchase_events,
                conflict_keys=["id"],
                commit=False,
            )
            self.writer.commit()
        except Exception:
            self.writer.rollback()
            raise

    async def _simulate_purchases(self):
        """Generates and writes a new purchase transaction, the primary simulation event."""
        # Select a random user
        user_list = await asyncio.to_thread(
            self.writer.select, table="users", order_by="RANDOM()", limit=1
        )
        if not user_list:
            logging.warning(
                "A random user is not retrieved. Skipping a purchase event generation."
            )
            return
        random_user = User.from_dict(user_list[0])

        # Potentially update the user's address
        if (
            self.args.user_update_prob > 0
            and random.random() < self.args.user_update_prob
        ):
            logging.info("Updating a user address...")
            random_user = random_user.update_address(
                country=self.args.country,
                state=self.args.state,
                postal_code=self.args.postal_code,
                fake=self.fake,
            )
            await asyncio.to_thread(self._upsert_users_locked, [random_user])

        # Generate the order and its associated events
        order = Order.new(user=random_user, fake=self.fake)
        order_items = []
        purchase_events = []
        for _ in range(order.num_of_item):
            order_item = OrderItem.new(order=order, fake=self.fake)
            purchase_events.extend(
                Event.new(
                    user=random_user,
                    order_item=order_item,
                    event_category=EventCategory.PURCHASE.value,
                    fake=self.fake,
                )
            )
            order_items.append(order_item)
        self._assign_runtime_ids(order, order_items, purchase_events)

        await asyncio.to_thread(
            self._persist_purchase_bundle,
            order,
            order_items,
            purchase_events,
        )
        if self.clickstream_publisher:
            for event in purchase_events:
                await asyncio.to_thread(self.clickstream_publisher.publish, event)

    def _simulate_order_update(self):
        """Synchronous helper containing the logic for updating an order. To be run in a thread."""
        with self._db_lock:
            return self._simulate_order_update_locked()

    def _simulate_order_update_locked(self):
        updatable_statuses = [
            OrderStatus.PROCESSING.value,
            OrderStatus.SHIPPED.value,
            OrderStatus.COMPLETE.value,
        ]
        random_order_list = self.writer.select(
            table="orders",
            where_clause="status in (:processing_status, :shipped_status, :complete_status)",
            where_params={
                "processing_status": OrderStatus.PROCESSING.value,
                "shipped_status": OrderStatus.SHIPPED.value,
                "complete_status": OrderStatus.COMPLETE.value,
            },
            order_by=(
                "case "
                f"when status = '{OrderStatus.COMPLETE.value}' then 0 "
                f"when status = '{OrderStatus.SHIPPED.value}' then 1 "
                "else 2 end, RANDOM()"
            ),
            limit=1,
        )
        if not random_order_list:
            logging.warning(
                "A random order is not retrieved. Skipping random order event upate."
            )
            return

        random_order = Order.from_dict(random_order_list[0])
        random_user = User.from_dict(
            self.writer.select(
                table="users",
                where_clause="id = :uid",
                where_params={"uid": random_order.user_id},
            )[0]
        )
        random_items = [
            OrderItem.from_dict(d)
            for d in self.writer.select(
                table="order_items",
                where_clause="order_id = :oid",
                where_params={"oid": random_order.order_id},
            )
        ]

        random_order.update_status(fake=self.fake, return_probability=self.args.return_prob)
        updated_items = [
            item.update_status(order=random_order) for item in random_items
        ]

        random_events = []
        for item in updated_items:
            event_category = None
            if item.status == OrderStatus.CANCELLED.value:
                event_category = EventCategory.CANCEL.value
            elif item.status == OrderStatus.RETURNED.value:
                event_category = EventCategory.RETURN.value

            if event_category:
                random_events.extend(
                    Event.new(
                        user=random_user,
                        order_item=item,
                        event_category=event_category,
                        fake=self.fake,
                    )
                )
        for event in random_events:
            event.id = self.event_ids.allocate()

        try:
            self.writer.upsert(
                table="orders",
                data=[random_order],
                conflict_keys=["order_id"],
                commit=False,
            )
            self.writer.upsert(
                table="order_items",
                data=updated_items,
                conflict_keys=["id"],
                commit=False,
            )
            if random_events:
                self.writer.upsert(
                    table="events",
                    data=random_events,
                    conflict_keys=["id"],
                    commit=False,
                )
            self.writer.commit()
        except Exception:
            self.writer.rollback()
            raise
        if random_events and self.clickstream_publisher:
            for event in random_events:
                self.clickstream_publisher.publish(event)

    async def _simulate_side_tasks(self):
        """Runs secondary simulation events based on their respective probabilities."""
        side_tasks = []

        if (
            self.args.user_create_prob > 0
            and random.random() < self.args.user_create_prob
        ):
            logging.info("Creating a new user...")
            new_user = User.new(
                country=self.args.country,
                state=self.args.state,
                postal_code=self.args.postal_code,
                fake=self.fake,
            )
            new_user.id = self.user_ids.allocate()
            side_tasks.append(
                asyncio.to_thread(self._upsert_users_locked, [new_user])
            )

        if (
            self.args.ghost_create_prob > 0
            and random.random() < self.args.ghost_create_prob
        ):
            logging.info("Creating a ghost event...")
            ghost_events = self._sanitize_browsing_events(Event.new(
                user=None,
                order_item=None,
                event_category=EventCategory.GHOST.value,
                fake=self.fake,
            ))
            side_tasks.append(
                asyncio.to_thread(self._upsert_events_locked, ghost_events)
            )

        if (
            self.args.order_update_prob > 0
            and random.random() < self.args.order_update_prob
        ):
            logging.info("Update an order status...")
            for _ in range(max(1, self.args.order_updates_per_iter)):
                side_tasks.append(asyncio.to_thread(self._simulate_order_update))

        if side_tasks:
            await asyncio.gather(*side_tasks)

    def _upsert_users_locked(self, users: list[User]):
        with self._db_lock:
            self.writer.upsert(table="users", data=users, conflict_keys=["id"])

    def _upsert_events_locked(self, events: list[Event]):
        with self._db_lock:
            self.writer.upsert(table="events", data=events, conflict_keys=["id"])

    async def run(self):
        """The main simulation loop, which orchestrates primary and side tasks."""
        current_iteration = 0
        while True:
            if 0 < self.args.max_iter <= current_iteration:
                logging.info(
                    f"Stopping data generation after reaching {current_iteration} iterations."
                )
                break

            try:
                wait_time = random.expovariate(self.args.avg_qps)
                await asyncio.sleep(wait_time)

                await self._simulate_purchases()
                await self._simulate_side_tasks()
            except (SQLAlchemyError, OperationalError) as e:
                self.consecutive_db_errors += 1
                logging.warning(
                    f"A database error occurred. Consecutive error count: {self.consecutive_db_errors}/{self.max_consecutive_errors}. "
                    f"Error: {e}"
                )
                if self.consecutive_db_errors >= self.max_consecutive_errors:
                    logging.critical(
                        f"Exceeded max consecutive DB error limit ({self.max_consecutive_errors}). "
                        "The simulation will now stop."
                    )
                    break
                await asyncio.sleep(5)
            else:
                if self.consecutive_db_errors > 0:
                    logging.info(
                        "Database operation successful. Resetting consecutive error counter."
                    )
                self.consecutive_db_errors = 0
                current_iteration += 1
        logging.info("Simulation loop has finished.")

    async def close(self):
        """Gracefully closes the database connection and publisher."""
        logging.info("Closing database connection...")
        if self.writer.conn and not self.writer.conn.closed:
            await asyncio.to_thread(self.writer.close)
        if self.clickstream_publisher and hasattr(self.clickstream_publisher, 'close'):
            self.clickstream_publisher.close()
        logging.info("Shutdown complete.")


async def run_simulation(args: argparse.Namespace):
    """Orchestrates the creation, initialization, and execution of the simulator."""
    simulator = TheLookECommSimulator(args, Faker())
    try:
        if await simulator.initialize():
            await simulator.run()
    except asyncio.CancelledError:
        logging.warning("Data generation task was cancelled.")
    finally:
        await simulator.close()


def main():
    """
    Parses command-line arguments and starts the data generation simulation.
    """
    # fmt: off
    parser = argparse.ArgumentParser(description="Generate theLook eCommerce data")
    ## --- General Arguments ---
    parser.add_argument("--avg-qps", type=float, default=20.0, help="Average events per second.")
    parser.add_argument("--max-iter", type=int, default=-1, help="Max number of successful iterations. Default -1 for infinite.")
    ## --- User Arguments ---
    parser.add_argument("--init-num-users", type=int, default=1000, help="Initial number of users to create.")
    parser.add_argument("--country", default="*", help="User country.")
    parser.add_argument("--state", default="*", help="User state.")
    parser.add_argument("--postal-code", default="*", help="User postal code.")
    parser.add_argument("--user-create-prob", type=float, default=0.05, help="Probability of generating a new user. Default is 0.05. Set to 0 to disable.")
    parser.add_argument("--user-update-prob", type=float, default=0.1, help="Probability of updating a user address. Default is 0.1. Set to 0 to disable.")
    ## --- Order Arguments ---
    parser.add_argument("--order-update-prob", type=float, default=0.4, help="Probability of updating an order status. Default is 0.4. Set to 0 to disable.")
    parser.add_argument("--order-updates-per-iter", type=int, default=3, help="Number of order status updates to attempt when order-update-prob is triggered.")
    parser.add_argument("--return-prob", type=float, default=0.2, help="Probability that a Complete order moves to Returned on an update.")
    parser.add_argument("--init-inventory-per-product", type=int, default=20, help="Initial inventory units generated per product.")
    ## --- Ghost Event Arguments ---
    parser.add_argument("--ghost-create-prob", type=float, default=0.2, help="Probability of generating a ghost event. Default is 0.2. Set to 0 to disable.")
    ## --- Database Arguments ---
    parser.add_argument("--db-host", default="localhost", help="Database host.")
    parser.add_argument("--db-port", type=int, default=5432, help="Database port.")
    parser.add_argument("--db-user", default="db_user", help="Database user.")
    parser.add_argument("--db-password", default="db_password", help="Database password.")
    parser.add_argument("--db-name", default="fh_dev", help="Database name.")
    parser.add_argument("--db-schema", default="public", help="Database schema.")
    parser.add_argument("--db-batch-size", type=int, default=1000)
    ## --- Kafka Arguments ---
    parser.add_argument("--bootstrap-servers", type=str, default="localhost:9092", help="Bootstrap server addresses.")
    parser.add_argument("--topic-prefix", type=str, default="ecomm", help="Kafka topic prefix.")
    parser.add_argument("--publish-kafka", action="store_true", help="Publish generated events to Kafka.")
    # fmt: on

    args = parser.parse_args()
    logging.info(args)

    try:
        asyncio.run(run_simulation(args))
    except KeyboardInterrupt:
        logging.warning("Data generator stopped by user.")
    except Exception as e:
        logging.critical(f"An unexpected top-level error occurred: {e}", exc_info=True)
    finally:
        logging.info("Application shutdown complete.")


if __name__ == "__main__":
    main()
