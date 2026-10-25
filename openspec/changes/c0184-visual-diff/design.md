## Context

- **Request.** P2-10 of the analysis of 2026-10-25: "conferir uma mudança feita por agente".
- **What exists.** `fenolite diff` (record and tree views), the board and sheet scenes, overlays (c0176).

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. The difference is computed on scenes, not files, so it works for every format the viewer reads.
2. A moved part is one change, not a removal and an addition (as `diff` counts it).
3. The page shows NEW with the overlay; a toggle shows OLD.

## Risks / Trade-offs

- **Noise.** Refilled zones change every fill polygon; zone fills are compared by area and net, not by
  vertex, and reported as one change per zone.
