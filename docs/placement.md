# Placement

How do parts get from the staging row onto the board, and how do I know that a placement is legal before
KiCad opens it? This page describes `fenolite place`, the two strategies, the legality check and how a
placement survives the next build. The normative text is in `openspec/specs/placement/spec.md`; the
KiCad facts are in `docs/formats/kicad/board.md` ("Board outline as rings", "Moved footprints"). The
command contract is in `docs/cli-contract.md` ("`place`").

A placement is never a verdict: KiCad's DRC judges the board (`fenolite check`). Every `place` reply
carries `evidence.level` `KICAD-VERIFIED`, which covers the moved footprints and the touching courtyards
(`H-K-PLACE-MOVE`, `H-K-PLACE-TOUCH`), not the layout.

## Strategies

| strategy | what it moves | how |
|---|---|---|
| `grid` (default) | every footprint that is off the board, or those of `--only` | shelf packing, left to right and top to bottom, at 0° on the top side; translation only |
| `manual` | the footprints named by `--move REF=X,Y[,ROT[,SIDE]]` | a translation, or a re-placement from the library definition when the rotation or the side changes |

The grid is deterministic: the same board gives the same positions, in component-path order.

## The command

```console
fenolite build design.py --out build/blink --confirm      # parts without place() are staged beside the outline
fenolite place build/blink --dry-run                       # the plan: which parts go where
fenolite place build/blink --confirm                       # grid: every staged part goes onto the board
fenolite place build/blink --move R1=12mm,8mm --confirm    # manual: R1 to (12 mm, 8 mm)
fenolite place build/blink --move D1=38mm,20mm,90,bottom --confirm
fenolite place build/blink --only R1,C3 --gap 1mm --confirm
```

- A part is **off the board** when its position lies outside the bounding box of the outline. The build
  stages parts there (`layout.unplaced`), and the grid places exactly those, or the ones `--only` names.
- The grid fills the bounding box of the outline, inset by `--margin` (1 mm), row by row. A part's
  courtyard box lands on a `--pitch` grid (0.5 mm) and keeps `--gap` (0.5 mm) from the courtyards that
  are already on the board, from cut-outs and from the parts placed before it. A part that fits nowhere
  stays staged, with `place.no-room`. The three defaults are Fenolite choices, not fabrication rules.
- `--move REF=X,Y[,ROT[,SIDE]]` uses the frame of the script's `place()`: `X` and `Y` are lengths with a
  unit, measured from the top-left corner of the outline's bounding box, Y down. A translation keeps
  every child of the footprint. A new rotation or side re-places the footprint from its library
  definition, which the command finds through the project's `fp-lib-table` (a built project vendors
  its footprints under `lib/`); the footprint keeps its uuid, reference, value, properties, lock and
  pad nets. Without the definition the move is refused (`place.no-definition`).
- Tracks and vias do not follow a part. When a moved part had copper on its pads, `place.copper-left`
  says so. Script copper (`docs/copper.md`) follows the pads again at the next build.
- With a `place.*` error nothing is written (exit code 5) unless `--force` is given. `--force` also
  moves a part that is locked on the board.
- `-o FILE` writes the board elsewhere and leaves the project as it is.

`result.moved` lists each moved part with its old and new placement (nanometres, microdegrees, side),
`result.unplaced` the references still off the board and `result.legality` the issues by code. Two runs
on equal boards write equal bytes.

From Python the pieces are plain functions:

```python
from pathlib import Path

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.replace import footprint_ref, move_footprint
from fenolite.placement import check

design = read_board(Path("build/blink/blink.kicad_pcb"))
names = {fp.id: footprint_ref(design, fp) for fp in design.board.footprints}
issues = check(KicadBackend().placed_extents(design), board_outline(design).rings, names=names)
```

## Legality codes

The check uses the placed courtyards of the board frame (`docs/copper.md`, `PlacedExtent`) and the board
outline as rings. All predicates are exact integer geometry.

| code | severity | when |
|---|---|---|
| `place.courtyard-overlap` | error | two courtyards on the same face overlap |
| `place.outside-outline` | error | a courtyard leaves the board ring or enters a cut-out |
| `place.edge-clearance` | warning | a courtyard is closer to the board edge than the edge clearance |
| `place.no-extent` | info | a footprint has neither a courtyard nor pad copper; it is not judged |
| `place.no-outline` | info | the board has no closed outline; only overlaps are judged |

In `fenolite build` every placement issue is at most a warning: a build never refuses for placement.
In `fenolite place` an error refuses the write unless `--force` is given.

The other codes of `fenolite place` are `place.no-definition`, `place.locked` and `place.unknown-ref`
(errors), and `place.no-room`, `place.copper-left` and `place.script-locked` (warnings); the table in
`docs/cli-contract.md` lists all of them.

What the check does not judge:

- Courtyards that only touch, along an edge or at a corner, do not overlap. KiCad reports no
  `courtyards_overlap` for them on 9.0.9 and 10.0.6 (probe `place-touch`, `H-K-PLACE-TOUCH`).
- A courtyard that touches the outline is inside. A cut-out that lies wholly inside a courtyard is not
  reported.
- A courtyard drawn with arcs or circles is judged on a polygon within 5 µm of it, and its message ends
  with "(approximate extent)". A footprint without a courtyard is judged on the hull of its pads.
- The edge clearance is the smallest board-wide `edge_clearance` rule of the model design, and 0 without
  one. A board read from a file holds no rules, so `fenolite place` uses 0.
- A board whose `Edge.Cuts` graphics do not chain into a closed ring by exact endpoint equality has no
  outline here (`place.no-outline`), even when KiCad closes it: edge items inside footprints are not
  chained, and there is no snapping tolerance (`docs/evidence/kicad-board-read.md`, "Outline rings").
- Silkscreen, fields and copper are not placement: see `docs/copper.md` and `fenolite check`.

## How a placement survives a build

The board is the layout authority (`docs/lens.md`). A part that `place` moved onto the board is on the
board, so the next `fenolite build` keeps it there. A part with a locked `place()` in the script goes
back to the script's placement; `place` warns about it with `place.script-locked`.
