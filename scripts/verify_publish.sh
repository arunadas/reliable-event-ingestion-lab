#!/usr/bin/env bash

set -euo pipefail

usage() {
  printf 'Usage: %s {fast|full}\n' "${0##*/}" >&2
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command_name="$1"

  command -v "$command_name" > /dev/null 2>&1 ||
    fail "Missing required command: $command_name"
}

run_check() {
  check_name="$1"
  shift

  printf '\n==> %s\n' "$check_name"
  "$@"
}

require_running_service() {
  service_name="$1"
  running_services="$2"

  case $'\n'"$running_services"$'\n' in
    *$'\n'"$service_name"$'\n'*)
      ;;
    *)
      printf 'ERROR: Required Compose service is not running: %s\n' \
        "$service_name" >&2
      printf 'Start the local infrastructure with:\n' >&2
      printf '  colima start\n' >&2
      printf '  docker compose up -d\n' >&2
      exit 1
      ;;
  esac
}

mode="${1:-}"

case "$mode" in
  fast|full)
    ;;
  *)
    usage
    exit 2
    ;;
esac

require_command git

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" ||
  fail "Not inside a Git repository."

cd "$repo_root"

git diff --cached --quiet &&
  fail "No staged changes to verify."

branch="$(git branch --show-current)"

printf 'Verification mode: %s\n' "$mode"
printf 'Branch: %s\n' "${branch:-DETACHED}"
printf 'Staged files:\n'

while IFS= read -r -d '' path; do
  printf '  %s\n' "$path"

  case "$path" in
    .env.example)
      ;;
    .env | .env.* | */.env | */.env.* | \
      .venv/* | */.venv/* | \
      __pycache__/* | */__pycache__/* | \
      .pytest_cache/* | */.pytest_cache/* | \
      .mypy_cache/* | */.mypy_cache/* | \
      .ruff_cache/* | */.ruff_cache/* | \
      .claude/CLAUDE.md | \
      .claude/worktrees/* | \
      docs/superpowers/*)
      fail "Unsafe staged path: $path"
      ;;
  esac
done < <(
  git diff --cached --name-only -z --diff-filter=ACMR
)

require_command gitleaks
require_command uv

run_check "Staged whitespace" git diff --cached --check

printf '\n==> Staged secret scan\n'
git diff --cached --binary | gitleaks stdin

run_check \
  "Ruff lint" \
  uv run --no-editable --locked ruff check src tests

run_check \
  "Ruff format" \
  uv run --no-editable --locked ruff format --check src tests

run_check \
  "Mypy" \
  uv run --no-editable --locked mypy src

run_check \
  "Unit tests" \
  uv run --no-editable --locked pytest tests/unit

if [[ "$mode" == "full" ]]; then
  require_command docker

  run_check \
    "Docker Compose configuration" \
    docker compose config --quiet

  printf '\n==> Running Compose services\n'
  running_services="$(docker compose ps --status running --services)"
  require_running_service "postgres" "$running_services"
  require_running_service "redpanda" "$running_services"

  run_check \
    "PostgreSQL readiness" \
    docker compose exec -T postgres sh -c \
    'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

  run_check \
    "Redpanda cluster health" \
    docker compose exec -T redpanda \
    rpk cluster health --exit-when-healthy

  run_check \
    "Integration tests" \
    uv run --no-editable --locked pytest tests/integration -m integration

  run_check \
    "Git history secret scan" \
    gitleaks git .

  printf '\nFull verification passed.\n'
else
  printf '\nFast verification passed.\n'
fi

printf 'Verified staged files:\n'

while IFS= read -r -d '' path; do
  printf '  %s\n' "$path"
done < <(
  git diff --cached --name-only -z --diff-filter=ACMR
)
