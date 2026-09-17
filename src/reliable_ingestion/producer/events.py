from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

SCHEMA_VERSION = 1

EventType = Literal[
    "CartCreated",
    "CartItemAdded",
    "CartItemSavedForLater",
    "CartPurchased",
]


def format_timestamp(dt: datetime) -> str:
    utc_dt = dt.astimezone(UTC)
    millis = utc_dt.microsecond // 1000
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{millis:03d}Z"


@dataclass(frozen=True)
class Aggregate:
    id: str
    version: int
    type: str = "cart"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "id": self.id, "version": self.version}


@dataclass(frozen=True)
class CartEvent:
    event_id: str
    event_type: EventType
    occurred_at: datetime
    produced_at: datetime
    producer: str
    producer_instance_id: str
    producer_sequence: int
    aggregate: Aggregate
    customer_id: str
    correlation_id: str
    causation_id: str
    payload: dict[str, Any] | None = None
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        envelope: dict[str, Any] = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "occurred_at": format_timestamp(self.occurred_at),
            "produced_at": format_timestamp(self.produced_at),
            "producer": self.producer,
            "producer_instance_id": self.producer_instance_id,
            "producer_sequence": self.producer_sequence,
            "aggregate": self.aggregate.to_dict(),
            "customer_id": self.customer_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }
        if self.payload is not None:
            envelope["payload"] = self.payload
        return envelope

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":")).encode("utf-8")
