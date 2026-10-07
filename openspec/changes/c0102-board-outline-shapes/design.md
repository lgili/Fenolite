## Context

- **Scope.** The review of 2026-10-05 of the gaps to a complex board found three gaps that no change and no roadmap line owned: a script outline is a rectangle, without arcs, cut-outs or slots; board-level and mounting holes cannot be declared; a built board cannot take a new outline or a new copper count without `--discard-layout`, which drops the routing. This change, c0102 of milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches"), takes the three. c0009 and c0017 deferred arcs to "the mixed contour model (v0.2)", which no change took.
- **What exists** (`origin/dev` at `9aba2dff`, read on 2026-10-07):
  - Model. `Outline(points, cutouts)` (`model/board.py:86`), without arcs. `Hole(position, drill, plated)` (`:332`) exists. No KiCad reader and no script fills `Board.holes`: the Altium import does, c0085 writes each one to the Altium document as a free pad without copper, and `pcb.write_board` raises `ValueError` for it ("a KiCad board holds holes only inside footprints", `pcb.py:2675`). c0096, implemented on its own branch, adds a script call that fills it ("Relation to c0096").
  - Script. `Design.board(width, height, copper=2, planes=None)`. `to_model` writes the rectangle from `BOARD_ORIGIN` and never fills `cutouts`; a zone declared without an outline takes the four points of that rectangle. `arc_to(mid, end)` (c0068) gives an `ArcStep` of board-frame points for script copper.
  - Writer ("Outline lowering"). One `gr_line` on `Edge.Cuts` per edge of every ring, with the uuid `kicad_uuid(outline, "outline:<ring>:<edge>")`; no `gr_arc`; `kicad.board.outline-conflict` when the board also holds edge graphics.
  - Readers of the outline. `outline.board_outline` (`outline.py:146`) gives a model outline's points and cut-outs as rings (`source` `model`), and otherwise chains the root edge graphics and the edge items of footprints (`frame.footprint_edges`), joining endpoints closer than `CHAIN_GAP`, 10 µm (c0074, archived). Its rings feed the placement guard, `place`, `route` and the Specctra boundary. `analysis.boundary.board_boundary` repeats the model branch; `lens.build._staging` (`build.py:535`) and `lens.preserve._off_board` (`preserve.py:265`) take a box of `Outline.points`.
  - Lens. In `merge_layout` the board's edge graphics always win. `_edges_are_outline` (`preserve.py:251`) compares `line` graphics only, so a board with an arc in its edge would report `layout.outline-kept` on every rebuild. A script zone without an outline compares its new rectangle with the board's zone and keeps the old one with `kicad.zone.overridden`. A board whose copper names differ from `created_layers(copper)` gives `layout.copper-mismatch` (error). c0100 keeps that error, names the board's count in its hint, and leaves count changes to this change (its Decision 6). Placements have a third source since c0069 (archived): `placements.toml`, between the board and `place()`, written by `fenolite sync --to-source`.
  - Authoring (c0055, c0056). `Footprint.pad(kind="np_thru_hole")` is accepted with a drill, but its number must be non-empty (`dsl/footprint.py:63-64`); c0055 listed non-plated holes as a non-goal. A DSL `Symbol` needs at least one pin. Model `SymbolDef` has `in_bom` and `on_board`.
  - Altium build. No `.PcbDoc` for an outline with cut-outs (`altium.pcbdoc-not-written`, `lens/altium.py:616-617`); otherwise it writes `Outline.points`. Since c0085 (open on `dev`, code merged) a planned document holds the board's texts, graphics, keep-outs and holes, each written or reported by item (`lens.altium_copper.lower_items`), and `result.pcb` counts them by kind (`hole` among them); a hole is a round free pad without copper.
- **Measured on 2026-10-05,** on the branch where this proposal was written (`review-roadmap-complex-board`); not repeated on `dev` at `9aba2dff`, and tasks 1.2 and 1.3 record every part again as a probe. Boards built through the model API of that branch and written by its `write_board` for targets 9 and 10, run with `kicad-cli` 10.0.6 (macOS) and 9.0.9 (the pinned image), identical on both majors unless said. Drill files with the options of `exports.plan`: `pcb export drill --format excellon --excellon-units mm --excellon-separate-th --drill-origin absolute`.
  1. *Arcs and cut-outs.* A 60 × 40 mm outline with corners of radius 3 mm (`gr_arc`, mid points rounded to the nanometre), a round cut-out of 3.2 mm made of two `gr_arc`, a slot of 12 × 2 mm, a slot of 12 × 1.5 mm turned 30° (points rounded by `Transform.placement`) and a rectangular cut-out. `pcb drc --format json --severity-all` reports no `invalid_outline`; both drill files hold no hole; `pcb export gerbers --layers Edge.Cuts` draws 10 arcs (`G02` with `G75`). After `pcb upgrade --force` (10.0.6; 9.0.9 has no `upgrade`) the 22 items keep their uuids, 20 are unchanged, and the two negatively oriented arcs have start and end swapped (`H-G-ARC-DIR`). `board_outline` of the read board gives 5 rings.
  2. *A zone on the bounding box.* A zone on `B.Cu` whose outline is the 60 × 40 mm box of that board, refilled by `pcb drc --refill-zones --save-board` (10.0.6; 9.0.9 has no `--refill-zones`): of 376 fill vertices, none lies outside the board or inside a cut-out, and the closest lies 0.4973 mm from an edge ring polygonised at 5 µm; the board-setup edge clearance is 0.5 mm.
  3. *Malformed outlines,* on a 40 × 30 mm board: a round cut-out of 4 mm crossing the right edge, the same touching it at one point, two overlapping round cut-outs, a board ring that crosses itself, a round cut-out inside a larger one, and a control. 10.0.6 reports `invalid_outline` for the first four; 9.0.9 for the overlap and the crossing ring only; neither for the nested cut-out or the control.
  4. *Copper outside the outline* (10.0.6). A track and a via wholly outside a 50 × 30 mm board give only `track_dangling` and `via_dangling`; a track and a via across its edge give `copper_edge_clearance`.
  5. *Holes.* A board with a root `(pad "" np_thru_hole …)` fails to load on both majors ("Failed to load board", exit 3). Footprints with `(attr board_only exclude_from_pos_files exclude_from_bom)`: an `np_thru_hole` pad numbered `""` of 3.2 mm, two oval ones of 1 × 3 mm (one turned 30°), and a `thru_hole` pad `"1"` of 3.2 mm drill and 6 mm copper on `GND`. The NPTH file holds `T2C3.200` at the round hole and each slot as `X…Y…G85X…Y…` between its centres (`--excellon-oval-format` defaults to `alternate`); the PTH file holds the plated hole; `pcb export pos` lists only the SMD part; `pcb export ipcd356` gives three `367` records. 10.0.6's re-save keeps the empty numbers and the attributes.
  6. *Courtyards on both sides* (10.0.6). A hole footprint with a circle on `F.CrtYd` and on `B.CrtYd`, overlapped by a top part and by a bottom part: `courtyards_overlap` for both, and the build's placement guard gives `place.courtyard-overlap` for both pairs. Its messages name footprints by id, since authored footprints carry no Reference yet (c0077).
  7. *Copper count changed by text edit,* on a four-layer board built by that branch for each target (a script track through via steps to `In1.Cu`, a blind via `F.Cu`–`In1.Cu`, a zone on `In2.Cu`):
     - rows `(8 "In3.Cu" signal)` and `(10 "In4.Cu" signal)` added: the DRC report of the control; the Gerber job file lists 6 copper layers with KiCad's default stack-up (0.035 mm copper, 0.274 mm dielectrics);
     - rows `In1.Cu` and `In2.Cu` removed with the items on them: loads, with only the dangling ends that the removal leaves;
     - the rows removed and the items kept: loads, and `item_on_disabled_layer` (error) names the two tracks and the blind via; the zone is not named;
     - a four-layer stack-up written by KiCad (from a cached demo board) put into `setup`, with 6 or 2 rows: the job file lists the copper layers with no thickness at all; with 4 rows, its own values. 10.0.6's re-save keeps the stale four-layer stack-up when rows were added.
  8. *The proposal's branch, in process (2026-10-05).*
     - A part with KiCad's `Mechanical:MountingHole` symbol and `MountingHole:MountingHole_3.2mm_M3` footprint builds, exit 0.
     - An authored footprint must number its `np_thru_hole` pad: `"MH"` builds, with `build.pad-without-pin`, and the placement guard skips the part (`place.no-extent`: no courtyard, no pad copper); `""` raises `DslError`.
     - A read board whose footprints hold `(layers "*.Cu" "*.Mask")` pads raises `LossyWriteError` with `kicad.board.projection-read-only` once its copper rows change, unless each such pad's layers are re-expanded in the order of the wildcard, the copper of the new table first; then it writes.
     - In KiCad's 10.0.6 library, `MountingHole` is a symbol without pins and with `(in_bom no)`; `MountingHole_3.2mm_M3` holds `(pad "" np_thru_hole circle … (layers "*.Cu" "*.Mask"))`, `(attr exclude_from_pos_files exclude_from_bom)` and a `F.CrtYd` circle drawn 0.05 mm wide.

  None of these probes is committed. Each becomes a recorded probe or a test of this change.
- **Constraints.** Stdlib only. `dsl` imports `core` and `model` only, and `lens` never imports `geometry` (`package-layering`). Integers in nanometres; a point that is not an integer is rounded once, half to even. No value shipped: hole sizes, courtyards and radii are the user's (plan D6).

## Goals / Non-Goals

**Goals**
- A script draws a board that KiCad accepts: lines and arcs, round, slot and polygon cut-outs, and holes drilled where it says.
- What KiCad calls a malformed outline stops the build.
- A built and routed board follows a new outline or a new copper count and keeps what still fits.

**Non-Goals**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Arcs are a table of `Outline`.** `Outline.arcs: tuple[OutlineArc, ...]`, with `OutlineArc(ring, edge, mid)`: ring 0 is `points` and ring k is `cutouts[k − 1]`; edge i joins vertex i to vertex i + 1 (mod n), and an entry makes it the arc through `mid`. Entries are sorted by `(ring, edge)`, at most one per edge. A ring has three vertices or more, or two when one of its two edges is an arc: a circle is two arcs. This is the three-point form of KiCad's file, of the model's `Arc` and of `arc_to` (c0068 Decision 7). The canonical writer omits the default `()`, so every `board.json` written before keeps its bytes.
   - Rejected: a point type with an optional mid in `points`: older files would no longer load, and every reader of `points` would change at once. Rejected: the outline as edge `Graphic`s: two forms of one outline, and the lens treats edge graphics as the board's. Rejected: `geometry.Path` in the model, which may not import `geometry`.

2. **Closed paths in the script, and three helpers.** `board(outline=path)` takes the place of `width` and `height`; `design.cutout(path)` adds a cut-out to either form. A path is a sequence of `(x, y)` pairs and `arc_to(mid, end)` steps in the frame of `place()`. It closes with a straight edge to its first point unless its last element ends there; a last pair equal to the first point is that closure. `fenolite.dsl.shape`, a namespace like c0071's `select` because c0103 takes `design.rect` and `design.circle` for drawings, gives `rect(x, y, width, height, *, radius=None)`, `circle(x, y, diameter)` and `slot(start, end, width)`, each returning a path.
   - The DSL refuses what needs no geometry: an empty path, a first element that is not a point, an edge of length 0, an arc whose mid lies on the line through its ends, a two-point ring without an arc, a radius above half a side, an odd diameter or width in nanometres, a slot whose ends coincide.
   - A point that is not an integer, the mid of a corner at 45° or a tangent point of a slot at an angle, is rounded half to even once with `math.isqrt`; a horizontal or vertical slot and a circle are exact. The arc then runs through three integer points, as KiCad stores it.
   - Rejected: arcs by centre and angle, and fillets (c0068 Decision 7). Rejected: an `outline()` call beside `board()`: two outlines for one board. Rejected: cut-outs as rule areas: KiCad mills only `Edge.Cuts`.

3. **The build checks the rings with KiCad's strictest verdict.** `outline.check_outline(design)` polygonises the rings at `DEFAULT_TOL` and gives `kicad.outline.invalid` (error) for a ring that crosses or touches itself, two rings that cross or touch, a cut-out outside the board ring, and a cut-out inside another. The first two are 10.0.6's `invalid_outline`, a cut-out that only touches the edge included, which 9.0.9 accepts (measurement 3); one verdict serves both targets, as c0074 Decision 5 chose at 10 µm. A cut-out inside a cut-out loads in KiCad as a further piece of board (measurement 3), and a ring outside the board ring would be a second board (not measured); both are refused because `board_outline` takes every ring after the first for a cut-out. The step runs after `to_model`, so `build` exits 5 and writes nothing.
   - Rejected: leaving it to `check`: a malformed outline then reaches the placer, the router and the fill. Rejected: verdicts per target: one script, two answers.

4. **The writer signs the outline.** One `gr_line` or `gr_arc` per edge, stroke 0.1 mm as today. An arc whose `orient2d(start, mid, end)` is negative is written with start and end swapped, so KiCad's re-save keeps it (measurement 1). The uuid of an edge is `kicad_uuid(outline, "outline:<digest>:<edge text>")`. The edge text is `line X1 Y1 X2 Y2` or `arc X1 Y1 X2 Y2 XM YM` in nanometres, the two ends in increasing `(x, y)` order; the digest is the first 16 hexadecimal digits of the SHA-256 of the sorted edge texts, each followed by a newline.
   - So the edge graphics of a board tell whether they are an outline Fenolite wrote and nobody changed: the digest of their own texts gives back each one's uuid. A move in KiCad keeps the uuid and changes the text. A re-save keeps uuids and coordinates (`H-K-UUID-KEEP-2`, measurement 1), and the text ignores the direction that KiCad changes.
   - Rejected: today's uuids by position (`outline:<ring>:<edge>`). c0019 Decision 10 rejected recognising Fenolite's outline by uuid because a resize in KiCad keeps them; a uuid that holds the geometry it was written with does not have that flaw. Rejected: the last outline recorded in `.fenolite/`, a cache (c0019 Decision 11 rejected the same for fills).

5. **An outline change on a built board.** `outline.merge_outline(built, board, *, locked=False) -> OutlineMerge` adapts the existing board before the other rules of `merge_layout`:

   | the board's edge graphics | compared with the script's outline | result |
   |---|---|---|
   | none | — | the script's outline, as today |
   | any | equal, as edge texts | kept, and re-signed when every uuid is a position uuid of an older Fenolite |
   | signed: Fenolite's, unchanged (Decision 4) | different | replaced, `kicad.outline.replaced` (info) |
   | not signed: changed, drawn in KiCad, or older | different, `locked=True` | replaced, `kicad.outline.forced` (warning) |
   | not signed | different, unlocked | kept, `layout.outline-kept` (warning), its hint naming `board(..., locked=True)` |

   - *Replaced* means: the board's edge graphics are removed and its `outline` becomes the script's, which the writer then signs.
   - Each track, arc and via that the board holds and that is not script copper is dropped when it does not fit the new board. It fits when its copper (its core widened by half its width, a via's disc) touches no ring and its first core point lies inside the board ring and outside every cut-out, decided with `thick_touch` and `point_in_ring` on the rings of `board_outline`. `kicad.outline.copper-dropped` (warning) gives the counts and the nets. KiCad's DRC would not report copper left wholly outside (measurement 4); copper across the edge leaves an open connection that `route` can close (c0108).
   - A board zone matched to a script zone takes the box of the new outline when its own outline is the box of the replaced one and the script zone's is the new box: that is a zone declared without an outline, which today keeps the old rectangle.
   - Edge items inside footprints are left alone. Since c0074 `board_outline` chains them into the outline (`H-K-OUTLINE-FPEDGE`), but the script does not draw them and a kept footprint keeps its own graphics, so `merge_outline` signs, compares and replaces the root graphics only. When it replaces them and a footprint holds an edge item, the message of `kicad.outline.replaced` or `kicad.outline.forced` names those footprints, whose edge items remain part of what KiCad reads as the outline. A board whose outline closes only with footprint edge items was not written by Fenolite, has no signed content, and follows the rows "not signed".
   - Footprints never move; the placement guard names those left outside (`place.outside-outline`). Script copper is regenerated as always. Fills are dropped by `fill_inputs_digest`, which holds the edge content.
   - Rejected: the script always wins (c0019 Decision 10). Rejected: keeping copper outside, which nothing reports (measurement 4). Rejected: moving footprints inside, which is a placer's work (c0022). Rejected: removing a footprint's edge items when the outline is replaced: it would edit a footprint the user placed, for an outline the script cannot describe.

6. **A copper count change on a built board.** When the board's copper names are those of `created_layers` for another count of c0100's `CREATED_COPPER_COUNTS` (c0100's `created_count`), `layers.merge_layers(board, copper) -> LayerMerge` adapts the existing board instead of `layout.copper-mismatch`:
   - Rows of the layers that stay keep their `kicad` bag, with the type and user name set in KiCad; rows of new inner layers come from `created_layers(copper)`; rows of removed layers go. KiCad numbers the inner layers `In1.Cu` to `In<n − 2>.Cu`, so a smaller count removes the deepest ones.
   - On a removed layer, tracks and arcs are dropped; vias whose two layers name it are dropped, through vias stay; zones and rule areas lose the layer and are dropped when none is left; graphics and texts on it are dropped. `kicad.layers.removed` (warning) gives the counts per layer. KiCad would load them and report `item_on_disabled_layer` (measurement 7).
   - Pads of kept footprints whose `layers` child holds a wildcard are re-projected on the new table; otherwise the writer refuses (measurement 8).
   - A `stackup` child of `setup` whose copper layers are not the new table is removed, with `kicad.layers.stackup-reset` (warning), so KiCad derives its default; a stale one leaves the job file without thicknesses (measurement 7). With c0101 archived, its `merge_stackup` then finds no board stack-up and writes the script's, when there is one.
   - `kicad.layers.added` (info) names the new layers. `layout.copper-mismatch` stays for every other difference.
   - Rejected: the refusal, whose only way out drops the routing. Rejected: moving copper of a removed layer to a kept one, which changes the meaning of what was routed. Rejected: keeping the stale stack-up (measurement 7).

7. **Holes are parts with generated definitions.** `design.hole(ref, x, y, *, drill, length=None, rot=0, pad=None, courtyard=None, locked=True) -> Part` adds a part whose symbol and footprint the DSL generates (`dsl/holes.py`, model types only) in the library `Fenolite_Holes`:
   - Footprint: one pad. Without `pad`, an unnumbered `np_thru_hole` of the hole's size; with `pad`, a `thru_hole` numbered `1` with that copper size. Round, or oval for a slot of overall length `length` along the footprint's X axis. Layers `*.Cu` and `*.Mask`; flags `exclude_from_pos_files` and `exclude_from_bom`. A courtyard on `F.CrtYd` and `B.CrtYd`, drawn 0.05 mm wide: a circle for a round hole and a rectangle for a slot, of width `courtyard`, by default the larger of the hole and the pad. Named after its sizes: `NPTH_3.2mm`, `NPTH_Slot_1x3mm`, `PTH_3.2mm_Pad_6mm`, with `_Courtyard_<c>mm` when `courtyard` is given.
   - Symbol: `Hole`, without a pin, or `Hole_Pad`, with one passive pin `1`; both with `in_bom` false, as KiCad's `MountingHole` and `MountingHole_Pad` (measurement 8).
   - The part is placed at `(x, y)` on the top side, turned by `rot`, locked by default: an enclosure fixes a hole, so the script's position wins over a move in KiCad (`layout.place-forced`). A plated hole joins a net with `connect(net, part[1])`.
   - For the layout lens a hole part is a part like any other. "Placement precedence" places it: locked, so the script wins over the board and over an entry of `placements.toml`. `fenolite sync --to-source` lists it in `placements.toml` with the other parts; the entry then equals the script's position, and a hole declared with `locked=False` takes the entry as any unlocked part does. No rule of its own.
   - The build gains no step: the definitions travel as authored ones (c0055, c0058), since `cmd_build` reads `.definition` of every entry of `Design.footprints` and `Design.symbols`; the pinless symbol, which the `Symbol` builder refuses, is registered through a holder with that attribute. They are written to `lib/Fenolite_Holes.pretty` and `lib/Fenolite_Holes.kicad_sym`, and the parts are placed, matched and preserved as any part. The drill, position and test files follow measurement 5; the courtyard makes the placement guard judge holes on both sides (measurement 6).
   - Rejected: `Board.holes` lowered by the writer, which KiCad reads back as a footprint, so no rebuild would see a hole again. This is the form c0096 implemented (a neutral `Hole`, refused by its KiCad build); the maintainer decided on 2026-10-07 that the footprint form stands ("Relation to c0096"). Rejected: a round cut-out, which is milled, not drilled: no drill file holds it (measurement 1). Rejected: footprints without a symbol, a new path through the build where KiCad's library gives holes a symbol. Rejected: requiring KiCad's library part, which works (measurement 8) but needs the libraries and takes no size.

8. **Unnumbered hole pads in authored footprints.** `Footprint.pad("", kind="np_thru_hole", …)` is accepted: KiCad leaves its own mounting holes unnumbered (measurement 8) and keeps them so through a re-save (measurement 5). A footprint may hold several; their ids take a counter. An empty number for another kind still raises. An unnumbered pad maps to no pin and gives no `build.pad-without-pin`.
   - Rejected: a reserved number such as `MH` for holes, which KiCad's own library does not use and which gives `build.pad-without-pin` on every build (measurement 8).

9. **The readers of the outline.**
   - `board_outline` polygonises model arcs at `tol` and sets `exact` false. `outline.outline_box(design)` gives the exact box of the rings, arcs included (`Arc.bbox`), for the staging row and the off-board test, which take a box of `Outline.points` today and would collapse for a round board of two arcs.
   - `board_boundary` polygonises model arcs and gives them the band of curved edges, `arc_tol + 1`. `fill_inputs_digest` adds `Outline.arcs` to the outline's text.
   - A zone without an outline takes the box of the board ring's vertices and arc mid points, which `to_model` computes without geometry. The helpers put a vertex or a mid on every extreme of a curve; when an arc of the board ring bulges beyond that box, `check_outline` gives `kicad.outline.zone-short` (warning) naming the zones. KiCad clips the fill to the board (measurement 2).
   - The Altium build: Decision 14.
   - Rejected: computing the zone's box in the build, which would give `to_model` and the build two answers.

10. **Codes.** `kicad.outline.invalid` (error) and `kicad.outline.zone-short` (warning) in `outline.CHECK_ISSUE_CODES`; `kicad.outline.replaced` (info), `kicad.outline.forced` (warning) and `kicad.outline.copper-dropped` (warning) in `outline.MERGE_ISSUE_CODES`; `kicad.layers.added` (info), `kicad.layers.removed` (warning) and `kicad.layers.stackup-reset` (warning) in `layers.MERGE_ISSUE_CODES`. They are `kicad.*` codes, so they pass the build and lens tables unchanged, as c0031 and c0068 (Decision 6) did; "Build issue codes" and "Layout issue codes" are not modified. `layout.outline-kept` and `layout.copper-mismatch` keep their rows.
    - Rejected: `layout.*` and `build.*` codes, which need MODIFIED closed tables that other proposals of v0.4 would then have to regenerate.

11. **The lock is a build parameter.** `board(..., locked=True)` is read by `dsl.outline_locked(design)` and passed as `build_design(…, lock_outline=…)` to `merge_layout`, as c0101 passes `lock_stackup`. KiCad's lock flag is not written on the edge items: its token form on drawings is not measured.
    - Rejected: a `locked` field of the model's `Outline`: a board read from a file has no outline in the model, so the field would hold a script setting that no reader fills.

12. **Requirements shared with other changes** (checked on `origin/dev` at `9aba2dff`, `openspec/changes/*/specs`, on 2026-10-07).
    - No open change on `dev` holds a delta of the nine requirements this change modifies. c0074 and c0069 are archived, and three living texts moved since this proposal was written: "Board outline as rings" (endpoints joined below 10 µm, footprint edge items, `joined`), "Placement precedence" (the placements file, `layout.source-stale`, `layout.source-unknown`) and "Board content outside the design is kept" (group members that follow a renamed footprint). Their deltas were regenerated from the living text with this change's edits only.
    - "Board and placements in the DSL": c0096, then c0100, then this change. "Zones in the DSL": c0100, then this change. The deltas here are the living text of `dev` with this change's edits; c0100 lands first (a prerequisite), so task 0.1 regenerates both on the text it leaves (the counts 2, 4, 6 and 8, `inner_layers`), and on c0096's `anchor=` when c0096 is on `dev`.
    - "Layer count across rebuilds" is ADDED by c0100 and refuses a count change. It is not living on `dev`, so no delta of it can be written yet; once c0100 is archived, task 0.1 adds a MODIFIED delta that keeps its same-count rule and gives a count change to "Copper layer changes across rebuilds".
    - "PCB document output": the living text predates c0085, which holds no delta of it (its "Complete board in an Altium build" is ADDED). This change modifies the requirement for arcs and holes and, in the same delta, corrects the one sentence that c0085 overtook (board items reported per kind even when the document is planned), because the hole rule would contradict it otherwise.
    - No open change on `dev` modifies "DSL to model", "Outline lowering" or "Board boundary".
    - c0101's `merge_stackup` runs after `merge_layers`. c0103 leaves `Edge.Cuts` drawings to this change and owns keep-outs around holes. c0118 places tooling holes with `design.hole()`. c0077 (agent track, a proposal) gives hole footprints their Reference and Value; until then they hold none, as every authored footprint.
    - A change on a branch that maps several pads to one pin (c0123, not on `dev`) touches the pad-to-pin mapping that "Unnumbered hole pads in authored footprints" relies on; task 0.1 reads its state before task 5.1.
    - Rejected: writing these deltas on the texts of c0100 and c0096 now. They are not living, and an archive of this change before theirs would carry their edits.

13. **Guide line.** If c0080 is archived first, `board(outline=…)`, `shape`, `cutout` and `hole` get one tested line on its guide page (task 8.2). Rejected: writing the lines now, before the page and its test exist.

14. **The Altium build.** Three cases, each a rule of "PCB document output":
    - *Arcs.* An outline with arcs plans no PCB document, as an outline with cut-outs does today (`altium.pcbdoc-not-written`, naming the arcs). The document writes `Outline.points` only, and no fact row of `docs/formats/altium/` gives the form of an arc in the board outline.
    - *Hole parts.* They are not components of the Altium build: no schematic symbol, no library footprint, no component record. The lens hands each one to the document as a model `Hole`, the item c0085 already writes as a free pad without copper and counts under the kind `hole`. So a round hole that is not plated reaches the document through an existing record, with no new fact. A slot and a plated hole have no such record (the board hole of the model is round, without copper and without a net): each gives one `altium.not-lowered` with `where` `hole/<component id>`, is counted under `hole` of `result.pcb.not_lowered`, and the message of a plated hole says that its pin is absent from its net in the Altium project.
    - *The sentence c0085 overtook.* The living requirement says a planned document still reports keep-outs, texts, graphics and holes with one issue per kind. On `dev` that holds only for a build without a document (`board_not_lowered`); with one, `lower_items` writes or reports each item. The delta states this, in the words of c0085's "Complete board in an Altium build".
    - The courtyard of a hole part is not written: a free pad has none. `docs/altium.md` says so.
    - No row of the Altium rule table is touched: this change adds no rule kind and no selector.
    - Rejected: leaving every hole part out with one issue of the `holes` kind, as this proposal first said. c0085 writes round holes; reporting them as not lowered would drop what the document can hold.
    - Rejected: writing hole parts as components with their generated footprint. It needs a pinless symbol in the Altium schematic and an unnumbered pad in the library, neither of which has a fact row; the free pad needs neither.

15. **One new model key, and what an older release does with it.** `Outline.arcs` is additive: the canonical writer omits it when empty, and a document written before loads unchanged. The other direction does not hold, as for every additive key (the convention c0126 set): release 0.2.x cannot read a model document that carries `arcs`, because its reader refuses an unknown key. `docs/design-model.md` and the changelog say so (tasks 8.1 and 9.3), and the `board.json` that release 0.2.0 wrote, which c0126 commits as `tests/data/model/v0.2.0/blink_2layer.board.json`, must still load and serialise to its own bytes (task 2.1).

## Relation to c0096

c0096 (`constrained-board-placement`) is implemented on the branch `codex/c0096-constrained-placement` and is not on `dev` at `9aba2dff`. Its design records, in the table "Relation to c0103, c0113 and c0102", that its hole call conflicts with this change in signature, representation and KiCad support, and prefers this change's form for KiCad. The maintainer decided on 2026-10-07 (decision 2 of the v0.4 review): this change's form stands, and c0096 adapts to it. `Design.hole` is the call of this change: a locked part with a generated footprint.

| c0096 has | what becomes of it |
|---|---|
| `Design.hole(key, x, y, drill, *, plated=False, frame, tolerance, source, status, evidence) -> Hole` | goes. `Design.hole(ref, x, y, *, drill, length=None, rot=0, pad=None, courtyard=None, locked=True) -> Part` takes the name |
| `Design.holes`, the script's holes by key | goes. Hole parts are parts of the design |
| the row `hole`, prefix `hol`, key `hole:<hole key>` of `fenolite.dsl.KEYS` and of "Identifier derivation" | goes. A hole part is a component (`component:<ref>`), and its pad follows the rule of placed copies |
| `to_model` lowering script holes into `Board.holes` | goes ("Board holes in the DSL": `to_model` adds no `Hole`) |
| the KiCad build refusing script holes with `FEN-3004`, naming "a validated drill footprint" | goes. The KiCad build writes the hole footprint |
| "Altium hole lowering retains its contract", for script holes | replaced by "PCB document output" of this change, which reaches the same free pad record for a round hole that is not plated |
| `Hole.intent` and `Board.holes` in the model | stay, for readers and model callers; no script call fills them |
| `MechanicalIntent` on a hole | stays as a type. A hole part is a locked part, and c0096's own `Part.place(…, anchor=)` carries a `MechanicalIntent` on a locked placement, so the intent of a hole can ride on its placement. How `hole()` exposes it is for c0096's regenerated delta to state |
| `MechanicalReservation`, which names an existing footprint or pad drill | unchanged, and a better fit: the drill of a hole part is the pad of a footprint |

- Either change may reach `dev` first. If c0096 is first, task 5.2 of this change removes the names of the first five rows; they are in no release, and the changelog names them. If this change is first, c0096 is rebased without them.
- In both cases c0096 regenerates its MODIFIED "Board and placements in the DSL" and "Identifier derivation" from the living text and rewrites its ADDED "Mechanical primitives and locked anchors", whose scenarios author holes with a key.
- The module `fenolite.dsl.holes` of this change and c0096's attribute `Design.holes` would be two meanings of one word in one package; with the attribute gone only the module remains.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/board.py`, `schemas/fenolite.model.v0/board.json` | `OutlineArc(ring, edge, mid)`; `Outline.arcs` |
| `src/fenolite/dsl/design.py` | `board(width=None, height=None, copper=2, planes=None, *, outline=None, locked=False)`, `cutout(path)`, `hole(ref, x, y, *, drill, length=None, rot=0, pad=None, courtyard=None, locked=True) -> Part`; `Design.outline_path`, `Design.cutout_paths` |
| `src/fenolite/dsl/shape.py` (new) | `rect`, `circle`, `slot`; `fenolite.dsl` re-exports the module as `shape` |
| `src/fenolite/dsl/holes.py` (new) | `HOLE_LIBRARY = "Fenolite_Holes"`, `hole_footprint(drill, *, length, pad, courtyard) -> Footprint`, `hole_symbol(*, plated) -> SymbolDef`, `HoleSymbol(definition)`, the holder registered in `Design.symbols` |
| `src/fenolite/dsl/footprint.py` | unnumbered `np_thru_hole` pads |
| `src/fenolite/dsl/convert.py` | the outline with its cut-outs and arcs; the zone box; `outline_locked(design) -> bool` |
| `src/fenolite/backends/kicad/pcb.py` | `gr_arc` edges, positive orientation, signed uuids |
| `src/fenolite/backends/kicad/outline.py` | model arcs in `board_outline`; `outline_box`; `edge_texts`, `outline_digest`, `edge_uuid`; `check_outline`, `CHECK_ISSUE_CODES`; `merge_outline`, `OutlineMerge`, `MERGE_ISSUE_CODES` |
| `src/fenolite/backends/kicad/layers.py` | `merge_layers`, `LayerMerge`, `MERGE_ISSUE_CODES` |
| `src/fenolite/lens/preserve.py` | both adaptations in `merge_layout(…, lock_outline=False)`; edges compared as texts; `_off_board` on `outline_box`; `Outline.arcs` in `fill_inputs_digest` |
| `src/fenolite/lens/build.py`, `src/fenolite/cli/cmd_build.py` | the `check_outline` step; `lock_outline=`; staging on `outline_box` |
| `src/fenolite/lens/altium.py`, `lens/altium_copper.py` | arcs refuse the `.PcbDoc`; hole parts become board holes of the document or are reported (`hole/<component id>`) |
| `src/fenolite/cli/data/explain.toml` | one entry per new code (eight), and the `fix` texts of `layout.outline-kept` and `layout.copper-mismatch` |
| `src/fenolite/analysis/boundary.py` | model arcs |
| unit tests | `tests/unit/model/test_outline_arcs.py`; `tests/unit/dsl/test_outline_paths.py`, `test_shape.py`, `test_holes.py`, `test_footprint_holes.py`; `tests/unit/backends/kicad/test_outline.py`, `test_outline_write.py`, `test_outline_merge.py`, `test_layers_merge.py`; `tests/unit/lens/test_build_outline.py`, `test_build_holes.py`, `test_preserve_outline.py`, `test_preserve_layers.py`; `tests/unit/analysis/test_boundary.py` |
| oracle tests | `tests/kicad/board/_outlinebench.py`, `test_outline_shapes.py`, `_holebench.py`, `test_holes.py`; `tests/kicad/zones/test_zone_box.py`; `tests/kicad/lens/_layerbench.py`, `test_layer_change.py`, `test_outline_rebuild.py`; probes in `tests/kicad/_probes.py` and `docs/evidence/kicad/probes/*.json` |
| docs | `docs/dsl.md` ("Board", "Holes"), `docs/lens.md` (outline and layer changes), `docs/altium.md` (arcs, holes), `docs/design-model.md` (`Outline.arcs`, the 0.2.x sentence), `docs/formats/kicad/board.md` (the facts of measurements 1 to 7), `docs/cli-contract.md` (the codes) |

Public names a script sees: `board(outline=, locked=)`, `cutout`, `hole`, `shape.rect`, `shape.circle`, `shape.slot`.

## New names

- Model field: `Outline.arcs`; type `OutlineArc(ring, edge, mid)`.
- Script: `board(outline=, locked=)`, `Design.cutout`, `Design.hole`, `Design.outline_path`, `Design.cutout_paths`, `fenolite.dsl.shape` (`rect`, `circle`, `slot`), `fenolite.dsl.holes` (`HOLE_LIBRARY`, `hole_footprint`, `hole_symbol`, `HoleSymbol`), `outline_locked`; the library name `Fenolite_Holes` with the footprint names `NPTH_…`, `PTH_…` and the symbols `Hole`, `Hole_Pad`.
- KiCad backend: `outline_box`, `edge_texts`, `outline_digest`, `edge_uuid`, `check_outline`, `CHECK_ISSUE_CODES`, `merge_outline`, `OutlineMerge`, `MERGE_ISSUE_CODES` (`outline.py`); `merge_layers`, `LayerMerge`, `MERGE_ISSUE_CODES` (`layers.py`); the keywords `lock_outline` of `build_design` and `merge_layout`.
- Issue codes (eight): `kicad.outline.invalid`, `kicad.outline.zone-short`, `kicad.outline.replaced`, `kicad.outline.forced`, `kicad.outline.copper-dropped`, `kicad.layers.added`, `kicad.layers.removed`, `kicad.layers.stackup-reset`.
- Hypotheses (eight): `H-K-OUTLINE-ARCS`, `H-K-OUTLINE-INVALID`, `H-K-OUTLINE-OUTSIDE`, `H-K-ZONE-BOX`, `H-K-HOLE-FOOTPRINT`, `H-K-HOLE-COURTYARD`, `H-K-HOLE-SYMBOL`, `H-K-LAYER-CHANGE`.
- No CLI flag, no result key and no source id.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-OUTLINE-ARCS | An outline of `gr_line` and `gr_arc` items on `Edge.Cuts`, with cut-outs of arcs (a circle of two arcs, slots) and of lines, loads on 9.0.9 and 10.0.6 with no `invalid_outline`, puts no hole in the drill files and plots its arcs in the `Edge.Cuts` Gerber; a 10.0.6 re-save keeps every uuid and coordinate and swaps only negatively oriented arcs (S-0020, S-0029) | `tests/kicad/board/test_outline_shapes.py -k arcs` | probes `outline-arcs-drc` and `outline-arcs-drill` `absent` on both majors; `outline-arcs-keep` `equal` on 10.0.6 |
| H-K-OUTLINE-INVALID | 10.0.6 reports `invalid_outline` for a cut-out that crosses or touches the board edge, two overlapping cut-outs and a self-crossing ring; 9.0.9 for the last two only; neither for a cut-out inside a cut-out (S-0020, S-0029) | `tests/kicad/board/test_outline_shapes.py -k invalid` | probes `outline-invalid-<case>` with these outcomes, the control `absent` |
| H-K-OUTLINE-OUTSIDE | KiCad's DRC gives no `copper_edge_clearance` for a track or via wholly outside the outline, and one for each across the edge (S-0020, S-0029) | `tests/kicad/board/test_outline_shapes.py -k outside` | `outline-outside-free` `absent`, `outline-outside-across` `present`, on both majors |
| H-K-ZONE-BOX | A zone whose outline is the bounding box of a board with arcs and cut-outs, refilled by 10.0.6, holds no fill outside the board or inside a cut-out, and keeps the board-setup edge clearance from every ring within 5 µm (S-0020) | `tests/kicad/zones/test_zone_box.py` | probe `zone-box-fill` `absent` on 10.0.6 |
| H-K-HOLE-FOOTPRINT | No pad loads outside a footprint. An unnumbered `np_thru_hole` pad is drilled in the NPTH file of `pcb export drill --excellon-separate-th`, an oval one as one `G85` slot between its centres, a `thru_hole` one in the PTH file; `exclude_from_pos_files` keeps them out of the position file; IPC-D-356 gives `367` records for the NPTH pads (S-0020, S-0029) | `tests/kicad/board/test_holes.py` | `hole-root-pad` `reject`; `hole-drill` `equal`; `hole-pos` `absent`; on both majors |
| H-K-HOLE-COURTYARD | A footprint with courtyards on `F.CrtYd` and `B.CrtYd` gives `courtyards_overlap` with a top part and with a bottom part that overlap it, and none with a part clear of it (S-0020, S-0029) | `tests/kicad/board/test_holes.py -k courtyard` | `hole-courtyard-top` and `-bottom` `present`, `hole-courtyard-clear` `absent`, on both majors |
| H-K-HOLE-SYMBOL | A symbol library written by `sym.write_symbol_library` with a symbol without pins and one with a single pin, both with `(in_bom no)`, loads on both majors and exports both symbols (S-0020, S-0029) | `tests/kicad/board/test_holes.py -k symbol` | `hole-symbol-load` `equal` on both majors |
| H-K-LAYER-CHANGE | On a four-layer board, inner rows added with KiCad's numbers load with no new DRC finding and a job file of six copper layers; items left on a removed layer give `item_on_disabled_layer`; a `stackup` whose copper layers differ from the table leaves the Gerber job file without thicknesses, and a board without one gets KiCad's default (S-0020, S-0029) | `tests/kicad/lens/test_layer_change.py` | `layers-added` `absent`, `layers-left-items` `present`, `layers-stale-stackup` `present`, on both majors |

All eight start `INFERRED`, with the measurements of "Context" as their first record. Ids used without changing their level: `H-G-ARC-DIR`, `H-K-UUID-KEEP-2`, `H-G-PLACE-OUTLINE`, `H-K-LENS-KEEP`, `H-K-OUTLINE-CHAIN` (c0074).

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| arcs and cut-outs written, loaded and drilled as stated | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-OUTLINE-ARCS` |
| the build's ring check, for KiCad's cases | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-OUTLINE-INVALID` |
| holes: drill, position file, courtyard, symbol | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-HOLE-FOOTPRINT`, `-COURTYARD`, `-SYMBOL` |
| the zone box | KICAD-VERIFIED (10.0.x) | `H-K-ZONE-BOX` |
| copper dropped outside a new outline | KICAD-VERIFIED (9.0.x, 10.0.x) for the fact it rests on | `H-K-OUTLINE-OUTSIDE` |
| a copper count change | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-LAYER-CHANGE` |
| paths, helpers, digests, recognition, merges | mechanical | unit tests; the rebuild oracle of "Outline and layer changes pass the oracle" |
| arcs and holes in an Altium build | mechanical on c0085's records; the Altium build keeps its level | unit tests |

`lens.preserve.EVIDENCE` stays `INFERRED`, as its requirement states.

## Risks / Trade-offs

- **Routed copper dropped.** An outline change drops copper that no longer fits, and a count change drops the copper of removed layers. Mitigation: `--dry-run` lists the counts and nets in `issues` before anything is written, the mutation protocol keeps `.bak` files, and `route` closes what reopens.
- **An edited outline the user wanted replaced.** It wins, with `layout.outline-kept`, whose hint names the lock.
- **Old boards.** Edges with position uuids are re-signed when they equal the script's outline; when they differ, nothing tells whether KiCad edited them, so they count as edited. The first rebuild after the upgrade rewrites edge uuids once.
- **One verdict for both majors.** A cut-out that 9.0.9 accepts is refused for target 9. KiCad 10 would call that board malformed.
- **Rounded points.** A rotated slot or a rounded corner is exact to 0.5 nm per coordinate; the arc is the one through the three stored points, as in KiCad.
- **Polygonised edges.** The ring check and the copper rule judge arcs within `DEFAULT_TOL`, 5 µm, KiCad's default error; copper within 5 µm of a curved edge may be judged differently from KiCad.
- **Holes are locked by default,** unlike `place()`. A hole moved in KiCad snaps back with `layout.place-forced`; `locked=False` gives the board the last word.
- **The zone box** misses an arc that bulges beyond its vertices and mid, which only a hand-written `arc_to` can make; `kicad.outline.zone-short` names it.
- **Edge items inside footprints stay** when the outline is replaced. The new root outline and an old footprint cut-out may then form an outline KiCad calls malformed; the message names the footprints, and `check` reports what KiCad's DRC finds.
- **A plated hole in an Altium build** loses its pad and its pin, with one info. A design that needs the grounded hole in Altium places a footprint of its own.

## Migration Plan

- Additive for scripts: `board(width, height)` writes the same bytes, apart from the edge uuids (next item).
- The edge uuids of every built board change once, on the first build after this change: a fresh build writes signed uuids, and a rebuild re-signs edges that an older Fenolite wrote and nobody changed.
- Rebuilds that stopped with `layout.copper-mismatch` for a count change, or kept an old outline with `layout.outline-kept`, now apply the script and may drop copper. `CHANGELOG.md` says so, with `--dry-run` as the way to see it first.
- `board.json` files without arcs keep their bytes; with arcs they gain `arcs`. Release 0.2.x cannot read a model document that carries `arcs`: its reader refuses an unknown key.
- If c0096 reached `dev` first, scripts written against its `Design.hole(key, …)` change to `Design.hole(ref, …, drill=…)`; no release carried the old call.
- Rollback: the parts share the model field only; reverting the merges restores the refusals.

## Budget (6.75 days)

| part | days |
|---|---|
| registers, probes recorded (eight rows, benches of measurements 1 to 7) | 0.75 |
| model `OutlineArc`, schema, `board_outline`, `outline_box`, `board_boundary`, staging and off-board boxes | 0.5 |
| script paths, `cutout`, `shape`, `to_model`, the zone box | 1.0 |
| writer arcs and signed uuids, `check_outline`, the build step, the Altium refusal of arcs | 0.75 |
| holes: unnumbered pads, `hole()`, generated definitions, oracle | 1.0 |
| holes in an Altium build; the names of c0096 removed when it is on `dev` | 0.25 |
| outline merge: recognition, lock, copper dropped, zones, oracle | 1.0 |
| layer merge: rows, items, pads, stack-up, oracle | 0.75 |
| documentation and closing | 0.75 |

Cut order: (1) plated and slotted holes, keeping round non-plated ones; (2) `shape.slot` at an angle, keeping horizontal and vertical slots; (3) the outline lock, after which an edited outline always wins; (4) re-signing old edges, after which they count as edited. Never cut: arcs and cut-outs with the ring check, round non-plated holes, the outline change on an unedited board with its copper rule, and the count change with the stack-up reset.

## Open Questions

- **Should holes be locked by default?** Default: yes (Decision 7); `place()` stays unlocked by default.
- **Should a count change that drops routed copper need a flag?** Default: no; a warning, as `layout.net-removed` drops the copper of a removed net.
- **Should `board(..., locked=True)` also set KiCad's lock on the edge items?** Default: no, until the token of a locked drawing is measured on both majors.
- **Should copper within the edge clearance of a new outline also be dropped?** Default: no; KiCad's DRC reports it (`copper_edge_clearance`), and it may be one small move from fitting.
- **Should the courtyard of a hole default to more than the hole?** Default: no; screw heads and washers are the user's values (plan D6).
- **Should zone and rule-area outlines take arcs?** Default: not in this change; `OutlineArc` can serve them when a script needs one.
