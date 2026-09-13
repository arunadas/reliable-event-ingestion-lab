# Reliable Event Ingestion Lab

A reproducible laptop-scale lab for investigating correctness, idempotency, failure recovery, and replay in an event-driven ingestion pipeline.

## Status

Work in progress. The local development and container foundation is currently being prepared.

## Planned architecture

The initial working slice will use:

- A synthetic Python event producer
- Redpanda as the event broker
- A Python validation and ingestion consumer
- PostgreSQL as the transactional destination
- A dead-letter topic for malformed or rejected events
- Automated unit and integration tests

## Project goals

- Define explicit correctness and reliability invariants.
- Reproduce duplicate, malformed-event, restart, and replay scenarios.
- Compare naive ingestion with idempotent processing.
- Save the evidence required to support a technical article.
- Make the complete lab reproducible on an ARM64 development machine.

## Environment

- Python 3.12 managed with `uv`
- Colima
- Docker and Docker Compose
- `pytest`, `ruff`, and `mypy`

Detailed setup and experiment instructions will be added as the lab develops.
