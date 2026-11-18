from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class ConsumerConfig:
    bootstrap_servers: str
    group_id: str
    topic: str
    pg_host: str
    pg_port: int
    pg_db: str
    pg_user: str
    pg_password: str
    pg_schema: str
    session_timeout_ms: int = 10000
    sync_point: str | None = None
    sync_point_offset: tuple[int, int] | None = None


def read_env_file(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines; blank lines and # comments are ignored."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _parse_sync_offset(raw: str) -> tuple[int, int]:
    try:
        partition, offset = raw.split(":")
        return int(partition), int(offset)
    except ValueError as exc:
        raise ConfigError(
            "CONSUMER_SYNC_POINT_OFFSET must be '<partition>:<offset>'"
        ) from exc


def _integer(name: str, raw: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def load_config(
    environ: Mapping[str, str] | None = None, env_file: Path | None = None
) -> ConsumerConfig:
    """Build the configuration; process environment overrides the .env file."""
    values = read_env_file(env_file if env_file is not None else Path(".env"))
    values.update(os.environ if environ is None else environ)

    def required(name: str) -> str:
        value = values.get(name, "")
        if not value:
            raise ConfigError(f"{name} is required")
        return value

    schema = values.get("POSTGRES_SCHEMA") or "cart_projection"
    if not _SCHEMA_NAME.match(schema):
        raise ConfigError(
            "POSTGRES_SCHEMA must be a lowercase identifier "
            "(letters, digits, underscore)"
        )
    sync_offset = values.get("CONSUMER_SYNC_POINT_OFFSET")
    return ConsumerConfig(
        bootstrap_servers=values.get("KAFKA_BOOTSTRAP_SERVERS")
        or f"localhost:{values.get('REDPANDA_KAFKA_PORT') or '19092'}",
        group_id=required("CONSUMER_GROUP_ID"),
        topic=values.get("CONSUMER_TOPIC") or "cart-events",
        pg_host=values.get("POSTGRES_HOST") or "localhost",
        pg_port=_integer("POSTGRES_PORT", values.get("POSTGRES_PORT") or "5432"),
        pg_db=required("POSTGRES_DB"),
        pg_user=required("POSTGRES_USER"),
        pg_password=required("POSTGRES_PASSWORD"),
        pg_schema=schema,
        session_timeout_ms=_integer(
            "CONSUMER_SESSION_TIMEOUT_MS",
            values.get("CONSUMER_SESSION_TIMEOUT_MS") or "10000",
        ),
        sync_point=values.get("CONSUMER_SYNC_POINT") or None,
        sync_point_offset=_parse_sync_offset(sync_offset) if sync_offset else None,
    )
