# Placement

How do parts get from the staging row onto the board, and how do I know that a placement is legal before
KiCad opens it? This page describes `fenolite place`, its strategies, the legality check and how a
placement survives the next build. The normative text is in `openspec/specs/placement/spec.md`; the
KiCad facts are in `docs/formats/kicad/board.md` ("Board outline as rings", "Moved footprints"). The
command contract is in `docs/cli-contract.md` ("`place`").

A placement is never a verdict: KiCad's DRC judges the board (`fenolite check`). Every `place` reply
carries `evidence.level` `KICAD-VERIFIED`, which covers the moved footprints and the touching courtyards
(`H-K-PLACE-MOVE`, `H-K-PLACE-TOUCH`), not the layout. When the board holds a rule area that forbids
footprints, the reply also rests on `H-K-PLACE-KEEPOUT`, `KICAD-VERIFIED` on both majors since 2026-10-08.
When a placement rule was judged the level is `INFERRED`, because a `near` rule is Fenolite's own
definition ("Keep-outs" and "Placement rules" below).

## Strategies

| strategy | what it moves | how |
|---|---|---|
| `grid` (default) | every footprint that is off the board, or those of `--only` | shelf packing, left to right and top to bottom, at 0° on the top side; translation only |
| `manual` | the footprints named by `--move REF=X,Y[,ROT[,SIDE]]` | a translation, or a re-placement from the library definition when the rotation or the side changes |
| `constrained` | the unlocked footprints selected by an explicit constraints request | bounded, deterministic translation search; preserves side/rotation and checks the supplied geometry, copper and mechanical constraints |
| `regions` | every footprint that is off the board, or those of `--only` | one region per domain, the grid inside each, barrier parts across the boundaries ("Regions" below) |
| `reuse` | the `--only` parts, after the anchor | each part where its pads land on the pads of its part in the block of `--from`, turned and on the side the fit finds ("Layout reuse" below) |
| `group` | the parts of `--turn` or `--shift` | one rigid turn about a point or shift, with the copper and zones joined to their pads only; `--pose-search` ranks poses without writing ("Group moves" below) |

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
In `fenolite place` an error refuses the write unless `--force` is given. Only the findings the move makes
are judged (change c0432): the check also runs on the board before the moves, and an error found there too,
with the same code, `where` and message, on parts the command did not move, is `place.existing` (warning).
A board converted from Altium often has such findings, parts in a cut-out or courtyards that overlap, and
they no longer refuse every move. `result.legality` still counts the findings of the layout by their own
codes. The rule findings
(`placement.too-far`, `placement.rule-unresolved`, `placement.rule-skipped`) are no legality codes: `place`
and `build` report them as warnings at most ("Placement rules" below).

The other codes of `fenolite place` are `place.no-definition`, `place.locked` and `place.unknown-ref`
(errors), and `place.no-room`, `place.copper-left`, `place.script-locked` and `place.existing` (warnings).
A converted or imported board keeps each part's lock, so its parts are often `place.locked`; `--force`
moves them. The table in
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
says nothing of the routed length (change c0106) or of the area of a current loop. Grid and manual
placement report these findings without choosing a new position to satisfy them. The `constrained`
strategy can propose positions from an explicit constraints request and pad-distance objectives
([Constrained proposals](#constrained-proposals-c0096)); it does not automatically optimize all DSL
rules or routed electrical properties. Its finite search can miss a feasible placement.

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

## Regions

A first placement should already respect the isolation barriers: the parts of the primary side on one
side of the isolator, those of the secondary on the other, and the isolator across the border. `--strategy
regions` (change c0205) does that before routing. It is a lean initial placement, not an optimiser: the
parts of a region are packed by the grid, in component-path order, and nothing moves them closer to the
pads they join.

```console
fenolite place build/iso --strategy regions --barrier U5 --dry-run
fenolite place build/iso --strategy regions --group primary=J1,R1*,C1* --group secondary=U2,R2*,C2* \
    --barrier U5 --split x --confirm
fenolite place build/iso --strategy regions --group hv=J1,R1* --group lv=U2,C* \
    --region hv=0mm,0mm,25mm,40mm --region lv=25mm,0mm,60mm,40mm --barrier U5 --confirm
```

- **Domains.** By default a domain is an island of nets once the `--barrier` parts (isolators,
  transformers, optocouplers) are removed: `fenolite.analysis.ties.isolation_islands`, which
  `analyze --kinds domains` reports too. Every other part joins the nets of its pins, so all its nets
  are in one island. The domains are named `D1`, `D2`, … in band order, and `result.regions.rows[].nets`
  lists each one's nets. `--group NAME=GLOB[,GLOB...]` replaces them with the parts whose reference
  matches a glob, in the order given. A part in no domain (a mounting hole without a net, a reference no
  glob matches) stays where it was, with `place.region-unassigned`.
- **Regions.** Without `--region`, the bounding box of the outline is cut into one band per domain, along
  the longer side or along `--split`. A band first gets room for its widest staged part and the two
  margins; the rest of the length is shared in proportion to the courtyard-box area of the domain's parts.
  The bands follow the chain of barriers, so the two domains of each barrier are neighbours when the
  barriers form a chain. `--region NAME=X1,Y1,X2,Y2` gives each group its own rectangle instead, in the
  frame of `--move`.
- **Barriers.** A barrier whose pins lie in two domains whose regions touch is placed first, centred
  across the boundary between them, at the first free place along it. It keeps its rotation: a barrier
  whose pins face the wrong way shows up as crossings. A barrier with pins in one domain only, or in more
  than two, or whose two regions do not touch, is packed inside the first one's region, with
  `place.region-barrier`.
- **Inside a region** the grid of the default strategy packs the parts, inset by `--margin`, keeping
  `--gap` from the parts already on the board, the cut-outs, the rule areas that forbid footprints and the
  parts placed before. Neighbouring bands therefore keep twice the margin between their parts. A part
  that fits nowhere stays, with `place.no-room`.
- **The check.** After the moves, every open connection of the layout (`analysis.connectivity`, the
  minimum spanning tree over the pads of each net) whose two ends lie in two different regions counts
  against that pair. `place.region-crossing` gives the count and the nets per pair. Across an isolation
  barrier there should be none: only the barrier part joins the two sides. Count the routing ways of the
  borders that remain with `fenolite analyze --kinds crossings`.

`result.regions` holds, per region, its box (relative to the outline's top-left corner, as `--region`
takes it), its nets, its parts, the parts placed and not placed, its area, the area of the boxes placed in
it and their ratio in thousandths (`fill_permille`); the barriers with their two sides and whether they sit
on the boundary; the unassigned parts; and the crossings. The evidence is `INFERRED`
(`H-G-REGION-PLACE`): the regions are Fenolite's own rule, and KiCad's DRC still judges the board.

What it does not do: rotate or flip parts, move parts already on the board, read placement rules or
heights, keep creepage distances (draw a rule area or a slot across the border for that,
`board-insulation`), or shape regions other than rectangles.

## Layout reuse

A datasheet layout, a reference board or a channel already placed holds a block that the board should
repeat: a regulator with its capacitors, a gate driver, a measurement channel. `--strategy reuse`
(change c0210, implied by `--from`) copies the placement of that block, and with `--copper` its tracks,
arcs and vias, onto parts of the board. It copies by the pads, never by the part centres: a copy by the
centres can come out mirrored or turned without anyone noticing.

```console
fenolite place build/board --from datasheet.kicad_pcb --only U1,C1,C2,L1 --dry-run
fenolite place build/board --from build/board/board.kicad_pcb --only U11,C11,C12 \
    --map U11=U1 --map C11=C1 --map C12=C2 --copper --confirm
```

1. **Pairs.** Each part of `--only` is paired with the part of the same reference on the reference
   board, or with the one `--map TARGET=REFERENCE` names. Pads are paired by number, and only numbers
   that occur once in each footprint count. The other pads (three pads named `GND`) are paired by net
   partition (change c0227): the pairs by number map each reference net to one board net; in a part, a
   net with one such pad on each side pairs them, and with more each pad pairs with the reference pad
   whose goal lies nearest where the fit by number puts it, both ways and within `--tolerance`. A net
   whose pads cannot be told apart (no fit by number, or a tie) leaves them unpaired; `by_net` counts the
   pads paired by net.
2. **The block transform** maps the reference board onto the board. It is fitted on the pads of the
   anchor (`--anchor`, default the first part of `--only`), which stays where it is: place the anchor
   first. The fit tries the four quarter turns, with and without a mirror, and takes for each the
   translation that minimises the squared distances (the difference of the centroids); the candidate
   whose farthest pad is closest wins. A mirror is decided by the pads, so a reference read with the Y
   axis up (as some formats store it) gives a mirrored transform and a correct copy. When the pads cannot
   tell (an anchor of two pads), the anchor's own sides decide.
3. **Each part** is fitted the same way: its pads, where they lie now, onto the block transform of its
   reference part's pads. The fit composed with the part's placement gives its new position, angle and
   side. A part whose farthest pad stays more than `--tolerance` (default 0.05 mm) from its goal is not
   placed (`reuse.no-fit`); a part placed on the side opposite to the one the block gives it fits only
   mirrored, which usually means a mirrored footprint (`reuse.mirror-suspected`). A turn or a side change
   re-places the footprint from its library definition, as `--move` does.
4. **Checks.** The moved pads are measured against their goals (`reuse.check-failed` past the
   tolerance), the copper check with the project's rules compares the board after the moves with the
   board before (a part moved onto copper is `reuse.check-failed`), and the legality check judges the
   layout as for every strategy.
5. **Copper** (`--copper`). The reference tracks, arcs and vias joined to the paired pads, through tracks,
   arcs, vias and those pads only, are mapped through the block transform. Each reference net goes to the
   board net of the pads paired with its pads (a net that two board nets claim is left out,
   `net-ambiguous`), and when the anchor lies on the other side than its reference part the layers mirror
   in the stack (`F.Cu` and `B.Cu`, `In1.Cu` and the last inner layer). The copy is then settled, pass
   after pass until nothing changes: `tidy.prune` removes copies with a free end and vias joined on fewer
   than two layers; the copies of a group are an `island` unless the group holds two pads, or one pad and
   a fill or copper of the board; and each copy that a new copper-check finding names is left out with the finding's code.
   The copies that stay are locked. `result.reuse.copper.dropped` lists every reference item left out.
   **Zones** (change c0227): a zone of a block net whose stored fill joins paired pads only (a small pour
   under a regulator) is copied with its outline and its fill; a zone read without an outline gets the
   outline of its fill (the polygon of its one fill, else the convex hull of its fills). A zone that also
   joins an unpaired pad (a plane of the whole board) is `zone-beyond-block`, one without a fill over a
   paired pad `zone-unfilled`, and a copied zone whose copper group lost the image of one of its pads
   `pad-lost`. The copied fill is the reference fill moved: run `fenolite fill` (`reuse.fill-stale`).
6. **`--drc`** asks `kicad-cli` too: DRC on the board before and after, and no write when a violation type
   grows (`reuse.drc-new`).

`result.reuse` holds the transform, per part the pads matched and within the tolerance, the farthest
pad, the placements before and after, and the copied and dropped copper. The evidence is `INFERRED`
(`H-G-REUSE-FIT`): the fit is measured on the board frame, and no tool compares the copy with the
reference. After `--drc` it adds `H-K-REUSE-DRC` with the tool's version.

A part that does not fit stays where it was. A copied zone adds `H-G-REUSE-ZONE` to the evidence.

## Group moves

```sh
fenolite place build/board --turn U1,C1,C2,C3,C4 --about 20mm,20mm --pose-search --within 2mm
fenolite place build/board --turn U1,C1,C2,C3,C4 --about 20mm,20mm --angle 90 --confirm
fenolite place build/board --shift U1,C1,C2,C3,C4 --by 1mm,-1mm --confirm
```

`--turn REFS --about X,Y --angle DEGREES` and `--shift REFS --by DX,DY` (change c0227, the strategy
`group`) move a module and its satellites as one rigid piece. `X,Y` is in the frame of `--move`.

1. **Parts.** The move (a turn about the point, or a shift) is composed with each part's placement, so
   its new angle comes from its pads and a part on the bottom turns the right way. Every moved pad is
   measured against the move of its old position: farther than 1 µm is `place.group-failed`.
2. **Copper.** Each joined group of a net (tracks, arcs, vias and pads, without fills) that holds a pad of
   the group and no other pad moves with it, and each zone whose stored fill joins pads of the group only
   (its fill moves too: `place.fill-stale`). The copper on the group's pads is dragged (change c0432): a
   via that touches a pad of the group and no pad of another part moves with it, and the end of a track
   that touches a pad of the group or such a via moves too, its other end staying, so the track stretches.
   An arc that joins the group to another part stays (`place.copper-left`), as all copper does for
   `--move`.
3. **Checks.** The copper check with the project's rules compares the board before and after; a new
   finding is `place.group-failed` and nothing is written. The legality check judges the layout as for
   every strategy.
4. **`--pose-search`** (with `--turn` and `--about`, `--within` instead of `--angle`) writes nothing. It
   tries the four quarter turns about the point with every shift of step `--pitch` within `--within` on
   each axis, and ranks them by demand: per net with a pad in the group and one outside, the shortest
   distance between them, summed. `result.group.search` holds the demand of the group where it is
   (`current`) and the ten best poses; apply one with `--turn ... --angle` and `--shift`. The demand is a
   lower bound of the routing and the poses are not judged for legality.

The evidence is `INFERRED` (`H-G-GROUP-MOVE` and the rows of the copper check); `H-K-GROUP-DRC` records
that KiCad's DRC finds nothing new on a turned module of the bench.

## Placement in code

A script can place parts without coordinates (change c0255; `docs/dsl.md`, "Relative placement" and "Block
layout"). Unlike the strategies of `fenolite place`, which move footprints on a built board, these are
resolved by `fenolite build` before it writes: `fenolite.placement.relative.resolve` turns every relative
request, block pose and frame strategy into integer nanometres, and `fenolite.placement.strategies.arrange`
lays out the boxes of a frame.

- **Boxes.** A part's box is `footprint_extent` (the courtyard box, else the pad boxes) turned by its
  rotation and mirrored for the bottom side; with `by=` the box of that pad. A turn other than a quarter
  turn takes the bounds rounded outward (`Transform.apply_bbox`); a centre is `(a + b) // 2`.
- **Frames.** The top and each block instance are frames. Each is resolved in its own coordinates, innermost
  first: absolute requests, then the frame's strategy or block reuse, then the relative requests in
  topological order of their references, ties by path. A block's box is the union of its placed items;
  its pose puts its frame into the parent's. World positions are the poses composed top-down; a turned
  position rounds half to even.
- **Strategies.** `row` and `column` from `at`, `gap` apart, aligned on start edges, centres or end edges;
  `grid` in cells of the largest box plus `gap`; `pack` in shelves within a width, tallest first, a box
  wider than the width on a shelf of its own (`layout.strategy-overflow`). Creation order, no search.
- **Against the board.** The resolution is the code side of the precedence (`docs/lens.md`, "Placement
  precedence"); it is resolved again against the placements that the board or `edits.toml` decided, so a
  follower follows its reference. Block poses are resolved from the code alone.
- **Evidence.** `INFERRED` with `H-G-REL-RESOLVE`: a resolved position satisfies its request exactly,
  measured on the written board by the same box function (`tests/unit/cli/test_build_relative.py`); the
  KiCad read-back of `examples/relative/` on targets 9 and 10 holds every relation within 1 nm.
- **Codes.** `layout.relative-cycle` (error), `layout.relative-unresolved`, `layout.strategy-overflow`
  (warnings), `layout.block-moved` (info) and, for a block reuse, `reuse.port-unmapped` (error),
  `reuse.unknown-part` (warning) and `reuse.no-fit` (error) (`docs/cli-contract.md`, "build").

## How a placement survives a build

The board is the layout authority (`docs/lens.md`). A part that `place` moved onto the board is on the
board, so the next `fenolite build` keeps it there. A part with a locked `place()` in the script goes
back to the script's placement; `place` warns about it with `place.script-locked`.

## Joint optimization proposals (c0477)

```sh
fenolite place BOARD --strategy optimize --constraints placement.json --dry-run --json
```

The [request schema](../schemas/fenolite.placement-optimization.v0.json) uses exact footprint
IDs, optional allowed angles in microdegrees and a bounded work budget. The strategy uses
board coordinates in nm and keeps the current side. With no angle list it keeps the
current orientation. Locked, excluded and copper-attached footprints stay fixed. Regions,
margins and sampling parameters come from the request.

The reply lists sampled domains, fixed reasons, blockers, the deepest partial assignment and
complete proposals. It ranks them by reviewed pad-to-pad distance, missing channel inputs,
estimated channel overflow, half-perimeter wire length and movement. Reviewed `proximity`
intents seed poses near fixed endpoints and use two physical pad IDs. Required maximum
distances are hard constraints.
Unknown reviewed intent is reported without scoring it. Each proposal lists unavailable checks
and conservative extents. Exploration creates no board writes or confirmable plan.

On rectangular outlines with supported copper and rules, the estimator samples three cuts
per axis on each routing layer. It uses pad, hole, track, via and cutout bounds and the
known track widths and clearances of affected nets. A recognized differential pair with
known dimensions claims one combined lane. Ambiguous layers and unsupported geometry
appear in `missing_inputs`. The `channel_overflow_by_layer` values are congestion estimates
in nm of unserved lane width summed across the measured cuts.

Add a reviewed intent with `kind: "escape"`, `required: true`, two exact physical pads of
one net and a positive `max_distance_nm` to require a bounded routing probe. For escape
intent the distance is a limit on the provisional track length. Set `budget.probe_expansions`
to allocate work across the shortlist and all its probe subjects. Every candidate has the
same per-subject limit. The probe checks same-layer connections without vias and reserves
each successful provisional route for the next subject. If the shortlist fails the probes,
bounded refinement tries nearby poses with the same subject set and per-subject limit. Required failures appear as
`probe:<intent-key>:<status>`; successful candidates report the track length and work for
each checked connection in `probes`.
Review repeats the probes. Differential pairs, zones and other unsupported geometry can
block this check. The probe's result covers the supplied scope and budget. Confirmation
writes only the component poses. For a gate drive and its tracked return, use one
`gate-loop` intent with four pads in order: the two drive endpoints followed by the two
return endpoints. Each pair must share its own net. The two paths must coexist and each
must meet the supplied length limit. Plane returns and coupled routing are unavailable in
this placement probe.

### Review and apply a KiCad candidate

Save the full JSON reply, choose an ID from `result.optimization.candidates`, and review that
specific candidate. Open the saved reply in the viewer with
`fenolite view working.kicad_pcb --placement proposals.json --serve`, or export a standalone
page. Take `PLAN_ID` from `result.plan_id` of the review reply.

```sh
fenolite place working.kicad_pcb --strategy optimize --constraints placement.json --dry-run --json > proposals.json
fenolite place working.kicad_pcb --strategy optimize --constraints placement.json --proposal proposals.json --candidate ID --dry-run --json
fenolite place working.kicad_pcb --strategy optimize --constraints placement.json --proposal proposals.json --candidate ID --confirm --plan PLAN_ID --json
```

Review rechecks the exact poses on the current board and verifies the staged KiCad readback.
Confirmation replays those staged bytes. Keep the board, its project rules, the request and
the proposal fixed between review and confirmation. When an input changes, generate and
review a new proposal. Applied placements follow the existing layout precedence on rebuild.

### Review from a served viewer

```sh
fenolite view working.kicad_pcb --placement proposals.json --placement-request placement.json --serve --allow-actions
```

Open Project Review and choose **Refine placement** to use the same explicit request with
the current board and anchors. Under Actions choose **Apply placement candidate** and select
the candidate you reviewed. The dialog previews the staged board before you confirm. A board
change invalidates an earlier proposal and plan. A static export provides the candidate overlays
for inspection.

### Plan declared blocks in Python

`fenolite.placement.floorplan.bind_blocks` binds captured block layouts to the model's exact
footprints, pads and ports. Give each block reviewed origin alternatives, the fixed footprint
IDs and a layout projector. For a captured layout, use
`functools.partial(fenolite.reuse.blocklayout.apply_block_layout, saved_layout)` as the projector. Rigid blocks keep one transform across their members. Flexible blocks use the transformed
positions as member seeds. `plan_block_regions` compares the hierarchy with net-weighted
coarsening under the supplied area and region restrictions. `search_region_placements` expands
the region choices using the board frame and a whole-board judge. It tries bounded reassignments
across shared boundaries and reports every block that cannot fit. This API requires a resolved
Fenolite design with block instances and captured layouts.

### Use an Altium board

Pass a `.PcbDoc` or a `.PrjPcb` with exactly one readable PCB as `BOARD` to generate proposals
from native Altium geometry. To apply positions and open the result in Altium, convert into
a separate working directory, then optimize and review that KiCad copy.

```sh
fenolite convert source.PcbDoc --to kicad --out working --dry-run --json
fenolite convert source.PcbDoc --to kicad --out working --confirm --plan PLAN_ID --json
```

Use the generated `.kicad_pcb` as the placement input. Prepare the request with the working
board's footprint IDs and pad IDs, since conversion can change identities. The following
prints the identities from the authored blink board after conversion. Adjust the path to
match the conversion output.

```sh
uv run python - working/blink.kicad_pcb <<'PYTHON'
import sys
from pathlib import Path
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.replace import footprint_ref

design = read_board(Path(sys.argv[1]))
assert design.board is not None
for fp in design.board.footprints:
    print(footprint_ref(design, fp), fp.id, [(pad.number, pad.id) for pad in fp.pads])
PYTHON
```

For a first run, set `selected` to the footprint IDs you want to move and use the request below
with those IDs. Add reviewed proximity intents when you have confirmed the physical endpoints
that should stay close. Review any fixed reasons, especially when the board already has copper.

```json
{
  "schema": "fenolite.placement-optimization.v0",
  "selected": ["FOOTPRINT_ID"],
  "budget": {"evaluations": 64, "beam_width": 2},
  "constraints": {"max_candidates": 12, "pitch": 500000}
}
```

After applying the placement to the KiCad copy, review the conversion report and export a new
`.PcbDoc` to another directory.

```sh
fenolite convert working/blink.kicad_pcb --to altium --out exported --altium-pour outline --dry-run --json
fenolite convert working/blink.kicad_pcb --to altium --out exported --altium-pour outline --confirm --plan PLAN_ID --json
```

Each conversion uses its own plan ID. Inspect the reported conversion losses. The `outline`
option writes polygon outlines for repouring in Altium. Open the exported board in Altium
Designer, repour as applicable and run native DRC. Fenolite tests the exported file by
rereading it. Native editing of the source `.PcbDoc` remains gated on Altium Designer evidence.

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
A `GroupRegion` confines listed footprint extents. Edge/gap, outline/cutouts and slots, per-face keepouts,
drills crossing both faces and duplicate drill intents are checked. `MechanicalReservation` links
one existing drill pad to supplied physical volumes and measured/proposed source intent. Reservation
geometry is independent of drill diameter and neither creates holes nor disconnects copper.
`MechanicalConstraints` carries supplied board thickness, allowed penetrations, obstacles and named
missing assembly inputs. No application geometry is assumed.

The rings of the outline are those of `model.outline.outline_items` (change c0170;
`placement.legality.outline_rings`): the board ring and each cut-out by their vertices, and each slot of
`design.slot()` as its stadium polygonised within 1 µm. A courtyard over a slot is therefore reported
`cutout:<footprint>` as it is over the same ring drawn with `design.cutout()`, the preview draws the slots,
and the body-volume analysis counts a body that reaches through a slot as meeting no board material, as
through a convex cut-out (`tests/unit/placement/test_slot_obstacles.py`).

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

## Block layouts

A versioned `fenolite.block-layout.v0` TOML file stores exact part positions and copper in the block
frame: `b.layout(reuse="layouts/divider.toml", copper=True)` makes it the body's level 5 layout;
`inst.layout(...)` overrides the body's choice. The footprint set and pad numbers must match the
`parts_digest`; a mismatch gives `reuse.layout-stale` and stages the children. A changed local net map
places the parts and omits copper (`reuse.layout-nets`). Another block id or major version refuses the
build (`reuse.layout-block`). An older compatible layout applies with `reuse.layout-older`.
The file format is documented in [block-layout.md](formats/fenolite/block-layout.md).

`inst.place(mm(10), mm(8), side="bottom")` mirrors the entire block about its local vertical axis,
then applies its turn and translation. Every child flips side; layout copper maps through the same
transform, with front/back and inner copper layers mirrored through the stack. Changing the side of
a kept block pose carries its parts and the copper joined only to their pads (`layout.block-moved`).

Capture from a bench script with one laid-out block instance and every external net bound to a port:
`fenolite blocks capture out --instance dut -o layouts/divider.toml --dry-run --json`, review the plan,
then repeat with `--confirm --plan ID`. The command uses the recorded pose or `--origin anchor
--anchor top`, selects copper joined only to that instance and checks a 1 µm fit round trip. Copper that
joins outside pads stays out with `blocks.capture-copper-left`. It never edits the Python block; add
the `b.layout(reuse=...)` line explicitly. See [the example](../examples/blocks/layouts.py).
