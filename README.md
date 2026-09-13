# Reliable Event Ingestion Lab

A reproducible laptop-scale lab for investigating correctness, idempotency, failure recovery, and replay in an event-driven ingestion pipeline.

## Status

Work in progress. The reproducible local development and container foundation is operational. Application components and experiments have not yet been implemented.

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

## Prerequisites

- An ARM64 or AMD64 development machine
- Docker Engine and Docker Compose
- Colima when using the recommended macOS setup
- `uv` for Python and dependency management
- Git

## Initial setup

Create the private local configuration:

```bash
cp .env.example .env
```

Replace the placeholder PostgreSQL password in .env. Never commit the real .env file.
Create the Python environment and install locked dependencies:

uv sync
On macOS with Colima, start the container runtime:
colima start --cpu 8 --memory 12 --disk 100
Download and start the project services:
docker compose pull
docker compose up -d


## Verify the infrastructure
Check container state:
docker compose ps
Check PostgreSQL:
docker compose exec postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
Check Redpanda:
docker compose exec redpanda rpk cluster health
Redpanda Console is available at http://localhost:8080.

## Stop and resume the lab
Stop containers while preserving their data:
docker compose stop
Resume the stopped containers:
docker compose start
Remove the containers and project network while preserving named volumes:
docker compose down
Delete the containers, network, and all project data:
docker compose down -v
The -v operation is destructive and should be used only when the saved PostgreSQL and Redpanda data is no longer needed.
Stop the shared Colima virtual machine after stopping project containers:
colima stop
