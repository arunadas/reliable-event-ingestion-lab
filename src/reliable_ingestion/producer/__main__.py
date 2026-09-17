from __future__ import annotations

import logging
import random
import signal
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from ulid import ULID

from reliable_ingestion.producer.cart_simulator import generate_cart_business_events
from reliable_ingestion.producer.config import GeneratorConfig, parse_args
from reliable_ingestion.producer.events import Aggregate, CartEvent
from reliable_ingestion.producer.fault_injection import delay_seconds, should_duplicate
from reliable_ingestion.producer.metrics import GeneratorMetrics
from reliable_ingestion.producer.publisher import EventPublisher, PublicationFailedError

logger = logging.getLogger(__name__)


class _ShutdownRequested(Exception):
    pass


def _install_signal_handlers() -> None:
    def _handler(signum: int, frame: Any) -> None:
        raise _ShutdownRequested()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def run(
    config: GeneratorConfig,
    kafka_producer: Any,
    sleep: Any = time.sleep,
) -> GeneratorMetrics:
    metrics = GeneratorMetrics()
    rng = random.Random(config.seed)
    publisher = EventPublisher(kafka_producer, config.topic, metrics, sleep=sleep)

    sequence = 0
    events_emitted = 0
    start = time.monotonic()

    def _limit_reached() -> bool:
        if config.max_events is not None and events_emitted >= config.max_events:
            return True
        if (
            config.run_duration_seconds is not None
            and time.monotonic() - start >= config.run_duration_seconds
        ):
            return True
        return False

    try:
        for cart_index in range(config.num_carts):
            if _limit_reached():
                break

            cart_id = f"cart-{cart_index}"
            customer_id = f"customer-{cart_index}"
            correlation_id = f"session-{uuid.uuid4()}"

            for business_event in generate_cart_business_events(
                rng, order_id=cart_index
            ):
                if _limit_reached():
                    break

                sequence += 1
                metrics.record_generated()
                now = datetime.now(UTC)
                event = CartEvent(
                    event_id=str(ULID()),
                    event_type=business_event.event_type,
                    occurred_at=now,
                    produced_at=now,
                    producer="cart-simulator",
                    producer_instance_id=config.producer_instance_id,
                    producer_sequence=sequence,
                    aggregate=Aggregate(
                        id=cart_id, version=business_event.aggregate_version
                    ),
                    customer_id=customer_id,
                    correlation_id=correlation_id,
                    causation_id=f"command-{uuid.uuid4()}",
                    payload=business_event.payload,
                )

                wait_seconds = delay_seconds(
                    rng, config.delay_probability, config.max_delay_seconds
                )
                if wait_seconds > 0:
                    sleep(wait_seconds)

                try:
                    publisher.publish(event)
                except PublicationFailedError:
                    logger.error(
                        "exiting after publication failure",
                        extra={"event_id": event.event_id},
                    )
                    raise SystemExit(1)

                if should_duplicate(rng, config.duplicate_probability):
                    publisher.publish(event)

                events_emitted += 1
                if config.events_per_second > 0:
                    sleep(1.0 / config.events_per_second)
    except _ShutdownRequested:
        logger.info("shutdown requested, flushing producer")
    finally:
        kafka_producer.flush(10.0)
        metrics.run_duration_seconds = time.monotonic() - start
        logger.info("run complete", extra=metrics.as_dict())

    return metrics


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO)
    from confluent_kafka import Producer

    config = parse_args(argv)
    _install_signal_handlers()
    kafka_producer = Producer({"bootstrap.servers": config.broker_address})
    run(config, kafka_producer)


if __name__ == "__main__":
    main()
