from __future__ import annotations

import logging
import time
from typing import Any, Protocol

from reliable_ingestion.producer.events import CartEvent
from reliable_ingestion.producer.metrics import GeneratorMetrics

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 0.1
BACKOFF_MULTIPLIER = 2.0


class DeliveryResult:
    def __init__(self, topic: str, partition: int, offset: int) -> None:
        self.topic = topic
        self.partition = partition
        self.offset = offset


class KafkaProducerLike(Protocol):
    def produce(
        self, topic: str, key: bytes, value: bytes, on_delivery: Any
    ) -> None: ...
    def poll(self, timeout: float) -> int: ...
    def flush(self, timeout: float | None = None) -> int: ...


class PublicationFailedError(Exception):
    pass


class EventPublisher:
    def __init__(
        self,
        producer: KafkaProducerLike,
        topic: str,
        metrics: GeneratorMetrics,
        sleep: Any = time.sleep,
    ) -> None:
        self._producer = producer
        self._topic = topic
        self._metrics = metrics
        self._sleep = sleep

    def publish(self, event: CartEvent) -> DeliveryResult:
        key = event.aggregate.id.encode("utf-8")
        value = event.to_json_bytes()
        backoff = INITIAL_BACKOFF_SECONDS
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            outcome: dict[str, Any] = {}

            def on_delivery(
                err: Any, msg: Any, _outcome: dict[str, Any] = outcome
            ) -> None:
                _outcome["err"] = err
                _outcome["msg"] = msg

            start = time.monotonic()
            self._producer.produce(
                self._topic, key=key, value=value, on_delivery=on_delivery
            )
            self._producer.poll(0)
            self._producer.flush(10.0)
            latency_ms = (time.monotonic() - start) * 1000

            if "err" in outcome and outcome["err"] is None:
                msg = outcome["msg"]
                delivery = DeliveryResult(msg.topic(), msg.partition(), msg.offset())
                self._metrics.record_published(latency_ms)
                logger.info(
                    "published event",
                    extra={
                        "event_id": event.event_id,
                        "cart_id": event.aggregate.id,
                        "aggregate_version": event.aggregate.version,
                        "topic": delivery.topic,
                        "partition": delivery.partition,
                        "offset": delivery.offset,
                    },
                )
                return delivery

            if "err" in outcome:
                err = outcome["err"]
            else:
                err = Exception("delivery callback did not fire before flush timeout")
            last_error = RuntimeError(str(err))
            if attempt < MAX_RETRIES:
                self._metrics.record_retry()
                self._sleep(backoff)
                backoff *= BACKOFF_MULTIPLIER

        self._metrics.record_failure()
        logger.error(
            "publication failed after retries",
            extra={"event_id": event.event_id, "cart_id": event.aggregate.id},
        )
        raise PublicationFailedError(
            f"failed to publish event {event.event_id} after {MAX_RETRIES} attempts"
        ) from last_error
