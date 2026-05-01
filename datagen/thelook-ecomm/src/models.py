import datetime
import dataclasses
import random
import logging
import inspect
from enum import Enum
from collections import OrderedDict
from typing import List, Optional, Self

from faker import Faker

from src.utils import get_location, get_product_map

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
)


PRODUCT_MAP = get_product_map("products.csv")


def get_additional_ddls(schema: str):
    return {
        "distribution_centers": inspect.cleandoc(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.distribution_centers (
                id BIGINT PRIMARY KEY,
                name TEXT,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION
            );"""
        ),
        "products": inspect.cleandoc(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.products (
                id BIGINT PRIMARY KEY,
                cost DOUBLE PRECISION,
                category TEXT,
                name TEXT,
                brand TEXT,
                retail_price DOUBLE PRECISION,
                department TEXT,
                sku TEXT,
                distribution_center_id BIGINT,
                CONSTRAINT chk_products_non_negative_prices
                    CHECK (cost >= 0 AND retail_price >= 0),
                CONSTRAINT fk_products_distribution_center
                    FOREIGN KEY (distribution_center_id)
                    REFERENCES {schema}.distribution_centers (id)
            );"""
        ),
        "inventory_items": inspect.cleandoc(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.inventory_items (
                id BIGINT PRIMARY KEY,
                product_id BIGINT,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                sold_at TIMESTAMP WITHOUT TIME ZONE,
                cost DOUBLE PRECISION,
                product_category TEXT,
                product_name TEXT,
                product_brand TEXT,
                product_retail_price DOUBLE PRECISION,
                product_department TEXT,
                product_sku TEXT,
                product_distribution_center_id BIGINT,
                CONSTRAINT chk_inventory_cost_non_negative
                    CHECK (cost >= 0),
                CONSTRAINT chk_inventory_sold_after_created
                    CHECK (sold_at IS NULL OR sold_at >= created_at),
                CONSTRAINT fk_inventory_product
                    FOREIGN KEY (product_id)
                    REFERENCES {schema}.products (id),
                CONSTRAINT fk_inventory_distribution_center
                    FOREIGN KEY (product_distribution_center_id)
                    REFERENCES {schema}.distribution_centers (id)
            );"""
        ),
        "heartbeat": inspect.cleandoc(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.heartbeat (
                id INT PRIMARY KEY,
                ts TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            );
        """
        ),
    }


class OrderStatus(Enum):
    PROCESSING = "Processing"
    SHIPPED = "Shipped"
    COMPLETE = "Complete"
    CANCELLED = "Cancelled"
    RETURNED = "Returned"


class EventCategory(Enum):
    PURCHASE = "purchase"
    GHOST = "ghost"
    CANCEL = "cancel"
    RETURN = "return"


class ModelMixin:
    @classmethod
    def from_dict(cls, data: dict):
        valid_keys = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    @classmethod
    def from_rows(cls, rows: List[dict]):
        return [cls.from_dict(row) for row in rows]


@dataclasses.dataclass
class User(ModelMixin):
    id: int
    first_name: str
    last_name: str
    email: str
    age: int
    gender: str
    street_address: str
    postal_code: str
    city: str
    state: str
    country: str
    latitude: float
    longitude: float
    traffic_source: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @classmethod
    def new(
        cls,
        *,
        country: str = "*",
        state: str = "*",
        postal_code: str = "*",
        fake: Faker,
    ) -> Self:
        gender = fake.random_element(elements=("M", "F"))
        first_name = (
            fake.first_name_male() if gender == "M" else fake.first_name_female()
        )
        last_name = fake.last_name_nonbinary()
        location = get_location(country=country, state=state, postal_code=postal_code)
        traffic_source = fake.random_choices(
            elements=OrderedDict(
                zip(
                    ["Organic", "Facebook", "Search", "Email", "Display"],
                    [0.15, 0.06, 0.7, 0.05, 0.04],
                )
            ),
            length=1,
        )[0]
        return cls(
            id=random.randint(100000, 999999999),  # Generate random BIGINT ID
            first_name=first_name,
            last_name=last_name,
            email=f"{first_name.lower()}.{last_name.lower()}@{fake.safe_domain_name()}",
            age=random.randrange(12, 71),
            gender=gender,
            street_address=fake.street_address(),
            postal_code=location["postal_code"],
            city=location["city"],
            state=location["state"],
            country=location["country"],
            latitude=location["latitude"],
            longitude=location["longitude"],
            traffic_source=traffic_source,
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

    def update_address(
        self,
        *,
        country: str = "*",
        state: str = "*",
        postal_code: str = "*",
        fake: Faker,
    ) -> Self:
        current_data = dataclasses.asdict(self)
        updated_fields = {
            "street_address": fake.street_address(),
            "updated_at": datetime.datetime.now(),
            **get_location(country=country, state=state, postal_code=postal_code),
        }
        merged_data = {**current_data, **updated_fields}
        return self.from_dict(merged_data)

    def __str__(self):
        return f"User(id={self.id}, name='{self.first_name} {self.last_name}', location='{self.country}|{self.state}|{self.city}', source='{self.traffic_source}')"

    @staticmethod
    def ddl(schema: str):
        return inspect.cleandoc(
            f"""
        CREATE TABLE IF NOT EXISTS {schema}.users (
            id              BIGINT PRIMARY KEY,
            first_name      TEXT,
            last_name       TEXT,
            email           TEXT,
            age             INT,
            gender          TEXT,
            street_address  TEXT,
            postal_code     TEXT,
            city            TEXT,
            state           TEXT,
            country         TEXT,
            latitude        DOUBLE PRECISION,
            longitude       DOUBLE PRECISION,
            traffic_source  TEXT,
            created_at      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP WITHOUT TIME ZONE,
            CONSTRAINT chk_users_age_valid
                CHECK (age BETWEEN 12 AND 120),
            CONSTRAINT chk_users_updated_after_created
                CHECK (updated_at >= created_at)
        );
        """
        )


@dataclasses.dataclass
class Order(ModelMixin):
    order_id: int
    user_id: int
    status: str
    gender: str
    num_of_item: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    returned_at: Optional[datetime.datetime]
    shipped_at: Optional[datetime.datetime]
    delivered_at: Optional[datetime.datetime]

    @classmethod
    def new(cls, user: User, fake: Faker) -> Self:
        return cls(
            order_id=random.randint(100000, 999999999),  # Generate random BIGINT ID
            user_id=user.id,
            status=OrderStatus.PROCESSING.value,
            gender=user.gender,
            num_of_item=fake.random_choices(
                OrderedDict(zip([1, 2, 3, 4], [0.7, 0.2, 0.05, 0.05])),
                1,
            )[0],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
            returned_at=None,
            shipped_at=None,
            delivered_at=None,
        )

    def __str__(self):
        return f"Order(order_id={self.order_id}, user_id={self.user_id}, status='{self.status}', items={self.num_of_item})"

    def update_status(self, fake: Faker, return_probability: float = 0.02) -> Self:
        status_changed = False

        if self.status == OrderStatus.PROCESSING.value:
            # Transition from Processing to either Shipped or Cancelled
            new_status = fake.random_element(
                elements=OrderedDict(
                    [
                        (OrderStatus.SHIPPED.value, 0.95),
                        (OrderStatus.CANCELLED.value, 0.05),
                    ]
                )
            )
            if new_status == OrderStatus.SHIPPED.value:
                self.status = OrderStatus.SHIPPED.value
                self.shipped_at = datetime.datetime.now()
            else:
                self.status = OrderStatus.CANCELLED.value
                # Note: CSV data doesn't have cancelled_at field
            status_changed = True

        elif self.status == OrderStatus.SHIPPED.value:
            # Deterministic transition from Shipped to Complete.
            self.status = OrderStatus.COMPLETE.value
            self.delivered_at = datetime.datetime.now()
            status_changed = True

        elif self.status == OrderStatus.COMPLETE.value:
            # Probabilistic transition from Complete to Returned
            if random.random() < return_probability:
                self.status = OrderStatus.RETURNED.value
                self.returned_at = datetime.datetime.now()
                status_changed = True

        if status_changed:
            self.updated_at = datetime.datetime.now()

        return self

    @staticmethod
    def ddl(schema: str):
        return inspect.cleandoc(
            f"""
        CREATE TABLE IF NOT EXISTS {schema}.orders (
            order_id        BIGINT PRIMARY KEY,
            user_id         BIGINT,
            status          TEXT,
            gender          TEXT,
            created_at      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP WITHOUT TIME ZONE,
            returned_at     TIMESTAMP WITHOUT TIME ZONE,
            shipped_at      TIMESTAMP WITHOUT TIME ZONE,
            delivered_at    TIMESTAMP WITHOUT TIME ZONE,
            num_of_item     INT,
            CONSTRAINT fk_orders_user
                FOREIGN KEY (user_id)
                REFERENCES {schema}.users (id),
            CONSTRAINT chk_orders_num_items_positive
                CHECK (num_of_item >= 1),
            CONSTRAINT chk_orders_valid_status
                CHECK (status IN ('Processing', 'Shipped', 'Complete', 'Returned', 'Cancelled')),
            CONSTRAINT chk_orders_updated_after_created
                CHECK (updated_at >= created_at),
            CONSTRAINT chk_orders_shipped_after_created
                CHECK (shipped_at IS NULL OR shipped_at >= created_at),
            CONSTRAINT chk_orders_delivered_after_shipped
                CHECK (delivered_at IS NULL OR shipped_at IS NULL OR delivered_at >= shipped_at),
            CONSTRAINT chk_orders_returned_after_delivered
                CHECK (returned_at IS NULL OR (delivered_at IS NOT NULL AND returned_at >= delivered_at))
        );
        """
        )


@dataclasses.dataclass
class OrderItem(ModelMixin):
    id: int
    order_id: int
    user_id: int
    product_id: int
    inventory_item_id: Optional[int]
    status: str
    sale_price: float
    created_at: datetime.datetime
    updated_at: datetime.datetime
    returned_at: Optional[datetime.datetime]
    shipped_at: Optional[datetime.datetime]
    delivered_at: Optional[datetime.datetime]

    @classmethod
    def new(cls, order: Order, fake: Faker) -> Self:
        product_id = fake.random_element(PRODUCT_MAP.keys())
        base_price = float(PRODUCT_MAP[product_id]["retail_price"])
        sale_price = round(base_price * random.uniform(0.85, 1.0), 2)
        return cls(
            id=random.randint(100000, 999999999),  # Generate random BIGINT ID
            order_id=order.order_id,
            user_id=order.user_id,
            product_id=product_id,
            inventory_item_id=None,  # Will be populated later if needed
            status=order.status,
            sale_price=sale_price,
            created_at=order.created_at,
            updated_at=order.updated_at,
            shipped_at=order.shipped_at,
            delivered_at=order.delivered_at,
            returned_at=order.returned_at,
        )

    def __str__(self):
        return f"OrderItem(id={self.id}, order_id={self.order_id}, product_id={self.product_id}, status={self.status})"

    def update_status(self, order: Order) -> Self:
        self.status = order.status
        self.updated_at = order.updated_at
        self.shipped_at = order.shipped_at
        self.delivered_at = order.delivered_at
        self.returned_at = order.returned_at
        return self

    @staticmethod
    def ddl(schema: str):
        return inspect.cleandoc(
            f"""
        CREATE TABLE IF NOT EXISTS {schema}.order_items (
            id                  BIGINT PRIMARY KEY,
            order_id            BIGINT,
            user_id             BIGINT,
            product_id          BIGINT,
            inventory_item_id   BIGINT,
            status              TEXT,
            created_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMP WITHOUT TIME ZONE,
            shipped_at          TIMESTAMP WITHOUT TIME ZONE,
            delivered_at        TIMESTAMP WITHOUT TIME ZONE,
            returned_at         TIMESTAMP WITHOUT TIME ZONE,
            sale_price          DOUBLE PRECISION,
            CONSTRAINT fk_order_items_order
                FOREIGN KEY (order_id)
                REFERENCES {schema}.orders (order_id),
            CONSTRAINT fk_order_items_user
                FOREIGN KEY (user_id)
                REFERENCES {schema}.users (id),
            CONSTRAINT fk_order_items_product
                FOREIGN KEY (product_id)
                REFERENCES {schema}.products (id),
            CONSTRAINT fk_order_items_inventory
                FOREIGN KEY (inventory_item_id)
                REFERENCES {schema}.inventory_items (id),
            CONSTRAINT chk_order_items_sale_price_non_negative
                CHECK (sale_price >= 0),
            CONSTRAINT chk_order_items_updated_after_created
                CHECK (updated_at >= created_at),
            CONSTRAINT chk_order_items_shipped_after_created
                CHECK (shipped_at IS NULL OR shipped_at >= created_at),
            CONSTRAINT chk_order_items_delivered_after_shipped
                CHECK (delivered_at IS NULL OR shipped_at IS NULL OR delivered_at >= shipped_at),
            CONSTRAINT chk_order_items_returned_after_delivered
                CHECK (returned_at IS NULL OR (delivered_at IS NOT NULL AND returned_at >= delivered_at))
        );
        """
        )


@dataclasses.dataclass
class Event(ModelMixin):
    id: int
    user_id: Optional[int]
    sequence_number: int
    session_id: str
    ip_address: str
    city: str
    state: str
    postal_code: str
    browser: str
    traffic_source: str
    uri: str
    event_type: str
    created_at: datetime.datetime

    @staticmethod
    def new(
        user: Optional[User],
        order_item: Optional[OrderItem],
        event_category: str,
        fake: Faker,
    ) -> List[Self]:
        if event_category in ["purchase", "return", "cancel"]:
            assert order_item is not None
            user_id = user.id
            city = user.city
            state = user.state
            postal_code = user.postal_code
            product_id = order_item.product_id
            order_item_id = order_item.id
            if event_category == "purchase":
                created_at = order_item.created_at
                event_types = list(
                    set(fake.random_choices(["home", "department", "product"], 3))
                ) + ["cart", "purchase"]
            else:
                created_at = datetime.datetime.now()
                event_types = ["product", "cart", event_category]
        elif event_category == "ghost":
            location = (
                {
                    "city": user.city,
                    "state": user.state,
                    "postal_code": user.postal_code,
                }
                if user is not None
                else get_location()
            )
            user_id = user.id if user is not None else None
            city = location["city"]
            state = location["state"]
            postal_code = location["postal_code"]
            product_id = fake.random_element(PRODUCT_MAP.keys())
            order_item_id = None
            created_at = datetime.datetime.now()
            event_types = fake.random_elements(
                [
                    "home",
                    "department",
                    "category",
                    "product",
                    "cancel",
                    "purchase",
                    "return",
                ],
                length=fake.random_element(range(3, 7)),
            )
        else:
            raise RuntimeError(
                f"Unsupported event category: '{event_category}'. Allowed categories are: {', '.join(sorted(['purchase', 'cancel', 'ghost']))}."
            )
        session_id = fake.uuid4()
        ip_address = fake.ipv4()
        browser = fake.random_choices(
            OrderedDict(
                zip(
                    ["IE", "Edge", "Chrome", "Safari", "Firefox", "Other"],
                    [0.05, 0.1, 0.45, 0.2, 0.15, 0.05],
                )
            ),
            1,
        )[0]
        traffic_source = fake.random_choices(
            OrderedDict(
                zip(
                    ["Email", "Adwords", "Organic", "YouTube", "Facebook"],
                    [0.45, 0.3, 0.05, 0.1, 0.1],
                )
            ),
            1,
        )[0]
        events = [
            Event(
                id=random.randint(100000, 999999999),  # Generate random BIGINT ID
                user_id=user_id,
                sequence_number=idx + 1,
                session_id=session_id,
                ip_address=ip_address,
                city=city,
                state=state,
                postal_code=postal_code,
                browser=browser,
                traffic_source=traffic_source,
                uri=Event._generate_uri(event_type, order_item_id, product_id),
                event_type=event_type,
                created_at=created_at
                - Event._calculate_event_delay(len(event_types), idx, fake),
            )
            for idx, event_type in enumerate(event_types)
        ]
        return events

    def __str__(self):
        return f"Event(id={self.id}, is_ghost={self.user_id is None}, sequence_number={self.sequence_number}, event_type={self.event_type}, created_at={self.created_at})"

    @staticmethod
    def _generate_uri(event_type: str, item_id: Optional[str], product_id: int) -> str:
        if event_type == "product":
            return f"/{event_type}/{product_id}"
        elif event_type == "department":
            department = PRODUCT_MAP[product_id]["department"]
            category = PRODUCT_MAP[product_id]["category"]
            return f"/{event_type}/{department}/category/{category}"
        elif event_type in ["cancel", "return"]:
            return (
                f"/{event_type}/item/{item_id}"
                if item_id is not None
                else f"/{event_type}"
            )
        else:
            return f"/{event_type}"

    @staticmethod
    def _calculate_event_delay(
        num_events: int, idx: int, fake: Faker
    ) -> datetime.timedelta:
        if num_events == idx + 1:
            return datetime.timedelta(seconds=0)
        base_delay = (num_events - idx + 1) * 20
        jitter = fake.random_element(range(1, 10))
        return datetime.timedelta(seconds=base_delay + jitter)

    @staticmethod
    def ddl(schema: str):
        return inspect.cleandoc(
            f"""
        CREATE TABLE IF NOT EXISTS {schema}.events (
            id                  BIGINT PRIMARY KEY,
            user_id             BIGINT,
            sequence_number     INT,
            session_id          TEXT,
            ip_address          TEXT,
            city                TEXT,
            state               TEXT,
            postal_code         TEXT,
            browser             TEXT,
            traffic_source      TEXT,
            uri                 TEXT,
            event_type          TEXT,
            created_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_events_user
                FOREIGN KEY (user_id)
                REFERENCES {schema}.users (id),
            CONSTRAINT chk_events_sequence_positive
                CHECK (sequence_number >= 1),
            CONSTRAINT chk_events_type_valid
                CHECK (event_type IN ('home', 'department', 'category', 'product', 'cart', 'purchase', 'cancel', 'return'))
        );
        """
        )
