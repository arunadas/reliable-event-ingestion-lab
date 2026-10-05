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
_CATALOG_PRICE: dict[str, int] = dict(_CATALOG)

_MUTATION_ACTIONS: tuple[EventType, ...] = (
    "CartItemAdded",
    "CartItemRemoved",
    "CartItemSavedForLater",
    "SavedForLaterItemRemoved",
    "SavedForLaterItemMovedToCart",
)


@dataclass(frozen=True)
class BusinessEvent:
    event_type: EventType
    aggregate_version: int
    payload: dict[str, Any] | None


class _CartState:
    def __init__(self) -> None:
        self.active: dict[str, int] = {}
        self.saved: dict[str, int] = {}

    def active_total(self) -> int:
        return sum(self.active.values())

    def saved_total(self) -> int:
        return sum(self.saved.values())

    def valid_actions(self) -> list[EventType]:
        valid: list[EventType] = ["CartItemAdded"]
        if self.active_total() >= 2:
            valid.append("CartItemRemoved")
            valid.append("CartItemSavedForLater")
        if self.saved_total() >= 1:
            valid.append("SavedForLaterItemRemoved")
            valid.append("SavedForLaterItemMovedToCart")
        return valid

    def add_active(self, product_id: str, quantity: int) -> None:
        self.active[product_id] = self.active.get(product_id, 0) + quantity

    def take_active(self, rng: random.Random) -> tuple[str, int]:
        product_id = rng.choice(list(self.active.keys()))
        qty = self.active[product_id]
        total = self.active_total()
        max_removable = qty if total - qty >= 1 else qty - 1
        quantity = rng.randint(1, max_removable)
        self.active[product_id] -= quantity
        if self.active[product_id] == 0:
            del self.active[product_id]
        return product_id, quantity

    def take_saved(self, rng: random.Random) -> tuple[str, int]:
        product_id = rng.choice(list(self.saved.keys()))
        qty = self.saved[product_id]
        quantity = rng.randint(1, qty)
        self.saved[product_id] -= quantity
        if self.saved[product_id] == 0:
            del self.saved[product_id]
        return product_id, quantity

    def move_to_saved(self, product_id: str, quantity: int) -> None:
        self.saved[product_id] = self.saved.get(product_id, 0) + quantity

    def move_to_active(self, product_id: str, quantity: int) -> None:
        self.add_active(product_id, quantity)


def _random_catalog_item(rng: random.Random) -> tuple[str, int]:
    return rng.choice(_CATALOG)


def generate_cart_business_events(
    rng: random.Random, order_id: int
) -> list[BusinessEvent]:
    events: list[BusinessEvent] = []
    version = 1
    events.append(BusinessEvent("CartCreated", version, None))

    state = _CartState()

    product_id, unit_price_minor = _random_catalog_item(rng)
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
    state.add_active(product_id, quantity_delta)

    num_mutations = rng.randint(0, 5)
    for _ in range(num_mutations):
        action = rng.choice(state.valid_actions())
        version += 1

        if action == "CartItemAdded":
            product_id, unit_price_minor = _random_catalog_item(rng)
            quantity_delta = rng.randint(1, 3)
            state.add_active(product_id, quantity_delta)
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

        elif action == "CartItemRemoved":
            product_id, quantity = state.take_active(rng)
            events.append(
                BusinessEvent(
                    "CartItemRemoved",
                    version,
                    {"product_id": product_id, "quantity": quantity},
                )
            )

        elif action == "CartItemSavedForLater":
            product_id, quantity = state.take_active(rng)
            state.move_to_saved(product_id, quantity)
            events.append(
                BusinessEvent(
                    "CartItemSavedForLater",
                    version,
                    {"product_id": product_id, "quantity": quantity},
                )
            )

        elif action == "SavedForLaterItemRemoved":
            product_id, quantity = state.take_saved(rng)
            events.append(
                BusinessEvent(
                    "SavedForLaterItemRemoved",
                    version,
                    {"product_id": product_id, "quantity": quantity},
                )
            )

        elif action == "SavedForLaterItemMovedToCart":
            product_id, quantity = state.take_saved(rng)
            state.move_to_active(product_id, quantity)
            events.append(
                BusinessEvent(
                    "SavedForLaterItemMovedToCart",
                    version,
                    {"product_id": product_id, "quantity": quantity},
                )
            )

    total_amount_minor = sum(
        quantity * _CATALOG_PRICE[product_id]
        for product_id, quantity in state.active.items()
    )
    item_count = state.active_total()
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
