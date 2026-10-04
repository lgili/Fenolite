# board-analyses Specification

## Purpose
TBD - created by archiving change c0047-board-analyses. Update Purpose after archive.
## Requirements
### Requirement: Analysis package and report
`fenolite.analysis` SHALL hold the analyses of a board on the neutral model. It MUST import only the standard library, `core`, `model`, `geometry` and `backends.base` (`package-layering`, "Allowed import edges"), and its functions MUST be pure: they read no file, run no subprocess and write nothing.
- `fenolite.analysis.report.AnalysisReport` MUST be a frozen dataclass with `rows` (a tuple of `CurrentRow` or `DistanceRow` records), `issues` (a tuple of `Issue`), `summary` (a mapping of counts) and `evidence` (`Evidence`).
- Every length in a row MUST be an `int` in nanometres, every current an `int` in milliamperes, every temperature an `int` in millikelvin and every voltage an `int` in millivolts. No row field, summary value or issue text MUST come from a `float`.
- `rows` and `issues` MUST be sorted: rows by net names, then layer, then `where`; issues by code, `where`, message. The same inputs MUST give equal reports.

#### Scenario: Pure and repeatable
- **GIVEN** the design read from `tests/data/kicad/board/two_layer.kicad_pcb`, and `subprocess.run`, `subprocess.Popen` and `open` patched to raise
- **WHEN** `uv run pytest tests/unit/analysis/test_report.py -k pure` calls `analyze_current(design, temp_rise_mk=10_000, copper_thickness={"*": 35_000})` twice
- **THEN** both calls return equal reports and nothing raised

#### Scenario: No float in the source
- **WHEN** `uv run pytest tests/unit/analysis/test_report.py -k no_float` scans the AST of every module of `src/fenolite/analysis/`
- **THEN** no module names `float`, `math.sqrt`, `math.pow` or a float literal

### Requirement: Published capacity fit
`fenolite.analysis.current.capacity_ma(area_nm2, temp_rise_mk, *, external) -> int` SHALL return the current of the fit `I = K · ΔT^b · A^c`, with `I` in amperes, `ΔT` the temperature rise in kelvin and `A` the cross-section in square mils, as the source S-0269 states it. The module MUST define `FIT_K_EXTERNAL = Decimal("0.048")`, `FIT_K_INTERNAL = Decimal("0.024")`, `FIT_EXP_RISE = Decimal("0.44")`, `FIT_EXP_AREA = Decimal("0.725")` and `MIL_NM = 25_400`.
- The value MUST be computed with `decimal` in a local context of 40 digits, with `A = area_nm2 / MIL_NM²` and `ΔT = temp_rise_mk / 1000`, and MUST be returned in milliamperes rounded down, so a capacity is never overstated.
- `area_nm2` and `temp_rise_mk` MUST be `int`s above 0, else `ValueError`.
- The function MUST NOT read, embed or reproduce a chart, a table or a figure of any standard. Fenolite states the fit as S-0269 publishes it and claims no conformance to a standard.

#### Scenario: One millimetre track
- **WHEN** `uv run pytest tests/unit/analysis/test_current.py -k fit` calls `capacity_ma(1_000_000 * 35_000, 10_000, external=True)` and the same with `external=False`
- **THEN** the results are `2391` and `1195`

#### Scenario: Agreement with an independent computation
- **GIVEN** generated areas from 10⁹ to 10¹³ nm² and rises from 1 K to 100 K
- **WHEN** `uv run pytest tests/unit/analysis/test_current.py -k independent` compares `capacity_ma` with the same fit computed in the test with `math.exp` and `math.log`
- **THEN** every pair differs by at most 1 mA

#### Scenario: Invalid input
- **WHEN** `capacity_ma(0, 10_000, external=True)` and `capacity_ma(10**9, 0, external=True)` are called
- **THEN** each raises `ValueError`

### Requirement: Stated range of the fit
`fenolite.analysis.current` SHALL define the range in which S-0269 calls the fit valid: `FIT_MAX_EXTERNAL_MA = 35_000`, `FIT_MAX_INTERNAL_MA = 17_500`, `FIT_MAX_RISE_MK = 100_000` and `FIT_MAX_WIDTH_NM = 10_160_000` (400 mils). `in_range(width, temp_rise_mk, capacity_ma, *, external) -> bool` MUST be true only when the width, the rise and the capacity are each at most their limit. A row computed outside the range MUST carry `in_range=False`, and the report MUST hold one `analysis.fit-out-of-range` warning per net with the count of such rows. A via has no width; its row is judged by the rise and the capacity.

#### Scenario: Wide track flagged
- **GIVEN** a board with one 12 mm wide track on `F.Cu` and `copper_thickness={"*": 35_000}`
- **WHEN** `analyze_current(design, temp_rise_mk=10_000, copper_thickness=…)` runs
- **THEN** the row holds `capacity_ma == 14490` and `in_range is False`, and the issues hold one `analysis.fit-out-of-range` warning

### Requirement: Track and arc capacity
`fenolite.analysis.current.analyze_current(design, *, temp_rise_mk=None, copper_thickness=None, via_plating=None, requirements=None) -> AnalysisReport` SHALL give one `CurrentRow` per `Track` and per `Arc` of the board on a copper layer: `kind`, `where` (`provenance.locator`, else the entity id), `entity_id`, `net`, `layer`, `at` (the start point), `width`, `thickness`, `area_nm2`, `external`, `temp_rise_mk`, `capacity_ma` and `in_range`.
- The cross-section MUST be `width × thickness`. `external` MUST be true for the first and the last copper layer of `Board.layers` in table order, and false for the others.
- The thickness of a layer MUST be `copper_thickness[layer]`, else `copper_thickness["*"]`, else the `thickness` of the `StackLayer` of kind `copper` in `Board.stackup` whose `name` equals the layer name. Fenolite MUST NOT assume a thickness: an item whose layer has none MUST be left out and counted in `summary.skipped`, with one `analysis.input-missing` warning naming `copper thickness` and the count.
- The rise MUST be the `temp_rise_mk` of the governing current row of the item's net ("Requirement tables supplied by the user"), else the argument `temp_rise_mk`. Fenolite MUST NOT assume a rise: without one, the item is left out and counted the same way, the warning naming `temperature rise`.
- `summary.nets` MUST map each net name to the smallest `capacity_ma` of its rows and the `where` of that row. The analysis MUST NOT add the capacities of parallel items and MUST NOT judge zones. `summary.fit` MUST be `S-0269`, the source id of the fit.

#### Scenario: Quarter-millimetre track
- **GIVEN** a two-layer board with one track of net `VBUS`, 0.25 mm wide, on `F.Cu`
- **WHEN** `uv run pytest tests/unit/analysis/test_current.py -k track` calls `analyze_current(design, temp_rise_mk=20_000, copper_thickness={"*": 35_000})`
- **THEN** the report holds one row with `external is True`, `area_nm2 == 8_750_000_000` and `capacity_ma == 1187`, and `summary.nets["VBUS"]` names it

#### Scenario: Inner layer halves the constant
- **GIVEN** a four-layer board with the same 1 mm track on `F.Cu` and on `In1.Cu`
- **WHEN** `analyze_current(design, temp_rise_mk=10_000, copper_thickness={"*": 35_000})` runs
- **THEN** the rows hold 2391 mA with `external is True` and 1195 mA with `external is False`

#### Scenario: Nothing assumed
- **GIVEN** a board without a stackup and three tracks
- **WHEN** `analyze_current(design, temp_rise_mk=10_000)` runs
- **THEN** `rows` is empty, `summary.skipped == 3`, and the issues hold one `analysis.input-missing` warning naming `copper thickness` and 3

### Requirement: Via capacity
`analyze_current` SHALL give one `CurrentRow` of kind `via` per `Via` when `via_plating` is given. The cross-section MUST be the plated barrel, `π · (drill + via_plating) · via_plating`, with `Via.drill` taken as the finished hole diameter, rounded down to an integer by `barrel_area_nm2(drill, plating) -> int`, and the constant MUST be `FIT_K_EXTERNAL`, as S-0270 does (`H-G-AN-VIA`). `layer` MUST name the via's two layers joined by `/`. Without `via_plating`, vias MUST be left out and counted in `summary.skipped`, with one `analysis.input-missing` warning naming `via plating`. Fenolite MUST NOT assume a plating thickness.

#### Scenario: Via barrel
- **GIVEN** a via with `drill == 300_000`
- **WHEN** `uv run pytest tests/unit/analysis/test_current.py -k via` calls `analyze_current(design, temp_rise_mk=10_000, via_plating=25_000)`
- **THEN** the row holds `area_nm2 == 25_525_440_310` and `capacity_ma == 1902`

#### Scenario: Plating not given
- **GIVEN** a board with two vias and no track
- **WHEN** `analyze_current(design, temp_rise_mk=10_000)` runs
- **THEN** `rows` is empty and one `analysis.input-missing` warning names `via plating` and 2

### Requirement: Coefficients are recorded with their sources
`docs/analyses.md` SHALL hold the table "Capacity fit" with one row per constant of "Published capacity fit" and "Stated range of the fit" and for the barrel cross-section: the name of the constant in `fenolite.analysis.current`, its value, its unit, a source id registered in `docs/evidence/sources.md`, the evidence label `INFERRED` and a hypothesis id. Each row MUST state the fact in Fenolite's own words. The page MUST say that the source S-0269 attributes the fit to a standard which Fenolite did not consult, and MUST hold no table, chart or figure taken from a standard.

#### Scenario: Table equals the code
- **WHEN** `uv run pytest tests/unit/analysis/test_facts_page.py` parses the table "Capacity fit" of `docs/analyses.md`
- **THEN** every `FIT_*` constant and `MIL_NM` of `fenolite.analysis.current` has exactly one row with an equal value, every row names a registered source id, the label `INFERRED` and a registered hypothesis id

#### Scenario: Unsourced constant fails
- **GIVEN** a copy of the page whose `FIT_EXP_AREA` row has an empty source cell
- **WHEN** the checker of the same test reads it
- **THEN** it reports the row by name

### Requirement: Board boundary
`fenolite.analysis.boundary.board_boundary(board, *, arc_tol=DEFAULT_TOL, thickness=None) -> BoardBoundary` SHALL return the frozen record `BoardBoundary(outer, cutouts, thickness, band, source)`: the outer ring, the cut-out rings, the board thickness, the bound in nanometres of the approximation of curved edges, and `source`, one of `model`, `edge` and `none`.
- With `Board.outline`, `outer` MUST be its `points`, `cutouts` its `cutouts`, `band` 0 and `source` `model`.
- Otherwise the graphics on the layer of kind `edge` MUST be chained with `geometry.assemble_rings` by exact endpoint equality. Arcs and circles MUST be replaced by their polygonisation at `arc_tol`, and `band` MUST then be `arc_tol + 1`. The ring of largest area is `outer`; a ring inside it is a cut-out. `source` is `edge`.
- When no ring closes, or a `GeometryError` is raised, `source` MUST be `none` and `outer` empty; the function MUST NOT raise.
- `thickness` MUST be the argument when given, else the sum of the `thickness` of `Board.stackup.layers`, else `None`. Fenolite MUST NOT assume a board thickness.

#### Scenario: Outline from the model
- **GIVEN** a board whose `outline` is a 20 mm × 10 mm rectangle with one rectangular cut-out
- **WHEN** `uv run pytest tests/unit/analysis/test_boundary.py -k model` calls `board_boundary(board, thickness=1_600_000)`
- **THEN** `source == "model"`, `band == 0`, `len(cutouts) == 1` and `thickness == 1_600_000`

#### Scenario: Outline from edge graphics
- **GIVEN** a board without `outline` whose `edge` layer holds four lines closing a rectangle and four lines closing a slot inside it
- **WHEN** `board_boundary(board)` runs
- **THEN** `source == "edge"`, `outer` has four points, `cutouts` holds one ring and `thickness is None`

#### Scenario: Open contour
- **GIVEN** a board whose `edge` layer holds three lines that do not close
- **WHEN** `board_boundary(board)` runs
- **THEN** `source == "none"` and nothing raised

### Requirement: Copper of a net as thick shapes
`fenolite.analysis.copper.net_copper(design, *, pads, arc_tol=ARC_TOL_NM) -> NetCopper` SHALL turn the copper of the board into `Thick` shapes (`geometry-kernel`, "Thick shapes") per net and per copper layer, with the shapes that `copper-check` defines in "Copper items and their shapes": tracks, arcs as polylines with their band, vias on every layer of their span, pads from the `PadCopper` entries of c0028's `BoardPad` records, and zone fills. `fenolite.analysis` MUST NOT import `fenolite.checks`.
- Each shape MUST keep its item: `kind`, `where` (`REF-PIN` for a pad, `provenance.locator` otherwise), `entity_id` and its band (`arc_tol + 1` for an arc, else 0).
- Items that cannot be shaped, and every pad of a kind other than `np_thru_hole` when `pads` is `None`, MUST be counted per kind in `NetCopper.unsupported`; each analysis that uses the record MUST report one `analysis.item-unsupported` warning per kind with the count.
- Copper without a net MUST be left out.

#### Scenario: Shapes equal the copper check's
- **GIVEN** generated boards with tracks, arcs, vias, fills and fake `BoardPad` records
- **WHEN** `uv run pytest tests/unit/analysis/test_copper.py -k same_shapes` compares the shapes of `net_copper` with the copper items of `fenolite.checks.copper`
- **THEN** per layer and net, the two sets of `Thick` shapes are equal

#### Scenario: Layering holds
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes, and no module of `fenolite.analysis` imports `fenolite.checks`

### Requirement: Measures
A distance SHALL be reported as the frozen record `Measure(low, high, layer, points, items, bounded=False)`: `low` and `high` are integers in nanometres with `low ≤ d ≤ high`, `d` being the distance as this capability defines it; `layer` names the layer, or the two faces joined by `/`; `points` are the points of the path in order, rounded to integers; `items` are the `where` of the two copper items.
- When two shapes touch or overlap, `low` and `high` MUST be 0.
- `bounded` MUST be true only when a search stopped at its limit; `low` is then the limit and `high` is `None`. A bounded measure is judged by `low` alone: `low < r` is the `-undecided` warning.
- A requirement `r` MUST be judged the same way for every measure: `high < r` is a finding of severity `error`; `low < r ≤ high` is a finding of severity `warning` whose code ends in `-undecided`; `low ≥ r` is no finding.

#### Scenario: Judging an interval
- **WHEN** `uv run pytest tests/unit/analysis/test_distance.py -k judge` judges `Measure(low=5_100_000, high=5_100_002, …)` against 6 mm, 5.100001 mm and 5 mm
- **THEN** the verdicts are `error`, `warning` and none

### Requirement: Clearance on a layer
`fenolite.analysis.distance.analyze_distances(design, *, pads, boundary, pairs=(), within=None, requirements=None, arc_tol=ARC_TOL_NM) -> AnalysisReport` SHALL give one `DistanceRow(net_a, net_b, gaps, clearance, creepage)` per selected pair of nets, the names in sorted order.
- `gaps` MUST hold, for each copper layer that carries copper of both nets, a `Measure` of the smallest gap between a shape of one net and a shape of the other on that layer, the gap being that of `geometry-kernel`, "Exact gaps between thick shapes". `low` MUST be `thick_gap_floor` less the bands of the two items and not below 0; `high` MUST be `thick_gap_floor` plus 1 plus the bands; `points` MUST hold `thick_witness`.
- `clearance` MUST be the measure through air: the smallest of the `gaps` of the two outer copper layers and of the measure of "Clearance across the board edge". Cut-outs do not lengthen it. It is `None` when neither net has copper on an outer layer.
- Gaps on inner layers are distances inside the laminate. They MUST be reported in `gaps` and MUST NOT enter `clearance`.
- Selected pairs MUST be: each pair of `pairs`; each pair of nets that a distance row of `requirements` matches; and, with `within`, every pair of nets with a gap on a layer below `within`, found with one `SpatialIndex` per layer over `thick_bbox` grown by `within`. Without any of the three, `rows` is empty and one `analysis.input-missing` warning names `pair selection`.

#### Scenario: Two discs
- **GIVEN** a two-layer board with two through vias of diameter 1 mm, of nets `A` at (0, 0) and `B` at (10 mm, 0)
- **WHEN** `uv run pytest tests/unit/analysis/test_distance.py -k discs` calls `analyze_distances(design, pads=None, boundary=None, pairs=(("A", "B"),))`
- **THEN** the row holds a gap on `F.Cu` and on `B.Cu` with `low == 9_000_000` and `high == 9_000_001`, and `clearance.low == 9_000_000`

#### Scenario: Slot does not lengthen clearance
- **GIVEN** the same board with a rectangular cut-out from (4 mm, −3 mm) to (6 mm, 3 mm) between the vias
- **WHEN** `analyze_distances` runs with the boundary of the board
- **THEN** `clearance.low == 9_000_000` still

#### Scenario: Within finds the close pairs
- **GIVEN** 200 generated tracks on two layers and five nets
- **WHEN** `uv run pytest tests/unit/analysis/test_distance.py -k within` compares the pairs of `within=500_000` with those of a check of every pair of shapes
- **THEN** the two sets of pairs are equal

### Requirement: Creepage on the board surface
`fenolite.analysis.surface.surface_distance(a, b, boundary, *, limit=None) -> SurfacePath | None` SHALL search the shortest path along the board surface from a terminal of `a` to a terminal of `b`, a terminal being `Terminal(shape: Thick, face, band=0)` with `face` `top` or `bottom` and `band` the bound of the shape's approximation. The surface is the two outer faces inside `boundary.outer`, less the interior of every cut-out, joined by a wall of height `boundary.thickness` along every boundary edge.
- A path MUST be a chain of legs. A leg is a straight segment on one face that passes neither strictly inside a cut-out nor strictly outside `outer`; a wall drop of length `thickness` at a boundary vertex; or a wall crossing through the interior of one boundary edge, straight in the development that unfolds the two faces and the wall into one plane. A leg MAY run along a boundary edge.
- The search MUST consider paths that bend only at boundary vertices: the direct leg between each pair of core pieces of the two terminals, and legs from each core piece to each boundary vertex at the point of the piece nearest to it. Whether a leg is allowed MUST be decided with the kernel's exact predicates on integer or `Fraction` coordinates. Copper MUST NOT block a leg.
- The length of a leg from a shape MUST be the distance to its core less half its width. Lengths MUST be summed as integers scaled by 2²⁰ per nanometre, each a rounded-down square root, so the reported `length` is an integer with `length ≤ d < length + 2` on a boundary without curved edges. The direction across a wall MUST use a unit normal rounded at 2⁻⁶⁴.
- `SurfacePath` MUST hold `length`, `band` (`boundary.band` times the number of bends of the path, plus the bands of the two terminals it joins), `points`, each with its face, and `ends`, the indices of those two terminals in `a` and `b`.
- The search MAY leave out a leg that cannot lead to a shorter path: no path from a point to a conductor is shorter than their distance in plan view less the half width. Such pruning MUST NOT change the result.
- When `boundary.thickness` is `None`, no wall leg exists, and terminals on opposite faces are not joined.
- With `limit`, the search MAY stop when no path shorter than `limit` exists, and MUST then return `None`.
- Without `boundary`, or with `boundary.source == "none"`, the surface is one unbounded plane per face: only terminals on the same face are joined, by their gap.
- A terminal with a core point strictly outside `outer` or strictly inside a cut-out MUST be left out and counted as unsupported: `usable_terminals(terminals, boundary)` returns the terminals kept and the count left out, and `analyze_distances` reports that count in one `analysis.item-unsupported` warning.

`analyze_distances` MUST set `creepage` of a row from this search, over the shapes of the two nets on the two outer copper layers, the first copper layer being the `top` face: `low = max(0, length − band)`, `high = length + band + 2`. Holes, solder mask, coatings, components and copper of other nets MUST be ignored; `docs/analyses.md` MUST list them as limits.

#### Scenario: Around a slot
- **GIVEN** the two vias of "Two discs" and the cut-out from (4 mm, −3 mm) to (6 mm, 3 mm) in a 30 mm × 20 mm outline centred on (5 mm, 0)
- **WHEN** `uv run pytest tests/unit/analysis/test_surface.py -k slot` computes the creepage on the top face
- **THEN** `length == 11_000_000` (4.5 mm to the corner (4 mm, 3 mm), 2 mm along the slot, 4.5 mm from the corner (6 mm, 3 mm)), `band == 0`, the points name the two corners, and `clearance.low` is still 9 mm

#### Scenario: Slot open to the board edge
- **GIVEN** the same vias on a board whose outer ring has a notch from (4 mm, −10 mm) to (6 mm, 3 mm), open at the lower edge
- **WHEN** the creepage is computed with `thickness=None`
- **THEN** `length == 11_000_000`, the path passing the two upper corners of the notch

#### Scenario: Agreement with a grid search
- **GIVEN** generated rectangular boards with up to three rectangular cut-outs on a 0.1 mm grid and two disc terminals on the top face
- **WHEN** `uv run pytest tests/unit/analysis/test_surface.py -k grid` compares `length` with the shortest path of an eight-neighbour grid search at 0.1 mm
- **THEN** `length` is never above the grid's path length plus 1 nm, and never below 0.92 times it (the eight-neighbour metric overstates a straight length by at most 8.3 %)

#### Scenario: Limit stops the search
- **WHEN** the search of "Around a slot" runs with `limit=10_000_000`
- **THEN** it returns `None`, and the row's `creepage` has `bounded is True` and `low == 10_000_000`

### Requirement: Clearance across the board edge
For two nets with copper on opposite outer faces, `analyze_distances` SHALL report the path around the board edge when `boundary.thickness` is known and `boundary.source` is not `none`.
- The creepage is the result of "Creepage on the board surface", whose paths cross walls.
- The clearance across the edge MUST be the interval `low = dA + dB + thickness`, each of `dA` and `dB` being the smallest distance from the copper of one net on its face to the boundary, rounded down, and `high` the `high` of that creepage. A path through air leaves one face at the boundary, descends the thickness and reaches the other face, so it is never shorter than `low`; it is never longer than a surface path. `layer` MUST name the two faces joined by `/`.
- Without a thickness or a boundary, no path crosses a wall. A pair with copper only on opposite faces then has no clearance and no creepage, and one `analysis.input-missing` warning MUST name `board thickness` or `board outline` with the count of such pairs. A pair that also shares a face MUST be measured on each face alone and counted in `summary.faces_alone`, without a warning.

#### Scenario: Track above track
- **GIVEN** a 20 mm × 10 mm board from (0, 0), 1.6 mm thick, a 0.5 mm track of net `A` on `F.Cu` and one of net `B` on `B.Cu`, both from (5 mm, 2 mm) to (15 mm, 2 mm)
- **WHEN** `uv run pytest tests/unit/analysis/test_surface.py -k edge` analyses the pair
- **THEN** `creepage.low == 5_100_000` (1.75 mm to the edge, 1.6 mm down the wall, 1.75 mm back), and `clearance.low == 5_100_000` with `clearance.high == 5_100_002` and layer `F.Cu/B.Cu`

#### Scenario: Thickness unknown
- **GIVEN** the same board with `thickness=None`
- **WHEN** the pair is analysed
- **THEN** `clearance is None`, `creepage is None`, and one `analysis.input-missing` warning names `board thickness`

### Requirement: Requirement tables supplied by the user
`fenolite.analysis.requirements.load_requirements(text, *, file="") -> Requirements` SHALL parse a TOML document (`tomllib`) whose top-level key `schema` equals `fenolite.requirements.v0` and which holds any of the arrays `current`, `distance` and `step`. Every number MUST be a TOML integer; a float, an unknown key, a missing key or another `schema` MUST raise `FormatError` naming the file and the key.
- A selector is a table with exactly one of the keys `net` and `netclass`, whose value is a glob matched as `model.rules.Selector` matches it. A net without a class has the class `Default`.
- `[[current]]`: a selector under `select`, `milliamps` and `temp_rise_mk`. The governing row of a net MUST be the matching row with the largest `milliamps`.
- `[[distance]]`: selectors `a` and `b`, and either any of `clearance_nm`, `creepage_nm` and `embedded_nm`, or `millivolts`. A row matches a pair of different nets when `a` matches one and `b` the other, in either order. When several rows match a pair, the largest value of each quantity governs.
- `[[step]]`: `up_to_mv` and any of `clearance_nm`, `creepage_nm` and `embedded_nm`: the user's own table from voltage to distance. A distance row with `millivolts` takes its values from the step with the smallest `up_to_mv` that is at least its `millivolts`. Fenolite MUST NOT interpolate between steps. A voltage above every step gives no requirement and one `analysis.requirement-unmatched` warning naming the row.
- A row whose selectors match no net of the design MUST give one `analysis.requirement-unmatched` warning.
- `embedded_nm` MUST be judged against the gaps on inner layers, `clearance_nm` against `clearance` and `creepage_nm` against `creepage`.

#### Scenario: Step lookup without interpolation
- **GIVEN** steps `up_to_mv = 50_000` with `creepage_nm = 1_000_000` and `up_to_mv = 300_000` with `creepage_nm = 3_000_000`, and a distance row with `millivolts = 230_000`
- **WHEN** `uv run pytest tests/unit/analysis/test_requirements.py -k step` resolves the row
- **THEN** the creepage requirement is 3 mm, and with `millivolts = 400_000` there is none and one `analysis.requirement-unmatched` warning

#### Scenario: Floats refused
- **GIVEN** a document with `milliamps = 2.5`
- **WHEN** `load_requirements` parses it
- **THEN** a `FormatError` names `current[0].milliamps`

#### Scenario: Largest row governs
- **GIVEN** two distance rows that match the pair `L`, `N` with `creepage_nm` 2 mm and 4 mm
- **WHEN** the pair is resolved
- **THEN** the creepage requirement is 4 mm

### Requirement: No shipped requirement values
Fenolite SHALL ship no requirement value: no table from voltage to distance, no pollution degree, material group or altitude factor, no default temperature rise, copper thickness, plating thickness or board thickness, and no default current. `src/fenolite/analysis/` MUST hold no data file, and the only numeric constants of the capacity fit MUST be those of the table "Capacity fit". Example requirement files in tests and docs MUST be authored for Fenolite with round illustrative numbers, and MUST say so in a comment.

#### Scenario: No data files
- **WHEN** `uv run pytest tests/unit/analysis/test_facts_page.py -k no_data` lists `src/fenolite/analysis/`
- **THEN** it holds only `.py` files, and `load_requirements` has no default document

#### Scenario: Example is marked as authored
- **WHEN** the same test reads `tests/data/analysis/requirements_example.toml`
- **THEN** its first comment line holds the words `authored for Fenolite; illustrative values, not requirements`

### Requirement: Findings and issue codes
`fenolite.analysis.codes.ISSUE_CODES` SHALL be the closed table of the codes this capability emits, and `issue(code, message, …)` MUST refuse a code or a severity outside it:

| code | severity | meaning |
|---|---|---|
| `analysis.current-exceeded` | error | the capacity of an item is below the current its net requires |
| `analysis.clearance-below` | error | `clearance.high` is below the requirement |
| `analysis.clearance-undecided` | warning | the requirement lies inside the clearance interval, or `embedded_nm` lies inside the interval of a gap on an inner layer |
| `analysis.creepage-below` | error | `creepage.high` is below the requirement |
| `analysis.creepage-undecided` | warning | the requirement lies inside the creepage interval, or the search was bounded |
| `analysis.embedded-below` | error | a gap on an inner layer is below `embedded_nm` |
| `analysis.fit-out-of-range` | warning | rows computed outside the stated range of the fit |
| `analysis.input-missing` | warning | an input that Fenolite does not assume is absent; the items left out are counted |
| `analysis.item-unsupported` | warning | copper that could not be shaped, per kind; conductors outside the board, left out of the surface search |
| `analysis.requirement-unmatched` | warning | a requirement row that matches no net, or a voltage above every step |

- Each finding MUST be an `Issue` whose `where` names the item or the two items, and whose message gives the measured value, the requirement, the layer and the point in exact millimetres or milliamperes.
- Findings exist only against a requirement of the user. Without `requirements`, a report holds measured rows and no `-below`, `-undecided` or `-exceeded` issue.
- `AnalysisReport.findings() -> Findings` MUST return `model.findings.Findings(issues=…)` of the report, so a caller can attach the result to `Design.findings`. The analyses MUST NOT change the design.

#### Scenario: Current exceeded
- **GIVEN** the board of "Quarter-millimetre track" and a current row `select = {net = "VBUS"}`, `milliamps = 2000`, `temp_rise_mk = 20000`
- **WHEN** `uv run pytest tests/unit/analysis/test_findings.py -k current` runs `analyze_current(design, copper_thickness={"*": 35_000}, requirements=…)`
- **THEN** the issues hold one `analysis.current-exceeded` error whose message names 1187 mA, 2000 mA and `F.Cu`

#### Scenario: Creepage below, clearance met
- **GIVEN** the board of "Around a slot" and a distance row on `A`, `B` with `clearance_nm = 8_000_000` and `creepage_nm = 12_000_000`
- **WHEN** `analyze_distances` runs with the requirements
- **THEN** the issues hold one `analysis.creepage-below` error naming 11 mm and 12 mm, and no clearance issue

#### Scenario: Measured only
- **WHEN** the same analysis runs with `pairs=(("A", "B"),)` and no requirements
- **THEN** the row holds both measures and `issues` is empty

#### Scenario: Unknown code refused
- **WHEN** `issue("analysis.unknown", "x")` is called
- **THEN** a `ValueError` is raised

### Requirement: Analyze command
`fenolite analyze PATH` SHALL be a read-only command (`mutates` false, schema `fenolite.analyze.v0`) in `src/fenolite/cli/cmd_analyze.py`. `PATH` is a board file that a registered backend reads (`backends.registry.for_path`); an Altium board needs no option of its own once a backend reads it.
- Options: `--kinds current,clearance,creepage` (default: all three); `--requirements FILE`; `--temp-rise KELVIN` (a decimal number of at most three decimals); `--copper-thickness LENGTH` and `--copper-thickness LAYER=LENGTH` (repeatable); `--via-plating LENGTH`; `--board-thickness LENGTH`; `--pair NET_A NET_B` (repeatable); `--within LENGTH`; `--arc-tol LENGTH`. Lengths are parsed by `core.units.parse_length` and need a unit.
- Pads MUST come from the backend that read the file when it satisfies c0028's `BoardFrame`; otherwise `pads` is `None`.
- `result` MUST hold `current` and `distances` (the rows of the selected kinds, as JSON objects with the field names of the records), `summary`, and `inputs` (the option values in force and `boundary.source`). The rows of `clearance` and `creepage` come from one `analyze_distances` call; an unselected kind is left out of each row.
- The issues of the reports MUST be the envelope's `issues`. An issue of severity `error` gives exit code 5, as "Exit-code vocabulary" says of findings. An unknown kind, a malformed option or `--pair` with one name MUST be a usage error (`FEN-2001`, exit 2). An unreadable requirements file MUST be `FEN-3004`, exit 3.
- The command MUST run no external tool and write no file. `docs/cli-contract.md` MUST document it under the heading `analyze`, with the ten codes.

#### Scenario: Capacity of the example board
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_cmd.py -k example` runs `fenolite analyze tests/data/kicad/board/two_layer.kicad_pcb --kinds current --temp-rise 10 --copper-thickness 35um --json`
- **THEN** the exit code is 0, `result.current` holds one row per track and arc of the board, each `capacity_ma` an integer, and `evidence.level` is `INFERRED` or `UNVERIFIED`

#### Scenario: Requirement not met exits 5
- **GIVEN** an authored board in `tmp_path` with the slot of "Around a slot" and a requirements file asking 12 mm of creepage
- **WHEN** `fenolite analyze <board> --kinds creepage --requirements <file> --json` runs
- **THEN** the exit code is 5 and `issues` holds one `analysis.creepage-below` error

#### Scenario: Read-only and hermetic
- **GIVEN** `subprocess.run` patched to raise and a snapshot of the folder of the board
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_cmd.py -k readonly` runs the command
- **THEN** it succeeds and the folder is unchanged

#### Scenario: Usage error
- **WHEN** `fenolite analyze <board> --kinds thermal` runs
- **THEN** the exit code is 2 and stderr holds `FEN-2001`

### Requirement: Analysis evidence
`fenolite.analysis.EVIDENCE` SHALL be `Evidence(Level.INFERRED, hypotheses=("H-G-AN-EDGE", "H-G-AN-FIT", "H-G-AN-GAP", "H-G-AN-PATH", "H-G-AN-VIA"))`. The evidence of a report MUST be `Evidence.combine` of `EVIDENCE` and the evidence of the inputs that the caller passes, and MUST be `UNVERIFIED` when the report holds an `analysis.item-unsupported` or an `analysis.input-missing` issue. The level of `EVIDENCE` MUST stay `INFERRED` until an independent tool computes the same quantity; hand-computed cases and KiCad brackets MUST NOT raise it. `docs/analyses.md` MUST state which oracle could exist for each analysis.

#### Scenario: Evidence constant
- **WHEN** `uv run pytest tests/unit/analysis/test_report.py -k evidence_constant` reads `fenolite.analysis.EVIDENCE`
- **THEN** its level is `INFERRED` and its hypotheses are the five ids, each registered in `docs/hypotheses.md`

#### Scenario: Missing pads lower the level
- **GIVEN** a board with footprints
- **WHEN** `analyze_distances(design, pads=None, boundary=None, within=1_000_000)` runs
- **THEN** the issues hold one `analysis.item-unsupported` warning naming pads, and `evidence.level` is `UNVERIFIED`

### Requirement: KiCad creepage bracket is recorded
The KiCad test suite SHALL record, on `kicad-cli` 10.0.6, whether KiCad's `creepage` rule constraint (S-0272) agrees with Fenolite's creepage on authored benches: the bench of "Around a slot" and the bench of "Track above track", each written as a KiCad board with its slot on the edge layer and a custom rule `creepage` with `min` set 50 µm below and 50 µm above Fenolite's value. The probes `analysis-creepage-slot` and `analysis-creepage-edge` MUST record `equal` when `pcb drc` reports no creepage violation below and one above, `different` otherwise, and `absent` when the rules file was not loaded. The outcome MUST be written to `docs/evidence/board-analyses.md` and to the row `H-K-AN-CREEP`, or to its successor when the row is refuted. Because a through via lies on both faces, the slot bench uses two tracks on the top face whose round ends lie where the discs of "Around a slot" do. It is supporting data: it MUST NOT gate this change and MUST NOT raise `fenolite.analysis.EVIDENCE`.

#### Scenario: Bracket recorded
- **WHEN** `uv run pytest tests/kicad/analysis/test_creepage_bracket.py` runs on the local KiCad 10.0.6
- **THEN** both probes hold one of `equal`, `different` and `absent`, and the test fails only when a probe is missing

#### Scenario: Bench is hermetic to build
- **WHEN** `uv run pytest tests/unit/analysis/test_bracket_bench.py` builds the two benches in `tmp_path` without KiCad
- **THEN** each board reads back with `read_board`, and `analyze_distances` gives 11 mm and 5.1 mm on them (the edge bench with its thickness of 1.6 mm)

