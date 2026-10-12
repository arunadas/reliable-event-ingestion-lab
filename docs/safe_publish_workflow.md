# Safe Publish Verification Workflow

## Purpose

This project uses a repeatable verification workflow before Git commits are
published. Deterministic tools perform the security and quality checks. AI
assistants may invoke the workflow, explain failures, and help organize
commits, but they do not replace the underlying checks.

The workflow has two verification levels:

- Fast verification for normal incremental commits.
- Full verification for milestones and changes affecting infrastructure or
  integration behavior.

## Entry points

Developers and automation use:

```bash
make verify-publish
make verify-publish-full
```

Both targets delegate to one implementation:

```bash
scripts/verify_publish.sh fast
scripts/verify_publish.sh full
```

This prevents Make, Git hooks, CI, and AI assistants from implementing
different safety rules.

## Safety boundaries

The workflow is read-only with respect to Git and project data.

It must not:

- Stage or unstage files.
- Create commits.
- Push branches.
- Rewrite Git history.
- Delete files, containers, volumes, topics, or database data.
- Start or stop Colima or the Compose stack.

The developer approves every commit and push.

## Common preflight checks

Both modes must:

1. Confirm execution from this Git repository.
2. Display the current branch.
3. Require at least one staged change.
4. Display all staged filenames.
5. Reject staged private or generated files, including:
   - `.env` files other than `.env.example`
   - `.venv/`
   - Python and test caches
   - `.claude/CLAUDE.md`
   - `.claude/worktrees/`
   - `docs/superpowers/`
6. Stop immediately when a required command or check fails.
7. Restrict code-quality and test checks to the current checkout. Do not scan
   ignored directories, virtual environments, caches, or other Git worktrees.

## Fast verification

Fast verification runs:

1. `git diff --cached --check`
2. Gitleaks against the staged patch
3. Ruff lint checks
4. Ruff formatting checks
5. Mypy
6. Unit tests
7. A final staged-file summary

Fast mode is intended for ordinary coherent commits that do not require live
infrastructure validation.

## Full verification

Full verification runs every fast check, followed by:

1. Docker Compose configuration validation.
2. Confirmation that required Compose services are running.
3. PostgreSQL readiness validation.
4. Redpanda cluster-health validation.
5. Integration tests against PostgreSQL and Redpanda.
6. Gitleaks against committed Git history.

Full mode does not start infrastructure automatically. If Colima or a required
container is unavailable, it fails with instructions explaining what the
developer needs to start.

## Failure behavior

Each check prints its name before execution. A failed check stops the workflow
and preserves the failed command's exit status.

The script distinguishes among:

- A missing prerequisite.
- An unsafe staged path.
- A whitespace or formatting failure.
- A possible secret.
- A code-quality or test failure.
- Unavailable integration infrastructure.

A successful run prints the verification level and staged files that were
verified. Success does not authorize a commit or push.

## AI-assistant integration

A future personal `safe-publish` AI skill may:

- Inspect repository and branch status.
- Help divide changes into coherent commits.
- Recommend fast or full verification.
- Invoke the appropriate Make target.
- Explain failures.
- Suggest a commit message.
- Display what would be published.

The AI skill must request explicit user approval before committing or pushing.
The verification commands remain usable without an AI assistant.

Tool-specific interfaces, such as a Codex skill or Claude command, must invoke
the same Make targets rather than duplicate verification logic.

## Future integrations

After the local workflow has been proven, the same script may be invoked by:

- A pre-commit or pre-push Git hook.
- GitHub Actions.
- Other repositories in the project portfolio.

These integrations are outside the first implementation and must not weaken
the safety boundaries defined here.

## Acceptance criteria

The first implementation is complete when:

- Both Make targets are available.
- Fast mode passes on a safe staged change.
- Fast mode rejects an empty staging area.
- Fast mode rejects representative private paths.
- A failed check returns a non-zero status.
- Full mode passes when the Compose stack is healthy.
- Full mode fails clearly when required infrastructure is unavailable.
- The script never stages, commits, pushes, deletes, or starts infrastructure.
- The workflow is documented for developers.
