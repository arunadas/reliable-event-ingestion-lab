import random

import pytest

from reliable_ingestion.consumer.cart_rules import (
    CartState,
    Item,
    Purchase,
    evaluate,
)
from reliable_ingestion.consumer.envelope import Rejection
from reliable_ingestion.producer.cart_simulator import generate_cart_business_events


def add(product="sku-1", qty=2, price=500, currency="USD"):
    return {
        "product_id": product,
        "quantity_delta": qty,
        "unit_price_minor": price,
        "currency": currency,
    }


def qty(product="sku-1", quantity=1):
    return {"product_id": product, "quantity": quantity}


def purchase(item_count, total, currency="USD", order_id=1):
    return {
        "order_id": order_id,
        "total_amount_minor": total,
        "currency": currency,
        "item_count": item_count,
    }


def cart(version=2, active=None, saved=None, status="open"):
    return CartState(version, status, active or {}, saved or {})


def reason(result):
    assert isinstance(result, Rejection), result
    return result.reason


def test_new_cart_begins_with_cart_created_at_version_one():
    assert evaluate(None, "CartCreated", 1, None) == CartState(version=1)


def test_first_event_must_be_cart_created():
    assert reason(evaluate(None, "CartItemAdded", 1, add())) == "invalid_transition"


def test_event_before_cart_exists_is_a_version_gap():
    assert reason(evaluate(None, "CartItemAdded", 3, add())) == "version_gap"
    assert reason(evaluate(None, "CartCreated", 2, None)) == "version_gap"


def test_version_above_next_is_a_gap():
    assert reason(evaluate(cart(version=2), "CartItemAdded", 5, add())) == "version_gap"


@pytest.mark.parametrize("version", [1, 2])
def test_version_at_or_below_stored_is_a_conflict(version):
    assert (
        reason(evaluate(cart(version=2), "CartItemAdded", version, add()))
        == "version_conflict"
    )


def test_second_cart_created_is_invalid_even_at_next_version():
    assert reason(evaluate(cart(version=1), "CartCreated", 2, None)) == (
        "invalid_transition"
    )


def test_item_added_accumulates_quantity():
    state = evaluate(cart(1), "CartItemAdded", 2, add(qty=2))
    state = evaluate(state, "CartItemAdded", 3, add(qty=3))
    assert state.version == 3
    assert state.active == {"sku-1": Item(5, 500, "USD")}


@pytest.mark.parametrize("change", [{"price": 600}, {"currency": "EUR"}])
def test_item_added_at_different_price_or_currency_is_invalid_payload(change):
    state = cart(2, active={"sku-1": Item(1, 500, "USD")})
    assert reason(evaluate(state, "CartItemAdded", 3, add(**change))) == (
        "invalid_payload"
    )


def test_item_added_price_is_checked_against_saved_items_too():
    state = cart(2, saved={"sku-1": Item(1, 500, "USD")})
    assert reason(evaluate(state, "CartItemAdded", 3, add(price=1))) == (
        "invalid_payload"
    )


def test_remove_subtracts_from_active_only():
    state = cart(
        2, active={"sku-1": Item(3, 500, "USD")}, saved={"sku-1": Item(2, 500, "USD")}
    )
    result = evaluate(state, "CartItemRemoved", 3, qty(quantity=2))
    assert result.active == {"sku-1": Item(1, 500, "USD")}
    assert result.saved == {"sku-1": Item(2, 500, "USD")}


def test_remove_to_zero_drops_the_entry():
    state = cart(2, active={"sku-1": Item(2, 500, "USD")})
    assert evaluate(state, "CartItemRemoved", 3, qty(quantity=2)).active == {}


def test_remove_more_than_active_is_invalid_transition():
    state = cart(2, active={"sku-1": Item(2, 500, "USD")})
    assert reason(evaluate(state, "CartItemRemoved", 3, qty(quantity=3))) == (
        "invalid_transition"
    )


def test_remove_unknown_product_is_invalid_transition():
    state = cart(2, active={"sku-1": Item(2, 500, "USD")})
    assert reason(evaluate(state, "CartItemRemoved", 3, qty("sku-9"))) == (
        "invalid_transition"
    )


def test_save_for_later_moves_quantity_and_keeps_price():
    state = cart(2, active={"sku-1": Item(3, 500, "USD")})
    result = evaluate(state, "CartItemSavedForLater", 3, qty(quantity=2))
    assert result.active == {"sku-1": Item(1, 500, "USD")}
    assert result.saved == {"sku-1": Item(2, 500, "USD")}


def test_save_more_than_active_is_invalid_transition():
    state = cart(2, active={"sku-1": Item(1, 500, "USD")})
    assert reason(evaluate(state, "CartItemSavedForLater", 3, qty(quantity=2))) == (
        "invalid_transition"
    )


def test_saved_removed_requires_saved_quantity():
    state = cart(2, active={"sku-1": Item(5, 500, "USD")})
    assert reason(evaluate(state, "SavedForLaterItemRemoved", 3, qty())) == (
        "invalid_transition"
    )
    state = cart(2, saved={"sku-1": Item(2, 500, "USD")})
    assert evaluate(state, "SavedForLaterItemRemoved", 3, qty(quantity=2)).saved == {}
    assert reason(evaluate(state, "SavedForLaterItemRemoved", 3, qty(quantity=3))) == (
        "invalid_transition"
    )


def test_move_to_cart_transfers_same_amount_and_keeps_price():
    state = cart(
        2, active={"sku-1": Item(1, 500, "USD")}, saved={"sku-1": Item(3, 500, "USD")}
    )
    result = evaluate(state, "SavedForLaterItemMovedToCart", 3, qty(quantity=2))
    assert result.active == {"sku-1": Item(3, 500, "USD")}
    assert result.saved == {"sku-1": Item(1, 500, "USD")}


def test_move_more_than_saved_is_invalid_transition():
    state = cart(2, saved={"sku-1": Item(1, 500, "USD")})
    assert reason(
        evaluate(state, "SavedForLaterItemMovedToCart", 3, qty(quantity=2))
    ) == ("invalid_transition")


def test_purchase_matches_active_projection_and_excludes_saved():
    state = cart(
        4,
        active={"sku-1": Item(2, 500, "USD"), "sku-2": Item(1, 250, "USD")},
        saved={"sku-3": Item(9, 9999, "USD")},
    )
    result = evaluate(state, "CartPurchased", 5, purchase(3, 1250, order_id=12))
    assert result.business_status == "purchased"
    assert result.version == 5
    assert result.purchase == Purchase(12, 3, 1250, "USD")
    assert result.active == state.active
    assert result.saved == state.saved


def test_purchase_with_no_active_item_is_invalid_transition():
    state = cart(4, saved={"sku-1": Item(2, 500, "USD")})
    assert reason(evaluate(state, "CartPurchased", 5, purchase(0, 0))) == (
        "invalid_transition"
    )


@pytest.mark.parametrize(
    "payload",
    [purchase(3, 1000), purchase(2, 999), purchase(2, 1000, currency="EUR")],
)
def test_purchase_not_matching_projection_is_invalid_payload(payload):
    state = cart(4, active={"sku-1": Item(2, 500, "USD")})
    assert reason(evaluate(state, "CartPurchased", 5, payload)) == "invalid_payload"


def test_purchase_with_mixed_active_currencies_is_invalid_payload():
    state = cart(4, active={"sku-1": Item(1, 500, "USD"), "sku-2": Item(1, 500, "EUR")})
    assert reason(evaluate(state, "CartPurchased", 5, purchase(2, 1000))) == (
        "invalid_payload"
    )


@pytest.mark.parametrize(
    "event_type,payload",
    [
        ("CartItemAdded", add()),
        ("CartItemRemoved", qty()),
        ("CartPurchased", purchase(2, 1000)),
    ],
)
def test_new_event_after_purchase_is_invalid_transition(event_type, payload):
    state = cart(5, active={"sku-1": Item(2, 500, "USD")}, status="purchased")
    assert reason(evaluate(state, event_type, 6, payload)) == "invalid_transition"


def test_rejection_never_mutates_the_input_state():
    state = cart(2, active={"sku-1": Item(2, 500, "USD")})
    evaluate(state, "CartItemRemoved", 3, qty(quantity=5))
    evaluate(state, "CartItemRemoved", 3, qty(quantity=1))
    assert state == cart(2, active={"sku-1": Item(2, 500, "USD")})


@pytest.mark.parametrize("seed", range(40))
def test_every_generated_lifecycle_applies_cleanly(seed):
    state = None
    for event in generate_cart_business_events(random.Random(seed), order_id=seed):
        state = evaluate(
            state, event.event_type, event.aggregate_version, event.payload
        )
        assert isinstance(state, CartState), (event, state)
    assert state.business_status == "purchased"
    assert state.active
