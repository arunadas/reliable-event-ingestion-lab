# Event Generator Specification

## Purpose
event genrator is a python application which simulates online retail purchase and creates cart events

## Scope
Phase 1 - generate generates one cart lifecycle containing 3-4 events.

## Event Lifecycle
-CartCreated
-CartItemAdded
-CartItemSavedForLater
-CartPurchased

### Event sequence rules
CartCreated
   ↓
CartItemAdded (one or more)
   ↓
CartItemSavedForLater (optional, zero or more)
   ↓
CartPurchased




## Event Envelope

{
  "event_id": "01K...",
  "event_type": "CartCreated",
  "schema_version": 1,
  "occurred_at": "2026-09-14T19:10:12.123Z",
  "produced_at": "2026-09-14T19:10:12.125Z",
  "producer": "cart-simulator",
  "producer_instance_id": "generator-2",
  "producer_sequence": 4811,
  "aggregate": {
    "type": "cart",
    "id": "cart-456",
    "version": 16
  },
  "customer_id": "customer-123",
  "correlation_id": "session-789",
  "causation_id": "command-345"
}

{
  "event_id": "01K...",
  "event_type": "CartItemAdded",
  "schema_version": 1,
  "occurred_at": "2026-09-14T19:10:14.123Z",
  "produced_at": "2026-09-14T19:10:14.185Z",
  "producer": "cart-simulator",
  "producer_instance_id": "generator-2",
  "producer_sequence": 4812,
  "aggregate": {
    "type": "cart",
    "id": "cart-456",
    "version": 17
  },
  "customer_id": "customer-123",
  "correlation_id": "session-789",
  "causation_id": "command-345",
  "payload": {
    "product_id": "sku-123",
    "quantity_delta": 1,
    "unit_price_minor": 1599,
    "currency": "USD"
  }
}

{
  "event_id": "01K...",
  "event_type": "CartItemSavedForLater",
  "schema_version": 1,
  "occurred_at": "2026-09-14T19:10:20.123Z",
  "produced_at": "2026-09-14T19:10:20.195Z",
  "producer": "cart-simulator",
  "producer_instance_id": "generator-2",
  "producer_sequence": 4813,
  "aggregate": {
    "type": "cart",
    "id": "cart-456",
    "version": 18
  },
  "customer_id": "customer-123",
  "correlation_id": "session-789",
  "causation_id": "command-345",
  "payload": {
    "product_id": "sku-123",
    "quantity_delta": 1,
    "unit_price_minor": 1599,
    "currency": "USD"
  }
}

{
  "event_id": "01K...",
  "event_type": "CartPurchased",
  "schema_version": 1,
  "occurred_at": "2026-09-14T19:10:26.123Z",
  "produced_at": "2026-09-14T19:10:26.195Z",
  "producer": "cart-simulator",
  "producer_instance_id": "generator-2",
  "producer_sequence": 4814,
  "aggregate": {
    "type": "cart",
    "id": "cart-456",
    "version": 19
  },
  "customer_id": "customer-123",
  "correlation_id": "session-789",
  "causation_id": "command-345",
  "payload": {
    "product_id": "sku-456",
     "order_id": 12,
    "total_amount_minor": 2345,
     "currency" : "USD",
    "item_count" : 4
  }

}


## Event-Type Payloads
CartCreated:
  customer_id

CartItemAdded:
  product_id, quantity_delta, unit_price_minor, currency

CartItemSavedForLater:
  product_id, quantity

`CartItemSavedForLater` moves the specified quantity from the active cart
to saved-for-later. The quantity cannot exceed the active quantity.

CartPurchased:
  order_id, total_amount_minor, currency, item_count

`total_amount_minor` equals the sum of active item quantities multiplied
by their unit prices. Saved-for-later items are excluded.


## Field Semantics
- `event_id`: unique immutable ULID; retries reuse the same ID.
- `occurred_at`: when the simulated business action happened.
- `produced_at`: when the event was sent.
- `producer_sequence`: increases per producer instance.
- `aggregate.id`: cart ID and Redpanda message key.
- `aggregate.version`: increases independently for each cart.
- `correlation_id`: shared by events in one simulated shopping session.
- `causation_id`: ID of the simulated command that caused the event.
- Money uses integer minor units; floating-point prices are prohibited.

## Redpanda Output Contract

- Publish JSON events to the Redpanda topic `cart-events`.
- Use `aggregate.id` (`cart_id`) as the message key.
- Encode keys and values as UTF-8.
- Wait for broker acknowledgement before considering publication successful.

## Configuration

- Broker addresses
- Topic name
- Event rate per second
- Number of simulated carts
- Run duration or maximum event count
- Random seed
- Producer instance ID
- Duplicate probability
- Delay probability and maximum delay


## Retry and Failure Behavior
If publication fails, retry the same serialized event with the same
`event_id`, cart version, and producer sequence.
A retry must not create a new logical event.
Retry transient publication failures using bounded exponential backoff.
Retry at most 5 times. If exhausted, log the failure and exit non-zero.
All attempts reuse the exact serialized event.


## Logging and Metrics
Log successful publication with event_id, cart_id, aggregate_version,
topic, partition, and broker offset.

Logs are for observation only and must not be used to restore generator state.
Each generator run receives a new producer_instance_id.

events_generated_total
events_published_total
publication_retries_total
publication_failures_total
publish_latency_ms
run_duration_seconds

## Business Invariants
Items cannot be added before CartCreated
A purchase cart can not receive additional events.
An item must exist before being saved for later.
aggregate.version starts at 1 and increments by 1 for every cart event


## Antipatterns

- Do not generate a new `event_id` during a publication retry.
- Do not use floating-point values for money.
- Do not publish cart events without a `cart_id` key.
- Do not reuse an event ID for modified content.
- Do not decrease or reuse a cart aggregate version.
- Do not publish events after `CartPurchased`.
- Do not rely on timestamps to establish cart-event order.
- Do not embed broker credentials in source code.


## Acceptance Criteria

- Given the same random seed and configuration, the generator produces
  the same business-event sequence, excluding wall-clock timestamps.
- A fixed random seed reproduces the same carts, products, quantities,
prices, and event ordering. Timestamps and generated identifiers may differ.
- Every event conforms to the event schema.
- All events for one cart use the same Redpanda key.
- Cart versions begin at 1 and increase without gaps.
- Event IDs are unique across logical events.
- Publication retries retain the original event ID and payload.
- Graceful shutdown flushes outstanding producer records.
- Unit tests cover every event type and state transition.

## Non-Goals
- Order lifecycle events after `CartPurchased`
- Payment processing
- High-volume production
- Watermark and late-event simulation in Phase 1
Invalid-event probability
restartable generation, add a proper checkpoint file or database
