from datetime import UTC, datetime

import pytest
from reliable_ingestion.producer.publisher import (
    EventPublisher,
    PublicationFailedError,
)

from reliable_ingestion.producer.events import Aggregate, CartEvent
from reliable_ingestion.producer.metrics import GeneratorMetrics


class _FakeMessage:
    def __init__(self, topic, partition, offset):
        self._topic = topic
        self._partition = partition
        self._offset = offset

    def topic(self):
        return self._topic

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset


class _FakeProducer:
    """outcomes: list of "fail" or ("ok", partition, offset), consumed FIFO."""

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.produced_keys = []
        self.produced_values = []

    def produce(self, topic, key, value, on_delivery):
        self.produced_keys.append(key)
        self.produced_values.append(value)
        outcome = self._outcomes.pop(0)
        if outcome == "fail":
            on_delivery(Exception("boom"), None)
        else:
            _, partition, offset = outcome
            on_delivery(None, _FakeMessage(topic, partition, offset))

    def poll(self, timeout):
        return 0

    def flush(self, timeout=None):
        return 0


def _make_event():
    ts = datetime(2026, 9, 14, 19, 10, 12, 0, tzinfo=UTC)
    return CartEvent(
        event_id="event-1",
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
    )


def test_publish_success_returns_delivery_and_records_metrics():
    producer = _FakeProducer([("ok", 1, 100)])
    metrics = GeneratorMetrics()
    publisher = EventPublisher(producer, "cart-events", metrics, sleep=lambda s: None)

    result = publisher.publish(_make_event())

    assert result.topic == "cart-events"
    assert result.partition == 1
    assert result.offset == 100
    assert metrics.events_published_total == 1
    assert metrics.publication_retries_total == 0


def test_publish_uses_cart_id_as_key():
    producer = _FakeProducer([("ok", 0, 1)])
    metrics = GeneratorMetrics()
    publisher = EventPublisher(producer, "cart-events", metrics, sleep=lambda s: None)

    publisher.publish(_make_event())

    assert producer.produced_keys == [b"cart-456"]


def test_publish_retries_on_failure_then_succeeds_with_identical_payload():
    producer = _FakeProducer(["fail", "fail", ("ok", 0, 5)])
    metrics = GeneratorMetrics()
    publisher = EventPublisher(producer, "cart-events", metrics, sleep=lambda s: None)

    publisher.publish(_make_event())

    assert metrics.publication_retries_total == 2
    assert metrics.events_published_total == 1
    assert len(producer.produced_values) == 3
    assert len(set(producer.produced_values)) == 1  # identical bytes every attempt


def test_publish_raises_after_max_retries_and_records_failure():
    producer = _FakeProducer(["fail"] * 5)
    metrics = GeneratorMetrics()
    publisher = EventPublisher(producer, "cart-events", metrics, sleep=lambda s: None)

    with pytest.raises(PublicationFailedError):
        publisher.publish(_make_event())

    assert metrics.publication_failures_total == 1
    assert metrics.publication_retries_total == 4
    assert len(producer.produced_values) == 5
