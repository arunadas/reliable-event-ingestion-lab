from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
VERIFIER = PROJECT_ROOT / "scripts" / "verify_publish.sh"


def run_command(
    *args: str,
    cwd: Path,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()

    run_command("git", "init", "--quiet", cwd=repository)
    run_command(
        "git",
        "config",
        "user.name",
        "Safe Publish Test",
        cwd=repository,
    )
    run_command(
        "git",
        "config",
        "user.email",
        "safe-publish@example.invalid",
        cwd=repository,
    )

    (repository / ".gitignore").write_text(
        ".env\n.env.*\n!.env.example\n.claude/worktrees/\n",
        encoding="utf-8",
    )
    (repository / "README.md").write_text("# Test repository\n", encoding="utf-8")

    run_command("git", "add", ".gitignore", "README.md", cwd=repository)
    run_command(
        "git", "commit", "--quiet", "-m", "test: initialize repository", cwd=repository
    )

    return repository


def run_verifier(
    repo: Path, mode: str | None = None
) -> subprocess.CompletedProcess[str]:
    command = ["bash", str(VERIFIER)]
    if mode is not None:
        command.append(mode)

    return run_command(
        *command,
        cwd=repo,
        check=False,
        env=os.environ.copy(),
    )


def stage_file(
    repo: Path,
    relative_path: str,
    content: str = "test\n",
    *,
    force: bool = False,
) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    command = ["git", "add"]
    if force:
        command.append("--force")
    command.append(relative_path)

    run_command(*command, cwd=repo)


def test_rejects_missing_mode(repo: Path) -> None:
    result = run_verifier(repo)

    assert result.returncode != 0
    assert "Usage:" in result.stderr


def test_rejects_empty_staging_area(repo: Path) -> None:
    result = run_verifier(repo, "fast")

    assert result.returncode != 0
    assert "No staged changes" in result.stderr


def test_allows_env_example_but_rejects_private_env(repo: Path) -> None:
    stage_file(repo, ".env.example", "EXAMPLE_VALUE=replace_me\n")
    allowed_result = run_verifier(repo, "fast")

    assert "Unsafe staged path: .env.example" not in allowed_result.stderr

    stage_file(repo, ".env.local", "SECRET_VALUE=test-only\n", force=True)
    rejected_result = run_verifier(repo, "fast")

    assert rejected_result.returncode != 0
    assert "Unsafe staged path: .env.local" in rejected_result.stderr


def test_rejects_forced_staged_worktree_artifact(repo: Path) -> None:
    path = ".claude/worktrees/demo/generated.py"
    stage_file(repo, path, force=True)

    result = run_verifier(repo, "fast")

    assert result.returncode != 0
    assert f"Unsafe staged path: {path}" in result.stderr


def test_handles_staged_filename_with_spaces(repo: Path) -> None:
    path = "docs/name with spaces.md"
    stage_file(repo, path)

    result = run_verifier(repo, "fast")

    assert path in result.stdout
    assert f"Unsafe staged path: {path}" not in result.stderr
