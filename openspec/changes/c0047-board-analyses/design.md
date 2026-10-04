## Context

- **The roadmap line.** `docs/roadmap.md`, Phase 4, v0.3: "In parallel, an analyses track: current capacity, clearance and creepage distances." This change is that track. It works on the neutral model and names no backend.
- **The package exists in the layering table.** `package-layering`, "Allowed import edges": `checks`, `analysis`, `placement` → `model`, `geometry`, `backends.base`. `tests/unit/test_import_graph.py` already holds the row `analysis`. No layering change is needed.
- **What the model gives.** `Board.tracks`, `arcs`, `vias` (`drill`, `diameter`, `layers`), `zones` with `fills`, `footprints` with pads in the footprint frame, `outline` (`points`, `cutouts`), `graphics` on a layer of kind `edge`, `stackup` (`StackLayer.thickness`), `layers` (table order). `Circuit.nets` and `netclasses`. `Design.findings` (`Findings(issues)`).
- **What the model does not give.** No net voltage, no net current, no plating thickness. The KiCad reader fills neither `Board.outline` nor `Board.stackup` for a native board today: the outline is `Edge.Cuts` graphics, and the stack-up stays opaque. So thicknesses come from options, and the boundary from edge graphics.
- **c0029 (proposed, not yet implemented).** It adds `geometry/thick.py` to the kernel: `Thick(core, width, filled)`, `thick_bbox`, `thick_touch`, `thick_closer_than`, `thick_gap_floor`, `thick_witness`, exact with integers and `Fraction`. Its capability `copper-check` defines how each copper item becomes thick shapes ("Copper items and their shapes"), with `ARC_TOL_NM = 1_000`. That code lives in `checks/copper.py`, which `analysis` cannot import.
- **c0028 (proposed, not yet implemented).** It adds to `backends.base` the records `PadCopper(layer, core, width, filled, exact)` and `BoardPad(…, ref, number, kind, net_id, net, copper, hole, drill)` and the protocol `BoardFrame.board_pads(design, *, issues=None)`, which `KicadBackend` satisfies.
- **The kernel today.** `orient2d`, `classify_segments`, `intersection_point`, `point_in_ring`, `dist2_point_segment`, `dist2_segment_segment`, `segments_closer_than`, `floor_sqrt`, `ceil_sqrt`, `Polygon`, `assemble_rings`, `Arc.polygonize`, `DEFAULT_TOL = 5000`, `BBox`, `SpatialIndex`. The kernel returns no float.
- **The CLI.** Commands are discovered as `cli/cmd_*.py` modules with a `COMMAND`. `tests/consistency/test_cli_consistency.py` runs every command with its `example_args`. Error issues give exit 5. `core.units.parse_length` parses lengths with a unit.
- **A correction to the brief.** The brief says KiCad has no creepage command. No command prints a creepage distance, but KiCad 9 and 10 have a `creepage` constraint in custom rules (S-0272), which `kicad-cli pcb drc` evaluates. A rule can therefore bracket a value. This change records such a bracket and claims nothing from it (Decision 12).
- **Order.** c0028 → c0029 → c0047. No dependency on c0039–c0046. The batch table says this change depends only on the model and the geometry kernel; that holds with the kernel as c0029 extends it, plus c0028's plain records in `backends.base`.

## Goals / Non-Goals

**Goals:**
- Measured values with locations: capacity per track, arc and via; clearance and creepage per pair of nets.
- One published fit, each constant with its public source.
- Geometry decided with the kernel's exact predicates; every length an integer with a stated band.
- Requirements only from the user; findings only against them.
- One read-only command; results in the envelope's `issues`.
- Honest labels: `INFERRED` everywhere, with the possible oracles named.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A `check` stage or a change of `STAGE_ORDER`.
- A model field for voltage, current or plating.
- Exact algebraic lengths (sums of square roots compared exactly).
- Holes as creepage obstacles; grooves that a standard would bridge.

## Decisions

1. **Package `fenolite.analysis`, seven modules, plain functions.** `current`, `boundary`, `copper`, `surface`, `distance`, `requirements`, `codes`, plus `report`. Each analysis is a pure function from a `Design` and plain inputs to an `AnalysisReport`.
   - Rejected: `checks`. A check judges against the project's rules; an analysis measures and needs inputs the project does not hold.
   - Rejected: `geometry` for the surface search. It has one consumer and takes a board thickness and faces, which are not kernel notions. It can move to the kernel when `placement` or a rule needs it (Open Questions).

2. **One fit, stated as its public source states it.** `I = K · ΔT^0.44 · A^0.725`, `K` 0.048 on outer layers and 0.024 on inner layers, `A` in square mils, valid to 35 A (outer) or 17.5 A (inner), 100 K and 400 mils (S-0269, a help file of KiCad's calculator, read for facts). The same source attributes the fit to a standard. Fenolite did not read that standard, reproduces none of its charts and claims no conformance. `docs/analyses.md` says so.
   - The constants are `Decimal`s in `analysis/current.py`, one row each in `docs/analyses.md`, and `tests/unit/analysis/test_facts_page.py` keeps the page and the code equal.
   - Rejected: a newer chart-based method. Its data are charts and tables of a copyrighted standard.
   - Rejected: a physical model (resistive heating against convection). It needs heat-transfer coefficients that no public source fixes for a board, so it would be Fenolite's own unverified physics.
   - Rejected: offering several fits. One sourced fit is auditable; the result names it (`summary.fit == "S-0269"`).

3. **`decimal`, not `float`.** The fit has fractional exponents. `math.pow` goes through the platform C library (S-0011), so its last digits may differ between machines. `decimal` is the same software on every platform (S-0012). The value is computed at 40 digits and rounded down to an integer of milliamperes. Rounding down never overstates a capacity.
   - `decimal`'s power for a fractional exponent is well defined but not always correctly rounded in the last digit of the context. At 40 digits against a result in whole milliamperes, this cannot change the integer except on an exact boundary; the independent test bounds the difference at 1 mA.
   - `π` for the via barrel comes from the `decimal` recipe of S-0012, at the same precision.
   - Rejected: floats with a rounding rule. The repository's rule is that outputs are byte-identical across platforms.

4. **Nothing is assumed.** Temperature rise, copper thickness, plating thickness and board thickness have no default. A missing input leaves the items out, counts them and lowers the evidence to `UNVERIFIED` (`analysis.input-missing`). The model's `Board.stackup` is used when a reader fills it.
   - Rejected: 35 µm copper, 10 K rise or a usual plating as defaults. Each is a convention of some organisation, and a silent default makes a wrong board look analysed.

5. **Per item, not per net.** A row is one track, arc or via. `summary.nets` names the weakest item of each net. Parallel tracks, pours and planes are not combined: that is current-flow analysis, a non-goal.

6. **Via barrel as S-0270 does.** Cross-section `π · (drill + t) · t`, the outer constant, `Via.drill` as the finished hole (`H-G-AN-VIA`). The pad-to-barrel junction and the via length do not enter.
   - Rejected: pad holes. A through-hole pad carries a lead; its capacity is not a barrel question.

7. **Copper shapes follow c0029's rule, built here.** `analysis/copper.py::net_copper` builds `Thick` shapes exactly as `copper-check` "Copper items and their shapes" says, because `analysis` cannot import `checks`. A unit test compares the two builders on generated boards, as c0029 does for `rule_precedence` against `rule_order`. `Thick` and the gap functions are c0029's and are not duplicated.
   - Rejected: a `package-layering` change (`analysis → checks`). It would let an analysis depend on the check pipeline for 60 lines of item mapping.
   - Rejected: changing c0029 to hoist its builder into `geometry`. This change must not edit another change. It is an open question for c0029's review.

8. **Clearance on a layer is the thick gap.** Per layer, the smallest `thick_gap_floor` over the shapes of the two nets, found with one `SpatialIndex` per layer. On outer layers it is the distance through air; a cut-out between two conductors does not lengthen it. On inner layers it is a distance inside the laminate, reported apart (`gaps`) and judged only against `embedded_nm`.
   - Rejected: one number for all layers. Air and laminate are different insulations, and the user's tables differ for them.

9. **Creepage is a shortest path on a surface with holes, searched over boundary vertices.** The surface is the two outer faces, less the cut-outs, joined by walls of the board thickness along every boundary edge. A shortest path among polygonal obstacles bends only at obstacle vertices, so the graph has the boundary vertices of each face as nodes and three kinds of edges: straight legs on a face, wall drops at vertices, and wall crossings through an edge's interior, straight in the unfolded plane. Terminals attach through the nearest point of each core piece. Dijkstra runs on integer weights.
   - **What is exact.** Whether a leg is allowed (it does not cross a boundary edge properly, and its midpoint is inside the board) is decided with `orient2d`, `classify_segments` and `point_in_ring` on integer or `Fraction` points; nearest points on core pieces are `Fraction`s, scaled to integers for the predicates.
   - **What is bounded.** A path length is a sum of square roots. Each is a rounded-down integer square root scaled by 2²⁰ per nanometre, so with fewer than 2²⁰ legs the sum is below the true length by less than 1 nm: `length ≤ d < length + 2`. A wall crossing of a slanted edge uses a unit normal rounded at 2⁻⁶⁴, far inside that bound. Curved boundary edges add `boundary.band` per bend.
   - Rejected: exact comparison of sums of square roots. It is possible (repeated squaring) but slow and adds nothing a 2 nm band does not give.
   - Rejected: a grid or raster search. It is not exact in any sense and its error depends on the grid. It serves as the brute-force check in tests only.
   - Rejected: polygon offsetting of copper and a boolean backend. The boolean backends are extras; the core stays stdlib-only.
   - Rejected: holes as obstacles now. Ignoring a hole can only shorten the reported path. Plated holes are copper of their pad already.
   - Limit, documented: copper of a third net between two conductors is ignored. A floating conductor can shorten the real leakage path. `docs/analyses.md` lists it.

10. **Clearance across the edge is an interval.** For copper on opposite faces, a path through air leaves a face at the boundary, descends at least the thickness and reaches the other face. So `dA + dB + thickness` is a lower bound, and the surface path is an upper bound. The exact air path around a concave boundary can cut across a slot diagonally and is a three-dimensional problem; this change does not solve it and reports the interval (`H-G-AN-EDGE`).
    - When the nearest boundary points of the two conductors coincide, the interval is 2 nm wide, as in the scenario "Track above track".
    - Rejected: reporting the surface path as the clearance. It can overstate it (a slot of width `w`: `sqrt(w² + t²)` through air against `w + t` on the surface).
    - Rejected: a 3-D shortest path. Out of proportion for the track; an open question.

11. **One rule for judging intervals.** `high < r` is an error; `low < r ≤ high` is a warning (`-undecided`); `low ≥ r` passes. It holds for the 1 nm interval of a gap, the 2 nm interval of a path and the wide interval of Decision 10.
    - Rejected: an error whenever `low < r`. A wide interval would then fail boards that may be fine, with no way to tell.
    - Rejected: silence on undecided pairs. The user must know the measure did not decide.

12. **Oracles, said plainly.**
    - *Capacity.* KiCad's calculator computes the same fit, but only in its GUI; `kicad-cli` has no command for it. No independent command-line tool was found. The arithmetic is checked against a second computation in the test; the fit stays `INFERRED`.
    - *Clearance on a layer.* c0029's parity canaries bracket thick gaps with KiCad's `clearance` rule on 9.0.9 and 10.0.6. This change inherits that primitive and adds nothing to it; the measure stays `INFERRED` here.
    - *Creepage.* Hand-computed authored cases and a grid search are the check. KiCad's `creepage` constraint (S-0272) can bracket a value: a rule 50 µm below Fenolite's value must pass and one 50 µm above must fail. Task group 8 records this on 10.0.6 for two benches (`H-K-AN-CREEP`). KiCad's definition of the path is its own and is not documented beyond one sentence, so agreement or disagreement is recorded, not required, and it raises no label.
    - *Edge clearance.* None.
    - Rejected: gating on the KiCad bracket. Two tools with two undocumented path definitions agreeing on two benches is not verification of a board.

13. **Requirements are a user file, integers only.** TOML (`tomllib`, S-0273), schema `fenolite.requirements.v0`, arrays `current`, `distance` and `step`. Units are in the key names (`milliamps`, `temp_rise_mk`, `clearance_nm`, `millivolts`), so no number needs a parser and no float enters. Selectors are `net` or `netclass` globs, matched as `model.rules.Selector` matches them.
    - The `step` table is the user's own voltage-to-distance table. Lookup is the first step at or above the voltage. No interpolation: whether and how to interpolate is a rule of the standard the user follows.
    - The voltage of a pair is given on the distance row. Fenolite does not derive it from net names, and does not decide between peak, RMS or working voltage.
    - Rejected: voltages on nets in the model. A model delta for one analysis; and the pair voltage is not always a difference of two net voltages.
    - Rejected: reusing `RuleSet` with a new rule kind `creepage`. It changes the closed `RuleKind`, the schema and c0018's lowering. A later change can lower the user's requirements to backend rules.
    - Rejected: JSON. TOML allows comments, and a requirements file needs them.

14. **Command `fenolite analyze PATH`, read-only.** One command with `--kinds`. Results go to `result.current` and `result.distances`; findings go to the envelope's `issues`; an error finding exits 5 through the dispatcher, as for `check`. The board is read by `registry.for_path`, and pads come from the backend when it is a `BoardFrame`.
    - Rejected: three commands. One read of the board, one envelope, one schema.
    - Rejected: a `check` stage. `STAGE_ORDER` is pinned by c0020 and modified by c0029; a stage would need a second MODIFIED delta in that chain and inputs (`--requirements`, thicknesses) that `check` does not take.
    - Rejected: writing `findings.json`. The command is read-only; `AnalysisReport.findings()` gives a caller the `Findings` layer to attach.

15. **Pair selection is explicit.** Distances are computed for pairs named by `--pair`, matched by a distance row, or closer than `--within`. A whole board has too many pairs to search creepage for all of them, and most are irrelevant.
    - Each search has a limit: the largest requirement of the pair, or `--within`. A pair named by `--pair` alone is searched without a limit.

16. **Codes in their own table.** `analysis/codes.py::ISSUE_CODES`, ten codes, with `issue()` refusing others, as `checks/codes.py` does. `checks.codes` is not extended: its table is the closed list of `check`'s codes.

17. **No model, schema, FEN-code or layering change.** One new capability; every requirement is ADDED. Nothing is MODIFIED, so no archive-order constraint exists beyond c0028 and c0029 being archived first, because their names are used.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/analysis/__init__.py` (new) | `EVIDENCE: Evidence`; re-exports `analyze_current`, `analyze_distances`, `board_boundary`, `load_requirements`, `AnalysisReport` |
| `src/fenolite/analysis/report.py` (new) | `@dataclass(frozen=True, slots=True) class AnalysisReport(rows: tuple[CurrentRow \| DistanceRow, ...], issues: tuple[Issue, ...], summary: Mapping[str, object], evidence: Evidence)` with `findings() -> Findings`; `Measure(low: Nm, high: Nm \| None, layer: str, points: tuple[Point, ...], items: tuple[str, str], bounded: bool = False)`; `CurrentRow(kind: Literal["track", "arc", "via"], where: str, entity_id: str, net: str, layer: str, at: Point, width: Nm \| None, thickness: Nm, area_nm2: int, external: bool, temp_rise_mk: int, capacity_ma: int, in_range: bool)`; `DistanceRow(net_a: str, net_b: str, gaps: tuple[Measure, ...], clearance: Measure \| None, creepage: Measure \| None)`; `judge(measure: Measure, required: Nm) -> Literal["error", "warning"] \| None` |
| `src/fenolite/analysis/codes.py` (new) | `ISSUE_CODES: Mapping[str, tuple[Severity, ...]]`; `issue(code: str, message: str, *, severity: Severity \| None = None, where: str = "", hint: str = "") -> Issue` |
| `src/fenolite/analysis/current.py` (new) | `FIT_K_EXTERNAL`, `FIT_K_INTERNAL`, `FIT_EXP_RISE`, `FIT_EXP_AREA`, `MIL_NM`, `FIT_MAX_EXTERNAL_MA`, `FIT_MAX_INTERNAL_MA`, `FIT_MAX_RISE_MK`, `FIT_MAX_WIDTH_NM`; `capacity_ma(area_nm2: int, temp_rise_mk: int, *, external: bool) -> int`; `barrel_area_nm2(drill: Nm, plating: Nm) -> int`; `in_range(width: Nm \| None, temp_rise_mk: int, capacity_ma: int, *, external: bool) -> bool`; `analyze_current(design: Design, *, temp_rise_mk: int \| None = None, copper_thickness: Mapping[str, Nm] \| None = None, via_plating: Nm \| None = None, requirements: Requirements \| None = None) -> AnalysisReport` |
| `src/fenolite/analysis/boundary.py` (new) | `BoardBoundary(outer: tuple[Point, ...], cutouts: tuple[tuple[Point, ...], ...], thickness: Nm \| None, band: int, source: Literal["model", "edge", "none"])`; `board_boundary(board: Board, *, arc_tol: int = DEFAULT_TOL, thickness: Nm \| None = None) -> BoardBoundary` |
| `src/fenolite/analysis/copper.py` (new) | `ARC_TOL_NM = 1_000`; `CopperShape(shape: Thick, layer: str, kind: str, where: str, entity_id: str, band: int)`; `NetCopper(by_net: Mapping[str, tuple[CopperShape, ...]], unsupported: Mapping[str, int], outer: tuple[str, str] \| None)`; `net_copper(design: Design, *, pads: Sequence[BoardPad] \| None, arc_tol: int = ARC_TOL_NM) -> NetCopper` |
| `src/fenolite/analysis/surface.py` (new) | `Face = Literal["top", "bottom"]`; `SCALE_BITS = 20`; `Terminal(shape: Thick, face: Face)`; `SurfacePath(length: int, band: int, points: tuple[tuple[Point, Face], ...])`; `surface_distance(a: Sequence[Terminal], b: Sequence[Terminal], boundary: BoardBoundary \| None, *, limit: int \| None = None) -> SurfacePath \| None`; `boundary_distance(shape: Thick, boundary: BoardBoundary) -> int` |
| `src/fenolite/analysis/distance.py` (new) | `analyze_distances(design: Design, *, pads: Sequence[BoardPad] \| None, boundary: BoardBoundary \| None, pairs: Sequence[tuple[str, str]] = (), within: Nm \| None = None, requirements: Requirements \| None = None, arc_tol: int = ARC_TOL_NM) -> AnalysisReport` |
| `src/fenolite/analysis/requirements.py` (new) | `SCHEMA = "fenolite.requirements.v0"`; `NetSelector(net: str \| None, netclass: str \| None)`; `CurrentReq(select, milliamps, temp_rise_mk)`; `DistanceReq(a, b, clearance_nm, creepage_nm, embedded_nm, millivolts)`; `Step(up_to_mv, clearance_nm, creepage_nm, embedded_nm)`; `Requirements(currents, distances, steps)` with `current_for(net: Net, circuit: Circuit) -> CurrentReq \| None` and `distance_for(a: Net, b: Net, circuit: Circuit) -> tuple[Nm \| None, Nm \| None, Nm \| None]`; `load_requirements(text: str, *, file: str = "") -> Requirements` |
| `src/fenolite/analysis/PROVENANCE.md` (new) | rows for the fit, the barrel and the range (S-0269, S-0270), facts only |
| `src/fenolite/cli/cmd_analyze.py` (new) | `COMMAND` (`analyze`, `mutates=False`, `example_args=(EXAMPLE_BOARD, "--kinds", "current", "--temp-rise", "10", "--copper-thickness", "35um")`); `KINDS = ("current", "clearance", "creepage")` |
| `docs/analyses.md` (new) | the table "Capacity fit"; definitions of clearance and creepage as Fenolite measures them; the limits; the oracle table; the requirements file |
| `docs/evidence/board-analyses.md` (new) | the KiCad bracket outcomes and timings; counts only |
| `docs/cli-contract.md` (extended) | section `analyze`, the options and the ten codes |
| `tests/unit/test_provenance.py` (extended) | `PROVENANCE_PACKAGES` gains `analysis` |
| `tests/_analysis.py` (new) | `slot_board()`, `edge_board()`, `grid_shortest(…)`: authored boards and the grid search |
| `tests/data/analysis/requirements_example.toml` (new, authored) | illustrative values, marked as such |
| `tests/unit/analysis/test_report.py`, `test_current.py`, `test_facts_page.py`, `test_boundary.py`, `test_copper.py`, `test_surface.py`, `test_distance.py`, `test_requirements.py`, `test_findings.py`, `test_bracket_bench.py`; `tests/unit/cli/test_analyze_cmd.py` (new) | hermetic tests |
| `tests/kicad/analysis/_creepbench.py`, `test_creepage_bracket.py` (new); `tests/kicad/_probes.py` (rows added) | `needs_kicad`; recorded probes (see "Implementation notes" for the file name) |

Layering: every module of `analysis` imports `core`, `model`, `geometry` and `backends.base` only; `cmd_analyze` imports `analysis` and `backends`. Every edge is in "Allowed import edges", unchanged.

## Sources registered by this change

| id | URL | licence of the source | used for |
|---|---|---|---|
| S-0269 | https://gitlab.com/kicad/code/kicad/-/blob/10.0.6/pcb_calculator/tracks_width_versus_current_formula.md | GPL-3.0-or-later (a help text in the source tree; read for facts, nothing copied) | the fit `I = K · ΔT^0.44 · (W · H)^0.725`; `K` 0.024 inner and 0.048 outer; amperes, kelvin of rise, mils; valid to 35 A outer or 17.5 A inner, 100 K, 400 mils; the standard the text attributes it to |
| S-0270 | https://gitlab.com/kicad/code/kicad/-/blob/10.0.6/pcb_calculator/calculator_panels/panel_via_size.cpp | GPL-3.0-or-later (facts only; nothing transcribed or followed) | a via's capacity uses the barrel cross-section `π · (finished hole + plating) · plating` with the outer constant and the same exponents |
| S-0271 | https://docs.kicad.org/10.0/en/pcb_calculator/pcb_calculator.html | GPL-3.0-or-later or CC-BY-3.0-or-later (stated on the page) | the calculator is a GUI tool; it names the origin of its track-width formulas; it shows a spacing table from a standard, which Fenolite does not use |
| S-0272 | https://gitlab.com/kicad/code/kicad/-/blob/10.0.6/pcbnew/dialogs/panel_setup_rules_help_2constraints.md | GPL-3.0-or-later (a help text in the source tree; facts only) | custom rules have the constraints `clearance` ("electrical clearance between copper objects of different nets") and `creepage` ("creepage distance between copper objects of different nets"); basis of the bracket probe |
| S-0273 | https://docs.python.org/3/library/tomllib.html | PSF License Version 2 (stated on the page) | `tomllib` parses TOML 1.0 into `int`, `float`, `str` and tables; `TOMLDecodeError` |

S-0274 to S-0276 stay unused. Cited without change of level: S-0011 (`math` wraps the platform C library), S-0012 (`decimal` is identical on every platform; the `pi` recipe), S-0020 and S-0022 (`kicad-cli` 10.0.6 and `pcb drc` as the oracle of the bracket). Task 1.1 widens the "used for" cells of S-0012 and S-0022. All five pages were read on 2026-10-03. No standard was read.

## Hypotheses registered by this change

| id | backend | statement | settling test | criterion |
|---|---|---|---|---|
| H-G-AN-FIT | general | The fit of S-0269, with its constants and units as Fenolite records them, gives the capacity of an isolated conductor of rectangular section on a board, inside the range S-0269 states | `tests/unit/analysis/test_current.py`, `test_facts_page.py` | arithmetic equal to an independent computation within 1 mA; the fit itself has no oracle and stays `INFERRED` |
| H-G-AN-VIA | general | A via carries the fit's current for its barrel section `π · (drill + plating) · plating` with the outer constant, `Via.drill` being the finished hole (S-0270) | `tests/unit/analysis/test_current.py -k via` | as above; stays `INFERRED` |
| H-G-AN-GAP | general | The smallest `thick_gap_floor` over the shapes of two nets on an outer layer is their distance through air on that face, within the bands of arcs and approximated pads | `tests/unit/analysis/test_distance.py`; c0029's `H-K-COPPER-SHAPES` for the shapes | authored cases equal by hand; stays `INFERRED` here |
| H-G-AN-PATH | general | A shortest path on the board surface from one conductor to another bends only at boundary vertices and meets each conductor at the nearest point of a core piece, so the search of "Creepage on the board surface" finds it within its band | `tests/unit/analysis/test_surface.py` | every hand-computed case equal; the grid comparison within its bounds on every generated case |
| H-G-AN-EDGE | general | For copper on opposite faces, the distance through air is at least `dA + dB + thickness` and at most the surface path | `tests/unit/analysis/test_surface.py -k edge` | hand-computed cases inside the interval; no oracle; stays `INFERRED` |
| H-K-AN-CREEP | kicad | On `kicad-cli` 10.0.6, a custom rule `creepage` with `min` 50 µm below Fenolite's creepage reports no violation and one 50 µm above reports one, for a pair around a slot on one face and for a pair across the board edge (S-0272, S-0022) | `tests/kicad/analysis/test_creepage_bracket.py` | probes `analysis-creepage-slot` and `analysis-creepage-edge` = `equal`; `different` is recorded with a `-2` successor stating what KiCad reported |

- The stem of this change is `H-G-AN-`. The sixth row is about a tool acting on KiCad files, which the register writes `H-K-`; it keeps the family as `H-K-AN-`. No row `H-G-AN-*` or `H-K-AN-*` exists in `docs/hypotheses.md` or in an active change (`H-G-ANGLE` is another id).
- All rows get result `pending`; the five `H-G-AN-*` rows get level `INFERRED`, and `H-K-AN-CREEP` gets `UNVERIFIED` until it is run.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof | oracle that could exist |
|---|---|---|---|
| Arithmetic of the fit | mechanical | `test_current.py -k "fit or independent"` | none needed |
| Capacity of tracks, arcs and vias | `INFERRED` (`H-G-AN-FIT`, `H-G-AN-VIA`) | `test_current.py` | KiCad's calculator, GUI only; no command |
| Constants equal their recorded sources | mechanical | `test_facts_page.py` | — |
| Board boundary | mechanical (authored cases) | `test_boundary.py` | — |
| Copper shapes equal c0029's | mechanical | `test_copper.py -k same_shapes` | — |
| Clearance on a layer | `INFERRED` (`H-G-AN-GAP`) | `test_distance.py` | c0029's `clearance` rule canaries, for the gap primitive |
| Creepage | `INFERRED` (`H-G-AN-PATH`) | `test_surface.py` (hand-computed; grid search) | KiCad's `creepage` rule as a bracket, recorded (`H-K-AN-CREEP`) |
| Clearance across the edge | `INFERRED` (`H-G-AN-EDGE`) | `test_surface.py -k edge` | none |
| Requirements file | mechanical | `test_requirements.py` | — |
| Findings, codes, exit code | mechanical | `test_findings.py`, `test_analyze_cmd.py` | — |
| KiCad bracket | recorded on 10.0.6, never gating | `test_creepage_bracket.py` | — |

`fenolite.analysis.EVIDENCE` is `INFERRED` and stays `INFERRED` after this change. A report is `UNVERIFIED` when an item or an input was left out. The reply of `analyze` is the lowest of `EVIDENCE` and the reader's level.

## Budget (design-days; a size, not calendar time)

| work | days |
|---|---|
| registers, provenance, `docs/analyses.md` skeleton, predecessor names | 0.5 |
| report records, codes, the fit, track and via capacity | 1.25 |
| requirements file | 0.75 |
| board boundary | 0.5 |
| copper shapes and their equality test | 0.75 |
| clearance on a layer, pair selection, judging | 1.0 |
| surface search on one face | 1.5 |
| walls, edge crossing, edge clearance | 1.5 |
| grid search check and limits | 0.75 |
| `analyze` command and contract docs | 1.0 |
| KiCad bracket benches and probes | 1.0 |
| docs and closing | 1.0 |
| **total** | **11.5** |

Cut order: (1) the KiCad bracket becomes an open question (−1.0, and `H-K-AN-CREEP` is not registered); (2) wall crossings through edge interiors, keeping drops at vertices, with `H-G-AN-EDGE`'s upper bound widened (−0.75); (3) `--within` (−0.25). Not optional: the fit with its recorded sources, nothing assumed, clearance on a layer, creepage around cut-outs on one face, the requirements file, the command.

## Risks / Trade-offs

- [The fit's provenance is questioned: its public source attributes it to a copyrighted standard] → Fenolite records the public source, states the attribution, reads no standard and reproduces no chart. If the maintainer rejects it, the capacity analysis is cut and the distance analyses stand alone (Open Questions).
- [A user reads a measured value as conformance] → the proposal, `docs/analyses.md` and the command help say that Fenolite measures and the user decides; no reply says "pass" without a user requirement.
- [c0028 or c0029 renames a record] → task 1.3 re-checks the names against their archived text before code starts.
- [The search is slow on a boundary with many polygonised arc vertices] → `arc_tol` for the boundary defaults to the kernel's 5 µm; the limit prunes; timings are recorded in `docs/evidence/board-analyses.md`. If a demo board takes more than 60 s for one pair, boundary vertices on a nearly straight chain are thinned and the band grows by the thinning error.
- [Ignored features change the real path: holes, mask, third-net copper, component bodies] → listed as limits; holes only shorten the reported value; the others are named in the page and in the command help.
- [KiCad's creepage path differs] → recorded, never required.
- [Edge-graphic outlines with gaps] → `source == "none"`, `analysis.input-missing`, face-only results, `UNVERIFIED`.
- [Two copper builders drift] → the equality test of Decision 7.

## Migration Plan

- Additive: a package, a command, two doc pages, tests. No model, schema, FEN-code, stage or layering change. `fenolite capabilities` lists one more command.
- Rollback: remove `src/fenolite/analysis/`, `cmd_analyze.py`, the pages, the probe rows and the register rows.

## Implementation notes (2026-10-04)

What the implementation settled, where it differs from the tables above:

- **Predecessor names (task 1.3).** c0028 and c0029 are archived with the names this design uses: `geometry.thick` (`Thick`, `thick_bbox`, `thick_touch`, `thick_gap_floor`, `thick_witness`), `ARC_TOL_NM = 1_000`, and `BoardFrame.board_pads`, `BoardPad`, `PadCopper` in `backends.base`. Nothing was renamed. `checks.copper` keeps two shapes per arc, narrowed and widened by the band; `analysis.copper` keeps the nominal shape and the band beside it, and the equality test compares them through that band.
- **Names added.** `Terminal` gains `band`, and `SurfacePath` gains `ends` (the two terminals a path joins), so a measure can name its items and carry their bands. `surface.usable_terminals` returns the terminals that lie on the board and the count left out. `NetCopper` gains `layers`. `Requirements` gains `step_for` and `values`. The source id of the fit is `current.SOURCE_OF_FIT`, so every `FIT_*` name is a number of the table "Capacity fit". `EVIDENCE` is defined in `analysis.report` and re-exported.
- **Warning for an unknown thickness.** The scenario "Measured only" asks for no issue on the slot board, whose vias lie on both faces, while no thickness is given. So the warning is raised only for a pair that has copper only on opposite faces; a pair that shares a face is measured there and counted in `summary.faces_alone`.
- **An undecided gap inside the laminate** has no code of its own in the table of ten. It is reported as `analysis.clearance-undecided`, with a message that names the inner layer.
- **Bench files.** `tests/kicad/copper/_benches.py` already exists on the import path of the KiCad tests, so the bracket's helper is `tests/kicad/analysis/_creepbench.py`. The benches themselves are built by `tests/_analysis.creep_bench`, which the hermetic test can import. The slot bench uses two tracks on the top face instead of two through vias: a via lies on both faces, and KiCad would then see a path through the slot's wall.
- **The KiCad bracket.** `analysis-creepage-slot` is `equal`: KiCad reports an actual creepage of 11.0000 mm. `analysis-creepage-edge` is `different`: KiCad reports no creepage violation across the board edge at any `min`. `H-K-AN-CREEP` is refuted and `H-K-AN-CREEP-2` records both outcomes. Nothing gates on them.
- **Speed.** The first implementation took 129 s for one pair on a round board with 192 boundary vertices, above the 60 s of "Risks". The search now leaves out legs that cannot beat the best path known, using the distance in plan view to each conductor as a lower bound; the same case takes 4 s with the same result. No vertex is thinned.
- **A slot's wall does not bridge the slot.** A wall joins the two faces on one side of a cut-out. Copper on opposite faces on the two sides of a slot is still joined around the slot (11 mm plus one drop on the slot board), which a test pins.

## Open Questions

- **Provenance of the fit.** Default: accept S-0269 as the citable public source and state its attribution. For the maintainer to confirm.
- **A second check of the fit.** A public-domain measurement report from 1956 by a US federal laboratory is said to hold the curves such fits come from (`https://nvlpubs.nist.gov/nistpubs/Legacy/RPT/nbsreport4283.pdf`). It was not read for this change. Default: a later change may compare the fit with it and register it then.
- **KiCad bracket in this change.** Default: yes, recorded on 10.0.6 only. First cut if the size must shrink.
- **Hoisting the copper builder.** Default: two builders with an equality test. If c0029's review moves its builder into `geometry`, `analysis/copper.py` becomes a thin call and the test goes.
- **The surface search in the kernel.** Default: it stays in `analysis` until a second consumer exists.
- **Holes and narrow grooves.** Default: holes are ignored and every cut-out counts, whatever its width. A user option for a smallest counted groove width is a follow-up; Fenolite would ship no default for it.
- **Third-net copper on the path.** Default: ignored and documented. A follow-up could report the conductors a path crosses.
- **Exact air path across the edge.** Default: the interval of Decision 10.
- **Voltages in the model.** Default: none; the pair voltage lives in the user's file.
- **Lowering requirements to backend rules** (KiCad's `creepage` constraint; the roadmap's "full rules"). Default: not here.
- **Altium boards.** Default: analysable as soon as c0043's backend reads them; pads need that backend to satisfy `BoardFrame`, else they are counted as unsupported.
- **Register guard (c0014).** This design cites the six ids before task 1.1 registers them, as "Ids proposed by active changes" allows. Task 1.1 is the first implementation commit.
