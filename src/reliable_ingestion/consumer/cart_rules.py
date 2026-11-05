from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from reliable_ingestion.consumer.envelope import (
    INVALID_PAYLOAD,
    INVALID_TRANSITION,
    VERSION_CONFLICT,
    VERSION_GAP,
    Rejection,
)

OPEN = "open"
PURCHASED = "purchased"


@dataclass(frozen=True)
class Item:
    quantity: int
    unit_price_minor: int
    currency: str


@dataclass(frozen=True)
class Purchase:
    order_id: int
    item_count: int
    total_amount_minor: int
    currency: str


@dataclass(frozen=True)
class CartState:
    version: int
    business_status: str = OPEN
    active: dict[str, Item] = field(default_factory=dict)
    saved: dict[str, Item] = field(default_factory=dict)
    purchase: Purchase | None = None


def _take(
    collection: dict[str, Item], product_id: str, quantity: int, name: str
) -> tuple[dict[str, Item], Item] | Rejection:
    """Remove ``quantity`` of a product, dropping the entry when it hits zero."""
    item = collection.get(product_id)
    if item is None:
        return Rejection(INVALID_TRANSITION, f"product {product_id!r} is not {name}")
    if quantity > item.quantity:
        return Rejection(
            INVALID_TRANSITION,
            f"quantity {quantity} exceeds {name} quantity {item.quantity}",
        )
    remaining = dict(collection)
    if quantity == item.quantity:
        del remaining[product_id]
    else:
        remaining[product_id] = Item(
            item.quantity - quantity, item.unit_price_minor, item.currency
        )
    return remaining, item


def _put(
    collection: dict[str, Item], product_id: str, quantity: int, like: Item
) -> dict[str, Item]:
    updated = dict(collection)
    existing = updated.get(product_id)
    held = existing.quantity if existing is not None else 0
    updated[product_id] = Item(held + quantity, like.unit_price_minor, like.currency)
    return updated


def evaluate(
    cart: CartState | None,
    event_type: str,
    version: int,
    payload: dict[str, Any] | None,
) -> CartState | Rejection:
    """Validate a structurally valid, not-yet-applied event against the cart.

    Returns the next cart state, or the rejection that applies. The caller
    has already ruled out an applied duplicate of this event.
    """
    if cart is None:
        if version > 1:
            return Rejection(
                VERSION_GAP, f"version {version} received before the cart exists"
            )
        if event_type != "CartCreated":
            return Rejection(
                INVALID_TRANSITION, "a cart must begin with CartCreated at version 1"
            )
        return CartState(version=1)

    if version <= cart.version:
        return Rejection(
            VERSION_CONFLICT,
            f"version {version} is already applied by a different event "
            f"(stored version {cart.version})",
        )
    if version > cart.version + 1:
        return Rejection(
            VERSION_GAP, f"version {version} received at stored version {cart.version}"
        )
    if event_type == "CartCreated":
        return Rejection(INVALID_TRANSITION, "cart already exists")
    if cart.business_status == PURCHASED:
        return Rejection(INVALID_TRANSITION, "cart is already purchased")

    assert payload is not None
    active, saved = cart.active, cart.saved

    if event_type == "CartPurchased":
        if not active:
            return Rejection(INVALID_TRANSITION, "purchase requires an active item")
        item_count = sum(item.quantity for item in active.values())
        total = sum(item.quantity * item.unit_price_minor for item in active.values())
        currencies = {item.currency for item in active.values()}
        if payload["item_count"] != item_count:
            return Rejection(
                INVALID_PAYLOAD,
                f"item_count {payload['item_count']} does not match {item_count}",
            )
        if payload["total_amount_minor"] != total:
            return Rejection(
                INVALID_PAYLOAD,
                f"total_amount_minor {payload['total_amount_minor']} "
                f"does not match {total}",
            )
        if currencies != {payload["currency"]}:
            return Rejection(INVALID_PAYLOAD, "currency does not match the active cart")
        return CartState(
            version,
            PURCHASED,
            active,
            saved,
            Purchase(payload["order_id"], item_count, total, payload["currency"]),
        )

    product_id = payload["product_id"]

    if event_type == "CartItemAdded":
        added = Item(
            payload["quantity_delta"], payload["unit_price_minor"], payload["currency"]
        )
        held = active.get(product_id) or saved.get(product_id)
        if held is not None and (
            held.unit_price_minor != added.unit_price_minor
            or held.currency != added.currency
        ):
            return Rejection(
                INVALID_PAYLOAD,
                f"product {product_id!r} is already in the cart at a different "
                "unit price or currency",
            )
        return CartState(
            version, OPEN, _put(active, product_id, added.quantity, added), saved
        )

    quantity = payload["quantity"]
    if event_type == "CartItemRemoved":
        taken = _take(active, product_id, quantity, "active")
        if isinstance(taken, Rejection):
            return taken
        return CartState(version, OPEN, taken[0], saved)
    if event_type == "CartItemSavedForLater":
        taken = _take(active, product_id, quantity, "active")
        if isinstance(taken, Rejection):
            return taken
        return CartState(
            version, OPEN, taken[0], _put(saved, product_id, quantity, taken[1])
        )
    if event_type == "SavedForLaterItemRemoved":
        taken = _take(saved, product_id, quantity, "saved for later")
        if isinstance(taken, Rejection):
            return taken
        return CartState(version, OPEN, active, taken[0])
    if event_type == "SavedForLaterItemMovedToCart":
        taken = _take(saved, product_id, quantity, "saved for later")
        if isinstance(taken, Rejection):
            return taken
        return CartState(
            version, OPEN, _put(active, product_id, quantity, taken[1]), taken[0]
        )
    raise ValueError(f"unsupported event type {event_type!r}")
