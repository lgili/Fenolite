## Context

- **Request.** The maintainer's decisions of 2026-10-16: (1) target Altium with the **Embedded Board Array**, the native panel object that references the board's `.PcbDoc`, not a flattened copy; whether KiCad also gets a panel is for this design (open question 1); (2) all three separations: V-score, tabs with mouse bites, and a frame of rails with fiducials and tooling holes; (3) release 0.5.0.
- **What exists** (`release-0.5.0` at `03440f4`, read on 2026-10-16).
  - c0118 (archived) placed fiducials, test points and tooling holes on a board (`design.fiducial`, `test_point`, `tooling_hole`; generated footprints in `Fenolite_Assembly`) and left panels out: "the board's fiducials and tooling holes are its own, not a panel's". It measured that `kicad-cli` 10.0.6 has no panel command and that KiCad's library holds 31 panelisation footprints, and named three options (none, an own step of more than 10 design-days, an external tool). The maintainer now takes the own step.
  - c0167 (in 0.5.0): inner rings of `Edge.Cuts`, `geometry.rings.merge_rings` (union through the `geo` extra), `edge_outline`; c0169 (in 0.5.0): copper to every edge ring. A panel's routed gaps are inner rings of the frame's ring, so the KiCad side stands on them.
  - Altium: "PCB document output" refuses an outline with cut-outs or arcs; c0168 (after 0.5.0) writes cut-out regions behind its gate. The Altium panel needs neither: its board shape is the frame's rectangle, and its routed gaps are a route tool path on a mechanical layer (S-0791). Free non-plated round pads are written since c0085 (`pcbrecords.hole_record`); every document holds an empty `EmbeddedBoards6` storage (`pcbdoc.py:112`, `pcb-document.md`, "Storages").
  - Nothing in `src/` knows a panel; `docs/` names none.
- **Public facts** (read 2026-10-16; registered by this proposal as S-0790 to S-0802, S-0002 and S-0125 read again; rows in `docs/formats/altium/pcb-document.md` "Embedded board arrays", `docs/formats/kicad/panel.md` and `gerber.md` "Panels").
  - *Known about the Embedded Board Array* (S-0790, S-0791, S-0792): its properties (reference point X/Y, rotation counter-clockwise in degrees, PCB Document path, Column and Row Count, Mirrored, Column and Row Spacing = pitch, Column and Row Margin, Link Location to Embedded Board Origin, off by default = from the bottom-left of the board's objects; layer and parameter visibility); the panel is a separate document holding only arrays and tooling-hole free pads; tabs are a route tool path on a mechanical layer of type Route Tool Path; mouse bites are rows of small unplated pads; a mechanical layer can be of type V Cut; the panel's stack is synchronised to the board's; Gerber, NC Drill and ODB++ come from the panel.
  - *Unknown*: the records. KiCad's importer page (S-0002) lists `EmbeddedBoards6` as "Embedded board panels (not imported)" and says no more; no registered page gives its keys, how the document path is stored (absolute or relative), how margins relate to spacing in the file, or where a mechanical layer's type is stored. These are measured by observation (Part Q, Decision 8).
  - *Fabricators* (S-0793 to S-0801): V-score for rectangular boards, straight over the whole panel, boards touching; copper 0.45 mm (one) or 0.4 mm, 1.0 recommended (another) from a score; score lines 5 mm (one) or 2 mm (another) apart; 0.8 or 0.6 mm minimum thickness; mouse bites of 5 to 8 holes of 0.6 mm, 0.35 to 0.4 mm apart, on both sides of a board-to-board tab and not on the rail's side, on the centre line or a third into the board, tangent being the least intrusive; routed gaps 1.6 to 2 mm (1.2 minimum) or 2 mm; rails at least 5 mm; fiducials of 1 mm with a 2 mm opening, three in an L on the rails, centre at least 3.85 mm from the panel edge; tooling holes of 3.00 mm or 0.125 in; panel sizes from 50 × 50 to 250 × 350 mm or more.
  - *Gerber* (S-0125): file function `Vcut`, `.Part` `Array`, `MechanicalDrill` `Tooling` and `BreakOut`, `FiducialPad` `Panel`. Whether `kicad-cli` gives any of them for a panel is measured (`H-K-PANEL-GERBER`), not assumed.
- **Constraint.** Facts come from these pages, from `kicad-cli` run as an oracle, and from files the maintainer saves in his licensed Altium Designer 26.5 from inputs authored for Fenolite (LEGAL.md, A.1: files the contributor created). No vendor software is decompiled; no panelisation tool's code, preset or default is read (KiKit, S-0802, is prior art only, as c0118 named it); nothing from an employer or a private project.

## Goals / Non-Goals

**Goals**
- One panel script gives a KiCad panel board and an Altium panel document of the same layout, checked against cited fabrication rules before anything is written.
- The Altium panel is the native Embedded Board Array once Part Q has shown the written records; nothing is claimed for Altium before.

**Non-Goals**
- Everything under "Non-goals" in the proposal, and assembly outputs of a panel (`pnp`, `bom`, `testpoints` stay per board).

## Decisions

1. **A panel is its own script and its own command.** A panel script binds `panel = Panel("blink_panel", board="../blink/out/blink.kicad_pcb")`; `fenolite panel PANEL.py --out DIR --target {9,10,altium}` writes it. The board is a built board file (routed and filled), never the design script: a panel repeats copper that only the board holds. The suffix of `board=` names its backend: a `.kicad_pcb` for every target; a `.PcbDoc` (from `build --target altium`) for `--target altium` only.
   - Rejected: a `build` option. A build writes a board from a script; a panel is made from a finished board, often by someone else, and has its own checks and outputs.
2. **The panel model.** `model.panel.Panel(header, name, source, array, frame, separations, tabs, vscore, fiducials, tooling_holes, limits)`, frozen, canonical JSON `panel.json` (schema `schemas/fenolite.model.v0/panel.json`), lengths `Nm`, angles `Udeg`:
   - `source`: `PanelSource(path, sha256, backend)`; `array`: `PanelArray(rows, cols, gap_x, gap_y, rotation, mirrored=False)`, rotation a multiple of 90 000 000 µdeg; `frame`: `PanelFrame(top, bottom, left, right)` rail widths (0 = no rail); `separations`: one `Separation(between, method)` per edge set, `between` in `columns`, `rows`, `rails`, `method` in `vscore`, `tabs`.
   - `tabs`: `TabSpec(width, pitch, drill, hole_gap, holes, inset)`; `vscore`: `VScoreSpec(layer_name, line_width, clearance)`; `fiducials`: `PanelFiducial(ref, at, side, copper, mask)`; `tooling_holes`: `PanelHole(ref, at, drill)`; `limits`: `PanelLimits` (Decision 6), each field optional, `None` = the default.
   - `panel.layout(panel, board) -> PanelLayout` is pure and integer: `copies` (`PanelCopy(row, col, k, origin, rotation)`), `size`, `frame_ring`, `gap_rings`, `tab_items` (`Tab(id, edge, center, axis, holes)`), `score_lines` (`ScoreLine(id, axis, at, start, end)`), `fiducials`, `tooling_holes`. The board's box is the box of `edge_outline(board)`; a board without a closed outline is `panel.board-outline`.
   - Ids: `derived_id(prefix, "panel", key)` from new key rows: `pnl` `panel`, `pcy` `copy:<row>.<col>`, `ptb` `tab:<edge>:<k>`, `pvs` `vscore:<x|y>:<k>`, `pfd` `fiducial:<ref>`, `ptl` `tooling:<ref>`; an item of copy k keeps the source id inside its key, `derived_id(<its prefix>, "panel", "<copy key>/<source id>")`. Rows count from 1 at the top, columns from 1 at the left, `k = (row − 1) · cols + col`.
3. **The panel DSL** (`fenolite.dsl.panel`, re-exported names `Panel`): `grid(rows, cols, *, gap=None, gap_x=None, gap_y=None, rot=0, mirror=False)`; `fit(width, height, *, gap=None, rot=0)` with `rot="auto"`; `rails(*, top=mm(5), bottom=mm(5), left=0, right=0)`; `separate(method, *, between)`; `tabs(*, width=mm(5), pitch=mm(55), drill=mm(0.6), hole_gap=mm(0.4), holes=5, inset=0)`; `vscore(*, clearance=mm(0.45), layer="V-Score", line_width=mm(0.1))`; `fiducial(ref, x, y, *, copper=mm(1), mask=mm(2), side="top")` and `fiducials(*, copper, mask, sides=("top",))`; `tooling_hole(ref, x, y, *, drill=mm(3))` and `tooling_holes(*, drill=mm(3))`. Coordinates are panel-relative (origin top-left, Y down, as `board()`). Every bad value raises `DslError` at the call, naming the argument; a script that binds no `panel` is `FEN-3004`.
   - **Gaps.** A V-scored edge set has gap 0 (boards touch, S-0796, S-0798); `gap` is the routed gap of a tabbed set, 2 mm by default (S-0798). Between rails and boards the `rails` set's method decides: V-score touches, tabs leave the gap.
   - **The fit rule.** For usable width `U = W − left − right − 2·g_r` (g_r the rail gap when rails are tabbed and present) and box width `b`: `cols = ⌊(U + g_x) / (b + g_x)⌋`, rows likewise; `rot="auto"` takes the quarter turn that gives more copies, 0° on a tie. Zero copies is `panel.no-fit` (error). The panel then has the size of what it holds; `result.panel.unused` gives the rest of the asked size (open question 4).
4. **Separation drawn per target.**
   - *Tabs.* Along each tabbed edge of length L, `n = max(1, ⌈L / pitch⌉)` tabs at `(i + ½)·L/n`, each `width` wide. A tab between two boards has a row of `holes` holes of `drill` at each board's edge, a tab to a rail one row at the board's edge (S-0795); hole centres `drill + hole_gap` apart, tangent to the board edge outside it (`inset` 0, S-0793), or reaching `inset` into the board (at most `drill / 3`, S-0795).
   - *V-score.* One straight line per scored boundary, from panel edge to panel edge (S-0794, S-0801).
   - *KiCad.* Frame ring and gap rings on `Edge.Cuts`: the gap rings are the parts of the frame's inside not covered by rails, copies or tabs, united by c0167's `merge_rings` (the `geo` extra; without it `panel.needs-geo`, error); each copy's own cut-outs and slots stay inner rings. Score lines are `gr_line` items `line_width` wide on a user layer whose user name is `layer_name` (`H-K-BOARD-USERLAYERS`). Each tab's holes are one generated footprint `Fenolite_Panel:MouseBites_<n>x<d>mm_P<p>mm` of unnumbered `np_thru_hole` pads (`board_only`, `exclude_from_pos_files`, `exclude_from_bom`, locked), ref `MB<k>`. Fiducials and tooling holes are c0118's generated footprints, refs `PFID<k>` and `PTH<k>`.
   - *Altium.* The board shape is the frame's rectangle. Gap rings are tracks and arcs on a mechanical layer named `Route Tool Path`, score lines tracks on a mechanical layer named `V-Cut` (layer types per Decision 9); mouse-bite and tooling holes are free round non-plated pads (`hole_record`, S-0791); fiducials free round pads on the Top (and Bottom) Layer, copper `copper`, mask by the rule (open question 6).
5. **Copies.** KiCad and the flattened Altium document hold every item of the source board, moved by an exact integer translation and a quarter turn (no rounding), uuids derived from the copy ids, each net renamed `B<k>/<name>` (KiCad DRC would join unrenamed nets across copies, `H-K-PANEL-NETS`), designators kept (open question 3). Zones keep their fills, moved. Edges of each copy's outline are dropped: the panel's rings replace them. A renamed net equal to another is `panel.net-collision` (error).
6. **Checks and limits.** `panel.checks.check_panel(panel, layout, board) -> tuple[Issue, ...]` runs before any write; an error finding plans no write (exit 5). Defaults live in `panel.limits.DEFAULTS`, each naming its row of `panel.md` (`H-G-PANEL-LIMITS`); `limits=` of `Panel` overrides any of them.

   | code | severity | rule (default) | source |
   |---|---|---|---|
   | `panel.vscore-copper` | error | copper of any layer nearer than 0.45 mm to a score line | S-0799 (S-0794: 0.4) |
   | `panel.vscore-shape` | error | a board edge on a score line is not straight over the board's whole side, or a scored set has a gap | S-0791, S-0796, S-0801 |
   | `panel.vscore-spacing` | error, warning | parallel score lines nearer than 2 mm (error) or 5 mm (warning) | S-0796, S-0801 |
   | `panel.vscore-thickness` | error, warning, info | board thickness below 0.6 mm (error), below 0.8 mm (warning), unknown (info) | S-0794, S-0801 |
   | `panel.tab-copper` | error | copper nearer than 0.25 mm (outer) or 0.40 mm (inner) to a mouse-bite hole | S-0799 |
   | `panel.gap` | error, warning | routed gap below 1.2 mm (error) or 2.0 mm (warning) | S-0795, S-0798 |
   | `panel.tab-count` | warning | fewer than 5 holes per row, or a board held by fewer than two tabs | S-0795 |
   | `panel.tab-spacing` | warning | tabs more than 60 mm apart along an edge | S-0795 |
   | `panel.fiducial-place` | warning | a fiducial off the rails, its centre nearer than 3.85 mm to the panel edge, or fewer than three per assembled side | S-0794, S-0796, S-0797 |
   | `panel.tooling-place` | warning | a tooling hole not wholly on a rail | S-0800 |
   | `panel.size` | warning | a side under 50 mm or above 250 mm, or a scored panel under 70 × 70 mm | S-0795, S-0800, S-0794 |
   | `panel.board-outline`, `panel.no-fit`, `panel.net-collision`, `panel.needs-geo`, `panel.source-unreachable` | error | the board has no closed outline; nothing fits; a renamed net collides; tabs without the `geo` extra; no relative path from the panel to the referenced document | — |

   `fenolite check` of a written KiCad panel runs the board stages as for any board and these checks from `<panel>.panel.json` beside it.
7. **The command** (`cli-contract`, "Panel command"). `fenolite panel PANEL.py --out DIR --target {9,10,altium} [--altium-panel {auto,embedded,flat}] [--dry-run | --confirm --plan ID] [--seed] [--timestamp]`. KiCad: `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.panel.json`, `lib/Fenolite_Panel.pretty/*.kicad_mod`, the c0118 footprints used, `fp-lib-table`. Altium: `<name>.PcbDoc`, `<name>.PrjPcb` (the panel document alone), `<name>.panel.json`. `result.panel`: `rows`, `cols`, `copies`, `size`, `unused`, `separations`, `form` (`flat` or `embedded`), `written` per kind. Exit codes: 0; 2 for bad arguments (`--altium-panel` with a KiCad target, a `.PcbDoc` source for a KiCad target); 3 `FEN-3001` (no board file), `FEN-3004` (the script raised, or binds no `panel`), `FEN-3005` (the board's geometry); 4 `FEN-4001`, `FEN-4002`; 5 `FEN-5001` (error findings `panel.*`); 7 `FEN-7001` for `--altium-panel embedded` while the gate is off or with a `.kicad_pcb` source, and for `mirror=True` on a KiCad target. No new `FEN-` code; a written output edited since is refused as `build` refuses it.
   - `--altium-panel auto` (default): `embedded` when `EMBEDDED_ARRAYS` is true and the source is a `.PcbDoc`, otherwise `flat` with one `altium.panel-flattened` info naming the reason.
8. **The Embedded Board Array: measured, then written behind a gate.**
   - *Measurement by observation* (Part Q, phase A). Fenolite builds the authored fixture board `tests/data/panels/board.py` for Altium (`board.PcbDoc`, a two-layer 40 × 30 mm rectangle, authored for Fenolite). The maintainer, in his licensed Altium Designer 26.5, makes panels of it with the menu steps of the kit and saves one document per variant, each differing from the baseline by one property (Q1, Q2), plus the layer-type and two-array variants (Q3, Q4). Fenolite reads the saved files with its own compound reader: `fenolite diff A B --view records` between the baseline and each variant names the streams that changed, and a dump of an opaque stream (such as `EmbeddedBoards6`) through `backends/altium/read` ties each property to its bytes. Files pass `fenolite kit verify`'s path scan first; native files stay outside the repository; only measured facts, digests and sizes are committed, rows labelled `INFERRED` with `H-A-PANEL-RECORD` until Q7.
   - *Writer.* `pcbrecords.embedded_board_array(...)` from those rows; `pcbdoc.EMBEDDED_ARRAYS: Final = False`. The referenced document is named by its path relative to the panel document; no absolute path is ever written.
   - *Stop rules.* The array part stops, and the flattened panel is what ships, when any holds: (a) the saved variants do not tie every property of S-0790 that Fenolite sets (location, counts, spacing, rotation, document path) to a field; (b) a field depends on data Fenolite cannot compute (a digest or copy of the referenced board, a machine or user identifier, a licence field); (c) only an absolute path is accepted; (d) Q7 fails after one correction round; (e) the phase passes its 2.25 design-days. The stop is written under the task, `H-A-PANEL-RECORD` keeps its level, and `--altium-panel embedded` keeps exit 7.
   - *Gate.* `EMBEDDED_ARRAYS` is set by the maintainer's report of Q7, Q8 and Q9 only (`H-A-PANEL-KIT`), as c0168 gates its regions.
9. **Mechanical layer types.** Q3 measures where V Cut and Route Tool Path are stored. Until a written type is shown (Q8), the flattened and embedded documents name the layers `Route Tool Path` and `V-Cut` with no type: S-0792 says older versions find routing data by that name. Second item of the cut order.
10. **Exports.** `gerber_layers(design)` gives the board's user layer whose user name is the panel's score layer (`V-Score` by default), before `Edge.Cuts`, when the board has it; the plot's file function is what `kicad-cli` writes (`H-K-PANEL-GERBER`). The Altium panel's outputs are Altium's (Q9); `fenolite export` does not run Altium.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/panel.py`, `schemas/fenolite.model.v0/panel.json` | `Panel` and its parts |
| `src/fenolite/panel/layout.py`, `checks.py`, `limits.py`, `kicad.py`, `altium.py` | `layout`, `check_panel`, `DEFAULTS`, the KiCad board, the Altium lowering |
| `src/fenolite/dsl/panel.py`, `dsl/__init__.py` | `Panel` and its calls; the key rows |
| `src/fenolite/cli/cmd_panel.py`, `schemas/fenolite.panel.v0.json` | the command and its result |
| `src/fenolite/backends/altium/pcbrecords.py`, `pcbdoc.py` | `embedded_board_array`, `EMBEDDED_ARRAYS`, the two mechanical layers |
| `src/fenolite/exports/plan.py` | `gerber_layers` with the score layer |
| tests | `tests/unit/panel/` (layout, fit, checks, limits, ids), `tests/unit/dsl/test_panel.py`, `tests/unit/cli/test_panel_cmd.py`, `tests/kicad/panel/test_panel_board.py`, `tests/kicad/altium/test_panel_import.py`, `tests/unit/backends/altium/test_part_q.py`, `tests/data/panels/` (authored board and three panel scripts) |
| docs | `docs/panels.md` (new), `docs/dsl.md`, `docs/cli-contract.md`, `docs/altium.md`, `docs/exports.md`, `docs/evidence/altium-pcb.md` (Part Q), agent guide page `fabrication` |

## Sources registered by this change

Registered with the proposal in `docs/evidence/sources.md` (the highest id in use was S-0771; S-0740 to S-0759 are reserved for another branch and S-0772 onward for a parallel proposal, so this change starts at S-0790): S-0790 (Embedded Board Array properties), S-0791 (Board Panelization), S-0792 (mechanical layer types), S-0793 (Altium article on mouse bites and V-scores), S-0794 to S-0797 (JLCPCB: V-cut, mouse bites, panelization help, fiducials), S-0798 to S-0801 (Eurocircuits: customer panel basics, copper and the board edge, eC-panel, V-cut basics), S-0802 (KiKit, prior art only). S-0002 and S-0125 gain the reading of 2026-10-16.

## Hypotheses registered by this change

Registered with the proposal in `docs/hypotheses.md`, because the fact rows cite them.

| id | statement | settling test | criterion |
|---|---|---|---|
| `H-K-PANEL-LOAD` | The panel board loads in 9.0.9 and 10.0.6 with no `invalid_outline`, and its DRC gives each copy the source's findings only | `tests/kicad/panel/test_panel_board.py -k load` | probe `panel-load` `absent` |
| `H-K-PANEL-DRILL` | Mouse-bite and tooling holes reach the NPTH file at their places; no score line or gap reaches a drill file | `-k drill` | probe `panel-drill` `equal` |
| `H-K-PANEL-GERBER` | The score layer plots as one file of the score lines; its file function is recorded | `-k gerber` | probe `panel-gerber` recorded |
| `H-K-PANEL-NETS` | Renamed nets give no unconnected or shorting items between copies | `-k nets` | probe `panel-nets` `absent` |
| `H-G-PANEL-LIMITS` | Each default limit equals the cited figure | `tests/unit/panel/test_limits.py` | every default names its row |
| `H-A-PANEL-RECORD` | The array's records are those Q1 to Q4 measure, and a written one opens with the same array | kit request: Part Q, Q1 to Q4 and Q7 | each property tied to one field; Q7 as expected |
| `H-A-PANEL-LAYERKIND` | Where a mechanical layer's type is stored is what Q3 measures | kit request: Part Q, Q3 and Q8 | one storage found; Q8 as expected |
| `H-A-PANEL-FLAT` | KiCad 10.0.6 imports the flattened Altium panel at the KiCad panel's places within 10 nm | `tests/kicad/altium/test_panel_import.py` | probe `altium-panel-flat` `equal` |
| `H-A-PANEL-KIT` | Part Q cases Q7 to Q12 hold their expected outcomes | kit request: Part Q, Q7 to Q12 | one outcome per case |

## Part Q: the maintainer's kit (Altium Designer 26.5)

Built by task 2.3 into `~/fenolite-altium-checks/session-6/Q-panels/` (a `README.md` with these steps, `SHA256SUMS`); phase B files added by task 7.3. Coordinates in millimetres from the document origin. For each case send `as expected` or what differed in one sentence, the version (`AD <major>.<minor>`), the date and the SHA-256 of each file sent.

*Phase A, observation (`board/board.PrjPcb` with `board.PcbDoc`, built by Fenolite):*
1. **Q1** Add a new PCB `panel-a.PcbDoc` to `board.PrjPcb` (same folder). **Place » Embedded Board Array/Panelize**, pick `board.PcbDoc`, place it; in Properties set X 5, Y 5, Rotation 0, Column Count 2, Row Count 2, Column Spacing 42, Row Spacing 32, Mirrored off, Link Location off; choose "Synchronize Manually Later" if asked and note the dialog. Save. Expected: four boards with 2 mm gaps.
2. **Q2** From `panel-a`, **File » Save As** once per change, each made alone on a fresh copy of `panel-a`: `panel-cols4` (Column Count 4), `panel-rows3` (Row Count 3), `panel-spacing` (Column Spacing 45, Row Spacing 35), `panel-margin` (Column Margin 3, Row Margin 3; note whether the spacing fields change), `panel-rot90` (Rotation 90), `panel-mirror` (Mirrored on), `panel-link` (Link Location on), `panel-move` (X 12, Y 7). Expected: each saves; note any field that changed besides the one set.
3. **Q3** On `panel-a`, add two mechanical layers in the View Configuration or Layer Stack Manager, set one's Layer Type to V Cut and the other's to Route Tool Path, draw one track on each, save as `panel-layers`. Expected: saves; note the layer numbers and names Altium gives.
4. **Q4** On `panel-a`, place a second array of the same board at X 100, Y 5 (1 × 1), save as `panel-two`. Expected: two arrays.
5. **Q5** On `panel-a`, **File » Fabrication Outputs » Gerber Files** and **NC Drill Files** with defaults. Expected: four copies in the copper and drill outputs; send the list of files written (names only).
6. **Q6** Close Altium, zip the folder without the `History` and `Project Outputs` folders, and send it. Fenolite runs `fenolite kit verify`'s path scan before anything is read.

*Phase B, confirmation (files written by Fenolite after task 7.2; gate forced on for the kit only):*
7. **Q7** Open `written/panel.PrjPcb` and `panel.PcbDoc`. Expected: no repair message; one array of `board.PcbDoc`, 2 × 2, the properties of `expected.md`.
8. **Q8** Move one track of `board.PcbDoc`, save, return to `panel.PcbDoc` and refresh (or reopen). Expected: all four copies show the move. Then select the two mechanical layers. Expected: types V Cut and Route Tool Path when task 7.2 writes them, otherwise unassigned with the names `V-Cut` and `Route Tool Path`.
9. **Q9** Gerber Files and NC Drill Files of `written/panel.PcbDoc` with defaults. Expected: four copies; the mouse-bite and tooling holes in the non-plated drill file; the `V-Cut` layer in its own Gerber file.
10. **Q10** **Tools » Design Rule Check** on `written/panel.PcbDoc`. Expected: report every message; none is expected to block the outputs.
11. **Q11** Open `flat/panel.PcbDoc` (the flattened panel), run Q9 and Q10 on it. Expected: opens without repair; the same holes and layers; note any message about repeated designators.
12. **Q12** Save `written/panel.PcbDoc` as `panel-saved.PcbDoc` and run `FENOLITE_ALTIUM_Q12=<that file> uv run pytest tests/unit/backends/altium/test_part_q.py -k q12`. Expected: passes (the same array read back).

Q1 to Q4 settle `H-A-PANEL-RECORD`'s measurement and Q3 `H-A-PANEL-LAYERKIND`'s; Q7 to Q12 settle `H-A-PANEL-KIT`; Q7, Q8 and Q9 decide the gate.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| layout, fit, ids, checks, limits | mechanical | unit tests; `H-G-PANEL-LIMITS` |
| KiCad panel board | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-PANEL-LOAD`, `-DRILL`, `-NETS`; `-GERBER` recorded |
| flattened Altium panel | ORACLE-VERIFIED(kicad-cli) (10.0.6) | `H-A-PANEL-FLAT` |
| array records written, gate off | INFERRED | Part Q phase A rows, Fenolite's read-back |
| array written by default (`EMBEDDED_ARRAYS = True`) | ALTIUM-VERIFIED(kit) | `H-A-PANEL-KIT` Q7 to Q9 |

## Risks / Trade-offs

- **Fabricators disagree.** Defaults take the stricter published figure where one exists, name it, and are all overridable; the docs say to confirm with the fabricator.
- **The array may not be writable.** The stop rules end the attempt early; the flattened panel is a complete deliverable on its own, and an Altium user can still place the array by hand on it.
- **Duplicate designators** on a flattened panel may draw messages in Altium (Q11); KiCad's DRC is measured.
- **Panel size grows with copies.** Copying a dense board 8 times makes a large board file; the writer's throughput is measured on the fixtures.
- **Release 0.5.0.** c0171 owns the release record and its guard keeps `[Unreleased]` empty (as c0168 noted); the maintainer decides how this change's lines enter `[0.5.0]` (open question 7).

## Migration Plan

Additive: a new command, module, model document and schema; no existing output changes, except that `gerber_layers` lists a user layer named `V-Score` for a board that has one (none of the committed boards does).

## Budget (13 design-days)

| phase | content | days | depends on |
|---|---|---|---|
| P1 | facts and register (done with the proposal), census of `EmbeddedBoards6` in the public documents, Part Q phase A built | 0.75 | — |
| P2 | model, schema, ids, DSL, layout and fit | 2.5 | P1 |
| P3 | checks and limits | 1.5 | P2 |
| P4 | KiCad panel board and its probes | 2.5 | P2 |
| P5 | command, exports, agent guide | 1.25 | P3, P4 |
| P6 | flattened Altium panel and its oracle | 1.25 | P4 |
| P7 | array measurement, writer behind the gate, phase B kit, read-back | 2.25 | P1 (phase A), P6 |
| P8 | docs and closing | 1.0 | all |

Cut order: (1) the array writer (P7 after its measurement; the stop rules of Decision 8; the flattened panel ships); (2) mechanical layer types (named layers instead); (3) mixed separations (one method for every edge set); (4) `rot="auto"` of `fit`; (5) quarter turns (0° only). Never cut: the model and `grid`, the KiCad panel with its probes, the V-score and tab copper checks, the gate, the dry run and the confirm, the flattened Altium panel.

## Open questions

All decided by the maintainer on 2026-10-16: every recommended answer is accepted.

1. **Does KiCad get a panel too?** Decided 2026-10-16: yes. A flattened KiCad panel board is cheap (it stands on c0167's rings and c0118's footprints), `kicad-cli` verifies it on both majors, and it gives the flattened Altium panel its model and its oracle.
2. **One panel script per board, or panels inside the design script?** Decided 2026-10-16: a script of its own that names a built board (Decision 1).
3. **Should copies keep their designators?** Decided 2026-10-16: yes; nets are renamed `B<k>/…`, designators stay, so each copy reads like the board it is. If Q11 or the KiCad DRC objects, a suffix `_<k>` becomes an option.
4. **Does `fit()` make the panel the asked size or the size of what fits?** Decided 2026-10-16: the size of what fits; `result.panel.unused` reports the rest, and `rails()` can take it up explicitly.
5. **Mouse-bite holes tangent to the edge or reaching into the board?** Decided 2026-10-16: tangent by default (`inset=0`, the least intrusive, S-0793), with `inset` up to a third of the drill for fabricators that ask for it (S-0795).
6. **Panel fiducials in Altium as free pads?** Decided 2026-10-16: yes, free round pads with the mask from the rule, as c0118's footprint cannot be written to a `.PcbLib`; Q9 shows whether they reach the outputs. The page S-0791 names only tooling holes as acceptable free pads, so the docs say so.
7. **How does this change enter 0.5.0?** Decided 2026-10-16: release 0.5.0 is **held** until the native Embedded Board Array passes the maintainer's kit ("hold 0.5.0 until it closes"): Q7, Q8 and Q9 of Part Q decide `EMBEDDED_ARRAYS`, and the release waits on them. The stop rules of Decision 8 still apply: if the array cannot be established, the flattened Altium panel is what ships, and the hold ends with that verdict. The release change c0171 adds the row and moves the changelog lines into `[0.5.0]`, since its guard keeps `[Unreleased]` empty.
8. **Vendor-named limit presets** (`limits="jlcpcb"`)? Decided 2026-10-16: no; the defaults cite their sources, `limits=` takes the user's fabricator's figures, and a preset would age silently.
