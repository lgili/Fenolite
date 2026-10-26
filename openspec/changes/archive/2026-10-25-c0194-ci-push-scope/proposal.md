## Why

`.github/workflows/ci.yml` ran on every push, of a branch or of a tag. On 2026-10-25 the maintainer kept four
finished branches as tags `archive/*` and pushed three branches `backup/*` for a review: each push started a
full run of every job (unit on three systems, kicad-10, kicad-9, routing, viewer, wheel, dco), about two
hours of runner time each, for content that was only being kept or read. The maintainer asked that CI not run
on tags and backups.

## What Changes

- `ci.yml` runs on a push of any branch except `backup/**`, and on every pull request. A push of a tag runs
  no CI: with only a `branches` filter, GitHub does not run the workflow for a tag push.
- A release tag needs no run of its own: the tagged commit is the head of `main` that CI ran on.
- `tests/unit/test_ci_workflow.py` checks the trigger textually.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `ci-baseline`: ADDED "Pushes that run CI".

## Non-goals

- The scheduled `nightly.yml` and the `release.yml` of a published release are unchanged.
- No other branch name is excluded: a working branch of a change still runs every job.

## Evidence level required

- `INFERRED` from GitHub's public page on workflow syntax (a workflow that defines only `branches` does not run
  for a tag push; patterns starting with `!` exclude); the first push of a `backup/*` branch after this change
  shows it.

## Impact

- `.github/workflows/ci.yml`, `tests/unit/test_ci_workflow.py`, `CHANGELOG.md`, `docs/release/v0.5.md`.
- Size: an hour.
