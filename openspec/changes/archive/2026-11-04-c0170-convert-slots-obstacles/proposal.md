## Why

Last change of the request "board slots and cut-outs, end to end" (2026-10-15), after c0167 and c0168, against `origin/dev` at `a87723c`. A slot must survive a conversion and must stop placement and routing; today (design, "Context"):

- `convert --to altium` writes the first ring of a KiCad board's edges, an arc as two straight edges, and drops every other ring with "an edge outside the first ring of the outline" under the kind `outline`.
- A footprint pad with an oval drill (a KiCad mounting slot, `design.hole(…, length=…)`) is refused by the Altium library writer ("the drill is oval or has an offset"), so the whole footprint is lost.
- `convert --to kicad` from a document with overlapping cut-out regions would write overlapping `Edge.Cuts` rings, which KiCad calls `invalid_outline`; an imported `Hole` (c0168) has no KiCad form of its own.
- The router sees slots once c0167 puts them into `board_outline`, but nothing tests it, and the constrained placer and its preview read `Outline.cutouts` directly, so they would miss slots.

## What Changes

- **KiCad to Altium.** The edges of a read KiCad board are taken with `edge_outline` (c0167): the board ring is written as today, every inner ring becomes a cut-out region of c0168 (or a reported `cutout` loss while c0168's gate is off), a merged group counts once. A footprint pad with a slotted drill is written with c0168's slot fields in the library and the document.
- **Altium to KiCad.** Overlapping cut-out rings are merged with `merge_rings` before writing, reported as `changed`; without the `geo` extra they are a `refuse` loss (exit 7). An imported `Hole`, round or slotted, becomes the generated `Fenolite_Holes` footprint that `design.hole` makes; its builder moves from `dsl/holes.py` to `model/holes.py` so the KiCad backend can use it.
- **Report.** The kind `cutout` (group `board`) and the reasons for merged and dropped rings; every slot and cut-out is counted kept, changed or lost.
- **Verification.** The conversion compares the edge rings of the source and of the written project read back (`BoardFrame.board_edges`, c0169), within 1 µm and the region chord, besides `equivalent`.
- **Obstacles.** The constrained placer, its preview and the body-volume analysis take slots through `outline_items`; the Specctra design file holds each slot as a keep-out; a Freerouting run on the shared fixture routes no track through a slot.

Size: 4.5 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-conversion`: ADDED "Slots and cut-outs in a conversion", "Edge rings verified after a conversion".
- `altium-pcb-writer`: ADDED "Slotted drills of footprint pads".
- `kicad-file-backend`: ADDED "Board holes as generated footprints in a conversion".
- `constrained-board-placement`: ADDED "Slots are placement obstacles".
- `specctra-dsn`: ADDED "Slots in design files".

## Non-goals

- Arcs of the outer board ring in Altium (c0168's follow-up).
- Comparing outlines in `fenolite equivalent` (open question 2).
- Routers other than Freerouting.

## Evidence level required

- KiCad side: `KICAD-VERIFIED` (9.0.x, 10.0.x) for the converted fixture (no `invalid_outline`, the drill files).
- Altium side: `ORACLE-VERIFIED(kicad-cli)` through KiCad's import; the region form keeps c0168's level.
- Routing: `ORACLE-VERIFIED(freerouting)` on the fixture.

## Impact

- `backends/altium/lower.py`, `pcblib.py`; `lens/altium.py` (`pad_extras`); `convert/report.py`, `to_altium.py`, `to_kicad.py`; `model/holes.py` (moved from `dsl/holes.py`, re-exported); `placement/constrained_legality.py`, `preview.py`; `analysis/body_volumes.py`; `backends/specctra/dsn.py` (test only unless a gap is found); docs.
- Depends on c0167, c0168, c0169 (the frame's edges) and on c0159 to c0161 being archived.
