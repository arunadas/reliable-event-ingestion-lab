from __future__ import annotations

import subprocess

import pytest


@pytest.mark.integration
def test_postgres_and_redpanda_are_healthy() -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "redpanda",
            "rpk",
            "cluster",
            "health",
            "--exit-when-healthy",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Healthy:" in result.stdout
    assert "true" in result.stdout.lower()
