## Context

- **Request.** P0-3 of the analysis of 2026-10-25.
- **What exists.** `Board.keepouts` with `no_tracks`, `no_vias`, `no_pads`, `no_pours`, `no_footprints`;
  `read.rules` (rooms are rules); `BoardFrame.placed_extents` (courtyards).

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. Keep-outs use a 45° hatch in the layer's colour at half opacity; their outline stays solid.
2. Rooms are drawn only when their region is in the rule record (`H-A-ROOM` to record in task 0.1).
3. Courtyard overlaps are computed with the same polygon test the `check` stage uses, so the viewer and
   `check` agree.

## Risks / Trade-offs

- **Altium dimensions** may stay a note if no public file shows their records.
