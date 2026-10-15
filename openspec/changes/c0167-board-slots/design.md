## Context

- **Request.** The maintainer's capability request "board slots and cut-outs, end to end" (2026-10-15). It is split into four changes: this one (model, script, union, KiCad); c0168 (Altium slots and cut-outs); c0169 (copper-to-edge clearance, holes in cut-outs, creepage equality); c0170 (conversion and routing obstacles). Each later change depends on this one.
- **What exists** (`origin/dev` at `a87723c`, read on 2026-10-15). Each item checks a claim of the request; corrections are marked.
  - Model. `Outline(points, cutouts, arcs)` with `OutlineArc(ring, edge, mid)` (`model/board.py:158-180`). `Hole(position, drill, plated, intent)` is round only (`:526-533`). `HoleShape = Literal["round", "square", "slot"]` (`:58`) is used only by `Padstack.hole_shape`, with `hole_length` and `hole_rotation` (`:193-202`), so only for footprint pads. *Correction:* the request's "HoleShape has slot only for footprint pads" holds, and the type has a third value, `square`.
  - Script. *Correction: a script can already draw a slot.* `design.cutout(path)` (`dsl/design.py:1018`) takes `shape.slot(start, end, width)` (`dsl/shape.py:138`), a stadium between two centres with exact arcs, rounded half to even once. `design.hole(ref, x, y, *, drill, length=None, rot=0, pad=None, …)` (`dsl/design.py:804`) makes a locked part whose generated footprint holds an oval NPTH pad (c0102, Decision 7). Neither gives the slot an id: a cut-out is a ring of `Outline.cutouts` (`dsl/convert.py:325-332`), named `cut-out <k>` by its index.
  - KiCad writer. `_Writer.outline()` writes one `gr_line` or `gr_arc` per edge of every ring on `Edge.Cuts`, uuids signed with the outline's digest (`backends/kicad/pcb.py:2767-2823`, `_edgesign.py:41-65`). `write_board` raises `ValueError` for any `Board.holes` (`pcb.py:3321-3322`). *Correction:* overlapping rings are not written "as-is" by a build: `check_outline` (`outline.py:442-499`) gives `kicad.outline.invalid` for rings that cross or touch, and the build stops (`lens/build.py:1024-1026`). Only `write_board` called on a model (the API, `convert`) writes them as they are; then KiCad reports `invalid_outline` (measurement 1).
  - KiCad read-back. A read board has `Board.outline = None`; its edges stay graphics. `outline.board_outline` chains them into rings (`outline.py:218-269`); ring 0 is the board, the others cut-outs. No `Outline` and no slot is made.
  - Geometry. `BACKEND_ORDER = ("fallback",)` (`geometry/boolean/__init__.py:18`); the fallback's `operations` is `{"intersection"}` and its `union` raises `BackendUnavailable` (`fallback.py:29-43`). `pyproject.toml:39` declares `geo = ["shapely>=2.1", "pyclipper>=1.3"]`, and `_extra.GEO_MODULES` names both (`_extra.py:17`). Shapely bundles GEOS, which is LGPL (S-0015); pyclipper is MIT with Clipper 6.4.2 under the Boost licence (S-0016). The lock holds pyclipper 1.4.0 and shapely 2.1.2.
  - Integer trigonometry. `cos_sin_fixed(udeg)` is in `geometry/transform.py:111`; `dsl` may not import `geometry` (`tests/unit/test_import_graph.py:33`).
  - Analyses. `board_boundary` (`analysis/boundary.py:138-162`) takes `Outline.cutouts` with their arcs, else the edge rings; *the request is right* that creepage uses cut-outs and `--groove-width`. Eleven modules read `.cutouts` directly (`analysis/boundary.py`, `grooves.py`, `surface.py`, `body_volumes.py`, `backends/altium/lower.py`, `backends/kicad/_edgesign.py`, `outline.py`, `cli/cmd_analyze.py`, `lens/altium.py`, `placement/constrained_legality.py`, `placement/preview.py`).
  - Altium build. An outline with cut-outs or arcs plans no PCB document (`lens/altium.py:1059-1066`).
  - Names. `model.base.Slot` (`model/base.py:51`) and `backends/kicad/slots.py` already use the word for the opaque round-trip unit (capability `kicad-slots`).
- **Measured on 2026-10-15,** in the pinned images `kicad/kicad:10.0.6` and `kicad/kicad:9.0.9` through `cli_for(Path("docker:<image>"))`, on boards written by `write_board` of this base or built by `build_design`, `pcb drc --format json --severity-all` and `pcb export drill` with the options of `exports.plan`. Same outcome on both majors unless said. A scratch script, not committed; tasks 1.2 and 4.4 make each one a probe.
  1. *Overlap.* A 40 × 30 mm board with two cut-outs of `shape.slot` 2 mm wide, (10, 10)–(20, 10) mm and (20, 10)–(20, 20) mm, an L sharing one round end. `check_outline` gives one `kicad.outline.invalid` ("the rings cut-out 1 and cut-out 2 cross or touch"); `write_board` writes both rings; DRC reports `invalid_outline`; both drill files are empty.
  2. *Exact union.* The same L as one cut-out of seven vertices: lines, the outer quarter arc about (20, 10) mm through (20.707107, 9.292893) mm, the two other round ends, and the concave corner (19, 11) mm. `check_outline` gives nothing; DRC reports no violation.
  3. *Polygonised union.* The same L from shapely's buffer and union, 324 vertices, straight edges: no violation.
  4. *Drilled slots overlapping.* Two `design.hole(…, drill=mm(2), length=mm(12))`, one turned 90°, forming the L: the build gives no issue; the NPTH file holds two `G85` slots; DRC reports `courtyards_overlap` and `lib_footprint_issues` on both majors and `npth_inside_courtyard` on 10.0.6, and nothing about the holes.
  5. *Copper near the two forms.* A plated hole part (2 mm copper) 0.2 mm from the milled slot gives `copper_edge_clearance` on both majors. The same 0.2 mm from an oval NPTH pad gives `hole_clearance` on 10.0.6 and nothing on 9.0.9 (as `backends/kicad/drc.py:65-70` records for round holes).
  6. *Union in integers.* pyclipper 1.4.0, the two stadiums of measurement 1 polygonised by `board_outline(tol=1000)` (130 vertices each), `CT_UNION` with `PFT_NONZERO`: one ring of 164 vertices, of which exactly one is new, the concave corner (119, 111) mm, exact; every other vertex is an input vertex.
- **Constraints.** `core` and `model` stay stdlib-only and import nothing else; `dsl` imports `core` and `model`; third-party packages only through `_extra.load_extra`. Integers in nanometres and microdegrees.

## Goals / Non-Goals

**Goals**
- A slot is a first-class item of the board with a stable id, the same in every target.
- Overlapping slots and cut-outs mean their union, and no KiCad board is written whose outline crosses itself.
- A board written for KiCad reads back to the same slots within 1 µm, arcs as arcs.

**Non-Goals**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **A slot is a milled cut-out with parameters: `OutlineSlot` in `Outline.slots`.** `OutlineSlot(Entity)`: `center: Point`, `length: Nm` (overall, both round ends included), `width: Nm`, `rotation: Udeg` (the axis of its length, in the sense of `Transform.placement`). It is never plated. Its ring is the stadium of Decision 3; for every reader that takes rings it is one more cut-out after `Outline.cutouts`.
   - Why milled: the purpose is creepage, which is decided by board material, and a milled slot is board edge: KiCad judges copper near it with `copper_edge_clearance` on both majors (measurement 5); Altium's Board Outline Clearance measures to cut-out edges and names no hole (S-0460, page of AD 26). A drilled slot exists already (`design.hole(length=…)`), is judged by hole rules (`hole_clearance`, 10.0.6 only, measurement 5) and reports no overlap (measurement 4).
   - Rejected: `Hole` with a shape, a length and a rotation (drill = width). `Hole` is a drilled hole: Altium writes it as a free pad (c0085), KiCad refuses it (`pcb.py:3321`), and the maintainer's decision of 2026-10-07 keeps holes as footprints for KiCad. One field meaning "milled" in KiCad and "drilled" in Altium would be two meanings. c0168 extends `Hole` for the drilled form, where it fits.
   - Rejected: a new `Board.slots`. A slot outside an outline has no meaning, and every reader of `Board.outline` would have to learn a second collection.
   - Rejected: the ring alone (today's `cutout(shape.slot(…))`). It has no id and loses the centre, length and angle that a finding, a report and Altium's lowering need. It stays for drawn cut-outs.
   - Name. `slot` already names the opaque round-trip unit (`model.base.Slot`, `backends/kicad/slots.py`). The new type is always `OutlineSlot`, no module is named after it, and `docs/design-model.md` says which is which.

2. **Validation.** The DSL refuses at the call, and `check_outline` refuses on the model with `kicad.outline.invalid` naming `slot <name>`: `width` positive and even (its half is exact); `length > width` (a slot as long as wide is a circle: use `shape.circle`); `rotation` taken modulo 180°; the stadium inside the board ring and not touching it. The canonical writer omits `slots` when empty; the schema gains it.

3. **One stadium, in `core`.** `fenolite.core.stadium.stadium(center, length, width, rotation) -> Stadium(points, mids)`: with `u` the unit axis, `h = (length − width) / 2` and `r = width / 2`, the vertices `center ∓ h·u ∓ r·n` and the mids `center ± (length / 2)·u`, in the order of `shape.slot` (line, arc, line, arc). Each coordinate is rounded half to even once from the fixed-point cosine; at a multiple of 90° the ring is exact. The cosine table moves from `geometry/transform.py` to `fenolite.core.trig` and `geometry.transform` re-exports `cos_sin_fixed` (no value changes). `design.slot`, `shape.stadium`, the KiCad lowering, the checks and the Altium lowering all call it.
   - `shape.slot(start, end, width)` keeps its own rounding and its bytes; for a slot turned at an angle it may differ from `stadium` by 1 nm per coordinate, and `docs/dsl.md` says so.
   - Rejected: the helper in `geometry`, which `dsl` may not import. Rejected: copying the trigonometry into `dsl`.

4. **Script.** `design.slot(x, y, *, length, width, rot=0, name=None) -> str` adds one `OutlineSlot` after `board()`; `name` defaults to `S<n>` in call order and must be unique; the id is `key_id("slot", name)`, key row `slot` with prefix `slt` and key `slot:<slot name>`. It returns the name. `shape.stadium(x, y, length, width, rot=0)` returns the same ring as a path for `cutout()` and `board(outline=…)`. Both are taught in the agent guide (CONTRIBUTING, "The agent guide follows the code").
   - Rejected: `design.slot(start, end, width)`. The request and Altium's pad properties page (registered by c0168, task 1.1) describe a slot by centre, overall length, width and angle; `shape.slot` keeps the two-centre form for drawn rings.

5. **Union: a `clipper` backend and a curved merge.**
   - `geometry/boolean/clipper.py`: `ClipperBackend`, `name = "clipper"`, `operations = frozenset({"union"})`, through `load_extra("pyclipper")`; `union` runs `CT_UNION` with `PFT_NONZERO` on the integer rings and returns `normalize_polygons` of the result. Integer in, integer out (measurement 6); the coordinate domain is checked first.
   - `BACKEND_ORDER = ("fallback", "clipper")` and `select_backend(prefer=None, *, operation=None)`: with `operation`, the first available backend whose `operations` holds it, else `BackendUnavailable` naming the extra. Without it, the first available backend, which stays `fallback`: `analysis/body_volumes.py:126` gets what it gets today.
   - `geometry.rings.merge_rings(rings, *, tol=MERGE_TOL) -> tuple[CurvedRing, ...]`, `MERGE_TOL = 1_000` nm. A `CurvedRing` is a ring of vertices with optional arc mids per edge. Rings are grouped by overlap (`thick_touch` on their polygonisation at `tol`); a group of one is returned unchanged, with its exact arcs. A group is polygonised at `tol`, each polygonisation vertex tagged with its source arc, united by `select_backend(operation="union")`, and the arcs are put back: a maximal run of output vertices that are interior vertices of source arcs on one circle (two round ends of an L share theirs), with its two ends, becomes one arc from the first to the last end whose mid is the run's middle vertex (on the circle within 0.5 nm). A run without an interior vertex stays straight. The result is normalised (start at the least vertex, positive orientation).
   - A group whose union is not one ring without holes (two rings that only touch, or a ring enclosed by the union) is not merged: `check_outline` refuses it as today.
   - Rejected: shapely, which bundles LGPL GEOS (S-0015) and so falls under "Copyleft only across a process boundary". Rejected: an exact arc–arc boolean, whose intersection points are irrational and would be rounded anyway; the merge rounds only the new vertices and keeps every original arc on its circle. Rejected: writing the polygonised union (loads clean, measurement 3): arcs would become hundreds of lines.

6. **One lowering, in two layers.** `fenolite.model.outline.outline_items(outline) -> tuple[RingItem, ...]` (model and `core.stadium` only) gives every ring with its name (`board`, `cut-out <k>`, `slot <name>`), vertices and arc mids; `geometry.rings.merge_rings` merges them. `analysis`, `checks` and `placement`, which may not import a backend (`tests/unit/test_import_graph.py:28-49`), call this pair. In the KiCad backend `outline.lowered_outline(outline) -> Outline` returns an `Outline` without slots: the board ring, the cut-outs and the slot stadiums, overlapping groups merged by Decision 5, arcs as `OutlineArc`. `_edgesign.outline_rings` and `outline_edges`, `board_outline` (model branch), `outline_box`, `check_outline`, the edge signature and `fill_inputs_digest` read it, so the writer, the lens and the placement guard see one geometry.
   - `check_outline`: a slot that breaks Decision 2 gives `kicad.outline.invalid`; an overlap that `merge_rings` merges gives `kicad.outline.merged` (info) naming the items (`slot S1`, `cut-out 2`); without the `geo` extra it gives `kicad.outline.overlap` (error) naming them, with the hint `pip install 'fenolite[geo]'`, and the build stops as for `kicad.outline.invalid`.
   - `write_board` lowers the same way and refuses an unmerged overlap with `kicad.board.outline-overlap` (`LossyWriteError`), so the model API never writes what KiCad calls `invalid_outline` (measurement 1).
   - Rejected: a slot as an oval NPTH pad of a generated footprint. That is the drilled form, which exists (`design.hole`), reads back as a footprint, and is judged differently (measurements 4 and 5). `docs/dsl.md` says when to use which.

7. **Read-back.** `outline.edge_outline(design) -> Outline | None` gives the rings of `board_outline` with their exact lines and arcs (the edge graphics chained with `CHAIN_GAP`, before polygonisation), ring 0 the board and the others cut-outs, without slots. `outline.slots_of(outline) -> tuple[OutlineSlot, ...]` recognises a cut-out of two parallel lines of equal length and two half circles, within 1 nm, as a slot with a content id; `convert` (c0170) and the round-trip tests call it. `Board.outline` of a read board stays `None` (the lens contract).

8. **`Board.holes` in KiCad.** The refusal stands (maintainer's decision of 2026-10-07). The bare `ValueError` becomes the writer error `kicad.board.free-hole` naming the holes, with the hint "declare a hole with design.hole(), or place a board-only footprint with an unnumbered np_thru_hole pad" (`LossyWriteError`).

9. **The Altium build until c0168.** An outline with slots plans no PCB document, like one with cut-outs: `altium.pcbdoc-not-written` names the slots (`lens/altium.py:1065`), and `lower._outline` adds the slots to its skip of cut-outs.

10. **Analyses.** `board_boundary` takes `lowered_outline` of the model outline: slots are cut-outs and overlaps are merged. Without the extra and with an overlap, `BoardBoundary.problem` is `overlap-needs-geo`, and `fenolite analyze` gives `geometry.backend-unavailable` (exit 6).

11. **Codes.** `kicad.outline.merged` (info) and `kicad.outline.overlap` (error) join `outline.CHECK_ISSUE_CODES`; `kicad.board.outline-overlap` and `kicad.board.free-hole` are writer errors. All are `kicad.*` codes and pass the build tables unchanged (c0102, Decision 10). Each gets an `explain.toml` entry and a row of the agent guide's page `recovery`.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/core/trig.py` (new) | `cos_sin_fixed`, the fixed-point table (moved) |
| `src/fenolite/core/stadium.py` (new) | `Stadium(points, mids)`, `stadium(center, length, width, rotation)` |
| `src/fenolite/model/board.py`, `schemas/fenolite.model.v0/board.json` | `OutlineSlot`, `Outline.slots` |
| `src/fenolite/model/outline.py` (new) | `RingItem(name, points, mids)`, `outline_items(outline)` |
| `src/fenolite/dsl/design.py`, `dsl/shape.py`, `dsl/convert.py` | `Design.slot`, `Design.slot_specs`, `shape.stadium`, key `slot` |
| `src/fenolite/geometry/boolean/clipper.py` (new), `boolean/__init__.py` | `ClipperBackend`; `select_backend(…, operation=)` |
| `src/fenolite/geometry/rings.py` | `CurvedRing`, `merge_rings`, `MERGE_TOL` |
| `src/fenolite/backends/kicad/outline.py`, `_edgesign.py`, `pcb.py` | `lowered_outline`, `edge_outline`, `slots_of`; codes |
| `src/fenolite/analysis/boundary.py` | slots and merged rings; `BoardBoundary.problem` |
| `src/fenolite/lens/altium.py`, `backends/altium/lower.py`, `lens/preserve.py` | slots refuse the document; digest |
| tests | `tests/unit/core/test_stadium.py`, `tests/unit/model/test_outline_slots.py`, `tests/unit/dsl/test_slots.py`, `tests/unit/geometry/test_clipper.py`, `test_merge_rings.py`, `tests/unit/backends/kicad/test_slots_outline.py`, `tests/kicad/board/_slotbench.py`, `test_slots.py`; the shared fixture `tests/data/slots/design.py` |
| docs | `docs/geometry.md` ("Boolean backends", "Union of curved rings"), `docs/dsl.md` ("Board"), `docs/design-model.md`, `docs/formats/kicad/board.md`, `docs/analyses.md` ("Creepage"), `docs/cli-contract.md` |

The shared fixture `tests/data/slots/design.py`, authored for Fenolite, design name `slots`: a 60 × 40 mm board; a lone slot `S1` 12 × 2 mm at (15, 10) mm; two slots `S2` and `S3` 12 × 2 mm forming an L about (40, 10) mm; a round hole `design.hole("H1", …, drill=mm(3.2))`; one cut-out ring with arcs, `shape.rect(…, radius=mm(1))` (`cut-out 1`). c0168 to c0170 add their own items to copies of it.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-SLOT-RING | A slot written as a stadium cut-out on `Edge.Cuts` loads with no `invalid_outline`, reaches no drill file and reads back to the same slot within 1 µm, arcs as arcs (S-0020, S-0029) | `tests/kicad/board/test_slots.py -k ring` | `slot-ring-drc` and `slot-ring-drill` `absent` on both majors; `slot-ring-read` `equal` |
| H-K-SLOT-OVERLAP | Two overlapping cut-out rings give `invalid_outline` on 9.0.9 and 10.0.6 (measurement 1) | `-k overlap` | `slot-overlap` `present` on both majors |
| H-K-SLOT-UNION | The merged ring of overlapping slots, with its arcs, loads with no violation (measurement 2) | `-k union` | `slot-union` `absent` on both majors |
| H-K-HOLE-OVERLAP | Overlapping oval NPTH pads give no hole finding, and a pad 0.2 mm from one gives `hole_clearance` on 10.0.6 only (measurements 4, 5) | `-k drilled` | `slot-drilled-overlap` `absent`; `slot-drilled-near` `present` on 10, `absent` on 9 |
| H-G-RING-UNION | `merge_rings` is deterministic, keeps every source arc on its circle, and its union lies within `MERGE_TOL` of the exact union (measurement 6) | `tests/unit/geometry/test_merge_rings.py` | unit criteria |

All start `INFERRED` with the measurements of 2026-10-15 as their first record.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| slots, overlaps and merged rings in a KiCad board | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-SLOT-RING`, `-OVERLAP`, `-UNION` |
| read-back within 1 µm | KICAD-VERIFIED for the file KiCad re-saves (10.0.x); mechanical for the reader | `H-K-SLOT-RING` |
| stadium, union, recognition, validation | mechanical | unit tests, with and without the `geo` extra |
| analyses on slots | mechanical | unit tests (c0169 adds the creepage equality) |

## Risks / Trade-offs

- **Rounded union vertices.** A new vertex of a merged ring is rounded to the nanometre and lies within `MERGE_TOL` of the exact intersection; KiCad and Altium mill what the file says. Original arcs stay exact.
- **The extra is needed for overlaps only.** A board without overlapping items builds without `geo`; one with them is refused with a named code and the install hint.
- **Two forms of slot.** Milled (`design.slot`) and drilled (`design.hole(length=…)`); `docs/dsl.md` gives the rule: creepage and board shape, milled; a fastener or a press-fit, drilled.
- **The word `slot`.** See Decision 1.

## Migration Plan

- Additive. A design without slots writes the same bytes (asserted by every committed sample). Release 0.4.x cannot read a model document that carries `slots`; `docs/design-model.md` and the changelog say so.
- `write_board` callers that caught `ValueError` for `Board.holes` get `LossyWriteError` with `kicad.board.free-hole`.

## Budget (6.5 days)

| part | days |
|---|---|
| probes and register (measurements 1 to 6 as probes, facts) | 0.75 |
| `core.trig`, `core.stadium`, model, schema | 0.75 |
| script: `slot`, `shape.stadium`, key, guide | 0.5 |
| clipper backend, selection by operation, import rule | 0.75 |
| `merge_rings` with arcs put back | 1.25 |
| lowering, check, writer, codes | 1.0 |
| read-back, recognition, round trip | 0.5 |
| analyses boundary, Altium refusal, lens digest | 0.5 |
| docs and closing | 0.5 |

Cut order: (1) `slots_of` recognition (read-back compares rings); (2) arcs put back by `merge_rings` (merged rings written as lines, measurement 3); never cut: the slot entity, the stadium, the refusal of an unmerged overlap.

## Open questions

1. **Slot as `Outline.slots` (milled), not `Hole` with a shape?** Recommended: yes (Decision 1); c0168 extends `Hole` for drilled slots, so both forms exist with one meaning each. Decided by the maintainer on 2026-10-15: yes; a milled slot is `Outline.slots`, and c0168 extends `Hole` for the drilled slot, so both forms exist with one meaning each.
2. **Is a slot as long as it is wide (`length == width`) allowed?** Recommended: no; it is a circle, `shape.circle` draws it, and the request's "length ≥ width" becomes "length > width". Decided by the maintainer on 2026-10-15: no; `length` must exceed `width`, and a round hole is drawn with `shape.circle`.
3. **Should `merge_rings` need the `geo` extra, or should Fenolite ship a stdlib union of stadiums?** Recommended: the extra (pyclipper, Boost/MIT); the core stays small, and the refusal names the install. Decided by the maintainer on 2026-10-15: the `geo` extra (pyclipper); the core stays small, and the refusal names the install.
4. **Should cut-outs drawn with `cutout()` get names and ids too?** Recommended: no; they keep `cut-out <k>`. A ring that needs a name is a slot or will get its own change. Decided by the maintainer on 2026-10-15: no; drawn cut-outs keep `cut-out <k>`.
5. **Should a read KiCad board fill `Board.outline` with `edge_outline`?** Recommended: no; the lens owns the edges, and `edge_outline` is called where a model outline is needed (c0170). Decided by the maintainer on 2026-10-15: no; a read board keeps `Board.outline = None`, and `edge_outline` is called where a model outline is needed (c0170).
6. **Should `Board.holes` be written to KiCad as generated footprints?** Recommended: no (decision of 2026-10-07); the named refusal and its hint. Decided by the maintainer on 2026-10-15: no; the refusal of 2026-10-07 stands, with the name `kicad.board.free-hole` and its hint.
