# Development and Safe Publication Workflow

## Purpose

This guide describes how to review, verify, commit, and publish an intentional
change. The verification tools inspect the work; they never stage files,
create commits, push branches, or start infrastructure.

## Prerequisites

Fast verification requires:

- Git
- `uv`
- Gitleaks

Full verification additionally requires:

- Docker and Docker Compose
- Colima on the recommended macOS setup
- The repository's PostgreSQL and Redpanda Compose services already running

Start infrastructure separately when full verification is needed:

```bash
colima start
docker compose up -d
docker compose ps
```

The verification workflow does not run these commands for you.

## Daily publication sequence

Review the current branch and working tree:

```bash
git status --short --branch
```

Stage only the files that belong to one coherent change:

```bash
git add <intentional-files>
```

Run fast verification for ordinary code or documentation commits:

```bash
make verify-publish
```

Review the staged summary, commit, and push only after verification passes:

```bash
git diff --cached --stat
git commit -m "<type>: <meaningful description>"
git push origin main
```

## When to use full verification

Use full verification for milestones and changes that affect containers,
PostgreSQL, Redpanda, or integration behavior:

```bash
make verify-publish-full
```

Full mode runs every fast check, validates the Compose configuration and
service health, runs integration tests, and scans committed Git history for
secrets.

## Understanding failures

Every check prints a heading before it runs. A non-zero exit means publication
must stop at that check. Fix the reported issue, stage the intended correction,
and run the same verification command again.

Common failure categories include:

- An unsafe or private staged path
- Whitespace, lint, formatting, type-check, or test errors
- A possible secret in the staged patch or Git history
- A missing required command
- Stopped or unhealthy PostgreSQL or Redpanda services

Verification success means the staged change passed the selected checks. It
does not authorize or perform a commit or push; those remain explicit developer
decisions.
