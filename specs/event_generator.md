# Event Generator Specification

## Purpose
The event generator is a Python application that simulates online retail
shopping sessions and produces cart events.

## Scope
Each simulated cart lifecycle begins with CartCreated, contains one or
more CartItemAdded events and zero or more valid cart mutation events,
and ends with exactly one CartPurchased event.

## Event Lifecycle
- CartCreated
- CartItemAdded
- CartItemRemoved
- CartItemSavedForLater
- SavedForLaterItemRemoved
- SavedForLaterItemMovedToCart
- CartPurchased

### Event sequence rules
CartCreated
    ↓
CartItemAdded (at least one)
    ↓
Zero or more valid cart actions:
    - CartItemAdded
    - CartItemRemoved
    - CartItemSavedForLater
    - SavedForLaterItemRemoved
    - SavedForLaterItemMovedToCart
    ↓
CartPurchased




## Event Envelope

{
  "event_id": "01K...001",
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
    "version": 1
  },
  "customer_id": "customer-123",
  "correlation_id": "session-789",
  "causation_id": "command-001"
}

{
  "event_id": "01K...002",
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
    "version": 2
  },
  "customer_id": "customer-123",
  "correlation_id": "session-789",
  "causation_id": "command-002",
  "payload": {
    "product_id": "sku-123",
    "quantity_delta": 4,
    "unit_price_minor": 1599,
    "currency": "USD"
  }
}

{
  "event_id": "01K...003",
  "event_type": "CartItemRemoved",
  "schema_version": 1,
  "occurred_at": "2026-09-14T19:10:14.123Z",
  "produced_at": "2026-09-14T19:10:14.185Z",
  "producer": "cart-simulator",
  "producer_instance_id": "generator-2",
  "producer_sequence": 4813,
  "aggregate": {
    "type": "cart",
    "id": "cart-456",
    "version": 3
  },
  "customer_id": "customer-123",
  "correlation_id": "session-789",
  "causation_id": "command-003",
  "payload": {
    "product_id": "sku-123",
    "quantity": 1
  }
}

{
  "event_id": "01K...004",
  "event_type": "CartItemSavedForLater",
  "schema_version": 1,
  "occurred_at": "2026-09-14T19:10:20.123Z",
  "produced_at": "2026-09-14T19:10:20.195Z",
  "producer": "cart-simulator",
  "producer_instance_id": "generator-2",
  "producer_sequence": 4814,
  "aggregate": {
    "type": "cart",
    "id": "cart-456",
    "version": 4
  },
  "customer_id": "customer-123",
  "correlation_id": "session-789",
  "causation_id": "command-004",
  "payload": {
    "product_id": "sku-123",
    "quantity": 2
  }
}

{
  "event_id": "01K...005",
  "event_type": "SavedForLaterItemRemoved",
  "schema_version": 1,
  "occurred_at": "2026-09-14T19:10:20.123Z",
  "produced_at": "2026-09-14T19:10:20.195Z",
  "producer": "cart-simulator",
  "producer_instance_id": "generator-2",
  "producer_sequence": 4815,
  "aggregate": {
    "type": "cart",
    "id": "cart-456",
    "version": 5
  },
  "customer_id": "customer-123",
  "correlation_id": "session-789",
  "causation_id": "command-005",
  "payload": {
    "product_id": "sku-123",
    "quantity":1
  }
}

{
  "event_id": "01K...006",
  "event_type": "SavedForLaterItemMovedToCart",
  "schema_version": 1,
  "occurred_at": "2026-09-14T19:10:20.123Z",
  "produced_at": "2026-09-14T19:10:20.195Z",
  "producer": "cart-simulator",
  "producer_instance_id": "generator-2",
  "producer_sequence": 4816,
  "aggregate": {
    "type": "cart",
    "id": "cart-456",
    "version": 6
  },
  "customer_id": "customer-123",
  "correlation_id": "session-789",
  "causation_id": "command-006",
  "payload": {
    "product_id": "sku-123",
    "quantity": 1
  }
}

{
  "event_id": "01K...007",
  "event_type": "CartPurchased",
  "schema_version": 1,
  "occurred_at": "2026-09-14T19:10:26.123Z",
  "produced_at": "2026-09-14T19:10:26.195Z",
  "producer": "cart-simulator",
  "producer_instance_id": "generator-2",
  "producer_sequence": 4817,
  "aggregate": {
    "type": "cart",
    "id": "cart-456",
    "version": 7
  },
  "customer_id": "customer-123",
  "correlation_id": "session-789",
  "causation_id": "command-007",
  "payload": {
     "order_id": 12,
    "total_amount_minor": 3198,
     "currency" : "USD",
    "item_count" : 2
  }

}


## State Transition Semantics

CartItemRemoved                 → subtract from active
CartItemSavedForLater           → active to saved
SavedForLaterItemRemoved        → subtract from saved
SavedForLaterItemMovedToCart    → saved to active

CartItemRemoved removes the specified positive quantity from the active
cart. The product must exist in the active cart, and quantity must not
exceed its active quantity. It does not affect saved-for-later quantity.

SavedForLaterItemRemoved permanently removes the specified positive
quantity from saved-for-later. The product must exist in saved-for-later,
and quantity must not exceed its saved quantity. It does not affect the
active cart.

SavedForLaterItemMovedToCart moves the specified positive quantity from
saved-for-later to the active cart. The product must exist in
saved-for-later, and quantity must not exceed its saved quantity. The
saved quantity decreases and the active quantity increases by the same
amount. The product retains its original unit price and currency.

`CartItemSavedForLater` moves the specified quantity from the active cart
to saved-for-later. The quantity cannot exceed the active quantity.

CartPurchased:
  order_id, total_amount_minor, currency, item_count

`total_amount_minor` equals the sum of active item quantities multiplied
by their unit prices. Saved-for-later items are excluded.

## Payload Contract
CartCreated
  no payload

CartItemAdded
  product_id: string
  quantity_delta: positive integer
  unit_price_minor: non-negative integer
  currency: string

CartItemRemoved
  product_id: string
  quantity: positive integer

CartItemSavedForLater
  product_id: string
  quantity: positive integer

SavedForLaterItemRemoved
  product_id: string
  quantity: positive integer

SavedForLaterItemMovedToCart
  product_id: string
  quantity: positive integer

CartPurchased
  order_id: non-negative integer
  total_amount_minor: non-negative integer
  currency: string
  item_count: non-negative integer


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
- Items cannot be added before CartCreated
- A purchased cart cannot receive additional events.
- An item must exist before being saved for later.
- aggregate.version starts at 1 and increments by 1 for every cart event
- All mutation quantities must be positive integers.
- An active item can be removed only if it exists in the active cart.
- Removed quantity cannot exceed active quantity.
- An item can be saved for later only if it exists in the active cart.
- Saved quantity cannot exceed active quantity.
- A saved item can be removed only if it exists in saved-for-later.
- Removed saved quantity cannot exceed saved quantity.
- An item can be moved back to the cart only if it exists in saved-for-later.
- Moved quantity cannot exceed saved quantity.
- Moving a saved item back decreases saved quantity and increases active
  quantity by exactly the same amount.
- When a product's quantity reaches zero, remove that product from the
  corresponding active or saved-for-later collection. Zero-quantity
  entries must not be retained.
- Product price and currency remain unchanged when moving between active
  and saved-for-later.
- No mutation event can occur after CartPurchased.
- Generate exactly one initial CartItemAdded event.
- Choose a mutation count uniformly from 0 through 5, inclusive.
- For each mutation, construct the set of action types that are valid for
  the current state and choose one uniformly from that set.
- CartItemAdded is always a valid mutation.
- Removal, save, and move actions are valid only when their preconditions
  are satisfied and the action leaves at least one active cart item.
- Before CartPurchased, the simulator must ensure that at least one active
  item remains. A mutation that would reduce the total active quantity to
  zero must either be skipped or limited so that one active unit remains.
- CartPurchased requires at least one active item.
- A mutation is valid only if it leaves at least one active item in the cart.



## Antipatterns

- Do not generate a new `event_id` during a publication retry.
- Do not use floating-point values for money.
- Do not remove an active cart item unless it has been added and remains active.
- Do not remove a saved-for-later item unless it exists in saved-for-later.
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
- Active-item removal never exceeds active quantity.
- Saved-item removal never exceeds saved quantity.
- Moving a saved item back to the cart decreases saved quantity and
  increases active quantity by the same amount.
- Moving an item back preserves its unit price and currency.
- Purchase item_count equals the sum of remaining active quantities.
- Purchase total_amount_minor equals the sum of active quantity multiplied
  by unit price after all removals, saves, and moves.
- Saved-for-later quantities remain excluded from purchase totals.
- No zero or negative mutation quantity is generated.
- Aggregate versions remain sequential across all new event types.
- Given the same seed, all new action choices and quantities are deterministic.
- The generator selects only actions that are valid for the current active
  and saved-for-later state; it never emits an invalid transition and then
  attempts to repair it afterward.
- Products whose active or saved quantity reaches zero are absent from the
  corresponding state collection.
- Every generated cart reaches CartPurchased with at least one active item.

## Non-Goals
- Order lifecycle events after `CartPurchased`
- Payment processing
- High-volume production
- Watermark and late-event simulation in Phase 1
Invalid-event probability
restartable generation, add a proper checkpoint file or database
