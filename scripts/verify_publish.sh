#!/usr/bin/env bash

set -euo pipefail

usage() {
  printf 'Usage: %s {fast|full}\n' "${0##*/}" >&2
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
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
