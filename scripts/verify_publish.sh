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

printf '\nFast verification passed.\n'
printf 'Verified staged files:\n'

while IFS= read -r -d '' path; do
  printf '  %s\n' "$path"
done < <(
  git diff --cached --name-only -z --diff-filter=ACMR
)
