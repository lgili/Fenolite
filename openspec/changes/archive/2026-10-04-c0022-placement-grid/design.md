## Context

- **Scope.** A split-off of plan item 0016 (plan D11: "placement: v0.1 `manual` + `grid`"). The roadmap row: "manual and grid placement; pre-write legality check (courtyard overlap, outside the outline, edge clearance)", with one day added for the check. The loop step is `fenolite place PROJECT --strategy grid --confirm` (plan, appendix B).
- **Staging.** c0011 stages every part without `place()` in one row that starts `STAGING_OFFSET` right of the outline, on the top side at 0°, with `layout.unplaced` (living `design-dsl`, "Placement of built parts").
- **Precedence.** c0019's `effective_placements` uses, per part: a locked `place()`, then the existing board, then `place()`, then staging (living `layout-lens`, "Placement precedence"). A footprint is "off the board" when its position lies outside the bounding box of the outline; an off-board footprint without `place()` is staged again. So a footprint that a placer moves onto the board is kept by every later build.
- **Re-placement.** c0019's `merge_layout` replaces a footprint by "c0011's placed copy at the effective placement, keyed by the component path" (`embed.place_footprint(defn, component=…, at=…, rotation=…, side=…, locked=…, key=…, copper=…)`), from the library definition. `mod.board_footprints` reads a placed footprint as a definition in the stored frame, which is the placed frame, so it cannot serve a new rotation or side.
- **Extents.** c0028's `BoardFrame.placed_extents(design) -> tuple[PlacedExtent, ...]` gives the front and back courtyard rings of each footprint in the board frame, with `source` (`courtyard`, `definition`, `pads`, `none`) and `exact`. `H-G-FRAME-CRTYD` proves them against KiCad's `courtyards_overlap` within 20 µm.
- **Outline.** A built design has `Board.outline` (points). A native board has only `Edge.Cuts` graphics; c0005's `geometry.assemble_rings` chains pieces exactly, and c0020 measures whether any corpus board needs a snapping tolerance (`H-G-EDGE-EXACT`), leaving outline assembly to this change.
- **Layering.** The `placement` row of `package-layering` exists: it may import `model`, `geometry` and `backends.base`.
- **Fields.** c0030 makes Reference, Value and other fields placed entities and keeps them on kept and re-placed footprints.
- **Constraints.** Stdlib only; integer nanometres; the roadmap gives this change 4.5 days.

## Reconciliation with the code (2026-10-04)

The proposal was written before c0028, c0029, c0030 and c0031 were implemented. Each name this change consumes was checked against the working tree at `cce425e`; the text below and the deltas were edited in place where reality differs.

| consumed | reality | edit |
|---|---|---|
| `lens.build.build_design` calls `legality.check` (old Decision 9) | `package-layering` lets `lens` import only `model` and `backends`, so `lens` cannot import `placement`. c0029 met the same limit and put its copper guard in `cmd_build` | Decision 9 and the `design-dsl` delta: the check is a step of `cmd_build` (`placement_guard`), beside `copper_guard`; `build_design` and `BUILD_ISSUE_CODES` stay unchanged; the codes join the envelope as "Build issue codes" allows |
| `BoardFrame.placed_extents(design)` | `placed_extents(design, *, issues=None)`; `PlacedExtent` holds `footprint_id`, `side`, `front`, `back`, `source`, `exact` and the property `own`; no reference | no edit: `check` takes `names` (footprint id to reference) |
| `Board.outline.points` as one ring | `Outline` also holds `cutouts` | Decision 3: the cut-outs of the model outline are the further rings |
| three outline problems | `assemble_rings` also raises `geometry.branching-contour` | Decision 3 and the delta add `branching-contour` |
| c0030 "has not archived" (risk note) | c0030 is archived: Reference, Value and the properties are `FootprintField`s, and `lens.fields.merge_fields` carries the board's field values to a re-placed footprint of the same side | Decision 4: a rotation keeps the old field values, a side change takes the definition's; the risk note is dropped |
| `embed.place_footprint(defn, component=…, at=…, rotation=…, side=…, locked=…, key=…, copper=…)` | as written; user properties are added to the definition with `embed.with_property` before placing | Decision 4 says so |
| the board-wide `edge_clearance` rule (c0026) | `model.rules.Rule` has the kind `edge_clearance`; the DSL has no call that creates one, and a board read from a file has no rules | Decision 5: the value comes from the model design's rules; `place` on a board file uses 0 |
| the frame of `place()` | `dsl.convert.BOARD_ORIGIN` puts the outline's top-left corner at (100 mm, 100 mm); a board file does not say so | Decision 8: `--move` positions are relative to the top-left corner of the bounding box of the board ring, and to the file origin without an outline |
| "the authored project" | no project of that name | the built blink (`examples/blink_2layer`) with its vendored `lib/` and `fp-lib-table` |
| `tests/unit/cli/test_build_cmd.py`, `tests/unit/lens/` (task 5.2) | the file is `test_build_command.py`; guards of `cmd_build` have their own file (`test_build_copper_guard.py`) | task 5.2 names `tests/unit/cli/test_build_placement_guard.py` |
| the copper guard of c0029 | `cmd_build.copper_guard(files, *, name, mode, target)` reads the planned board text back | `placement_guard` follows the same pattern and runs whenever the build planned files |

Every delta of this change is ADDED, so no MODIFIED base moved. No living requirement has one of the new requirement names.

## Goals / Non-Goals

**Goals:**
- `fenolite place` brings staged parts onto the board in a deterministic grid, or moves named parts, and the next `build` keeps them.
- A placement that overlaps courtyards or leaves the outline is reported before a board is written, with the references involved.
- A moved footprint is exactly the footprint KiCad would show: position, rotation, side and pad nets proved on both majors.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A placement quality score; a placer that rotates parts or uses the bottom side.

## Decisions

1. **Probe first.** Task group 2 pins two facts on 9.0.9 and 10.0.6 before the code relies on them: a moved footprint (`place-move-translate`, `place-move-rotate`, `place-move-flip`), and whether courtyards that only touch give `courtyards_overlap` (`place-touch`). Fallbacks: Decision 4 for the move, Decision 6 for touching.

2. **`placement` works on plain data.** `placement.legality` and `placement.grid` take `PlacedExtent`s, outline rings and lengths, and return issues and positions. They never see a board file. The CLI (`cmd_place`, `cmd_build`) passes the extents of `KicadBackend()`, the `BoardFrame`, as `checks` receives its oracle.
   - Rejected: placement inside `backends.kicad`. A second backend would need it again.

3. **Outline as rings.** `backends/kicad/outline.py::board_outline(design) -> BoardOutline(rings, source, problem)`:
   - `source == "model"`: `Board.outline.points` as the board ring and each of `Board.outline.cutouts` as a further ring;
   - `source == "edge"`: the root graphics on the layer of kind `edge` (lines, arcs, rectangles, polygons, circles), chained by `assemble_rings` with exact endpoints;
   - `problem` names why no ring could be closed (`open-contour`, `branching-contour`, `no-edge-content`, `footprint-edges-only`), and `rings` is then empty.
   - The largest ring by area is the board; rings inside it are cut-outs.
   - Arcs are approximated for containment only, with c0005's arc error bound stated in the result (`exact == False`).
   - Rejected: a snapping tolerance. c0020's census decides whether one is ever needed; until a board needs it, exact chaining stays (`H-G-EDGE-EXACT`).

4. **`move_footprint`.** `backends/kicad/replace.py::move_footprint(design, footprint_id, *, at=None, rotation=None, side=None, definitions=None, force=False) -> Design`:
   - **Translation** (`rotation` and `side` unchanged or `None`): only `FootprintInstance.position` changes. Pads, graphics and fields are footprint-relative, so every slot stays.
   - **Rotation or side change:** the footprint is replaced by `embed.place_footprint` of its library definition at the new placement, with its component, its lock, the board's copper layers and `key` equal to its `fenolite.path` when it has one (its reference otherwise). Each field of the old footprint that the definition lacks (`fenolite.path` and the user properties) is added to the definition with `embed.with_property` first, as the build does. Its uuid, its Reference and Value, and each pad's net by pad number are taken from the old footprint, as c0019's "Kept and re-placed footprints" does for a re-placed copy. When the side stays, every field that both footprints hold takes the old placement and appearance (the values of `lens.fields.FIELD_VALUES`), which are footprint-relative; a side change keeps the definition's fields, mirrored by `place_footprint`.
   - `definitions` maps lib ids to `FootprintDef`. The CLI resolves them from the project's `fp-lib-table` with c0008's resolver. Without a definition for the footprint's `lib_ref`, a rotation or side change raises `PlacementError` with `place.no-definition`.
   - A locked footprint is moved only when the caller says so (`--force`); otherwise `place.locked` (error).
   - Fallback if `place-move-rotate` or `place-move-flip` records `different`: the row gets a `-2` successor, `move_footprint` refuses rotation and side changes (`place.no-definition` for all), and the grid strategy is unaffected, because it only translates.
   - Rejected: inverting the placement of the board's own footprint node. The inverse of a flip needs every layer pair and every text mirrored back, which is the placer of c0017 run backwards; the library definition is exact and already there for built projects (c0027 vendors every row's footprints).
   - Rejected: moving attached tracks. Copper is the router's.

5. **Legality.** `placement.legality.check(extents, outline, *, edge_clearance=0, names) -> tuple[Issue, ...]`:
   - `place.courtyard-overlap` (error; `where` = `REF1,REF2` sorted): two footprints have rings on the same face whose interiors intersect;
   - `place.outside-outline` (error; `where` = the reference): a ring point lies outside the board ring or inside a cut-out;
   - `place.edge-clearance` (warning): a ring is inside the board but closer to its boundary than `edge_clearance`;
   - `place.no-extent` (info): a footprint whose extent has `source == "none"`; it is not judged;
   - `place.no-outline` (info): the outline has a `problem`; only overlaps are judged.
   - `edge_clearance` is the smallest `min` of the rules of kind `edge_clearance` whose first selector is `all`, in the model design the caller holds (`placement.legality.edge_clearance(design)`), else 0. A board read from a file has no rules, so `place` uses 0.
   - `place.outside-outline` is exact about the boundary: a ring that only touches the board ring or a cut-out ring is inside. A cut-out that lies wholly inside a courtyard is not reported: no ring point is in it.
   - Staged parts (off the board by c0019's definition, without `place()`) are not judged: `layout.unplaced` already names them.
   - All predicates are exact: ring against ring with `geometry`'s segment classification and point location; distances with the squared-distance predicates. An extent with `exact == False` lowers nothing: its verdict is reported with "(approximate extent)" in the message.

6. **Touching courtyards.** KiCad decides what "overlap" means. `place-touch` builds two courtyards that share an edge exactly and two that share one corner, and records whether `courtyards_overlap` appears. `legality` follows the recorded outcome: the default, pending the probe, is that touching is not an overlap (interiors must intersect). If the majors disagree, the stricter outcome is used and the row says so.

7. **Grid strategy.** `placement.grid.place(boxes, region, *, occupied, pitch, gap, margin) -> GridResult`:
   - `boxes`: the parts to place, in component-path order, each with the bounding box of its front extent relative to its position;
   - `region`: the bounding box of the board ring, inset by `margin` (default 1 mm);
   - `occupied`: the bounding boxes of the extents already on the board;
   - shelf packing, left to right and top to bottom: each box goes at the first position, on a `pitch` grid (default 0.5 mm) for its top-left corner, whose box, grown by `gap` (default 0.5 mm), intersects no occupied box and no cut-out; the row height is the tallest box of the row;
   - a part that fits nowhere stays staged, with `place.no-room` (warning);
   - parts keep rotation 0° and the top side, so the strategy only translates.
   - The result is the same for the same inputs: no randomness, no clock, no dictionary order.
   - Rejected: sorting by area. Component-path order keeps a module's parts together and is what the author sees in the script.

8. **`fenolite place PATH`** (`cli/cmd_place.py`, `mutates=True`). Flags: `--strategy grid|manual` (default `grid`), `--move REF=X,Y[,ROT[,SIDE]]` (repeatable; implies `manual`; lengths in the DSL's unit syntax, in the board frame of `place()`: relative to the top-left corner of the bounding box of the board ring, Y down; relative to the file origin when the board has no outline), `--only REF,REF` (grid: place only these staged parts), `--pitch`, `--gap`, `--margin`, `--force`, `-o/--out FILE`.
   - Grid places exactly the footprints that are off the board (c0019's definition), `--only` narrowing them.
   - After the moves, `legality.check` runs on the resulting layout. With any `place.*` error and no `--force`, the command returns no `PlannedWrite`, and the exit code is 5. With `--force` it writes and still reports the issues.
   - One `PlannedWrite` for the board (`--out` or in place); none when nothing moved.
   - `result`: `board`, `strategy`, `moved` (`[{ref, path, from, to}]` with positions in nm, rotation in µdeg and side; sorted by reference), `unplaced` (references still staged) and `legality` (counts by code).
   - Evidence: `placement.EVIDENCE`, `INFERRED` (`H-K-PLACE-MOVE` until settled); KiCad's DRC is the judge of a placement.
   - `example_args`: `(EXAMPLE_BOARD, "--move", "R1=12mm,8mm", "--out", "fenolite-placed.kicad_pcb", "--dry-run")`, hermetic; `mutation_example_args` the same without `--dry-run`.

9. **Legality in `build`.** `cmd_build.placement_guard(files, *, name, staged, edge_clearance)` reads the planned board text back, as c0029's `copper_guard` does, calls `legality.check` with the backend's `placed_extents` and the rings of `board_outline`, and returns the issues with severities capped at `warning`: a build never refuses for placement, because staged or overlapping parts are a normal intermediate state and KiCad's DRC is the gate. The step lives in `cmd_build` because `lens` may not import `placement` (`package-layering`); `build_design` and `BUILD_ISSUE_CODES` stay unchanged and the `place.*` codes join the envelope as "Build issue codes" allows.
   - Rejected: refusing the build. The dogfood author needed the report, and a refusal would block the first build of every design without `place()`.

10. **The next build keeps the placement.** No lens change: a placed part is on the board, so `effective_placements` keeps it. A part with an unlocked `place()` that the placer moved gives c0019's `layout.place-overridden`; with a locked `place()`, the script wins and `layout.place-forced` says so. `place` reports both cases in advance as `place.script-locked` (warning) for parts whose `.fenolite/` model has a locked placement, when the project is built.

11. **Determinism.** Two `place --confirm` runs on equal boards write equal bytes; `moved` is sorted; no value holds a path outside the project or a date.

12. **No model, schema or FEN-code change.** One new package under an existing layering row.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/placement/__init__.py` (new) | re-exports `check`, `place`, `GridResult`, `ISSUE_CODES`, `EVIDENCE` |
| `src/fenolite/placement/legality.py` (new) | `check(extents, outline_rings, *, edge_clearance=0, names, touching_overlaps=TOUCHING_OVERLAPS) -> tuple[Issue, ...]`; `TOUCHING_OVERLAPS: bool` (from the probe); `edge_clearance(design) -> Nm`; `interiors_intersect(a, b) -> bool` |
| `src/fenolite/placement/grid.py` (new) | `Box(path, ref, bbox)`; `GridResult(positions: Mapping[str, Point], unplaced: tuple[str, ...])`; `place(boxes, region, *, occupied, cutouts=(), pitch=500_000, gap=500_000, margin=1_000_000) -> GridResult` |
| `src/fenolite/placement/codes.py` (new) | `ISSUE_CODES`; `EVIDENCE` |
| `src/fenolite/backends/kicad/replace.py` (new) | `PlacementError(FenoliteError)` (`issues`); `move_footprint(…) -> Design` (Decision 4) |
| `src/fenolite/backends/kicad/outline.py` (new) | `BoardOutline(rings, source, problem, exact)`; `board_outline(design, *, tol=DEFAULT_TOL) -> BoardOutline` |
| `src/fenolite/cli/cmd_place.py` (new) | `COMMAND` (`place`, `mutates=True`) |
| `src/fenolite/cli/cmd_build.py` (extended) | `placement_guard`; legality issues in a build (Decision 9) |
| `tests/unit/placement/` (new) | `test_legality.py`, `test_grid.py` on authored rings |
| `tests/unit/backends/kicad/test_replace.py`, `test_outline.py`; `tests/unit/cli/test_place_cmd.py` (new) | hermetic |
| `tests/kicad/place/` (new) | `_placecases.py`, `test_place_probes.py`, `test_place_oracle.py` |
| `docs/placement.md` (new); `docs/cli-contract.md`; `docs/formats/kicad/board.md` | user guide; the `place` section; outline and re-placement facts |

## Sources registered by this change

None. Rows of other changes cited here: S-0010 and S-0038 (courtyard checks, the board edge), S-0020 (observed `kicad-cli` behaviour), S-0019 (IPC-D-356), S-0022 and S-0037 (`pcb export pos`). Task 1.1 widens S-0020 (touching courtyards, moved footprints) and S-0038 (the courtyard overlap check). S-0210 to S-0214 stay unused.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-PLACE-MOVE | A footprint moved by `move_footprint` is read by `kicad-cli` at the requested position, rotation and side, with each pad on its former net: translation on any board; rotation and side from the library definition (S-0022, S-0037, S-0019) | `tests/kicad/place/test_place_probes.py::test_move` | on 9.0.9 and 10.0.6, for the authored project: `pcb export pos` gives the requested placement for a translation, a 90° and a 30° rotation and a flip, and the IPC-D-356 pad nets are unchanged; probes `place-move-translate`, `place-move-rotate`, `place-move-flip` = `equal` |
| H-K-PLACE-TOUCH | Two courtyards that share an edge or a corner, with disjoint interiors, give no `courtyards_overlap` (S-0038, S-0020) | `tests/kicad/place/test_place_probes.py::test_touch` | on 9.0.9 and 10.0.6: no `courtyards_overlap` for the edge pair and the corner pair, and one for a pair overlapping by 20 µm; probe `place-touch` = `absent`; `TOUCHING_OVERLAPS` follows the outcome |
| H-G-PLACE-OUTLINE | `board_outline` closes at least one ring, or names its problem, for every readable non-heavy demo board, without a snapping tolerance (S-0024, S-0058; builds on `H-G-EDGE-EXACT`) | `tests/corpus/test_outline_corpus.py::test_outlines` | on the 21 boards: counts of `model`, `edge` and each `problem` recorded; no exception; a board with a closed outline in KiCad's own `pcb export stats` (10.0.6) has a ring |

Ids used without changing their level: `H-G-FRAME-CRTYD`, `H-G-EDGE-EXACT`, `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`, `H-K-PCB-POS`, `H-K-NET-IPC`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Moved footprints | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-PLACE-MOVE` | `test_place_probes.py::test_move` |
| Touching courtyards | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-PLACE-TOUCH` | `::test_touch` |
| Legality agrees with KiCad on the bench | KICAD-VERIFIED: every `place.courtyard-overlap` pair of the bench has a `courtyards_overlap` violation and no other pair has one | `test_place_oracle.py::test_legality_matches_drc` |
| Outline rings | CORPUS-VERIFIED, `H-G-PLACE-OUTLINE` | `test_outline_corpus.py` |
| Grid placer, command, build issues | mechanical | `tests/unit/placement`, `test_place_cmd.py` |
| Placed blink survives a rebuild | mechanical with the lens; observed on both majors | `test_place_oracle.py::test_placed_then_rebuilt` |

## Budget (6.0 days; the roadmap gives 4.5)

| work | days |
|---|---|
| registers, docs skeleton | 0.25 |
| probes (move, touch) | 1.0 |
| `outline.py`, corpus count | 0.75 |
| `legality` | 1.0 |
| `grid` | 0.75 |
| `move_footprint` | 1.0 |
| `place` command, build issues | 0.75 |
| oracle proofs, docs, closing | 0.5 |
| **total** | **6.0** |

Cut order: (1) rotation and side changes in `move_footprint` (translation only; `--move` then takes two values); (2) `place.edge-clearance`; (3) the outline from `Edge.Cuts` (built projects only, native boards give `place.no-outline`). Not optional: the grid strategy, overlap and outside-outline legality, the build report, the move proof on both majors.

## Risks / Trade-offs

- [A footprint without a courtyard] → c0028's extent falls back to the definition or the pad hull, with `source` saying so; `source == "none"` is reported and not judged.
- [The grid leaves parts staged on a small board] → `place.no-room` names them; the author places them or enlarges the outline.
- [A moved part leaves its tracks behind] → `place` warns with `place.copper-left` when a moved footprint's pads had copper ending on them; the router or the author fixes it.
- [Fields of a re-placed footprint] → c0030 is archived, so a rotation keeps the old field values (Decision 4); `H-K-PLACE-MOVE` is still judged on position, rotation, side and nets only.

## Migration Plan

Additive. To roll back, remove the package, the two backend modules and the command, and drop `placement_guard` from `cmd_build`.

## Open Questions

- **Severity of placement issues in `build`.** Default: warnings (Decision 9). The dogfood author asked for a check, not a gate.
- **Default pitch, gap and margin.** Defaults 0.5 mm, 0.5 mm and 1 mm are Fenolite choices, not fab rules. To confirm.
- **A `check` stage for legality.** Default: none; `courtyards_overlap` comes from KiCad's DRC through c0020.
- **Bottom-side and rotated grid placement.** Default: not in v0.1.
- **Snapping tolerance and footprint edge items.** Measured in task 3.2: 3 of the 21 demo boards have a closed outline in KiCad and no ring here (one gap of 33 nm; two outlines completed by edge items inside footprints). Default: exact chaining of root graphics stays, and those boards get `place.no-outline`. To decide: a tolerance of 1 µm, and chaining the edge items of footprints.
