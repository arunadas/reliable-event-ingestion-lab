# Lab Environment

Recorded on September 12, 2026.

## Host system

| Property | Value |
|---|---|
| Computer | 14-inch MacBook Pro |
| Processor | Apple M4 Pro |
| CPU cores | 14 total: 10 performance and 4 efficiency |
| Memory | 24 GB unified memory |
| Architecture | ARM64 |
| Operating system | macOS 15.7.9 |
| Available storage at setup | Approximately 744 GiB |

Machine hostname, serial number, hardware UUID, user paths, and other personal identifiers are intentionally excluded.

## Container environment

| Component | Version or allocation |
|---|---|
| Colima | 0.10.3 |
| Docker CLI | 29.8.0 |
| Docker Engine | 29.5.2 |
| Docker Compose | 5.5.1 |
| Colima CPUs | 8 |
| Colima memory | 12 GiB |
| Colima disk capacity | 100 GiB |
| Container architecture | Linux ARM64 |

## Project runtime

| Component | Version |
|---|---|
| Python | 3.12.10 |
| uv | 0.7.9 |
| Redpanda | 26.2.2 |
| Redpanda Console | 3.11.0 |
| PostgreSQL | 17.11 |
| confluent-kafka | 2.15.1 |
| psycopg | 3.3.5 |
| pytest | 9.0.2 |
| Ruff | 0.14.10 |
| mypy | 1.19.1 |

Exact Python dependency versions are recorded in `uv.lock`.

## Resource boundary

This is a laptop-scale development environment. Performance results apply only to the documented configuration, dataset, workload, and measurement method. They must not be interpreted as production-capacity estimates.

## Idle infrastructure baseline

Measured with all three services running and no application topics or workload.

| Measurement | Observed value |
|---|---|
| Redpanda memory | 848.6 MiB |
| PostgreSQL memory | 25.73 MiB |
| Redpanda Console memory | 29.34 MiB |
| Container image storage | 1.412 GB |
| Persistent volume storage | 64.9 MB |
| Active containers | 3 |

This snapshot confirms that the services start successfully within the allocated laptop resources. It is not a throughput or production-capacity benchmark.