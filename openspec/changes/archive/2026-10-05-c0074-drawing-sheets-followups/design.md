## Context

- **Scope.** Plan, v0.2b deliverables: "import of the user's `.kicad_wks`". c0068's design, Decision 13, moved to v0.2b: export presets, the outline snapping tolerance with the edge items of footprints, and stitching that avoids zones and the board edge (the rule kinds went to c0071). The roadmap lists them under v0.2b.
- **What exists.**
  - Model: `Board.sheet: SheetFrameRef(paper, portrait, width, height, drawing_sheet)` and `Board.title_block: TitleBlock(title, date, revision, organization, doc_id, responsible, approver, params)` (c0012).
  - `pro.apply_sheet_keys` sets `pcbnew.page_layout_descr_file` from `drawing_sheet` and `text_variables` from `params`; the schematic key "MUST NOT be touched" (`kicad-file-backend`, "Projects carry the drawing sheet and text variables"). Facts: the board key, project-relative or `${KIPRJMOD}/…`, gives the frame of `pcb export svg` (`H-K-PRO-WKS`); a missing file falls back silently to the default frame (`H-K-WKS-FALLBACK`).
  - `wks.read_drawing_sheet` and `wks.write_drawing_sheet`; the `*.sheet.toml` pipeline `SheetSpec` → `build_sheet` → `DrawingSheet`; the header `(version 20231118)` is the same for majors 8, 9 and 10; legacy roots `page_layout` and `drawing_sheet` are read.
  - The DSL has no call for the sheet or the title block.
  - `exports.plan.KINDS` with fixed options per kind; `helpmatrix` records commands, and options only for `pcb drc`.
  - `outline.board_outline` chains root edge graphics by exact endpoint equality (`H-G-EDGE-EXACT`) and marks boards whose only edge items are inside footprints (`footprint-edges-only`); `frame.py` already parses footprint children. Census of 2026-10-03/04: 18 of the 21 native demos close; `kicad-demo-10-0-6-pcb-01` has two loose endpoints 33 nm apart; `-14` and `-16` have gaps of 2.995 mm and 9.24 mm and 5 and 9 edge items inside footprints; KiCad's `has_outline` is true for all 21.
  - Stitching: "Zones, rule areas and the board edge MUST NOT count" (`manual-copper`, "Stitching vias"); `Keepout(outline, layers, no_tracks, no_vias, …)`.
- **Measured on 2026-10-05** (scratch probes, `kicad-cli` 9.0.9 in the pinned image and 10.0.6 locally, identical unless said):
  - **Schematic frame.** A two-sheet project whose `.kicad_pro` holds `schematic.page_layout_descr_file` = `probe.kicad_wks` or `${KIPRJMOD}/probe.kicad_wks`: `sch export svg` draws the probe sheet's text on both sheets. With the key absent, or with only `pcbnew.page_layout_descr_file`, neither sheet shows it.
  - **Outline chaining.** A 60 × 40 mm rectangle of four `gr_line` items whose last line stops short of the first corner: no `invalid_outline` for gaps of 0.5, 1, 2, 5, 8 and 9.999 µm; `invalid_outline` for 10.001, 10.5, 11, 11.5, 12, 15, 20 and 50 µm. At exactly 10 µm, 10.0.6 reports nothing and 9.0.9 reports `invalid_outline` (four entries on 9.0.9, one on 10.0.6).
  - **Export options**, from `--help`: `pcb export gerbers` has `--layers`, `--no-protel-ext`, `--no-x2`, `--no-netlist`, `--disable-aperture-macros`, `--precision`, `--subtract-soldermask`, `--use-drill-file-origin`, `--include-border-title`, `--exclude-refdes` and `--exclude-value` on both; `--check-zones` and `--variant` on 10 only; `--plot-invisible-text` on 9 only. `pcb export drill` has `--format`, `--excellon-units`, `--excellon-separate-th`, `--drill-origin`, `--excellon-zeros-format`, `--excellon-oval-format`, `--excellon-mirror-y`, `--excellon-min-header`, `--generate-map`, `--map-format` and `--gerber-precision` on both; `--generate-tenting` on 10 only. `pcb export pos` has `--format`, `--units`, `--side`, `--exclude-dnp`, `--exclude-fp-th`, `--smd-only`, `--use-drill-file-origin` and `--bottom-negate-x` on both; `--variant` on 10 only.
- **Constraints.** Stdlib only, integers only, no shipped presets or values, read-only on the user's source files.

## Goals / Non-Goals

**Goals:**
- A script names its frame and title block once, and both the board and the schematic show them.
- A user's fab options live in one file of theirs, applied the same way on both majors.
- `board_outline` closes what KiCad closes, and stitch vias never land where DRC forbids them.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Two DSL calls.** `d.sheet(paper="A4", *, portrait=False, width=None, height=None, drawing_sheet=None)` and `d.title_block(*, title="", date="", revision="", organization="", doc_id="", responsible="", approver="", variables={})`, each at most once, with the model's names.
   - `drawing_sheet` is a path relative to the script's folder, ending in `.kicad_wks` or `.sheet.toml`; any other ending raises `DslError`. The model's `SheetFrameRef.drawing_sheet` is the written name `<name>.kicad_wks`, never the source path, so the model holds no path of the user's machine.
   - `variables` become `TitleBlock.params`, and so the project's text variables; a reserved KiCad name is refused by the writer, as today.
   - Rejected: keywords on `board()` (it already carries the outline and the copper; the sheet is presentation); one call for both (the title block is also the schematic's).

2. **The sheet in the build.** `cmd_build` reads the source: a `.kicad_wks` through `wks.read_drawing_sheet` (its infos reported), a `*.sheet.toml` through `SheetSpec` and `build_sheet`. `build_design` writes the result with `wks.write_drawing_sheet` for the target as `<name>.kicad_wks`, an output of the build like the others, recorded in `.fenolite/build.json` and under "Edited outputs are not overwritten". The writer's errors stop the build with its codes.
   - A user's file is re-written, not copied: the root becomes `kicad_wks`, the header that of the target, and an uninventoried token is refused, so the output loads on the target major.
   - A missing source file is an input error (`FEN-3001`), because KiCad would silently fall back to its default frame (`H-K-WKS-FALLBACK`).

3. **The schematic key.** When the design has a drawing sheet and the build writes a schematic (c0061), `apply_sheet_keys` also sets `schematic.page_layout_descr_file` to the same name (`H-K-PRO-WKS-SCH`). Without a schematic the key stays untouched, as today.

4. **Export presets.** `fenolite export … --preset FILE` reads a TOML file of the user's (`schema = "fenolite.export-preset.v0"`), with the tables `gerbers`, `drill` and `pos`, each key mapped to one flag that both majors have:

   | table | key | values | flag |
   |---|---|---|---|
   | `gerbers` | `layers` | canonical layer names | `--layers` |
   | | `protel_extensions` | bool (default false) | `--no-protel-ext` when false |
   | | `x2`, `netlist_attributes`, `aperture_macros` | bool (default true) | `--no-x2`, `--no-netlist`, `--disable-aperture-macros` when false |
   | | `precision` | 5 or 6 | `--precision` |
   | | `subtract_soldermask`, `use_drill_file_origin`, `include_border_title`, `exclude_refdes`, `exclude_value` | bool (default false) | the flag of the same name when true |
   | `drill` | `format` | `excellon`, `gerber` | `--format` |
   | | `units` | `mm`, `in` | `--excellon-units` |
   | | `separate_th`, `mirror_y`, `minimal_header` | bool | `--excellon-separate-th`, `--excellon-mirror-y`, `--excellon-min-header` |
   | | `origin` | `absolute`, `plot` | `--drill-origin` |
   | | `zeros` | `decimal`, `suppressleading`, `suppresstrailing`, `keep` | `--excellon-zeros-format` |
   | | `oval_format` | `route`, `alternate` | `--excellon-oval-format` |
   | | `map` | `none`, `pdf`, `gerberx2`, `ps`, `dxf`, `svg` | `--generate-map --map-format` |
   | | `gerber_precision` | 5 or 6 | `--gerber-precision` (with `format = "gerber"`) |
   | `pos` | `format` | `csv`, `ascii`, `gerber` | `--format` |
   | | `units` | `mm`, `in` | `--units` |
   | | `side` | `front`, `back`, `both` | `--side` |
   | | `exclude_dnp`, `exclude_fp_th`, `smd_only`, `use_drill_file_origin`, `bottom_negate_x` | bool (default false) | the flag of the same name when true |

   - A key that is not given takes c0024's fixed value, so a preset holding only the defaults, and no preset at all, run the same arguments.
   - The enumerated values are those the probe records from both majors' help (`H-K-EXPORT-OPTIONS`); a value accepted by only one major is not offered.
   - `--check-zones` and `--board-plot-params` stay forbidden; 10-only options (`--variant`, `--generate-tenting`) are not offered.
   - The placement file is named `pos/<stem>-pos.csv`, `.pos` or `.gbr` by its format.
   - An unknown table, key or value, or a wrong schema, is an input error (exit 3, `FEN-3004`) naming the table and key, before any run.
   - Rejected: shipping presets for known fabs (clean-room, plan D6); passing free flags through (no checking, and a flag that one major lacks would fail at run time).

5. **Outline chaining.** `board_outline` joins edge endpoints closer than `outline.CHAIN_GAP` = 10 000 nm (squared distance below its square, exact), merging each group of endpoints into its smallest point before `assemble_rings`. A group holding more than two piece ends stays a `branching-contour`.
   - Strictly below 10 µm agrees with both majors. At exactly 10 µm, 10.0.6 closes and 9.0.9 does not; Fenolite then says "open", the safe answer for 9.0 and a false alarm for 10.0 only at that exact value (`H-K-OUTLINE-CHAIN`).
   - `BoardOutline.joined` counts the groups that were merged; `exact` stays about arcs.
   - Rejected: per-major tolerances (one board, two answers depending on the target, for a 1 nm boundary).

6. **Footprint edge items.** `frame.footprint_edges(board, layers)` gives each `fp_line`, `fp_arc`, `fp_circle`, `fp_rect` and `fp_poly` of a footprint on an edge layer as a board-frame graphic, through the footprint's placement (position, rotation, side). They are chained with the root graphics; a closed footprint circle or polygon is a ring by itself, a cut-out of the board (`H-K-OUTLINE-FPEDGE`). The problem `footprint-edges-only` disappears.

7. **Stitching.** A candidate is also dropped when its via disc meets a `Keepout` with `no_vias` on any copper layer (a through via crosses them all), or comes closer to any ring of `board_outline` than the edge clearance in force: the `min` of the governing board-wide `edge_clearance` rule (`rulemap.rule_order`), else the project's `min_copper_edge_clearance`. Without a closed outline the edge is not checked. Zones still do not count (`H-K-STITCH-AVOID`). The dropped candidates join the count of `kicad.copper.stitch-skipped`.

8. **Cut order.** First the less common preset keys (keep Gerber layers and extensions, drill format, units and origin, placement format, units and side), then the footprint edge items (keep the 10 µm chaining), never the drawing sheet, the schematic key and the stitching.

## Files and public API

- `src/fenolite/dsl/design.py`: `Design.sheet`, `Design.title_block`; `src/fenolite/dsl/convert.py`: `Board.sheet` and `Board.title_block` in `to_model`, `drawing_sheet_source(design)`.
- `src/fenolite/lens/build.py`, `src/fenolite/cli/cmd_build.py`: the sheet output and the `schematic` argument of `apply_sheet_keys`.
- `src/fenolite/backends/kicad/pro.py`: `apply_sheet_keys(…, schematic=False)`.
- `src/fenolite/backends/kicad/outline.py`: `CHAIN_GAP`, `BoardOutline.joined`; `src/fenolite/backends/kicad/frame.py`: `footprint_edges`.
- `src/fenolite/backends/kicad/copper.py`: keep-outs and the edge in the stitch clearance.
- `src/fenolite/exports/preset.py` (new): `PRESET_SCHEMA`, `Preset`, `read_preset(text, *, file="")`, `arguments(kind, preset, *, stem, layers)`; `src/fenolite/cli/cmd_export.py`: `--preset`.
- Tests: `tests/unit/dsl/test_sheet_calls.py`, `tests/unit/lens/test_build_sheet.py`, `tests/unit/backends/kicad/test_outline.py` (extended), `tests/unit/exports/test_preset.py`, `tests/unit/backends/kicad/test_copper_stitch.py` (extended); `tests/kicad/followups/test_followup_probes.py`.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-PRO-WKS-SCH | `schematic.page_layout_descr_file`, project-relative or `${KIPRJMOD}/<name>`, gives the drawing sheet that `sch export svg` draws on every sheet of the project; `pcbnew.page_layout_descr_file` alone does not (S-0020, S-0029) | `tests/kicad/followups/test_followup_probes.py -k schematic_sheet` | probes `wks-sch-key-relative` and `wks-sch-key-kiprjmod` `present`, `wks-sch-key-absent` and `wks-sch-key-board-only` `absent`, on both majors |
| H-K-OUTLINE-CHAIN | KiCad closes a board outline across endpoint gaps below 10 µm and reports `invalid_outline` above it; at exactly 10 µm, 10.0.x closes and 9.0.x does not (S-0020, S-0029) | `-k outline_chain` | probes `outline-gap-<gap>` at 9.999, 10 and 10.001 µm, with the outcomes stated, on both majors |
| H-K-OUTLINE-FPEDGE | Edge items inside footprints are part of the board outline: they close a board edge with the root items, and a closed one inside the board is a cut-out (S-0020, S-0029) | `-k footprint_edges` | probes `outline-fp-edge-closes` and `outline-fp-edge-cutout` `present` on both majors, and the 21 native demos all close in `board_outline` |
| H-K-EXPORT-OPTIONS | The options of Decision 4 exist with the listed values in `pcb export gerbers`, `drill` and `pos` on both majors, and each changes the written files as its name says (S-0020, S-0029, S-0037) | `-k export_options` | help rows `help-pcb-export-<kind>-<option>` `present` on both majors, and one run per option whose files differ from the default run |
| H-K-STITCH-AVOID | A stitch fence across a rule area that forbids vias and along the board edge gives, after Decision 7, no `items_not_allowed` and no `copper_edge_clearance` entry for its vias (S-0020, S-0029) | `-k stitch` | probe `stitch-avoid` `equal` on both majors, with the control fence of v0.1 giving both entries |

Ids used without changing their level: `H-K-PRO-WKS`, `H-K-WKS-FALLBACK`, `H-K-WKS-CORNER`, `H-G-PLACE-OUTLINE` (re-measured). `H-G-EDGE-EXACT` is set to refuted, with the measured tolerance.

## Risks / Trade-offs

- [A 10 µm join closes a shape the user left open on purpose] → KiCad closes it too; `joined` says how many joins happened.
- [A footprint edge item that KiCad treats differently, such as a text on `Edge.Cuts`] → only the five graphic kinds are taken; others stay opaque and are listed by the census.
- [A preset key whose flag changes meaning in a later major] → the probe pins each option per major; a change fails the probe test before a release.
- [The user's `.kicad_wks` is re-written] → the tree is equal up to the root name and the header; a census compares the source with the written file for every corpus sheet.

## Migration Plan

- Additive for scripts, presets and stitching inputs; designs without the new calls build the same bytes.
- `board_outline` may now close outlines it left open: `place`, `route` and the board views see more boards; boards that closed before close the same way unless two endpoints were within 10 µm.
- Stitching may drop vias that v0.1 placed in keep-outs or near the edge; each is counted in `kicad.copper.stitch-skipped`.
- Rollback: `CHAIN_GAP = 0` and no footprint edges restore v0.1's outline.

## Open Questions

- **Should `d.sheet()` also set the schematic's paper?** Default: no; the schematic layout chooses its paper (c0061, c0070).
- **Should a preset select kinds (`kinds = [...]`)?** Default: no; the command's flags select them.
- **Should stitching avoid zones of other nets?** Default: no, until zone fills exist at build time.
