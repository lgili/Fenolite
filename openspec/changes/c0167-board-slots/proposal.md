## Why

The maintainer's request "board slots and cut-outs, end to end" (2026-10-15): non-plated milled slots inside the outline lengthen creepage, and must survive KiCad, Altium, the checks and read-back; overlapping slots mean their union. First of four changes (c0167 to c0170), against `origin/dev` at `a87723c`.

A script can already draw a slot as a cut-out ring (`design.cutout(shape.slot(…))`, exact arcs, c0102) and a drilled slot (`design.hole(…, length=…)`, an oval NPTH pad). Missing (design, "Context"):

- A slot has no identity: a ring among `Outline.cutouts`, without id, centre, length or angle.
- Overlapping cut-outs stop the build (`kicad.outline.invalid`); through the model API they are written as they are, and KiCad 9.0.9 and 10.0.6 report `invalid_outline` (measured 2026-10-15).
- No union: the stdlib `fallback` intersects convex polygons only, although the `geo` extra declares `pyclipper`.
- A KiCad board read back gives edge rings, no `Outline` and no slot.

## What Changes

- **Model.** `OutlineSlot(id, center, length, width, rotation)` in `Outline.slots`: a non-plated, milled stadium; `length` is the overall length, both round ends included; rotation in microdegrees in the model frame. Additive key.
- **Shared stadium.** `fenolite.core.stadium` gives the ring of a slot (four vertices, two arc mids), used by the DSL, the backends and the checks; the fixed-point cosine table moves to `fenolite.core.trig`.
- **Script.** `design.slot(x, y, *, length, width, rot=0, name=None)` with the stable id `slot:<name>`; `shape.stadium(x, y, length, width, rot=0)` gives the same ring as a path for `cutout()`.
- **Union.** A `clipper` boolean backend (pyclipper, `geo` extra) with `union`; `geometry.rings.merge_rings` merges overlapping curved rings and puts the arcs back on their circles.
- **KiCad.** Slots are written as `Edge.Cuts` stadium rings with exact arcs. Overlapping slots and cut-outs are merged into one ring first; without the `geo` extra the build refuses them with `kicad.outline.overlap`, naming the items, and `write_board` refuses with `kicad.board.outline-overlap`. A free `Board.holes` entry is refused with a named code and a hint instead of a bare `ValueError`.
- **Read-back.** `outline.edge_outline(design)` gives a read board's edges as an `Outline` with exact arcs, and `outline.slots_of(outline)` recognises stadium cut-outs as slots within 1 nm.
- **Analyses.** `board_boundary` takes slots and merged rings.
- **Altium build.** Slots plan no PCB document, as cut-outs today (c0168 lifts both).

Size: 6.5 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-model`: ADDED "Board slots".
- `design-dsl`: ADDED "Slots in the DSL".
- `geometry-boolean-backends`: MODIFIED "Backend selection"; ADDED "Clipper union backend", "Union of curved rings".
- `kicad-file-backend`: MODIFIED "Outline shape checks"; ADDED "Slots and merged rings in the board file", "Outline read back from the edges", "Free holes refused by name".
- `board-analyses`: MODIFIED "Board boundary".
- `kicad-oracle`: ADDED "Slots pass the oracle".

## Non-goals

- Plated slots: a plated slot is a pad (`design.hole(…, length=…, pad=…)`).
- Altium slots and cut-outs (c0168), copper-to-edge clearance and creepage equality (c0169), conversion and routing obstacles (c0170).
- Writing `Board.holes` to KiCad: the maintainer's decision of 2026-10-07 (c0102, "Relation to c0096") stands; the refusal gets a name.
- Filling `Board.outline` of a read KiCad board.
- Arcs in zone outlines.

## Evidence level required

- KiCad behaviour of slots, overlaps and merged rings: `KICAD-VERIFIED` on 9.0.x and 10.0.x through the pinned images (four new `H-K-*` rows; first measured 2026-10-15).
- Stadium, union and recognition: unit tests (mechanical), with the `geo` extra and without it.

## Impact

- `core/trig.py`, `core/stadium.py` (new); `model/board.py`, `schemas/fenolite.model.v0/board.json`; `dsl/design.py`, `dsl/shape.py`, `dsl/convert.py`; `geometry/boolean/clipper.py` (new), `geometry/rings.py`; `backends/kicad/_edgesign.py`, `outline.py`, `pcb.py`; `analysis/boundary.py`; `lens/altium.py`, `lens/preserve.py`; docs.
- Release 0.4.x cannot read a model document that carries `slots` (unknown key).
