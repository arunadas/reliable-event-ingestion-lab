import random

from reliable_ingestion.producer.cart_simulator import (
    CURRENCY,
    generate_cart_business_events,
)


def test_first_event_is_cart_created_at_version_1():
    events = generate_cart_business_events(random.Random(1), order_id=0)
    assert events[0].event_type == "CartCreated"
    assert events[0].aggregate_version == 1
    assert events[0].payload is None


def test_last_event_is_cart_purchased():
    events = generate_cart_business_events(random.Random(1), order_id=0)
    assert events[-1].event_type == "CartPurchased"


def test_versions_increase_by_one_without_gaps_across_many_seeds():
    for seed in range(100):
        events = generate_cart_business_events(random.Random(seed), order_id=seed)
        versions = [e.aggregate_version for e in events]
        assert versions == list(range(1, len(versions) + 1))


def test_at_least_one_item_added_event_across_many_seeds():
    for seed in range(100):
        events = generate_cart_business_events(random.Random(seed), order_id=seed)
        added = [e for e in events if e.event_type == "CartItemAdded"]
        assert len(added) >= 1


def test_saved_for_later_never_exceeds_previously_active_quantity():
    for seed in range(200):
        events = generate_cart_business_events(random.Random(seed), order_id=seed)
        active_qty: dict[str, int] = {}
        for event in events:
            if event.event_type == "CartItemAdded":
                pid = event.payload["product_id"]
                active_qty[pid] = (
                    active_qty.get(pid, 0) + event.payload["quantity_delta"]
                )
            elif event.event_type == "CartItemSavedForLater":
                pid = event.payload["product_id"]
                qty = event.payload["quantity"]
                assert pid in active_qty, "saved product was never added"
                assert qty <= active_qty[pid]
                active_qty[pid] -= qty


def test_purchase_total_excludes_saved_for_later_quantity():
    for seed in range(200):
        events = generate_cart_business_events(random.Random(seed), order_id=seed)
        active: dict[str, dict] = {}
        for event in events:
            if event.event_type == "CartItemAdded":
                pid = event.payload["product_id"]
                item = active.setdefault(
                    pid,
                    {
                        "quantity": 0,
                        "unit_price_minor": event.payload["unit_price_minor"],
                    },
                )
                item["quantity"] += event.payload["quantity_delta"]
            elif event.event_type == "CartItemSavedForLater":
                active[event.payload["product_id"]]["quantity"] -= event.payload[
                    "quantity"
                ]
            elif event.event_type == "CartPurchased":
                expected_total = sum(
                    item["quantity"] * item["unit_price_minor"]
                    for item in active.values()
                )
                expected_count = sum(item["quantity"] for item in active.values())
                assert event.payload["total_amount_minor"] == expected_total
                assert event.payload["item_count"] == expected_count
                assert event.payload["currency"] == CURRENCY
                assert isinstance(event.payload["total_amount_minor"], int)


def test_purchase_payload_uses_given_order_id():
    events = generate_cart_business_events(random.Random(5), order_id=42)
    purchased = [e for e in events if e.event_type == "CartPurchased"][0]
    assert purchased.payload["order_id"] == 42


def test_same_seed_produces_identical_event_sequence():
    first = generate_cart_business_events(random.Random(7), order_id=0)
    second = generate_cart_business_events(random.Random(7), order_id=0)
    assert first == second


def test_money_fields_are_always_int():
    for seed in range(50):
        events = generate_cart_business_events(random.Random(seed), order_id=seed)
        for event in events:
            if event.payload is None:
                continue
            for key in ("unit_price_minor", "total_amount_minor"):
                if key in event.payload:
                    assert isinstance(event.payload[key], int)
