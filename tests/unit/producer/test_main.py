import json
import random

import pytest

from reliable_ingestion.producer.__main__ import run
from reliable_ingestion.producer.cart_simulator import generate_cart_business_events
from reliable_ingestion.producer.config import GeneratorConfig


def _business_fingerprint(raw_json_bytes):
    event = json.loads(raw_json_bytes)
    return (
        event["event_type"],
        event["producer"],
        event["producer_instance_id"],
        event["producer_sequence"],
        event["aggregate"],
        event.get("payload"),
    )


class _FakeMessage:
    def __init__(self, topic, partition, offset):
        self._topic, self._partition, self._offset = topic, partition, offset

    def topic(self):
        return self._topic

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset


class _AlwaysSucceedsProducer:
    def __init__(self):
        self.produced_values = []
        self._offset = 0

    def produce(self, topic, key, value, on_delivery):
        self.produced_values.append(value)
        on_delivery(None, _FakeMessage(topic, 0, self._offset))
        self._offset += 1

    def poll(self, timeout):
        return 0

    def flush(self, timeout=None):
        return 0


class _AlwaysFailsProducer:
    def produce(self, topic, key, value, on_delivery):
        on_delivery(Exception("boom"), None)

    def poll(self, timeout):
        return 0

    def flush(self, timeout=None):
        return 0


def _base_config(**overrides):
    defaults = dict(
        broker_address="localhost:19092",
        topic="cart-events",
        events_per_second=0.0,
        num_carts=1,
        max_events=None,
        run_duration_seconds=None,
        seed=3,
        producer_instance_id="generator-test",
        duplicate_probability=0.0,
        delay_probability=0.0,
        max_delay_seconds=0.0,
    )
    defaults.update(overrides)
    return GeneratorConfig(**defaults)


def test_run_generates_expected_event_count_for_single_cart():
    expected = generate_cart_business_events(random.Random(3), order_id=0)
    producer = _AlwaysSucceedsProducer()

    metrics = run(_base_config(), producer, sleep=lambda s: None)

    assert metrics.events_generated_total == len(expected)
    assert metrics.events_published_total == len(expected)
    assert len(producer.produced_values) == len(expected)


def test_run_is_deterministic_given_same_seed():
    producer_a = _AlwaysSucceedsProducer()
    run(_base_config(num_carts=3, seed=11), producer_a, sleep=lambda s: None)

    producer_b = _AlwaysSucceedsProducer()
    run(_base_config(num_carts=3, seed=11), producer_b, sleep=lambda s: None)

    fingerprints_a = [_business_fingerprint(v) for v in producer_a.produced_values]
    fingerprints_b = [_business_fingerprint(v) for v in producer_b.produced_values]
    assert fingerprints_a == fingerprints_b


def test_run_respects_max_events_limit():
    producer = _AlwaysSucceedsProducer()

    metrics = run(_base_config(max_events=2), producer, sleep=lambda s: None)

    assert metrics.events_generated_total == 2
    assert len(producer.produced_values) == 2


def test_run_duplicates_when_duplicate_probability_is_one():
    baseline_producer = _AlwaysSucceedsProducer()
    baseline_metrics = run(_base_config(), baseline_producer, sleep=lambda s: None)

    dup_producer = _AlwaysSucceedsProducer()
    run(
        _base_config(duplicate_probability=1.0),
        dup_producer,
        sleep=lambda s: None,
    )

    assert (
        len(dup_producer.produced_values) == 2 * baseline_metrics.events_generated_total
    )


def test_run_exits_nonzero_when_publication_exhausts_retries():
    producer = _AlwaysFailsProducer()

    with pytest.raises(SystemExit) as exc_info:
        run(_base_config(), producer, sleep=lambda s: None)

    assert exc_info.value.code == 1
