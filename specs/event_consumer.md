# Reliable Event Consumer Specification

## Purpose

The event consumer is a Python application that reads retail cart events from
Redpanda and incrementally maintains cart projections in PostgreSQL. Its main
goal is correctness during duplicate delivery, retries, crashes, replay, and
consumer-group rebalancing.

## Scope

Phase 1 provides a consumer group with these characteristics:

- Input comes from the `cart-events` topic.
- Redpanda assigns the topic's three partitions across up to three consumer
  processes.
- Each process uses one poll loop and processes one record at a time.
- Each record is handled in one PostgreSQL transaction.
- Broker offsets are committed manually only after durable handling.
- Consumer processes may run concurrently, but records assigned to one process
  are handled sequentially.

Replay tooling, quarantine scheduling, archival, and deployment orchestration
are outside this consumer's scope.

## Supported events

- `CartCreated`
- `CartItemAdded`
- `CartItemRemoved`
- `CartItemSavedForLater`
- `SavedForLaterItemRemoved`
- `SavedForLaterItemMovedToCart`
- `CartPurchased`

Payload and quantity-transfer rules must remain consistent with
[`event_generator.md`](event_generator.md).

## Reliability contract

For every source record, the consumer must:

1. Preserve the original key and value bytes.
2. Validate the envelope and message key.
3. Serialize work for the cart when a usable cart ID is available.
4. Apply, recognize as a duplicate, or quarantine the record durably.
5. Update the source-record outcome in the same database transaction.
6. Commit the next broker offset only after the database transaction commits.

The transaction must atomically contain all applicable changes:

- Cart projection updates
- Applied-event ledger entry
- Quarantine entry or resolution metadata
- Source-record outcome
- Recovery-status update

If PostgreSQL fails before commit, the transaction rolls back and the source
offset does not advance. If PostgreSQL commits but the broker offset commit is
lost, redelivery must produce no additional business effect.

## Source identity and outcomes

A source record is identified by `(topic, partition, offset)` within one source
cluster and topic lifetime.

`consumer_record_outcomes` records the initial durable outcome:

- `applied`
- `duplicate`
- `quarantined`

The initial outcome is immutable. Redelivery of the same source coordinate
must not create another outcome. An identical event received at a different
offset is a distinct source record and may have a `duplicate` outcome.

Operational attempt and retry counters are separate from these durable
reconciliation outcomes.

## Event identity and duplicate handling

`event_id` identifies a logical business event.

- Reprocessing an identical applied event is a successful no-op.
- The same `event_id` with changed immutable content is an
  `event_id_conflict`.
- A different event ID claiming an already-applied cart version is a
  `version_conflict`.
- Duplicate checks happen before stale-version rejection.
- Only successfully applied events belong in the applied-event ledger.
- A quarantined event is not an applied duplicate.

Immutable content is compared using canonical, sorted-key JSON and includes
the complete event envelope, including `produced_at`, `producer_instance_id`,
and `producer_sequence`. Topic, partition, offset, and transport headers are
excluded from the comparison.

## Structural validation

Structural validation must retain the original bytes even when parsing fails.
The consumer must not access an event ID, version, or cart field that could not
be parsed safely.

The message key must equal `aggregate.id`. A mismatch is quarantined as
`key_mismatch`. A rejected record never creates a cart projection.

Only input-validation and business-rule failures are quarantined. PostgreSQL
connectivity failures, timeouts, deadlocks, broker failures, and unexpected
application exceptions are operational failures and must stop or retry
processing without advancing past the unhandled record.

## State-transition rules

- A new cart begins with `CartCreated` at `aggregate.version = 1`.
- Each subsequent event version must equal the stored version plus one.
- A second `CartCreated` is invalid, even at the expected next version.
- Every mutation is validated against the current persisted cart state.
- Item quantities can never become negative.
- Removing or moving a saved item requires sufficient saved quantity.
- `CartPurchased` requires at least one active item.
- Purchase `item_count`, `total_amount_minor`, and `currency` must match the
  active cart projection. Saved-for-later items are excluded.
- New business events after purchase are invalid.
- An identical previously applied event remains a duplicate even after
  purchase.
- Valid partial cart state is persisted without waiting for purchase.

The projection has separate status dimensions:

- `business_status`: `open` or `purchased`
- `recovery_status`: `clear`, `pending_retry`, or `needs_review`

Recovery status uses this precedence:

1. `needs_review` when a non-retryable unresolved rejection exists.
2. `pending_retry` when an unresolved recoverable version gap exists.
3. `clear` when neither condition exists.

Status is recomputed while holding the cart lock whenever a rejection is
created or resolved.

## Version gaps

An event whose version is greater than the next expected version is
quarantined as `version_gap`. It must not advance the cart version.

For arrival order `1, 2, 5, 3, 4`:

1. Version 5 is quarantined.
2. Versions 3 and 4 apply normally.
3. Redelivery of the unchanged version 5 applies it exactly once.
4. Matching unresolved quarantine rows are marked resolved.

The consumer does not scan quarantine automatically. Reevaluation occurs only
when unchanged content is delivered again, either through source redelivery or
a separate replay process.

## PostgreSQL quarantine

The dead-letter queue is a PostgreSQL quarantine table, not a separate broker
topic. A quarantine row stores:

- Original key and value bytes
- Topic, partition, and offset
- Nullable parsed event ID and cart ID
- Rejection reason
- Stable `error_id`
- Immutable content hash when available
- Resolution status and resolving source coordinates

Quarantine persistence and the source-record outcome are committed in one
transaction. If persistence fails, the source offset does not advance.

The original bytes and rejection reason are immutable. Resolution metadata may
change. Rows without an event ID or content hash cannot be resolved through
content matching.

Supported rejection reasons include:

| Reason | Treatment |
| --- | --- |
| `version_gap` | Eligible for reevaluation after predecessors apply. |
| `malformed_event` | Requires investigation or corrected replay input. |
| `unsupported_schema` | Requires compatible consumer code or investigation. |
| `event_id_conflict` | Conflicting evidence is preserved for investigation. |
| `version_conflict` | Requires investigation; never replay blindly. |
| `invalid_transition` | Requires investigation. |
| `invalid_payload` | Requires investigation. |
| `key_mismatch` | Routing-contract violation; the event is not applied. |

An identical applied duplicate is a successful no-op and is not quarantined.

## Cart serialization and concurrency

Application, rejection, and cart creation for one cart are serialized with a
PostgreSQL advisory transaction lock derived deterministically from the schema
and cart ID.

A cart row is created only after a valid `CartCreated` passes every check.
Database unique constraints protect cart IDs, event IDs, cart versions, source
coordinates, and quarantine identities as appropriate.

If a concurrent transaction wins a unique-key race, the losing transaction
rolls back and reevaluates against committed state. Two consumers attempting
the same event concurrently must produce one business effect.

## Offset rules

After durably handling a record at offset N, the consumer commits N+1 for that
partition. Applied events, recognized duplicates, and durably quarantined
records all count as handled.

The consumer must never commit past an unhandled delivered record. Contiguous
means broker delivery order; it does not require waiting for offsets that the
broker did not deliver.

For an existing group, processing resumes from valid committed offsets. For a
new group, processing begins at the earliest retained offset and initialization
is recorded durably for each group, topic, and partition.

An initialized partition with no committed offset, or an offset outside the
retained low and high watermarks, is an explicit recovery error. The consumer
must not silently skip to a timestamp or the latest offset.

## Retries and operational failures

Transient PostgreSQL and retryable broker operations use bounded exponential
backoff with five total attempts, including the initial attempt.

- A database retry repeats the complete transaction on a usable connection.
- A lost database commit acknowledgement is reevaluated through deduplication.
- Exhausted retries cause a non-zero exit without advancing the source offset.
- Unexpected application exceptions are logged and stop processing.
- An empty poll is not a broker failure.

While idle, the consumer periodically probes the broker with an explicit
timeout. Five consecutive failed probes are treated as an outage and cause a
non-zero exit. A successful probe resets the failure count.

## Partition ownership

When a partition is revoked, the consumer drops its local tracker state and
skips any already-fetched records for that partition.

An offset commit rejected because the consumer no longer owns the partition is
not retried. Work on that partition stops immediately. If the group neither
revokes nor reassigns it within 60 seconds, the process exits non-zero rather
than remaining alive while unable to make progress.

A reassigned partition resumes from its committed offset, so skipped records
are delivered to the current owner.

## Shutdown

On `SIGINT` or `SIGTERM`, the consumer stops polling, finishes or rolls back the
in-flight transaction, and completes its associated offset commit when
appropriate.

Broker-client close is bounded at 30 seconds. A forced close exits non-zero and
does not create a separate shutdown offset commit. Offsets are committed only
immediately after durable handling of individual records.

## Schema and rebuilds

One PostgreSQL schema contains the projection, applied-event ledger,
quarantine, source outcomes, and initialization metadata. Startup schema
initialization is serialized, and an incompatible existing schema is rejected
without modification.

A complete rebuild requires retained source history or an archive. It replays
into a separate empty schema with fresh projection and deduplication tables;
the live schema remains untouched.

## Configuration

Configuration includes:

- Broker addresses
- Input topic
- Consumer group ID
- PostgreSQL connection information
- Projection schema
- Retry and timeout settings

Local secrets belong in ignored `.env` files and must never be committed.

## Acceptance criteria

- A valid cart lifecycle produces the expected PostgreSQL projection.
- Duplicate delivery and full replay create no duplicate business effects.
- A crash after database commit but before offset commit is safe.
- Version gaps and conflicting events are quarantined with specific reasons.
- Quarantine failure does not advance the source offset.
- Original malformed or conflicting evidence is preserved.
- Restart and reassignment resume safely from committed offsets.
- Concurrent attempts to apply the same event produce one business effect.
- Applied, duplicate, quarantined, and unresolved counts reconcile with the
  durable source-record outcomes.
- A fresh rebuild does not reuse deduplication state from the live projection.
- PostgreSQL or broker outages cause non-zero exit without skipping unhandled
  records.
