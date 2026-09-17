# Reliable event Ingestion Lab

## Project Overview
How can an ingestion platform provide effectively-once business outcomes when events may be duplicated, delayed, or replayed?

## Technology Stack
- **Architecture:** Event-driven ingestion
- **Application language:** Python
- **Event broker:** Redpanda
- **Target database:** PostgreSQL
- **Object storage:** MinIO
- **Container orchestration:** Docker Compose

## Core Requirements

### Event generator simulator
- online shopping cart events 
- python generator code simulator 
- refer specs/event-generator.md for details

### stream events (redPanda)
- redpanda used for laptop scale lab experiments
- one topic with 3 partitions hash key on cart_id 
- events publish from Event generation simulator

### consumer group (python)
- A Python consumer group with up to three active consumer instances.
- Redpanda dynamically assigns the three partitions across those instances.
- Each partition is processed sequentially.
- Process each partition in order, while different partitions run concurrently.
- Incrementally apply events to PostgreSQL cart projections while preserving per-partition order and preventing duplicate business effects.
- publish to target postgreSQL
- refer specs/event-consumer.md for details

## System Boundary
Generated events (python) → Redpanda → Python consumer → PostgreSQL
                              └→ archival consumer → MinIO

## Success Criteria
- Replaying the same event produces no additional business change.
- Crashing after the database commit but before the offset commit remains safe.
- A modified payload with an existing event_id is detected as a conflict.
- A version gap is detected rather than silently applied.
- PostgreSQL can be rebuilt from archived raw events.
- Tests reconcile generated, processed, duplicate, rejected, and pending events.

## Data Ownership
PostgreSQL is the target projection database, not the source of events.
Its cart state is derived from immutable events consumed from Redpanda.
The projection must be rebuildable by replaying archived events.

### performance target
- start with one event per transaction for correctness and failure testing.
- Then use small micro-batches, such as 100-500 events or a 50-200 ms collection window.

### Deliverables
compose.yaml
database migrations/schema
event schema
producer and consumer configuration
archival/replay utility
unit tests
integration/failure tests
experiment definitions
experiment results
README/run instructions
