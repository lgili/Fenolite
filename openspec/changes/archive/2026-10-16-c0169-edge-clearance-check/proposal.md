## Why

Third change of the request "board slots and cut-outs, end to end" (2026-10-15), after c0167, against `origin/dev` at `a87723c`. A slot keeps copper apart; Fenolite cannot tell whether copper keeps its distance from it:

- `fenolite.checks.copper` judges copper against copper only: tracks, arcs, vias, pads and fills of different nets. It never measures copper against the board edge, a cut-out or a slot, although the rule kind `edge_clearance` exists in the model and is written to KiCad (`edge_clearance`) and to Altium (`BoardOutlineClearance`).
- Fenolite judges no drilled hole: a via drilled into a slot, or two drilled slots that overlap, pass. KiCad reports nothing for two overlapping oval NPTH pads (measured 2026-10-15), while Altium's Hole To Hole Clearance flags overlapping holes (S-0460).
- Creepage takes cut-outs, and after c0167 slots, but nothing shows that a slot and the same ring drawn as a cut-out give the same creepage.

Measured on 2026-10-15 in the pinned images: KiCad's `copper_edge_clearance` on both majors measures from the copper to the edge line, without the edge's stroke width, against the board setup's 0.5 mm (a pad 0.47 mm away is reported, 0.52 mm is not).

## What Changes

- **Edge clearance in the copper check.** Every copper item (track, arc, via, pad, fill) is judged against the board's edge rings: the outer ring, cut-outs and slots, merged as c0167 lowers them. The limit is the governing `edge_clearance` rule or the board minimum the project gives (`min_copper_edge_clearance`); the distance is to the edge line. A finding `copper.edge-clearance` names the item, the ring (`board`, `cut-out <k>`, `slot <name>`) and the limit, with an explanation of the rules considered, as clearance findings have.
- **Board edges through the frame.** Backends give the edge rings through `BoardFrame.board_edges` (KiCad: the exact edge lines and arcs; Altium: the board outline and cut-out regions), so the check stays free of backends.
- **Drilled holes.** `copper.hole-in-cutout` (error) for a drilled hole that breaks into a cut-out, a slot or the edge; `copper.hole-overlap` (warning) for two drilled holes whose areas overlap.
- **Creepage.** A slot gives the same creepage as the same stadium drawn with `cutout(shape.stadium(…))`, and an L of two slots the same as its merged ring.
- **Cross-check with KiCad.** A bench of copper at measured distances from an outer edge, a cut-out and a slot, judged by Fenolite and by `kicad-cli pcb drc` on 9.0.9 and 10.0.6: the same items.

Size: 5 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `copper-check`: ADDED "Copper to board edge clearance", "Drilled holes against cut-outs and holes".
- `backend-protocol`: ADDED "Board edges of a frame".
- `copper-rule-explanation`: ADDED "Edge clearance explanation".
- `verification-loop`: MODIFIED "Copper stage issue codes".
- `board-analyses`: ADDED "Slots in creepage".
- `kicad-oracle`: ADDED "Edge clearance agrees with KiCad".

## Non-goals

- Hole-to-hole and hole-to-copper clearance values (`hole_to_hole`, `hole_clearance` rules): KiCad's DRC judges them at `check`; Fenolite adds only the overlap and the break into a cut-out.
- Silk-to-edge clearance.
- Moving copper away from an edge (placement and routing, c0170).

## Evidence level required

- Edge distance and the combination of rule and board minimum: `KICAD-VERIFIED` on 9.0.x and 10.0.x (`H-K-EDGE-CENTRE`, `H-K-EDGE-RESOLVE`); the check's own evidence stays `INFERRED`, as the copper check's does.
- Holes and creepage equality: unit tests (mechanical).

## Impact

- `checks/copper.py`, `checks/clearance.py`, `checks/codes.py`; `backends/base.py`; `backends/kicad/backend.py` (frame), `backends/altium/backend.py` (frame); `cli/data/explain.toml`; docs (`docs/copper-rule-explanations.md`, `docs/cli-contract.md`, `docs/analyses.md`, `docs/formats/kicad/drc.md`).
- A board whose copper is too close to its edge gains findings in `check` and in the build's copper guard. Depends on c0167; c0168 adds Altium cut-outs.
