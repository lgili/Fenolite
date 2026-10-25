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
3. The reply's issues carry no stage, so a finding's stage comes from its code's prefix (`STAGE_OF`), and its
   evidence is that stage's. ERC findings (they name schematic symbols) are placed on sheets only, and the
   findings of the board stages on boards only; the others on either.
4. Names resolve against the scene: pads by label, parts by reference, KiCad locators of tracks, arcs and vias
   by the scene's labels, zones by their index in the scene's new `zones` list, and nets by the box of their
   copper. A box that holds another named box whole (a zone around a pad) is dropped, so the marker lands on
   the item.

## Risks / Trade-offs

- **Report limits.** A DRC capped by `summary.limits` is a lower bound (`check.report-limit`); the panel says
  so.
