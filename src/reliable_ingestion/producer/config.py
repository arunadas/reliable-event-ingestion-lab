from __future__ import annotations

import argparse
import os
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratorConfig:
    broker_address: str
    topic: str
    events_per_second: float
    num_carts: int
    max_events: int | None
    run_duration_seconds: float | None
    seed: int
    producer_instance_id: str
    duplicate_probability: float
    delay_probability: float
    max_delay_seconds: float


def _default_broker_address() -> str:
    port = os.environ.get("REDPANDA_KAFKA_PORT", "19092")
    return f"localhost:{port}"


def parse_args(argv: list[str] | None = None) -> GeneratorConfig:
    parser = argparse.ArgumentParser(description="Cart event generator")
    parser.add_argument("--broker-address", default=_default_broker_address())
    parser.add_argument("--topic", default="cart-events")
    parser.add_argument("--events-per-second", type=float, default=10.0)
    parser.add_argument("--num-carts", type=int, default=10)
    parser.add_argument("--max-events", type=int, default=None)
    parser.add_argument("--run-duration-seconds", type=float, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--duplicate-probability", type=float, default=0.0)
    parser.add_argument("--delay-probability", type=float, default=0.0)
    parser.add_argument("--max-delay-seconds", type=float, default=0.0)
    args = parser.parse_args(argv)

    return GeneratorConfig(
        broker_address=args.broker_address,
        topic=args.topic,
        events_per_second=args.events_per_second,
        num_carts=args.num_carts,
        max_events=args.max_events,
        run_duration_seconds=args.run_duration_seconds,
        seed=args.seed,
        producer_instance_id=f"generator-{uuid.uuid4()}",
        duplicate_probability=args.duplicate_probability,
        delay_probability=args.delay_probability,
        max_delay_seconds=args.max_delay_seconds,
    )
