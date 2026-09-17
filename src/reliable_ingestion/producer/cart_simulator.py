from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from reliable_ingestion.producer.events import EventType

CURRENCY: str = "USD"

_CATALOG: list[tuple[str, int]] = [
    ("sku-100", 999),
    ("sku-200", 1599),
    ("sku-300", 2499),
    ("sku-400", 799),
    ("sku-500", 4999),
]


@dataclass(frozen=True)
class BusinessEvent:
    event_type: EventType
    aggregate_version: int
    payload: dict[str, Any] | None


@dataclass
class _ActiveItem:
    unit_price_minor: int
    quantity: int


def generate_cart_business_events(
    rng: random.Random, order_id: int
) -> list[BusinessEvent]:
    events: list[BusinessEvent] = []
    version = 1
    events.append(BusinessEvent("CartCreated", version, None))

    active: dict[str, _ActiveItem] = {}

    num_adds = rng.randint(1, 3)
    for _ in range(num_adds):
        product_id, unit_price_minor = rng.choice(_CATALOG)
        quantity_delta = rng.randint(1, 3)
        version += 1
        events.append(
            BusinessEvent(
                "CartItemAdded",
                version,
                {
                    "product_id": product_id,
                    "quantity_delta": quantity_delta,
                    "unit_price_minor": unit_price_minor,
                    "currency": CURRENCY,
                },
            )
        )
        item = active.get(product_id)
        if item is None:
            active[product_id] = _ActiveItem(unit_price_minor, quantity_delta)
        else:
            item.quantity += quantity_delta

    num_saves = rng.randint(0, 2)
    saveable = [pid for pid, item in active.items() if item.quantity > 0]
    for _ in range(min(num_saves, len(saveable))):
        product_id = rng.choice(saveable)
        item = active[product_id]
        quantity = rng.randint(1, item.quantity)
        item.quantity -= quantity
        version += 1
        events.append(
            BusinessEvent(
                "CartItemSavedForLater",
                version,
                {"product_id": product_id, "quantity": quantity},
            )
        )
        if item.quantity == 0:
            saveable.remove(product_id)

    total_amount_minor = sum(
        item.quantity * item.unit_price_minor for item in active.values()
    )
    item_count = sum(item.quantity for item in active.values())
    version += 1
    events.append(
        BusinessEvent(
            "CartPurchased",
            version,
            {
                "order_id": order_id,
                "total_amount_minor": total_amount_minor,
                "currency": CURRENCY,
                "item_count": item_count,
            },
        )
    )
    return events
