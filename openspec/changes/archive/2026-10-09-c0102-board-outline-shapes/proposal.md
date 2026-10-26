## Why

A script declares a rectangle only: `Outline` holds no arc and no call fills its cut-outs. A mounting hole needs a library part. On a built board a new outline is ignored (`layout.outline-kept`) and a new copper count refused (`layout.copper-mismatch`), unless `--discard-layout` drops the routing (`origin/dev` at `9aba2dff`). The review of 2026-10-05 of the gaps to a complex board found no owner for these three gaps; its proposals are milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches").

Probes on `kicad-cli` 10.0.6 and 9.0.9 (2026-10-05, on the branch where this proposal was written; not repeated on `dev`):

- `gr_line` and `gr_arc` outlines with round and slot cut-outs load clean; cut-outs reach no drill file.
- A root `pad` does not load; an unnumbered `np_thru_hole` pad is drilled in the NPTH file.
- 10.0.6 reports `invalid_outline` for a cut-out touching the edge; 9.0.9 does not.
- DRC reports nothing for copper wholly outside the outline, and `item_on_disabled_layer` for copper on removed layers.

## What Changes

- **Model.** `Outline.arcs`: an edge becomes an arc through a mid point.
- **Script.** `board(outline=…, locked=False)` and `design.cutout(path)` take closed paths of points and `arc_to` steps; `fenolite.dsl.shape` gives `rect` with rounded corners, `circle` and `slot`.
- **Writer and build.** A `gr_line` or positively oriented `gr_arc` per edge, uuids signed with the outline's digest. Rings that cross or touch stop the build.
- **Holes.** `design.hole(ref, x, y, drill=…)`: a locked part with a generated symbol and footprint, round or slotted, plated or not. Authored footprints accept unnumbered holes. This is the one hole call of the DSL: c0096 adapts to it (design, "Relation to c0096").
- **Outline change on a built board.** An outline Fenolite wrote and nobody edited follows the script, with zones lacking an outline; copper that no longer fits is dropped. An edited outline wins unless locked. Edge items inside footprints stay with their footprints.
- **Copper count change on a built board.** Inner layers are added or removed with their copper; a stale stack-up is removed.
- **Altium.** An outline with arcs plans no PCB document, as one with cut-outs. A round hole that is not plated is written as the board hole of c0085 (a free pad without copper); a slot and a plated hole are reported with `altium.not-lowered`.

Size: 6.75 design-days; cut order in the design.

## Prerequisites

- Release 0.3.0 is out, with c0085, c0090 and c0126 archived: the Altium rules of this change are worded on c0085's "Non-plated holes and slots" and "Complete board in an Altium build", and c0126 gives the convention and the 0.2.0 fixture for additive model keys.
- c0100 is on `dev`: `CREATED_COPPER_COUNTS`, `created_count`, and "Layer count across rebuilds", which this change modifies once it is living. c0101 is on `dev` when its `merge_stackup` is to run after the layer merge (the stack-up reset stands without it).
- c0096 (implemented on its own branch): by the maintainer's decision of 2026-10-07 this change's `Design.hole` stands and c0096 adapts. Either may reach `dev` first; the design says which names of c0096 go and who removes them. c0097 and c0099 are not touched.
- This change lands before c0103 (keep-outs around holes), c0108, c0113 and c0118 (tooling holes use `design.hole()`).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-model`: ADDED "Board outline arcs".
- `design-dsl`: MODIFIED "Board and placements in the DSL", "DSL to model", "Zones in the DSL"; ADDED "Outline shapes in the DSL", "Outline shapes in a build", "Board holes in the DSL", "Board holes in a build".
- `dsl-footprint-authoring`: ADDED "Unnumbered hole pads in authored footprints".
- `kicad-file-backend`: MODIFIED "Outline lowering", "Board outline as rings"; ADDED "Outline shape checks".
- `layout-lens`: MODIFIED "Placement precedence", "Board content outside the design is kept"; ADDED "Outline changes across rebuilds", "Copper layer changes across rebuilds".
- `board-analyses`: MODIFIED "Board boundary".
- `altium-build`: MODIFIED "PCB document output".
- `kicad-oracle`: ADDED "Outline shapes and holes pass the oracle", "Outline and layer changes pass the oracle".

## Non-goals

- Arcs in zone and rule-area outlines: nowhere, because KiCad clips fills to the board outline (measured).
- `Board.holes` in KiCad: nowhere, KiCad has no such hole. The field stays for readers (an Altium board).
- Keep-outs around holes: c0103. Tooling holes: c0118.
- Arcs and cut-outs of the outline in the Altium document, and a slot or a plated hole there: nowhere for now. Each needs a record whose form has no fact row in `docs/formats/altium/`; until one exists the build refuses the document (arcs, cut-outs) or reports the hole.
- KiCad's lock flag on edges: nowhere until measured.
- Moving parts left outside a new outline: `place` (c0022).
- Moving copper between layers: nowhere, it changes what was routed.
- Removing or replacing edge items that live inside footprints: nowhere; they belong to their footprints.
- Limits: cut-outs that 9.0.9 accepts are refused for both targets; copper within 5 µm of a curved edge may be judged unlike KiCad; a smaller count drops the deepest inner layers; a zone without an outline may miss a hand-drawn arc's bulge (warned).

## Evidence level required

- New rows `H-K-OUTLINE-ARCS`, `H-K-OUTLINE-INVALID`, `H-K-HOLE-FOOTPRINT`, `H-K-LAYER-CHANGE` (both majors measured); `H-K-OUTLINE-OUTSIDE`, `H-K-HOLE-COURTYARD`, `H-K-HOLE-SYMBOL` (both majors before merge); `H-K-ZONE-BOX` (10.0.6, where fill runs).
- Paths, digests, merges: unit tests. The Altium part is mechanical on c0085's records; the evidence of the Altium build does not rise.

## Impact

- Changed: model and schema, DSL (new `shape.py`, `holes.py`), board writer, `outline.py`, `layers.py`, lens, analysis boundary, Altium build, `cli/data/explain.toml`, docs.
- One model key is added (`arcs` of the outline). Documents written before load unchanged; release 0.2.x cannot read a document that carries it, because its reader refuses an unknown key.
- The first rebuild re-signs older edge items; refused changes now apply.
- If c0096 is on `dev` first, its `Design.hole(key, …)`, `Design.holes` and the key `hole:<key>` are removed by this change (an API that no release carries).
