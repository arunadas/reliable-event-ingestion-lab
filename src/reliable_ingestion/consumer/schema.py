from __future__ import annotations

import hashlib

import psycopg
from psycopg import sql

from reliable_ingestion.consumer.config import ConsumerConfig

SCHEMA_VERSION = 1

EXPECTED_TABLES: frozenset[str] = frozenset(
    {
        "schema_meta",
        "carts",
        "cart_items",
        "applied_events",
        "quarantine",
        "consumer_record_outcomes",
        "consumer_partition_init",
    }
)

# Bounds on a single statement and lock wait, so one record's retries stay
# well inside the consumer's max.poll.interval.ms.
CONNECT_TIMEOUT_SECONDS = 5
STATEMENT_TIMEOUT_MS = 5000
LOCK_TIMEOUT_MS = 5000

_DDL = """
CREATE TABLE schema_meta (
    -- A true-only primary key permits at most one metadata row.
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    schema_version integer NOT NULL
);

CREATE TABLE carts (
    cart_id text PRIMARY KEY,
    version bigint NOT NULL CHECK (version >= 1),
    business_status text NOT NULL
        CHECK (business_status IN ('open', 'purchased')),
    recovery_status text NOT NULL
        CHECK (recovery_status IN ('clear', 'pending_retry', 'needs_review')),
    customer_id text NOT NULL,
    order_id bigint,
    purchased_item_count bigint,
    purchased_total_amount_minor bigint,
    purchased_currency text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE cart_items (
    cart_id text NOT NULL REFERENCES carts (cart_id),
    product_id text NOT NULL,
    collection text NOT NULL CHECK (collection IN ('active', 'saved')),
    quantity bigint NOT NULL CHECK (quantity > 0),
    unit_price_minor bigint NOT NULL CHECK (unit_price_minor >= 0),
    currency text NOT NULL,
    PRIMARY KEY (cart_id, product_id, collection)
);

CREATE TABLE applied_events (
    event_id text PRIMARY KEY,
    cart_id text NOT NULL,
    aggregate_version bigint NOT NULL,
    event_type text NOT NULL,
    content_hash text NOT NULL,
    canonical_event text NOT NULL,
    source_topic text NOT NULL,
    source_partition integer NOT NULL,
    source_offset bigint NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (cart_id, aggregate_version)
);

CREATE TABLE quarantine (
    error_id uuid PRIMARY KEY,
    topic text NOT NULL,
    partition_id integer NOT NULL,
    record_offset bigint NOT NULL,
    record_key bytea,
    record_value bytea,
    event_id text,
    cart_id text,
    aggregate_version bigint,
    content_hash text,
    rejection_reason text NOT NULL CHECK (rejection_reason IN (
        'version_gap', 'malformed_event', 'unsupported_schema',
        'event_id_conflict', 'version_conflict', 'invalid_transition',
        'invalid_payload', 'key_mismatch')),
    rejection_detail text NOT NULL,
    quarantined_at timestamptz NOT NULL DEFAULT now(),
    resolution_status text NOT NULL DEFAULT 'unresolved'
        CHECK (resolution_status IN ('unresolved', 'resolved')),
    resolution_reason text
        CHECK (resolution_reason IN ('applied', 'duplicate_of_applied')),
    resolved_at timestamptz,
    resolved_by_topic text,
    resolved_by_partition integer,
    resolved_by_offset bigint,
    UNIQUE (topic, partition_id, record_offset),
    CHECK (
        (resolution_status = 'unresolved'
            AND resolution_reason IS NULL AND resolved_at IS NULL
            AND resolved_by_topic IS NULL AND resolved_by_partition IS NULL
            AND resolved_by_offset IS NULL)
        OR
        (resolution_status = 'resolved'
            AND event_id IS NOT NULL AND content_hash IS NOT NULL
            AND resolution_reason IS NOT NULL AND resolved_at IS NOT NULL
            AND resolved_by_topic IS NOT NULL
            AND resolved_by_partition IS NOT NULL
            AND resolved_by_offset IS NOT NULL)
    )
);

CREATE INDEX quarantine_unresolved_by_cart
    ON quarantine (cart_id) WHERE resolution_status = 'unresolved';
CREATE INDEX quarantine_unresolved_by_event
    ON quarantine (event_id, content_hash)
    WHERE resolution_status = 'unresolved';

CREATE FUNCTION quarantine_preserve_original() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.error_id, NEW.topic, NEW.partition_id, NEW.record_offset,
        NEW.record_key, NEW.record_value, NEW.event_id, NEW.cart_id,
        NEW.aggregate_version, NEW.content_hash, NEW.rejection_reason,
        NEW.rejection_detail, NEW.quarantined_at)
       IS DISTINCT FROM
       (OLD.error_id, OLD.topic, OLD.partition_id, OLD.record_offset,
        OLD.record_key, OLD.record_value, OLD.event_id, OLD.cart_id,
        OLD.aggregate_version, OLD.content_hash, OLD.rejection_reason,
        OLD.rejection_detail, OLD.quarantined_at)
    THEN
        RAISE EXCEPTION 'quarantine original record is immutable';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER quarantine_preserve_original
    BEFORE UPDATE ON quarantine
    FOR EACH ROW EXECUTE FUNCTION quarantine_preserve_original();

CREATE TABLE consumer_record_outcomes (
    topic text NOT NULL,
    partition_id integer NOT NULL,
    record_offset bigint NOT NULL,
    outcome text NOT NULL
        CHECK (outcome IN ('applied', 'duplicate', 'quarantined')),
    event_id text,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (topic, partition_id, record_offset)
);

CREATE FUNCTION outcome_is_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'consumer_record_outcomes rows are immutable';
END
$$;

CREATE TRIGGER outcome_is_immutable
    BEFORE UPDATE ON consumer_record_outcomes
    FOR EACH ROW EXECUTE FUNCTION outcome_is_immutable();

CREATE TABLE consumer_partition_init (
    group_id text NOT NULL,
    topic text NOT NULL,
    partition_id integer NOT NULL,
    initialized_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, topic, partition_id)
);
"""


class IncompatibleSchemaError(Exception):
    pass


def advisory_lock_key(*parts: str) -> int:
    """Deterministic signed 64-bit advisory-lock key.

    Derived from SHA-256 so every process and run computes the same key;
    Python's built-in hash() is salted per process and must not be used.
    """
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def connect(config: ConsumerConfig) -> psycopg.Connection:
    return psycopg.connect(
        host=config.pg_host,
        port=config.pg_port,
        dbname=config.pg_db,
        user=config.pg_user,
        password=config.pg_password,
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        options=(
            f"-c search_path={config.pg_schema} "
            f"-c statement_timeout={STATEMENT_TIMEOUT_MS} "
            f"-c lock_timeout={LOCK_TIMEOUT_MS}"
        ),
    )


def initialize_schema(conn: psycopg.Connection, schema: str) -> None:
    """Create the schema's tables, or verify an existing compatible schema.

    Serialised by an advisory lock so concurrent starters initialise one at
    a time. An existing schema that this code did not create at the current
    version is rejected without being changed.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (advisory_lock_key("schema-init", schema),),
            )
            cur.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
            )
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s",
                (schema,),
            )
            existing = {row[0] for row in cur.fetchall()}
            cur.execute(
                sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema))
            )
            if not existing:
                cur.execute(_DDL)
                cur.execute(
                    "INSERT INTO schema_meta (schema_version) VALUES (%s)",
                    (SCHEMA_VERSION,),
                )
            else:
                _verify_compatible(cur, schema, existing)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def _verify_compatible(cur: psycopg.Cursor, schema: str, existing: set[str]) -> None:
    if "schema_meta" not in existing:
        raise IncompatibleSchemaError(
            f"schema {schema!r} has tables but no schema_meta; "
            "it was not created by this consumer"
        )
    cur.execute("SELECT schema_version FROM schema_meta")
    row = cur.fetchone()
    found = row[0] if row is not None else None
    if found != SCHEMA_VERSION:
        raise IncompatibleSchemaError(
            f"schema {schema!r} has schema_version {found}, "
            f"expected {SCHEMA_VERSION}; use a fresh schema"
        )
    missing = EXPECTED_TABLES - existing
    if missing:
        raise IncompatibleSchemaError(
            f"schema {schema!r} is missing tables: {sorted(missing)}"
        )
