# Placement

How do parts get from the staging row onto the board, and how do I know that a placement is legal before
KiCad opens it? This page describes `fenolite place`, the two strategies, the legality check and how a
placement survives the next build. The normative text is in `openspec/specs/placement/spec.md`; the
KiCad facts are in `docs/formats/kicad/board.md` ("Board outline as rings", "Moved footprints"). The
command contract is in `docs/cli-contract.md` ("`place`").

A placement is never a verdict: KiCad's DRC judges the board (`fenolite check`). Every `place` reply
carries `evidence.level` `KICAD-VERIFIED`, which covers the moved footprints and the touching courtyards
(`H-K-PLACE-MOVE`, `H-K-PLACE-TOUCH`), not the layout. The level is lower in two cases: when the board
holds a rule area that forbids footprints, the reply also rests on `H-K-PLACE-KEEPOUT`, and when a
placement rule was judged it is `INFERRED`, because a `near` rule is Fenolite's own definition ("Keep-outs"
and "Placement rules" below).

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
- The grid also leaves the bounding box of every rule area that forbids footprints free, whatever the
  area's layers and shape: an L-shaped area costs its whole box, so a board with large areas leaves more
  parts staged ("Keep-outs" below).
- `--move REF=X,Y[,ROT[,SIDE]]` uses the frame of the script's `place()`: `X` and `Y` are lengths with a
  unit, measured from the top-left corner of the outline's bounding box, Y down. A translation keeps
  every child of the footprint. A new rotation or side re-places the footprint from its library
  definition, which the command finds through the project's `fp-lib-table` (a built project vendors
  its footprints under `lib/`); the footprint keeps its uuid, reference, value, properties, lock and
  pad nets. Without the definition the move is refused (`place.no-definition`).
- Tracks and vias do not follow a part. When a moved part had copper on its pads, `place.copper-left`
  says so. Script copper (`docs/copper.md`) follows the moved part at the next build where its tracks
  end at pads (`part.pad(…)`) or its points are anchors in the part's frame (`part.at(…)`,
  `part.pad(…).at(…)`): vias, waypoints and thermal arrays given that way are regenerated at the
  part's new place, with the same ids. Script copper given by board points stays where those points
  say, and so does copper drawn in KiCad.
- With a `place.*` error nothing is written (exit code 5) unless `--force` is given. `--force` also
  moves a part that is locked on the board.
- `-o FILE` writes the board elsewhere and leaves the project as it is.

`result.moved` lists each moved part with its old and new placement (nanometres, microdegrees, side),
`result.unplaced` the references still off the board and `result.legality` the issues by code.
`result.rules` holds the counts of the placement rules that were judged and `result.measures` the wire
length and the congestion of the layout after the moves ("Placement rules" and "Measures" below). Two
runs on equal boards write equal bytes.

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
| `place.keepout` | error | a courtyard enters a rule area that forbids footprints, on the face the area judges |
| `place.edge-clearance` | warning | a courtyard is closer to the board edge than the edge clearance |
| `place.keepout-no-courtyard` | warning | the pads of a part without a courtyard lie in such an area |
| `place.no-extent` | info | a footprint has neither a courtyard nor pad copper; it is not judged |
| `place.no-outline` | info | the board has no closed outline; only overlaps and keep-outs are judged |

In `fenolite build` every placement issue is at most a warning: a build never refuses for placement.
In `fenolite place` an error refuses the write unless `--force` is given. The rule findings
(`placement.too-far`, `placement.rule-unresolved`, `placement.rule-skipped`) are no legality codes: `place`
and `build` report them as warnings at most ("Placement rules" below).

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

## Keep-outs

A rule area that forbids footprints (`(footprints not_allowed)` in KiCad, `Keepout.no_footprints` in the
model) is judged by the legality check, in `place` and in the placement guard of `build`, under one code:
`place.keepout`. The check gets the board's keep-outs through `check(…, keepouts=board.keepouts)` and
judges those that forbid footprints as KiCad's DRC does. The rule was measured on 18 benches
(`H-K-PLACE-KEEPOUT`; `docs/formats/kicad/board.md`, "Rule areas that forbid footprints"):

- The courtyard is what counts, not the pads and not the silkscreen. A part is reported when the interior
  of its courtyard meets the interior of the area: an overlap of 10 µm is reported, and an area whose
  edge lies on the courtyard line is not.
- Faces follow copper layers. An area on `F.Cu` judges front courtyards and one on `B.Cu` back courtyards;
  an area on inner layers only judges no part.
- KiCad never reports a part without a courtyard. Fenolite judges the hull of its pads and gives
  `place.keepout-no-courtyard`, a warning: a part without a courtyard in an antenna keep-out is a defect
  that no other check would see.
- The message names the area by its name when the model gives it one, and the face.

`fenolite place` refuses a move into such an area (exit code 5) unless `--force` is given, and its grid
keeps out of the area's bounding box. `fenolite build` reports the same finding as a warning. `fenolite
check` does not judge keep-outs a second time: on a KiCad project KiCad's DRC reports them in `drc.kicad`.
On Altium documents no stage judges a part in a keep-out (`docs/altium.md`). In a script,
`design.rule_area(name, outline, layers=("F.Cu",), forbid=("footprints",))` declares such an area
(`docs/dsl.md`, "Rule areas"); one drawn in KiCad is judged the same way.

## Placement rules

`design.near(key, parts, anchor, *, within, severity="error")` states which parts belong near which pads
(`docs/dsl.md`, "Placement rules"): a decoupling capacitor near its supply pin, a crystal and its load
capacitors near the oscillator pins, a module near its controller. The rules are model data
(`RuleSet.proximity`, `docs/design-model.md`); the build stores them in `.fenolite/rules.json`, and no
backend lowers them, because neither KiCad's rule language nor an Altium document holds a maximum
distance between parts.

`fenolite.checks.placement.judge(design, rules, pads=…)` judges them on the pad positions of a board:

- A part meets a rule when one of its selected pads and one pad of the anchor have centres at most
  `within` apart. The comparison is exact, on squared integers. A part that is on both sides of a rule is
  at distance 0.
- A part that fails gives one `placement.too-far` with the rule's severity. The message names the rule,
  the part's path, the nearest anchor pad as `REF-NUMBER`, the distance and the limit. The distance that
  is printed is rounded up to the nanometre, so a printed distance is above the limit exactly when the
  rule fails: a part 0.4 nm too far reads 2.000001 mm against a limit of 2 mm, never 2 mm.
- A rule that names a part or a pad that the board does not hold gives `placement.rule-unresolved`
  (error); an unresolved anchor leaves the whole rule unjudged. A part off the board gives
  `placement.rule-skipped` (info), and the rule is not judged for it.
- The counts are per rule family: `{"near": {"judged", "failed", "skipped"}}`, one count per rule and
  part. The height limits add the family `height` ("Height limits").

Who judges them:

| command | what it does with a rule finding |
|---|---|
| `fenolite check` | the default stage `placement.rules`, on KiCad projects and on Altium documents; an error gives exit code 5 |
| `fenolite build` | a warning at most, in `result.placement.rules`; a build never refuses for placement |
| `fenolite place` | a warning at most, in `result.rules`; a rule never refuses a move |

The rules are those of the last build: `check` and `place` read `.fenolite/`, so a rule changed in the
script applies at the next build. A board without a script has no rule. Distances join pad centres: a rule
says nothing of the routed length (change c0106) or of the area of a current loop. No command moves a part
to meet a rule: the grid ignores them, and a placer that reads them is planned (`docs/roadmap.md`).

## Height limits

A part may not be tall under a lid, a heat sink or a display. A script states a part's height with
`Part(..., height=…)` and a limit over a named rule area with `design.height_limit(area, max=…)`
(`docs/dsl.md`, "Part heights and height limits"; change c0140).

- **One source of height.** A part's height is the outward height of the bodies of its footprint, computed
  by `fenolite.model.board.outward_height` and by nothing else: the largest upper bound of the bodies, its
  `height` for a body of today's model. A script height is such a body; a board imported from Altium
  brings its own. `Component` has no height, and no footprint property holds one.
- **Where heights are read.** `fenolite.checks.placement.heights_of(design, model)`: the footprint of the
  board being judged when it holds a body (a reading of Altium documents), else the footprint of the same
  component path in the `.fenolite/` model of a built project (a KiCad file holds no body), else none.
  The bodies of the two are never mixed.
- **Under an area.** Every rule area whose name is the limit's `area` limits the parts under it. A part is
  under an area when the area's layers hold `F.Cu` and the part is on the top side, or `B.Cu` and it is on
  the bottom side, and the interior of a ring of the courtyard of its own face meets the interior of the
  area's outline; rings that only touch do not meet. This is the face rule of the keep-outs
  (`H-K-PLACE-KEEPOUT`). An area on inner layers only judges no part. A part without a courtyard is judged
  on the hull of its pads, and its finding ends with "(approximate extent)". The body's own outline is not
  used.
- **Who is judged.** Not a part marked `dnp`, nor a part off the board. A part marked `board_only`, or
  whose pads are all non-plated holes (a logo, a mounting hole), only when its height is known.
- **Findings.** A part taller than the limit gives `placement.too-tall` with the limit's severity; a part
  equal to it is no finding. A judged part without a known height gives `placement.height-unknown`
  (warning): an unknown height under a limit is never a pass. A limit whose area the board does not hold
  gives `placement.rule-unresolved` (error). One part under two areas of one name gives one finding.
- **Counts.** The family `height` of the counts: `{"judged", "failed", "unknown"}`, one count per limit
  and part under one of its areas. Without a limit the family is absent.

| command | what it does with a height finding |
|---|---|
| `fenolite check` | the default stage `placement.rules` (`summary.rules.height`), on KiCad projects and on Altium documents; an error gives exit code 5 |
| `fenolite build` | a warning at most, in `result.placement.rules.height`; a build never refuses for a height |
| `fenolite place` | a warning at most, in `result.rules.height`, after the moves; the grid does not read heights |

A limit compares one number with one bound. What lies below the top of a body, a tall part on the other
side, a shape in space and parts that reach through the board are the volume analysis of change c0099
(`check_body_volumes`), which a height limit does not replace. On the Altium target a script height is
not written, and a PCB document holds no rule-area name, so a limit is judged there only on documents
that hold both (`docs/altium.md`).

## Measures

`place` and the stage `placement.rules` of `check` say how long and how crowded the wiring of a placement
will be, so that two placements of one board can be compared before routing.
`fenolite.checks.placement.measure(design, pads=…, pitch=…)` computes them from pad positions, in
integers:

| key | meaning |
|---|---|
| `nets` | the measured nets: those with two pads or more on the board and no zone |
| `hpwl` | the sum, over measured nets, of the width plus the height of the box of their pads (nm) |
| `ratsnest` | the sum of each net's Euclidean minimum spanning tree over its pads, each edge rounded down (nm) |
| `longest` | the five nets of largest `hpwl`: `{net, pads, hpwl, ratsnest}` |
| `left_out` | what is not measured: `zone_nets`, `one_pad_nets` and `off_board` (parts off the board) |
| `congestion` | `{cell, pitch, tracks_per_layer, busiest, layers_needed}`, or `null` for a board without an outline |

- A net carried by a zone is left out: it joins through its copper, and it would dwarf every other net.
- `ratsnest` is Fenolite's own tree. It is a lower bound of the wire that joins the pads, not KiCad's
  ratsnest, which `kicad-cli` does not export.
- **Congestion** is an estimate after the idea of a uniform wire density per net (S-0680). The board's box
  is cut into square cells of side `cell`: 2 mm, or the longer side divided by 128 when that is larger.
  Each measured net spreads its `hpwl` evenly over its box, grown to at least one cell. `tracks` of a cell
  is the wire it gets divided by `cell`: the number of cell-long tracks it must carry. `busiest` lists the
  five cells of most tracks, by their centres in the frame of `place()`.
- With a `pitch` (the track width plus the clearance of the net class `Default` of the project),
  `tracks_per_layer` is how many tracks one layer of a cell holds, and `layers_needed` maps a number of
  layers to the number of cells that need as many. Both are `null` without that class.
- `place` adds `change`: `hpwl` and `ratsnest` after the moves minus before, both 0 when nothing moved.

How to read them: compare two placements of the same board. Fewer cells that need more layers than the
board has, and a smaller `hpwl`, mean an easier board to route. The single busiest cell says little; the
counts of `layers_needed` tell placements apart. The numbers are no verdict: the router decides, and
routed copper is not measured.

Cost, measured on 2026-10-08 on an Apple M4 with Python 3.13 by `tests/unit/checks/test_placement_measures.py
-k synthetic_600`, on a layout of 600 parts and 1 650 pads that the test writes (338 measured nets, 150
rules): `judge` 0.09 s and `measure` 0.31 s. Their inputs cost more on a real board: reading the board and
its pads. No time is asserted by a test.

## How a placement survives a build

The board is the layout authority (`docs/lens.md`). A part that `place` moved onto the board is on the
board, so the next `fenolite build` keeps it there. A part with a locked `place()` in the script goes
back to the script's placement; `place` warns about it with `place.script-locked`.

## Constrained proposals (c0096)

`placement.constrained.propose_placement` consumes a neutral `BoardFrame`, explicit
`PlacementConstraints` and optional exact-pad `PlacementObjective` rows. Its bounded, deterministic
translation lattice preserves locks, unselected footprints, side, rotation, pads and net topology.
A finite greedy search can miss a globally feasible layout; unplaced parts retain their positions
and report reasons. Candidate counts, source/request SHA-256 and objective measures are returned.
A connected-pad chain is represented by its ordered pair objectives with distinct keys.
Pad centre distance is an airwire surrogate; it measures no routed electrical property.

### Frames and inputs

All constraints and volumes use the written board frame, integer nm and integer microdegrees.
A `GroupRegion` confines listed footprint extents. Edge/gap, outline/cutouts, per-face keepouts,
drills crossing both faces and duplicate drill intents are checked. `MechanicalReservation` links
one existing drill pad to supplied physical volumes and measured/proposed source intent. Reservation
geometry is independent of drill diameter and neither creates holes nor disconnects copper.
`MechanicalConstraints` carries supplied board thickness, allowed penetrations, obstacles and named
missing assembly inputs. No application geometry is assumed.

### Checker interface and assessment

The kernel imports no checks or analysis package. A `PlacementChecker` callback supplies neutral
`PlacementLegality`, copper findings and mechanical inspections. The fallback checks geometry and
reports absent copper/mechanical verifiers. Candidates with unavailable copper checking cannot be
accepted. The CLI adapter runs the existing copper checker, takes each finding's relation from the
copper report (c0097), and runs the body-volume check of c0099 (`analysis.body_volumes`) on the
supplied volumes; unknown body checking and missing bodies remain explicit missing inputs. Intrinsic package
findings retain their original severity, clearance, location and source. They are never exemptions.

`PlacementAssessment.state` is `findings`, `incomplete` or `checked` for these supplied placement
checks only. It retains missing inputs and known findings and does not establish electrical,
routing, assembly or manufacturing readiness. Evidence stays `INFERRED`
under H-G-CONSTRAINED-PLACE and H-G-PLACEMENT-PREVIEW.

### CLI transaction and previews

`fenolite place PATH --strategy constrained --constraints request.json --preview-dir views --dry-run`
plans a request using `schemas/fenolite.placement-request.v0.json`. Repeating with `--confirm` writes
the board and both SVGs with receipts. `--force` is refused. The previews query serialized board
readback, show layer copper, holes, locks and optional conservative extents, and reflect the bottom
view once globally. Through-hole copper appears on both faces. Existing manual/grid modes retain
their contract.
