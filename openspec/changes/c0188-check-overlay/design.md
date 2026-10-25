## Context

- **Request.** P1-8 of the analysis of 2026-10-25.
- **What exists.** `fenolite check` replies (`issues` with `where`, `at`, layers), `--overlay` for `analyze`.

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. A finding's marker is its `at` point, or the box of the objects it names; findings without a position are
   listed only.
2. `--check run` runs `check` in the same process and is read-only.

## Risks / Trade-offs

- **Report limits.** A DRC capped by `summary.limits` is a lower bound (`check.report-limit`); the panel says
  so.
