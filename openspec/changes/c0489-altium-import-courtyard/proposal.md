# c0489: a footprint imported from Altium gets a derived courtyard

## Why

The Altium import reads no courtyard (`docs/formats/altium/import.md`, "The import reads no courtyard";
`backends.altium.frame.placed_extents`). Altium has no fixed courtyard layer, so none is guessed. The extent
of an imported footprint is the hull of its pads' copper (`source == "pads"`).

So placement legality only sees pads. Two parts whose bodies overlap, and whose pads do not, give no
finding. A KiCad copy converted from Altium has no `F.CrtYd` either, so `place` and the optimizer judge it
the same way. On the maintainer's board (private; codes and counts only) parts could be placed body on
body with no finding.

## What Changes

- On import, a footprint without a courtyard gets one, derived in this order:
  1. from the outline on a mechanical layer whose kind is courtyard, when the document states the kind by a
     key with a public source;
  2. from the outline on a mechanical layer whose kind is assembly, grown by the margin;
  3. from the convex hull of its component body outlines (body projections) and its pads' copper, grown by
     the margin.
- The margin is a declared Fenolite constant, `DERIVED_COURTYARD_MARGIN` (0.25 mm), recorded with its
  evidence label.
- The derived courtyard is a footprint graphic on `F.CrtYd` or `B.CrtYd` (the footprint's side), marked as
  derived: evidence `INFERRED` with hypothesis `H-A-IMP-COURTYARD`, and the pair `derived=courtyard` in its
  `altium` bag. It is never taken for a source item.
- The Altium frame's `placed_extents` uses it, with `exact=False` and a new source value `derived`.
- A derived courtyard is not written back to Altium: directly from the model, or through KiCad with a
  carrier, as long as it is unchanged.

## Impact

- `src/fenolite/backends/altium/adapter/board.py`, `adapter/library.py`, a new
  `adapter/courtyard.py`, `adapter/bodies.py` (body outlines), `backends/altium/frame.py`.
- `src/fenolite/backends/base.py` (`PlacedExtent.source` gains `derived`).
- `src/fenolite/backends/altium/lower.py`, `src/fenolite/convert/to_kicad.py`, `convert/to_altium.py`, a new
  carrier module beside `convert/straightarcs.py`.
- `docs/formats/altium/import.md`, `docs/formats/altium/pcb-records.md` (mechanical layer kinds, if a
  public source states them).
