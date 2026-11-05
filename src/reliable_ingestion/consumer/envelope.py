from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SUPPORTED_SCHEMA_VERSION = 1

SUPPORTED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "CartCreated",
        "CartItemAdded",
        "CartItemRemoved",
        "CartItemSavedForLater",
        "SavedForLaterItemRemoved",
        "SavedForLaterItemMovedToCart",
        "CartPurchased",
    }
)

MALFORMED_EVENT = "malformed_event"
UNSUPPORTED_SCHEMA = "unsupported_schema"
KEY_MISMATCH = "key_mismatch"
INVALID_PAYLOAD = "invalid_payload"
EVENT_ID_CONFLICT = "event_id_conflict"
VERSION_CONFLICT = "version_conflict"
VERSION_GAP = "version_gap"
INVALID_TRANSITION = "invalid_transition"

# PostgreSQL bigint upper bound; larger values would fail in the database
# as an unexpected error instead of being rejected as invalid input.
MAX_BIGINT = 2**63 - 1
# Per-event quantities and unit prices are capped so that projection sums
# stay far inside the bigint range.
MAX_QUANTITY = 2**31 - 1

_REQUIRED_STRINGS = (
    "occurred_at",
    "produced_at",
    "producer",
    "producer_instance_id",
    "customer_id",
    "correlation_id",
    "causation_id",
)

_QUANTITY_EVENTS = frozenset(
    {
        "CartItemRemoved",
        "CartItemSavedForLater",
        "SavedForLaterItemRemoved",
        "SavedForLaterItemMovedToCart",
    }
)


@dataclass(frozen=True)
class SourceRecord:
    topic: str
    partition: int
    offset: int
    key: bytes | None
    value: bytes | None


@dataclass(frozen=True)
class Rejection:
    reason: str
    detail: str


@dataclass(frozen=True)
class ParsedRecord:
    """Validation result for one source record.

    The original bytes stay on ``source``. Fields that could not be parsed
    are None; ``rejection`` is set when the record is structurally invalid.
    """

    source: SourceRecord
    event_id: str | None = None
    cart_id: str | None = None
    aggregate_version: int | None = None
    content_hash: str | None = None
    canonical_json: str | None = None
    event_type: str | None = None
    customer_id: str | None = None
    payload: dict[str, Any] | None = None
    rejection: Rejection | None = None


def canonical_json(envelope: dict[str, Any]) -> str:
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"))


def content_hash(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _usable_string(value: Any) -> str | None:
    # PostgreSQL text cannot store NUL or unpaired surrogates.
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return value


def _is_int(value: Any, minimum: int, maximum: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and minimum <= value <= maximum
    )


def _payload_problem(event_type: str, envelope: dict[str, Any]) -> str | None:
    payload = envelope.get("payload")
    if event_type == "CartCreated":
        return None if payload is None else "CartCreated must not carry a payload"
    if not isinstance(payload, dict):
        return f"{event_type} requires a payload object"

    if event_type == "CartItemAdded":
        expected = {"product_id", "quantity_delta", "unit_price_minor", "currency"}
    elif event_type in _QUANTITY_EVENTS:
        expected = {"product_id", "quantity"}
    else:
        expected = {"order_id", "total_amount_minor", "currency", "item_count"}
    if set(payload) != expected:
        return f"payload fields must be exactly {sorted(expected)}"

    if event_type == "CartPurchased":
        for name in ("order_id", "total_amount_minor", "item_count"):
            if not _is_int(payload[name], 0, MAX_BIGINT):
                return f"{name} must be a non-negative integer"
        if _usable_string(payload["currency"]) is None:
            return "currency must be a non-empty string"
        return None

    if _usable_string(payload["product_id"]) is None:
        return "product_id must be a non-empty string"
    if event_type == "CartItemAdded":
        if not _is_int(payload["quantity_delta"], 1, MAX_QUANTITY):
            return "quantity_delta must be a positive integer"
        if not _is_int(payload["unit_price_minor"], 0, MAX_QUANTITY):
            return "unit_price_minor must be a non-negative integer"
        if _usable_string(payload["currency"]) is None:
            return "currency must be a non-empty string"
        return None
    if not _is_int(payload["quantity"], 1, MAX_QUANTITY):
        return "quantity must be a positive integer"
    return None


def parse_record(source: SourceRecord) -> ParsedRecord:
    """Structurally validate a source record without touching the database.

    Never raises for invalid input: the returned result carries a rejection
    and whichever identifying fields could be parsed.
    """
    if source.value is None:
        return ParsedRecord(source, rejection=Rejection(MALFORMED_EVENT, "null value"))
    try:
        envelope = json.loads(source.value.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        return ParsedRecord(
            source,
            rejection=Rejection(MALFORMED_EVENT, f"not valid JSON: {exc}"),
        )
    if not isinstance(envelope, dict):
        return ParsedRecord(
            source, rejection=Rejection(MALFORMED_EVENT, "value is not a JSON object")
        )

    try:
        canonical: str | None = canonical_json(envelope)
    except (ValueError, RecursionError):
        canonical = None
    aggregate = envelope.get("aggregate")
    aggregate_dict = aggregate if isinstance(aggregate, dict) else {}
    version = aggregate_dict.get("version")
    event_type = envelope.get("event_type")

    def result(rejection: Rejection | None) -> ParsedRecord:
        return ParsedRecord(
            source,
            event_id=_usable_string(envelope.get("event_id")),
            cart_id=_usable_string(aggregate_dict.get("id")),
            aggregate_version=version if _is_int(version, 1, MAX_BIGINT) else None,
            content_hash=content_hash(canonical) if canonical is not None else None,
            canonical_json=canonical,
            event_type=_usable_string(event_type),
            customer_id=_usable_string(envelope.get("customer_id")),
            payload=envelope.get("payload")
            if isinstance(envelope.get("payload"), dict)
            else None,
            rejection=rejection,
        )

    def malformed(detail: str) -> ParsedRecord:
        return result(Rejection(MALFORMED_EVENT, detail))

    if canonical is None:
        return malformed("envelope cannot be canonicalised")

    schema_version = envelope.get("schema_version")
    if not _is_int(schema_version, -MAX_BIGINT, MAX_BIGINT):
        return malformed("schema_version is missing or not an integer")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        return result(Rejection(UNSUPPORTED_SCHEMA, f"schema_version {schema_version}"))

    if _usable_string(envelope.get("event_id")) is None:
        return malformed("event_id is missing or not a usable string")
    if _usable_string(event_type) is None:
        return malformed("event_type is missing or not a usable string")
    if not isinstance(aggregate, dict):
        return malformed("aggregate is missing or not an object")
    if aggregate.get("type") != "cart":
        return malformed("aggregate.type must be 'cart'")
    if _usable_string(aggregate.get("id")) is None:
        return malformed("aggregate.id is missing or not a usable string")
    if not _is_int(version, 1, MAX_BIGINT):
        return malformed("aggregate.version is missing or not a positive integer")
    for name in _REQUIRED_STRINGS:
        if _usable_string(envelope.get(name)) is None:
            return malformed(f"{name} is missing or not a usable string")
    if not _is_int(envelope.get("producer_sequence"), -MAX_BIGINT, MAX_BIGINT):
        return malformed("producer_sequence is missing or not an integer")

    if event_type not in SUPPORTED_EVENT_TYPES:
        return result(Rejection(UNSUPPORTED_SCHEMA, f"event_type {event_type!r}"))

    try:
        key = source.key.decode("utf-8") if source.key is not None else None
    except UnicodeDecodeError:
        key = None
    if key != aggregate["id"]:
        return result(
            Rejection(KEY_MISMATCH, "message key does not equal aggregate.id")
        )

    problem = _payload_problem(event_type, envelope)
    if problem is not None:
        return result(Rejection(INVALID_PAYLOAD, problem))
    return result(None)
