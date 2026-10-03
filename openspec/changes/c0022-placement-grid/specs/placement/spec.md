## ADDED Requirements

### Requirement: Placement package
`fenolite.placement` SHALL hold the placement strategies and the legality check, working on plain data of `fenolite.backends.base` (`PlacedExtent`), `fenolite.geometry` and `fenolite.model`. It MUST import no backend module (`package-layering`), MUST use no random generator and no clock, and MUST give equal results for equal inputs.

#### Scenario: Layering holds
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes, and a module under `src/fenolite/placement/` that imports `fenolite.backends.kicad` makes it fail naming `placement → backends.kicad`

### Requirement: Placement legality
`placement.legality.check(extents, outline_rings, *, edge_clearance=0, names, touching_overlaps=TOUCHING_OVERLAPS) -> tuple[Issue, ...]` SHALL judge a layout with exact integer predicates and report:
- `place.courtyard-overlap` (error, `where` = the two references sorted and joined by a comma) for each pair of footprints that have rings on the same face whose interiors intersect; rings that only touch count as an overlap exactly when `touching_overlaps` is true;
- `place.outside-outline` (error, `where` = the reference) for each footprint with a ring point outside the board ring or inside a cut-out ring;
- `place.edge-clearance` (warning) for each footprint inside the board whose ring is closer to a board or cut-out boundary than `edge_clearance`;
- `place.no-extent` (info) for each footprint whose extent has `source == "none"`, which is then not judged;
- `place.no-outline` (info), once, when `outline_rings` is empty; only overlaps are then judged.

`TOUCHING_OVERLAPS` MUST equal what the committed probe files record for `place-touch` (`H-K-PLACE-TOUCH`). Issues MUST be sorted by code, then `where`. A footprint on the top side MUST be judged with its front rings against other footprints' front rings, and likewise for back rings.

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

### Requirement: Grid placement
`placement.grid.place(boxes, region, *, occupied, cutouts=(), pitch=500_000, gap=500_000, margin=1_000_000) -> GridResult` SHALL give a position to each box, in the order given, by shelf packing inside `region` inset by `margin`:
- a box MUST go at the first position, scanning rows top to bottom and columns left to right on a `pitch` grid, at which the box grown by `gap` on every side intersects no occupied box, no cut-out and no box placed before it;
- a row's height MUST be the tallest box placed in it;
- a box that fits nowhere MUST be listed in `GridResult.unplaced` and MUST get no position;
- every position MUST be a multiple of `pitch` from the inset region's top-left corner.

#### Scenario: Deterministic rows
- **GIVEN** five authored boxes and a 20 × 10 mm region
- **WHEN** `uv run pytest tests/unit/placement/test_grid.py -k rows` calls `place` twice
- **THEN** both results are equal, the boxes fill the first row left to right in the given order, and the next row starts below the tallest box of the first

#### Scenario: Occupied area avoided
- **GIVEN** an occupied box in the top-left of the region
- **WHEN** `place` runs
- **THEN** no placed box, grown by `gap`, intersects it

#### Scenario: No room
- **GIVEN** a box wider than the inset region
- **WHEN** `place` runs
- **THEN** it is in `unplaced` and has no position

### Requirement: Placement issue codes
`placement.ISSUE_CODES` SHALL map every code that `placement` and the `place` command emit to one severity, and SHALL hold at least: `place.courtyard-overlap` (error), `place.outside-outline` (error), `place.no-definition` (error), `place.locked` (error), `place.unknown-ref` (error), `place.edge-clearance` (warning), `place.no-room` (warning), `place.copper-left` (warning), `place.script-locked` (warning), `place.no-extent` (info), `place.no-outline` (info). `docs/cli-contract.md` MUST document every key.

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/placement -k codes` collects every `place.*` literal under `src/fenolite/placement/`, `backends/kicad/replace.py` and `cli/cmd_place.py`
- **THEN** each is a key of `ISSUE_CODES`, and every key appears in `docs/cli-contract.md`

### Requirement: Placement evidence
`placement.EVIDENCE` SHALL be `INFERRED` and name `H-K-PLACE-MOVE` and `H-K-PLACE-TOUCH`, and SHALL become `KICAD-VERIFIED` only when both rows are `KICAD-VERIFIED (9.0.x, 10.0.x)`. A placement is never a verdict: KiCad's DRC judges the board.

#### Scenario: Evidence follows the register
- **WHEN** `uv run pytest tests/unit/placement -k evidence` reads `docs/hypotheses.md`
- **THEN** the level of `placement.EVIDENCE` is `KICAD-VERIFIED` exactly when both rows are verified on both majors
