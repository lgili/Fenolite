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
2. Rooms are drawn only when their region is in the rule record; task 0.1 registers a hypothesis for the room records.
3. Courtyard overlaps are computed by `placement.legality.check`, as `fenolite place` computes them, so the
   viewer and `place` agree. `cmd_view` runs it (the layering rules keep `placement` out of `view`) and passes
   the findings and the extents to `build_scene`. Overlaps flagged "approximate extent" (extents made from pad
   copper, every Altium board today) are a note: on the public boards they are capacitors inside a crystal's
   or a connector's pad hull, no conflict.
4. A new primitive kind `h` (a hatched ring) carries keep-outs, Altium keep-out regions and marks; v1 encodes it
   as `p`. Dimensions use the model's `Dimension`: KiCad's side of an orthogonal offset (`board.md`,
   KICAD-VERIFIED), the same side for an aligned one (INFERRED). Layers that hold a dimension, and Altium's
   Keep-Out Layer, are shown by default.

## Risks / Trade-offs

- **Altium dimensions** may stay a note if no public file shows their records.
