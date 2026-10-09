## ADDED Requirements

### Requirement: Placement rules judged
`fenolite.checks.placement.judge(design, rules, *, pads) -> RuleReport` SHALL judge the `near` rules of `rules` on the board of `design`, and SHALL return `RuleReport(issues, counts)`. It lives in `checks` because the stage of `verification-loop`, "Placement rules stage", runs it, and `place` and `build` call it from the CLI (`package-layering`).
- **Inputs.** `design` is a board model: a board read from a file of any backend, or the planned board of a build read back. `pads` is its `BoardFrame.board_pads`. `rules` is `rules_of(model)`, a `PlacementRules` that holds `RuleSet.proximity` of the model that carries the rules (the `.fenolite/` model of a built project, or the built model). The component path of a footprint is its component's `fenolite.path` property, else its reference.
- **Board.** `board_box(design)` is the box of `Board.outline` when the model holds one, else of the graphics on the layers of kind `edge` (an arc by its exact box), else `None`. A footprint whose position lies outside that box is off the board; a rule that names it is not judged for it and gives `placement.rule-skipped` (info). Without a box every footprint is on the board.
- **Near.** The selected pads of a `PadSelection` are the pads of the footprint with its path whose number equals `number`, every pad when `number` is empty, or only the one at `index` among them in the footprint's pad order. For each `ProximityRule` and each distinct path of its `parts`, the rule holds when one of the path's selected pads and one selected pad of `anchor` have positions (`BoardPad.position`) at a distance of at most `within`, compared on squared integers without rounding. Otherwise it MUST give one `placement.too-far` with the rule's severity, whose `where` is the part's reference and whose message names the rule, the path, the nearest anchor pad as `REF-NUMBER`, the distance rounded up to the nanometre and written in millimetres, and `within`. A distance that is printed is therefore above `within` exactly when the rule fails. A path in both `parts` and `anchor` is at distance 0.
- **Unresolved.** A selection whose path has no footprint, or whose number or index the footprint lacks, MUST give one `placement.rule-unresolved` (error) naming the rule and the selection; an unresolved anchor leaves its rule unjudged.
- **Counts.** `counts` MUST be a mapping from a rule family to its counts. This requirement gives the family `near`: `{"near": {"judged", "failed", "skipped"}}`, one count per rule and path. A later requirement may add a family; callers MUST print the mapping as it is.
- Issues MUST be sorted by code, then `where`, then message. The function MUST read no file and use no clock, and equal inputs MUST give equal outputs.

#### Scenario: Decoupling rule met and missed
- **GIVEN** a board whose pad 7 of `U1` lies at (10, 10) mm, pad 1 of `C5` at (11.5, 10) mm and pad 1 of `C6` at (14, 10) mm, and the rule `ProximityRule("dec", (PadSelection("C5", "1"), PadSelection("C6", "1")), (PadSelection("U1", "7"),), 2_000_000)`
- **WHEN** `uv run pytest tests/unit/checks/test_placement_rules.py -k decoupling` runs `judge`
- **THEN** it gives one `placement.too-far` error with `where == "C6"`, naming `dec`, `U1-7`, 4 mm and 2 mm, and `counts == {"near": {"judged": 2, "failed": 1, "skipped": 0}}`

#### Scenario: Distance equal to the limit
- **GIVEN** the same board with pad 1 of `C6` at (12, 10) mm
- **WHEN** `judge` runs
- **THEN** it gives no `placement.too-far`

#### Scenario: A distance just above the limit is printed above it
- **GIVEN** the same board with pad 1 of `C6` at (11, 11.732051) mm, whose distance to pad 7 of `U1` is 2 mm plus a fraction of a nanometre
- **WHEN** `judge` runs
- **THEN** it gives one `placement.too-far` whose message names 2.000001 mm, never 2 mm

#### Scenario: Unresolved and skipped rules
- **GIVEN** a rule naming `ch9/C1`, which the board does not hold, and a rule naming `C7`, whose footprint lies outside the board's box
- **WHEN** `judge` runs
- **THEN** it gives `placement.rule-unresolved` for the first rule and `placement.rule-skipped` (info) for `C7`

#### Scenario: A board read from an Altium document
- **GIVEN** `examples/blink_routed/design.py` built with `--target altium --confirm`, the PCB reading of its `.PcbDoc`, the pads of `AltiumBackend().board_pads`, and the rule `ProximityRule("led", (PadSelection("D1"),), (PadSelection("R1", "2"),), 5_000_000)`
- **WHEN** `uv run pytest tests/unit/checks/test_placement_rules.py -k altium` runs `judge`
- **THEN** it gives one `placement.too-far` with `where == "D1"`, the same verdict as on the KiCad build of that script

### Requirement: Placement measures
`fenolite.checks.placement.measure(design, *, pads, pitch=None) -> Measures` SHALL give the wire length and the congestion of a placement from pad positions, in integers, and `Measures.to_json()` SHALL give `{nets, hpwl, ratsnest, longest, left_out, congestion}`.
- **Pads and nets.** The counted pads are those of the footprints on the board ("Placement rules judged"). A measured net holds at least two counted pads and no `Zone` of the board is on it. `left_out` MUST count `zone_nets`, `one_pad_nets` (nets with fewer than two counted pads) and `off_board` (footprints off the board).
- **Lengths.** `hpwl` MUST be the sum over measured nets of the width plus the height of the box of their pad positions. `ratsnest` MUST be the sum over measured nets of the length of a Euclidean minimum spanning tree of their pad positions, found by comparing squared distances exactly, each edge floored to the nanometre. `longest` MUST hold up to five entries `{net, pads, hpwl, ratsnest}` in decreasing `hpwl`, ties by net name. `nets` counts the measured nets.
- **Congestion.** `None` without a board box. Otherwise the cells are squares of side `cell`, 2 mm or the longer side of the box divided by 128 and rounded up to a whole micrometre, whichever is larger, laid from the box's top-left corner. Each measured net's box is grown, around the floor of its mid point, to at least `cell` in width and in height. Its share in a cell is its `hpwl` times the area its grown box shares with the cell, divided by the grown box's area, floored; a cell's `tracks` is the sum of the shares divided by `cell`, floored. With a `pitch` no larger than `cell`, `tracks_per_layer` MUST be `cell` divided by `pitch`, floored, and `layers_needed` MUST map each number of layers k to the number of cells with at least one track whose `tracks` divided by `tracks_per_layer`, rounded up, is k; otherwise both MUST be `None`. `busiest` MUST hold up to five cells with at least one track, `{x, y, tracks}`, in decreasing `tracks`, then by row, then by column, `x` and `y` being the cell's centre measured from the box's top-left corner.
- `congestion` MUST be `{cell, pitch, tracks_per_layer, busiest, layers_needed}`. The reply MUST stay bounded: five nets and five cells whatever the board.
- The function MUST read no file, use no clock and no float, and give equal outputs for equal inputs.

#### Scenario: Lengths computed by hand
- **GIVEN** a board whose box is 20 mm × 10 mm, a net `A` with pads at (2, 2), (6, 2) and (6, 5) mm, a net `B` with pads at (1, 8) and (19, 8) mm, a net `C` with pads at (0, 0) and (3, 4) mm, a net `GND` with three pads and a zone, a net `N1` with one pad, and a footprint off the board with a pad on `A`
- **WHEN** `uv run pytest tests/unit/checks/test_placement_measures.py -k by_hand` runs `measure`
- **THEN** `hpwl` is 32 mm, `ratsnest` is 30 mm, `nets` is 3, `left_out` is `{"zone_nets": 1, "one_pad_nets": 1, "off_board": 1}` and `longest[0]["net"]` is `B`

#### Scenario: Congestion of two cells
- **GIVEN** a board whose box is 4 mm × 2 mm, ten nets each with pads at (0.5, 1) and (3.5, 1) mm, and `pitch` 0.4 mm
- **WHEN** `measure` runs
- **THEN** `cell` is 2 mm, both cells carry 7 tracks, `tracks_per_layer` is 5, `layers_needed` is `{2: 2}`, and `busiest` lists (1, 1) mm and then (3, 1) mm

#### Scenario: No pitch
- **WHEN** `measure` runs on the same board without `pitch`
- **THEN** `tracks_per_layer` and `layers_needed` are `None`, and `busiest` is unchanged

## MODIFIED Requirements

### Requirement: Placement legality
`placement.legality.check(extents, outline_rings, *, edge_clearance=0, names, keepouts=(), touching_overlaps=TOUCHING_OVERLAPS) -> tuple[Issue, ...]` SHALL judge a layout with exact integer predicates and report:
- `place.courtyard-overlap` (error, `where` = the two references sorted and joined by a comma) for each pair of footprints that have rings on the same face whose interiors intersect; rings that only touch count as an overlap exactly when `touching_overlaps` is true;
- `place.outside-outline` (error, `where` = the reference) for each footprint with a ring point outside the board ring or inside a cut-out ring; a ring that only touches a boundary is inside;
- `place.edge-clearance` (warning) for each footprint inside the board whose ring is closer to a board or cut-out boundary than `edge_clearance`;
- `place.keepout` (error, `where` = the reference), once per footprint and keep-out, for each footprint whose extent has `source` `courtyard` or `definition` and each `Keepout` of `keepouts` with `no_footprints`, when the keep-out's layers hold `F.Cu` and the interior of one of the footprint's front rings meets the interior of the keep-out's outline, or they hold `B.Cu` and a back ring does; rings that only touch the outline do not meet it, and a keep-out on inner layers only judges no footprint. The message names the keep-out by its `name` when it has one, and the face;
- `place.keepout-no-courtyard` (warning, `where` = the reference) for the same test on a footprint whose extent has `source == "pads"`, the hull of its pads; KiCad's DRC does not report such a footprint (`H-K-PLACE-KEEPOUT`);
- `place.no-extent` (info) for each footprint whose extent has `source == "none"`, which is then not judged;
- `place.no-outline` (info), once, when `outline_rings` is empty; only overlaps and keep-outs are then judged.

`placement.legality.edge_clearance(design)` SHALL give the smallest `min` of the design's rules of kind `edge_clearance` whose first selector is `all`, and 0 without one.

`TOUCHING_OVERLAPS` MUST equal what the committed probe files record for `place-touch` (`H-K-PLACE-TOUCH`). `placement.legality.KEEPOUT_EVIDENCE` MUST name `H-K-PLACE-KEEPOUT` and be `KICAD-VERIFIED` exactly when that row is `KICAD-VERIFIED (9.0.x, 10.0.x)`, else `INFERRED`. Issues MUST be sorted by code, then `where`. A footprint on the top side MUST be judged with its front rings against other footprints' front rings, and likewise for back rings.

#### Scenario: Overlap named
- **GIVEN** two authored extents whose front rings overlap by 20 µm and a third that is clear of both
- **WHEN** `uv run pytest tests/unit/placement/test_legality.py -k overlap` runs `check`
- **THEN** it reports one `place.courtyard-overlap` whose `where` holds the two references, and nothing for the third

#### Scenario: Opposite faces do not overlap
- **GIVEN** two extents at the same position, one with only front rings and one with only back rings
- **WHEN** `check` runs
- **THEN** it reports no `place.courtyard-overlap`

#### Scenario: Outside the outline and in a cut-out
- **GIVEN** a 50 × 30 mm board ring with a 10 mm square cut-out, one extent across the right edge and one inside the cut-out
- **WHEN** `check` runs
- **THEN** it reports `place.outside-outline` for both

#### Scenario: Edge clearance
- **GIVEN** an extent 0.2 mm from the board edge and `edge_clearance` of 0.5 mm
- **WHEN** `check` runs
- **THEN** it reports one `place.edge-clearance` warning, and none with `edge_clearance` of 0

#### Scenario: Rotated extent
- **GIVEN** the extent of a 4 × 1 mm courtyard placed at 270° beside another part, clear at 0° and overlapping at 270°
- **WHEN** `check` runs on both layouts
- **THEN** only the 270° layout gives `place.courtyard-overlap`

#### Scenario: Keep-out by face
- **GIVEN** a keep-out with `no_footprints` on `F.Cu` only, a top-side extent whose front ring enters it by 10 µm, a bottom-side extent wholly inside it, and the same keep-out moved to `B.Cu` only
- **WHEN** `uv run pytest tests/unit/placement/test_legality.py -k keepout` runs `check` on both
- **THEN** the `F.Cu` keep-out gives `place.keepout` for the top-side part only, and the `B.Cu` keep-out for the bottom-side part only

#### Scenario: Touching keep-out
- **GIVEN** a keep-out with `no_footprints` whose edge lies on the courtyard line of a top-side extent
- **WHEN** `check` runs
- **THEN** it reports no `place.keepout`

#### Scenario: Part without a courtyard
- **GIVEN** an extent of source `pads` wholly inside a keep-out with `no_footprints` on `F.Cu`, and a board without a closed outline
- **WHEN** `check` runs
- **THEN** it reports one `place.keepout-no-courtyard` warning, no `place.keepout`, and `place.no-outline`
