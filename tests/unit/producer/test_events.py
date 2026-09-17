from datetime import UTC, datetime

from reliable_ingestion.producer.events import Aggregate, CartEvent, format_timestamp


def _make_event(payload=None):
    ts = datetime(2026, 9, 14, 19, 10, 12, 123000, tzinfo=UTC)
    return CartEvent(
        event_id="01K0EXAMPLE",
        event_type="CartCreated",
        occurred_at=ts,
        produced_at=ts,
        producer="cart-simulator",
        producer_instance_id="generator-1",
        producer_sequence=1,
        aggregate=Aggregate(id="cart-456", version=1),
        customer_id="customer-123",
        correlation_id="session-789",
        causation_id="command-345",
        payload=payload,
    )


def test_format_timestamp_is_utc_millisecond_with_z_suffix():
    ts = datetime(2026, 9, 14, 19, 10, 12, 123456, tzinfo=UTC)
    assert format_timestamp(ts) == "2026-09-14T19:10:12.123Z"


def test_to_dict_omits_payload_when_none():
    event = _make_event(payload=None)
    d = event.to_dict()
    assert "payload" not in d


def test_to_dict_includes_payload_when_present():
    event = _make_event(payload={"product_id": "sku-123", "quantity_delta": 1})
    d = event.to_dict()
    assert d["payload"] == {"product_id": "sku-123", "quantity_delta": 1}


def test_to_dict_has_required_envelope_fields():
    event = _make_event()
    d = event.to_dict()
    assert d["event_id"] == "01K0EXAMPLE"
    assert d["event_type"] == "CartCreated"
    assert d["schema_version"] == 1
    assert d["aggregate"] == {"type": "cart", "id": "cart-456", "version": 1}
    assert d["customer_id"] == "customer-123"
    assert d["correlation_id"] == "session-789"
    assert d["causation_id"] == "command-345"
    assert d["producer"] == "cart-simulator"
    assert d["producer_instance_id"] == "generator-1"
    assert d["producer_sequence"] == 1


def test_to_json_bytes_round_trips_as_utf8_json():
    import json

    event = _make_event(payload={"product_id": "sku-123"})
    raw = event.to_json_bytes()
    assert isinstance(raw, bytes)
    decoded = json.loads(raw.decode("utf-8"))
    assert decoded["event_id"] == "01K0EXAMPLE"
    assert decoded["payload"] == {"product_id": "sku-123"}
