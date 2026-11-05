import json

import pytest

from reliable_ingestion.consumer.envelope import SourceRecord, parse_record


def envelope(event_type="CartItemAdded", version=2, payload="default", **overrides):
    payloads = {
        "CartCreated": None,
        "CartItemAdded": {
            "product_id": "sku-1",
            "quantity_delta": 2,
            "unit_price_minor": 500,
            "currency": "USD",
        },
        "CartItemRemoved": {"product_id": "sku-1", "quantity": 1},
        "CartItemSavedForLater": {"product_id": "sku-1", "quantity": 1},
        "SavedForLaterItemRemoved": {"product_id": "sku-1", "quantity": 1},
        "SavedForLaterItemMovedToCart": {"product_id": "sku-1", "quantity": 1},
        "CartPurchased": {
            "order_id": 7,
            "total_amount_minor": 1000,
            "currency": "USD",
            "item_count": 2,
        },
    }
    event = {
        "event_id": "evt-1",
        "event_type": event_type,
        "schema_version": 1,
        "occurred_at": "2026-09-14T19:10:12.123Z",
        "produced_at": "2026-09-14T19:10:12.125Z",
        "producer": "cart-simulator",
        "producer_instance_id": "generator-2",
        "producer_sequence": 4811,
        "aggregate": {"type": "cart", "id": "cart-1", "version": version},
        "customer_id": "customer-1",
        "correlation_id": "session-1",
        "causation_id": "command-1",
    }
    chosen = payloads.get(event_type) if payload == "default" else payload
    if chosen is not None:
        event["payload"] = chosen
    event.update(overrides)
    return event


def record(value, key=b"cart-1", offset=0):
    if isinstance(value, dict):
        value = json.dumps(value).encode()
    return SourceRecord("cart-events", 0, offset, key, value)


@pytest.mark.parametrize(
    "event_type",
    [
        "CartCreated",
        "CartItemAdded",
        "CartItemRemoved",
        "CartItemSavedForLater",
        "SavedForLaterItemRemoved",
        "SavedForLaterItemMovedToCart",
        "CartPurchased",
    ],
)
def test_every_supported_event_type_parses(event_type):
    parsed = parse_record(record(envelope(event_type)))
    assert parsed.rejection is None
    assert parsed.event_id == "evt-1"
    assert parsed.cart_id == "cart-1"
    assert parsed.aggregate_version == 2
    assert parsed.event_type == event_type
    assert parsed.customer_id == "customer-1"
    assert parsed.content_hash is not None and len(parsed.content_hash) == 64


def test_original_bytes_and_coordinates_are_kept_unchanged():
    raw = b'{"event_id": broken'
    source = SourceRecord("cart-events", 2, 41, b"cart-9", raw)
    parsed = parse_record(source)
    assert parsed.source is source
    assert parsed.source.value == raw
    assert parsed.source.key == b"cart-9"


def test_malformed_json_has_no_parsed_fields():
    parsed = parse_record(record(b'{"event_id": broken'))
    assert parsed.rejection.reason == "malformed_event"
    assert parsed.event_id is None
    assert parsed.cart_id is None
    assert parsed.aggregate_version is None
    assert parsed.content_hash is None


def test_invalid_utf8_is_malformed():
    assert parse_record(record(b"\xff\xfe")).rejection.reason == "malformed_event"


@pytest.mark.parametrize("value", [b"[]", b'"x"', b"3", b"null", b"true"])
def test_json_that_is_not_an_object_is_malformed_and_unhashed(value):
    parsed = parse_record(record(value))
    assert parsed.rejection.reason == "malformed_event"
    assert parsed.content_hash is None
    assert parsed.event_id is None


def test_null_value_is_malformed():
    parsed = parse_record(SourceRecord("cart-events", 0, 0, b"cart-1", None))
    assert parsed.rejection.reason == "malformed_event"
    assert parsed.content_hash is None


def test_null_key_is_key_mismatch():
    parsed = parse_record(record(envelope(), key=None))
    assert parsed.rejection.reason == "key_mismatch"
    assert parsed.cart_id == "cart-1"
    assert parsed.event_id == "evt-1"
    assert parsed.content_hash is not None


def test_key_different_from_aggregate_id_is_key_mismatch():
    parsed = parse_record(record(envelope(), key=b"cart-2"))
    assert parsed.rejection.reason == "key_mismatch"
    assert parsed.cart_id == "cart-1"


def test_key_that_is_not_utf8_is_key_mismatch():
    parsed = parse_record(record(envelope(), key=b"\xff"))
    assert parsed.rejection.reason == "key_mismatch"


@pytest.mark.parametrize(
    "missing",
    [
        "event_id",
        "event_type",
        "schema_version",
        "occurred_at",
        "produced_at",
        "producer",
        "producer_instance_id",
        "producer_sequence",
        "aggregate",
        "customer_id",
        "correlation_id",
        "causation_id",
    ],
)
def test_missing_required_envelope_field_is_malformed(missing):
    event = envelope()
    del event[missing]
    parsed = parse_record(record(event))
    assert parsed.rejection.reason == "malformed_event"
    assert parsed.content_hash is not None


def test_missing_aggregate_version_is_malformed_with_partial_metadata():
    event = envelope()
    del event["aggregate"]["version"]
    parsed = parse_record(record(event))
    assert parsed.rejection.reason == "malformed_event"
    assert parsed.aggregate_version is None
    assert parsed.cart_id == "cart-1"
    assert parsed.event_id == "evt-1"


@pytest.mark.parametrize("version", [0, -1, "2", 2.0, True, None, 2**63])
def test_unusable_aggregate_version_is_malformed(version):
    parsed = parse_record(record(envelope(version=version)))
    assert parsed.rejection.reason == "malformed_event"
    assert parsed.aggregate_version is None


def test_wrong_aggregate_type_is_malformed():
    event = envelope()
    event["aggregate"]["type"] = "order"
    assert parse_record(record(event)).rejection.reason == "malformed_event"


@pytest.mark.parametrize("field", ["event_id", "customer_id"])
def test_nul_character_in_identifier_is_malformed(field):
    parsed = parse_record(record(envelope(**{field: "bad\u0000id"})))
    assert parsed.rejection.reason == "malformed_event"
    if field == "event_id":
        assert parsed.event_id is None


def test_nul_character_in_cart_id_is_malformed_and_cart_id_unusable():
    event = envelope()
    event["aggregate"]["id"] = "cart\u0000-1"
    parsed = parse_record(record(event, key="cart\u0000-1".encode()))
    assert parsed.rejection.reason == "malformed_event"
    assert parsed.cart_id is None


def test_unsupported_schema_version():
    parsed = parse_record(record(envelope(schema_version=2)))
    assert parsed.rejection.reason == "unsupported_schema"
    assert parsed.event_id == "evt-1"


def test_unknown_event_type_is_unsupported_schema():
    parsed = parse_record(record(envelope(event_type="CartAbandoned", payload=None)))
    assert parsed.rejection.reason == "unsupported_schema"


def test_cart_created_with_payload_is_invalid_payload():
    parsed = parse_record(record(envelope("CartCreated", payload={"x": 1})))
    assert parsed.rejection.reason == "invalid_payload"


@pytest.mark.parametrize(
    "event_type,change",
    [
        ("CartItemAdded", {"quantity_delta": 0}),
        ("CartItemAdded", {"quantity_delta": -1}),
        ("CartItemAdded", {"quantity_delta": 1.5}),
        ("CartItemAdded", {"quantity_delta": True}),
        ("CartItemAdded", {"quantity_delta": 2**40}),
        ("CartItemAdded", {"unit_price_minor": -1}),
        ("CartItemAdded", {"unit_price_minor": 9.99}),
        ("CartItemAdded", {"currency": ""}),
        ("CartItemAdded", {"product_id": 5}),
        ("CartItemAdded", {"product_id": "sku\u0000"}),
        ("CartItemAdded", {"unexpected": 1}),
        ("CartItemRemoved", {"quantity": 0}),
        ("CartItemSavedForLater", {"quantity": "1"}),
        ("SavedForLaterItemRemoved", {"product_id": ""}),
        ("SavedForLaterItemMovedToCart", {"quantity": -3}),
        ("CartPurchased", {"order_id": -1}),
        ("CartPurchased", {"item_count": -1}),
        ("CartPurchased", {"total_amount_minor": 2**63}),
        ("CartPurchased", {"currency": None}),
    ],
)
def test_bad_payload_shape_is_invalid_payload(event_type, change):
    event = envelope(event_type)
    event["payload"].update(change)
    parsed = parse_record(record(event))
    assert parsed.rejection.reason == "invalid_payload"
    assert parsed.event_id == "evt-1"
    assert parsed.cart_id == "cart-1"


@pytest.mark.parametrize("event_type", ["CartItemAdded", "CartPurchased"])
def test_missing_payload_is_invalid_payload(event_type):
    parsed = parse_record(record(envelope(event_type, payload=None)))
    assert parsed.rejection.reason == "invalid_payload"


def test_missing_payload_field_is_invalid_payload():
    event = envelope("CartItemRemoved")
    del event["payload"]["quantity"]
    assert parse_record(record(event)).rejection.reason == "invalid_payload"


def test_key_order_and_whitespace_do_not_change_content_hash():
    event = envelope()
    compact = json.dumps(event, separators=(",", ":")).encode()
    reordered = json.dumps(dict(reversed(list(event.items()))), indent=2).encode()
    assert (
        parse_record(record(compact)).content_hash
        == parse_record(record(reordered)).content_hash
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("produced_at", "2026-09-14T19:10:13.000Z"),
        ("producer_instance_id", "generator-3"),
        ("producer_sequence", 4812),
        ("occurred_at", "2026-09-14T19:10:13.000Z"),
        ("correlation_id", "session-2"),
    ],
)
def test_any_changed_envelope_field_changes_content_hash(field, value):
    base = parse_record(record(envelope()))
    changed = parse_record(record(envelope(**{field: value})))
    assert changed.rejection is None
    assert base.content_hash != changed.content_hash


def test_changed_payload_changes_content_hash():
    base = parse_record(record(envelope()))
    event = envelope()
    event["payload"]["quantity_delta"] = 3
    assert parse_record(record(event)).content_hash != base.content_hash


def test_source_coordinates_do_not_affect_content_hash():
    first = parse_record(record(envelope(), offset=1))
    second = parse_record(
        SourceRecord("other-topic", 2, 99, b"cart-1", json.dumps(envelope()).encode())
    )
    assert first.content_hash == second.content_hash


def test_unpaired_surrogate_in_identifier_is_malformed():
    raw = json.dumps(envelope()).replace("evt-1", "evt-\\ud800").encode()
    parsed = parse_record(record(raw))
    assert parsed.rejection.reason == "malformed_event"
    assert parsed.event_id is None
