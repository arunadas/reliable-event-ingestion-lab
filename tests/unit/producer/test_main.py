import json
import random
from collections import defaultdict

import pytest

from reliable_ingestion.producer.__main__ import _ShutdownRequested, run
from reliable_ingestion.producer.cart_simulator import generate_cart_business_events
from reliable_ingestion.producer.config import GeneratorConfig
from reliable_ingestion.producer.metrics import GeneratorMetrics


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
        self.produced_keys = []
        self.flush_calls = 0
        self._offset = 0

    def produce(self, topic, key, value, on_delivery):
        self.produced_values.append(value)
        self.produced_keys.append(key)
        on_delivery(None, _FakeMessage(topic, 0, self._offset))
        self._offset += 1

    def poll(self, timeout):
        return 0

    def flush(self, timeout=None):
        self.flush_calls += 1
        return 0


class _AlwaysFailsProducer:
    def produce(self, topic, key, value, on_delivery):
        on_delivery(Exception("boom"), None)

    def poll(self, timeout):
        return 0

    def flush(self, timeout=None):
        return 0


def _base_config(**overrides):
    defaults = {
        "broker_address": "localhost:19092",
        "topic": "cart-events",
        "events_per_second": 0.0,
        "num_carts": 1,
        "max_events": None,
        "run_duration_seconds": None,
        "seed": 3,
        "producer_instance_id": "generator-test",
        "duplicate_probability": 0.0,
        "delay_probability": 0.0,
        "max_delay_seconds": 0.0,
    }
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


def test_run_flushes_producer_after_normal_completion():
    producer = _AlwaysSucceedsProducer()

    run(_base_config(), producer, sleep=lambda s: None)

    assert producer.flush_calls >= 1


def test_run_flushes_and_returns_metrics_on_shutdown_mid_run():
    producer = _AlwaysSucceedsProducer()
    sleep_calls = {"count": 0}

    def _sleep_then_shutdown(_seconds):
        sleep_calls["count"] += 1
        if sleep_calls["count"] >= 2:
            raise _ShutdownRequested()

    metrics = run(
        _base_config(num_carts=5, events_per_second=1000.0),
        producer,
        sleep=_sleep_then_shutdown,
    )

    assert isinstance(metrics, GeneratorMetrics)
    assert metrics.events_generated_total >= 1
    assert producer.flush_calls >= 1


def test_run_uses_consistent_key_per_cart_and_unique_event_ids():
    producer = _AlwaysSucceedsProducer()

    run(_base_config(num_carts=3, seed=5), producer, sleep=lambda s: None)

    decoded = [json.loads(v) for v in producer.produced_values]

    # All events for one cart use the identical Redpanda key.
    keys_by_cart = defaultdict(set)
    for key, event in zip(producer.produced_keys, decoded):
        keys_by_cart[event["aggregate"]["id"]].add(key)
    for cart_id, keys in keys_by_cart.items():
        assert len(keys) == 1, f"cart {cart_id} used multiple keys: {keys}"
        assert keys == {cart_id.encode("utf-8")}

    # Event IDs are unique across the whole run.
    event_ids = [event["event_id"] for event in decoded]
    assert len(event_ids) == len(set(event_ids))

    # Per-cart aggregate versions restart at 1 for each new cart.
    versions_by_cart = defaultdict(list)
    for event in decoded:
        versions_by_cart[event["aggregate"]["id"]].append(event["aggregate"]["version"])
    for cart_id, versions in versions_by_cart.items():
        assert versions[0] == 1, (
            f"cart {cart_id} did not start at version 1: {versions}"
        )
