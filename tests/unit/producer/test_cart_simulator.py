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


def test_second_event_is_the_single_initial_item_added():
    for seed in range(100):
        events = generate_cart_business_events(random.Random(seed), order_id=seed)
        assert events[1].event_type == "CartItemAdded"


def test_mutation_count_is_between_zero_and_five():
    for seed in range(200):
        events = generate_cart_business_events(random.Random(seed), order_id=seed)
        # events = CartCreated, initial CartItemAdded, mutations..., CartPurchased
        mutation_count = len(events) - 3
        assert 0 <= mutation_count <= 5


def test_full_state_invariants_hold_across_all_mutation_types():
    for seed in range(300):
        events = generate_cart_business_events(random.Random(seed), order_id=seed)
        active: dict[str, int] = {}
        saved: dict[str, int] = {}
        prices: dict[str, int] = {}

        for event in events:
            payload = event.payload

            if event.event_type == "CartCreated":
                assert payload is None

            elif event.event_type == "CartItemAdded":
                pid = payload["product_id"]
                qty = payload["quantity_delta"]
                assert qty > 0
                assert payload["currency"] == CURRENCY
                prices.setdefault(pid, payload["unit_price_minor"])
                assert prices[pid] == payload["unit_price_minor"]
                active[pid] = active.get(pid, 0) + qty

            elif event.event_type == "CartItemRemoved":
                pid = payload["product_id"]
                qty = payload["quantity"]
                assert qty > 0
                assert pid in active, "removed product was never active"
                assert qty <= active[pid]
                active[pid] -= qty
                if active[pid] == 0:
                    del active[pid]
                assert sum(active.values()) >= 1, "removal emptied the active cart"

            elif event.event_type == "CartItemSavedForLater":
                pid = payload["product_id"]
                qty = payload["quantity"]
                assert qty > 0
                assert pid in active, "saved product was never active"
                assert qty <= active[pid]
                active[pid] -= qty
                if active[pid] == 0:
                    del active[pid]
                assert sum(active.values()) >= 1, "save emptied the active cart"
                saved[pid] = saved.get(pid, 0) + qty

            elif event.event_type == "SavedForLaterItemRemoved":
                pid = payload["product_id"]
                qty = payload["quantity"]
                assert qty > 0
                assert pid in saved, "removed item was never saved for later"
                assert qty <= saved[pid]
                saved[pid] -= qty
                if saved[pid] == 0:
                    del saved[pid]

            elif event.event_type == "SavedForLaterItemMovedToCart":
                pid = payload["product_id"]
                qty = payload["quantity"]
                assert qty > 0
                assert pid in saved, "moved item was never saved for later"
                assert qty <= saved[pid]
                saved[pid] -= qty
                if saved[pid] == 0:
                    del saved[pid]
                active[pid] = active.get(pid, 0) + qty

            elif event.event_type == "CartPurchased":
                expected_total = sum(active[pid] * prices[pid] for pid in active)
                expected_count = sum(active.values())
                assert expected_count >= 1, "purchase requires an active item"
                assert payload["total_amount_minor"] == expected_total
                assert payload["item_count"] == expected_count
                assert payload["currency"] == CURRENCY
                assert isinstance(payload["total_amount_minor"], int)


def test_every_new_mutation_type_is_generated_across_seed_range():
    seen: set[str] = set()
    for seed in range(300):
        events = generate_cart_business_events(random.Random(seed), order_id=seed)
        seen.update(event.event_type for event in events)

    for event_type in (
        "CartItemRemoved",
        "SavedForLaterItemRemoved",
        "SavedForLaterItemMovedToCart",
    ):
        assert event_type in seen, f"{event_type} was never generated"


def test_moved_back_item_keeps_price_and_currency_in_purchase_total():
    # Seed 67 adds 1 x sku-100 and 2 x sku-400, saves both sku-400 units,
    # then moves exactly one of them back before purchasing.
    events = generate_cart_business_events(random.Random(67), order_id=67)
    assert [(e.event_type, e.payload) for e in events] == [
        ("CartCreated", None),
        (
            "CartItemAdded",
            {
                "product_id": "sku-100",
                "quantity_delta": 1,
                "unit_price_minor": 999,
                "currency": CURRENCY,
            },
        ),
        (
            "CartItemAdded",
            {
                "product_id": "sku-400",
                "quantity_delta": 2,
                "unit_price_minor": 799,
                "currency": CURRENCY,
            },
        ),
        ("CartItemSavedForLater", {"product_id": "sku-400", "quantity": 2}),
        ("SavedForLaterItemMovedToCart", {"product_id": "sku-400", "quantity": 1}),
        (
            "CartPurchased",
            {
                "order_id": 67,
                # 1 x 999 (sku-100) + 1 x 799 (moved-back sku-400 at its
                # original price); the sku-400 unit still saved is excluded.
                "total_amount_minor": 999 + 799,
                "currency": CURRENCY,
                "item_count": 2,
            },
        ),
    ]


def test_purchase_payload_uses_given_order_id():
    events = generate_cart_business_events(random.Random(5), order_id=42)
    purchased = next(e for e in events if e.event_type == "CartPurchased")
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
