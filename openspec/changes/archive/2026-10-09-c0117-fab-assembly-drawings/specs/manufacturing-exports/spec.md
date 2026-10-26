## ADDED Requirements

### Requirement: Drawing specification files
`fenolite.exports.drawing_spec.read_spec(text, *, file="") -> DrawingSpec` SHALL read a drawing specification, a TOML file of the user's whose `schema` is `fenolite.drawing-spec.v0`, and SHALL refuse anything else before any tool runs.
- The key set MUST be closed:
  - `[page]`: `paper` (`auto` or a name of `PAPER_SIZES`), `portrait` (bool), `drawing_sheet` (a path ending in `.kicad_wks` or `.sheet.toml`, relative to the file's folder), `text_size`, `gap` and `notes_width` (lengths);
  - `[fab]`: `title` (text), `tables` (a list of `board`, `stackup`, `drill`, `impedance`, `notes`; `impedance` is accepted so that the schema id need not change when a change gives that block content, "Drawing tables and notes"), `dimensions` (bool), `dimension_offset` (length), `dimension_precision` (an integer from 0 to 4), `notes` (a list of texts) and `at` (a table of block name to two lengths);
  - `[assembly]`: `title_top` and `title_bottom` (texts), `sides` (a list of `top`, `bottom`), `dnp` (`crossout`, `hide` or `show`), `values`, `pads` and `designators` (bools), `designator_size` (length), `notes` and `at`.
- Lengths MUST be strings with a unit, read by `core.units.parse_length`; the file MUST be parsed with `parse_float=Decimal`, and no float MUST be created.
- The defaults MUST be: `paper = "auto"`, `portrait = false`, no `drawing_sheet`, `text_size = "1.5mm"`, `gap = "5mm"`, `notes_width = "120mm"`, the titles `Fabrication drawing`, `Assembly drawing, top side` and `Assembly drawing, bottom side`, all five tables, `dimensions = true`, `dimension_offset = "8mm"`, `dimension_precision = 2`, no note, both sides, `dnp = "crossout"`, `values = false`, `pads = false`, `designators = true` and `designator_size = "1mm"`. `DEFAULT` MUST hold them, and `export` MUST use it when no file is given.
- A wrong or missing schema id, an unknown table or key, a value of the wrong type or outside its set, a length without a unit, `portrait = true` with `paper = "auto"`, an `at` entry naming a block that its page does not have, or a note holding a control character other than a line feed MUST raise `SpecError`, which MUST list every problem in file order with its dotted key.
- Fenolite MUST ship no note text and no default tolerance, class, material or finish.

#### Scenario: Defaults
- **WHEN** `uv run pytest tests/unit/exports/test_drawing_spec.py -k defaults` reads a file holding only `schema = "fenolite.drawing-spec.v0"`
- **THEN** the result equals `DEFAULT`, `fab.notes` is empty and `page.text_size` is 1500000

#### Scenario: Every problem in file order
- **GIVEN** a file with `[page] paper = "B9"`, `[fab] colour = "red"` and `[assembly] dnp = "maybe"`
- **WHEN** `read_spec` reads it
- **THEN** `SpecError` lists three problems naming `page.paper`, `fab.colour` and `assembly.dnp`, in that order

#### Scenario: Lengths carry units
- **GIVEN** a file with `[page] gap = 5`
- **WHEN** `read_spec` reads it
- **THEN** `SpecError` names `page.gap`

### Requirement: Drawing tables and notes
`fenolite.exports.drawing_tables` SHALL build the blocks of a drawing from the model read from the board, and SHALL size every block with the measured text bounds, so that KiCad never wraps a cell.
- A block MUST be a table of texts `text_size` high with strokes of 0.15 × `text_size`, 1 mm cell margins and a header row naming its columns (`Board` and `Value` for the board block); the notes block has no header row. Lengths MUST be printed in millimetres as exact decimals with at least three decimals (`0.300`, `1.600`, `0.2104`), and a stack-up thickness of 0 as an empty cell.
- **Board**: `Copper layers`; `Outline`, the width and height of the bounding box of the first ring of `board_outline` (`W x H`); with a stack-up, `Thickness` (`Stackup.thickness()`), `Finish` and `Impedance controlled` (`yes` or `no`); `Smallest drill`. The block MUST hold no row about via protection: the model of this change holds none.
- **Stack-up**: one row per entry of `Board.stackup` from the top, entries of kind `solderpaste` left out, with the columns `Layer`, `Type` (`copper`, `core`, `prepreg`, `soldermask`, `silkscreen`, or `dielectric` when `dielectric_kind` is unset), `Material`, `Thickness`, `Dk` (`epsilon_r`), `Df` (`loss_tangent`) and `Color`. A column empty in every row MUST be dropped, and a last row `Total` MUST hold `Stackup.thickness()`. A board without a stack-up MUST get no stack-up block and one `drawing.stackup-missing` (info).
- **Drill**: `drill_rows(design)` MUST give one row per plating, span, drill and slot length, with its count and kinds, from the pads of `board_pads` that have a drill (`thru_hole` plated, `np_thru_hole` not; the slot length from `Padstack.hole_length`, none for a round hole) and the vias of `Board.vias` (plated; the span from `layers`; a through via spans the outer copper layers). Rows MUST come in this order: through spans first, plated before unplated, then the other spans by the stack order of their first layer, then by drill and slot length. The block's columns MUST be `Drill`, `Slot`, `Plated`, `Layers`, `Count` and `Holes` (`via`, `pad` or `via, pad`), `Slot` dropped when no row has a slot, and a last row MUST hold the total count.
- **Impedance**: the model of this change holds no impedance target, so `impedance_block(design)` MUST return no block, and a `tables` list that names `impedance` MUST give neither a block nor an issue.
- **Notes**: one row per note of the spec, with `1.`, `2.`, … in the first column and the note in the second, `notes_width` wide, without border or separator; no block without a note.
- `text_width(text, size)` MUST count `GLYPH_BOUND`, 1.45 × `size`, for each character of `GLYPH_SET` (printable ASCII and `±µ°×ΩÄÖÜßéèçñ–—…`) and 2 × `size` for any other, plus `LINE_EXTRA`, 0.25 × `size`, for a text that holds any character (KiCad draws a line of n glyphs of advance a n × a + 0.25 × the size long, as the probe `draw-glyph-bound` measured on 2026-10-08); `LINE_PITCH` MUST be 1.61 × the size (`H-K-DRAW-TEXT`). A column MUST be as wide as its widest line by `text_width` plus 2 mm, and a row as high as the line count of its tallest cell × the pitch plus 2 mm.
- `break_lines(text, width, size)` MUST break a note at spaces, greedily, into lines that each fit `width` by `text_width`, MUST cut a word longer than `width`, MUST keep the note's own line feeds, and MUST join the lines with `\n`.
- The functions MUST be pure.

#### Scenario: Stack-up rows of a two-layer board
- **GIVEN** a model whose stack-up holds `F.SilkS` (silkscreen, 0), `F.Paste` (solderpaste, 0), `F.Mask` (0.01 mm), `F.Cu` (0.035 mm), `dielectric 1` (core, 1.51 mm, `FR4`, `epsilon_r` `4.5`), `B.Cu` (0.035 mm), `B.Mask` (0.01 mm), `B.Paste` and `B.SilkS`, without colours or loss tangents
- **WHEN** `uv run pytest tests/unit/exports/test_drawing_tables.py -k stackup` builds the block
- **THEN** it has seven entry rows from `F.SilkS` to `B.SilkS` without paste rows and without the columns `Color` and `Df`, the core row reads `core`, `FR4`, `1.510` and `4.5`, and the last row reads `Total` and `1.600`

#### Scenario: Drill rows of vias and pads
- **GIVEN** a four-layer model with three through vias of 0.3 mm, one blind via of 0.1 mm from `F.Cu` to `In1.Cu`, two `thru_hole` pads of 1.0 mm, one `thru_hole` pad with an oval drill of 1.0 mm by 2.0 mm and one `np_thru_hole` pad of 3.2 mm
- **WHEN** `drill_rows` runs
- **THEN** the rows are, in order: plated `F.Cu` to `B.Cu` 0.300 (3, `via`), 1.000 (2, `pad`) and 1.000 with slot 2.000 (1, `pad`); unplated `F.Cu` to `B.Cu` 3.200 (1, `pad`); plated `F.Cu` to `In1.Cu` 0.100 (1, `via`); and the block's total is 8

#### Scenario: No stack-up
- **GIVEN** a model whose `Board.stackup` is `None`
- **WHEN** the blocks of the fabrication page are built
- **THEN** there is no stack-up block, the board block has no `Thickness`, `Finish` or `Impedance controlled` row, and one `drawing.stackup-missing` info is returned

#### Scenario: Notes are broken by the bound
- **GIVEN** a note of 227 characters, a width of 78 mm and a size of 1.5 mm
- **WHEN** `break_lines` runs
- **THEN** every line's `text_width` is at most 78 mm, the lines joined with spaces give the note back, and its row is the line count × 2.415 mm plus 2 mm high

### Requirement: Drawing page layout
`fenolite.exports.drawing_layout` SHALL lay out each drawing page at 1:1 around the board, and SHALL choose the page's paper.
- The board MUST stay where the board file puts it: page coordinates MUST be board coordinates (`H-K-DRAW-PAGE`), and no scale option MUST be passed.
- The board box of a page MUST be:
  - fabrication: the bounding box of the outline, grown at the top and at the left by `dimension_offset` + 2 × `text_size` when `dimensions` is true, joined with the extent of every root item on `Dwgs.User`;
  - top assembly: the outline's box joined with the courtyard boxes of the top-side footprints (`placed_extents`) and the extent of the root items on `F.Fab`;
  - bottom assembly: the same for the bottom side and `B.Fab`, mirrored by x ↦ W − x for the page width W.
- For KiCad's default sheet the margin box MUST be the page less 10 mm on each side, and the obstacles the band from there to the border 12 mm inside each edge and the title block box [W − 120 mm, W − 12 mm] × [H − 44 mm, H − 12 mm] (`H-K-DRAW-SHEET`). For any other sheet the margin box MUST be the page less the sheet's margins, and the obstacles the boxes of the lines and texts that `templates.layout` predicts on the page. `cmd_export` MUST compute them and pass them as rectangles, so that `exports` imports no `templates`.
- `place(blocks, *, page, board_box, obstacles, gap, fixed)` MUST give each block, in the order board, stack-up, drill, impedance, notes, the first top-left corner, in the order of x then y, among the margin box's left edge and the right edges of every obstacle, of the board box and of every placed block plus `gap`, and the margin box's top edge and the bottom edges of the same boxes plus `gap`, at which the block lies in the margin box and is at least `gap` from every obstacle, the board box and every placed block. A block named in `fixed` MUST take that corner and MUST meet the same conditions.
- The paper MUST be the spec's when it names one; with `auto` it MUST be the first of A4, A3, A2, A1 and A0 in landscape on which the board box lies in the margin box at least `gap` from every obstacle and every block is placed. Page sizes MUST be those KiCad plots.
- When no paper is found, or the named paper does not hold the board box or a block, the page MUST give `drawing.no-room` (error) naming the page, the block or the board box with its corners in millimetres, and the smallest paper that holds it or that none does; `export` MUST then plan no write.
- `place` and `choose_paper` MUST be pure and deterministic.

#### Scenario: The 600-part probe board on KiCad's default sheet
- **GIVEN** a fabrication page whose board box spans (89 mm, 89 mm) to (258 mm, 279 mm), one block of 150 mm × 200 mm, `gap` 5 mm and KiCad's default sheet
- **WHEN** `uv run pytest tests/unit/exports/test_drawing_layout.py -k paper` chooses the paper with `auto`
- **THEN** A4 and A3 are refused, the paper is A2, and the block's corner is (263 mm, 17 mm)

#### Scenario: A fixed block over the title block
- **GIVEN** a top assembly page with `paper = "A3"`, KiCad's default sheet, a board box from (100 mm, 100 mm) to (176 mm, 192 mm), one note of one line and `at.notes = ["310mm", "260mm"]`
- **WHEN** the page is laid out
- **THEN** it gives `drawing.no-room` naming `notes` and A2 as the smallest paper that holds it

#### Scenario: The bottom page is mirrored
- **GIVEN** a bottom assembly page on A3, whose page width is 419.989 mm, and an unmirrored box from x = 100 mm to x = 176 mm
- **WHEN** its board box is computed
- **THEN** the box spans x = 243.989 mm to x = 319.989 mm

#### Scenario: A board outside every page
- **GIVEN** a fabrication page whose board box starts at x = −20 mm
- **WHEN** the paper is chosen with `auto`
- **THEN** the page gives `drawing.no-room` naming the board box and stating that no paper holds it

### Requirement: Drawing plot copies
`fenolite.backends.kicad.drawing.plot_copy(board_text, items, *, paper, portrait, major, layers) -> str` SHALL return the text of a copy of the board that holds a page's items, and no drawing kind SHALL write the board file.
- The copy MUST equal the board's text except for: the `paper` node, set to the page's paper and orientation; the item nodes, appended as root children; and, for each name in `layers` that the layer table lacks, the row `(17 "Dwgs.User" user "User.Drawings")`, `(35 "F.Fab" user)` or `(33 "B.Fab" user)`.
- A `PlotTable` MUST become a `table` node whose children come in the order `column_count`, `uuid` (major 10 only), `layer`, `border`, `separators`, `column_widths`, `row_heights`, `cells`, each `table_cell` holding `start`, `end`, `margins`, `span`, `layer`, `uuid` and `effects` (`H-K-DRAW-ITEMS`). A `PlotText` MUST become a `gr_text`, with `mirror` in its `justify` on a back layer. A `PlotDimension` MUST become an `orthogonal` `dimension` node in c0103's form (`H-K-DIM`).
- Every uuid MUST be `uuid5` of the page kind and the block and cell names, and two calls with equal arguments MUST return equal texts.
- `layer_extent(board_text, layer)` MUST give the bounding box of every coordinate (`at`, `start`, `end`, `mid`, `center`, `xy`) of the root items on `layer`, or `None` when there is none.
- `shows_reference(footprint, layer)` MUST be true when the footprint holds, on `layer`, a text `${REFERENCE}` or a `Reference` property that is not hidden.
- `KicadCli.run` and `KicadCli.export` MUST accept `bytes` as a source in `files`, written under its name in the run folder; such a file MUST NOT be among the outputs unless the run changed it.

#### Scenario: Only the page's changes
- **GIVEN** the text of `tests/data/kicad/board/two_layer.kicad_pcb`, whose layer table has no `Dwgs.User`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_drawing_copy.py -k copy` calls `plot_copy` with one table of three columns and two rows on `Dwgs.User`, paper `A3`, major 9 and `layers=("Dwgs.User",)`
- **THEN** the copy holds `(paper "A3")`, the `Dwgs.User` row and one `table` without `uuid`; with those three changes undone it is tree-equal to the board text; and the board file's SHA-256 is unchanged

#### Scenario: Target 10 table
- **WHEN** the same call runs with major 10
- **THEN** the table holds a `uuid` right after `column_count`, and every child follows the order of the requirement

#### Scenario: Same input, same copy
- **WHEN** `plot_copy` runs twice with equal arguments
- **THEN** the two texts are equal

#### Scenario: A footprint that shows its reference
- **GIVEN** a footprint of KiCad's libraries with a `${REFERENCE}` text on `F.Fab`, and a catalog footprint whose `F.Fab` holds only its body outline
- **WHEN** `shows_reference(footprint, "F.Fab")` runs on each
- **THEN** it is true for the first and false for the second

### Requirement: Fabrication drawing kind
The export kind `fab-drawing` SHALL produce the fabrication drawing from plot copies, and SHALL check its drill table against KiCad's drill report on every run.
- The page MUST be plotted by `pcb export pdf --mode-single --layers Edge.Cuts,Dwgs.User --include-border-title --drill-shape-opt 0 -D FENOLITE_DRAWING=<fab.title> [--drawing-sheet <sheet>] -o drawings/<stem>-fab.pdf <stem>.kicad_pcb` on a copy that holds the blocks of `fab.tables` that have content, placed by "Drawing page layout", and, when `dimensions` is true, the two dimensions of the outline's bounding box: horizontal at `dimension_offset` above it, vertical at `dimension_offset` left of it, in millimetres with `dimension_precision` decimals.
- The maps and the report MUST come from `pcb export drill -o drawings/ --format excellon --excellon-units mm --excellon-separate-th --drill-origin absolute --generate-map --map-format pdf --generate-report <stem>.kicad_pcb` on the copy set; every `*-drl_map.pdf` file and `<stem>-drill.rpt` that it writes MUST be an artefact, and its `.drl` files MUST NOT. The `drill` kind with the preset key `drill.map` ("Export presets") writes maps of its own under `drill/`; an export that selects both MUST keep both sets, each under its own kind, and `docs/drawings.md` MUST say that the two are the same maps.
- `read_drill_report(text)` MUST give, per drill file named in the report, each tool's diameter and hole count, reading tool lines that close with `)` or `))`. When the multiset of (diameter, count) of a file differs from the drill rows of that file (plated through, unplated through, each other span), the kind MUST give `drawing.drill-mismatch` (error) naming the file, the diameter and both counts. A report from which no file is read MUST give `drawing.drill-report-unread` (warning), and the drill block MUST stay.
- Artefacts MUST have the kind `fab-drawing` and the layer `None`; `VOLATILE_PREFIXES["fab-drawing"]` MUST be `/CreationDate` and `Created on` (`H-K-DRAW-REPEAT`).
- `--check-zones` and `--board-plot-params` MUST NOT be passed.

#### Scenario: Files of the kind
- **GIVEN** a fake `kicad-cli` whose `pcb export pdf` writes `drawings/b-fab.pdf`, and whose `pcb export drill` writes `drawings/b-PTH.drl`, `drawings/b-NPTH.drl`, both maps and a report that matches the board
- **WHEN** `uv run pytest tests/unit/exports/test_drawings.py -k fab` runs `run_fab_drawing`
- **THEN** the artefacts are `drawings/b-NPTH-drl_map.pdf`, `drawings/b-PTH-drl_map.pdf`, `drawings/b-drill.rpt` and `drawings/b-fab.pdf`, all of kind `fab-drawing`, and no `.drl` file is among them

#### Scenario: Both forms of a tool line
- **WHEN** `read_drill_report` reads the lines `T1  0.300mm  0.0118"  (83 holes))` and `T2  0.600mm  0.0236"  (6 holes)` under `Drill file 'b-PTH.drl' contains`
- **THEN** it gives, for `b-PTH.drl`, 83 holes of 0.300 mm and 6 holes of 0.600 mm

#### Scenario: A count that differs
- **GIVEN** a fake report giving 84 holes of 0.300 mm in `b-PTH.drl` for a board with 83
- **WHEN** `fenolite export <board> --out fab --fab-drawing --confirm` runs
- **THEN** the issues hold `drawing.drill-mismatch` naming `b-PTH.drl`, `0.300`, `83` and `84`, the exit code is 5, and `fab` does not exist

#### Scenario: Dates do not change the content hash
- **GIVEN** two drawing PDFs that differ only in their `/CreationDate` line, and two reports that differ only in their `Created on` line
- **WHEN** `content_sha256` is computed for each with the kind `fab-drawing`
- **THEN** both pairs have equal values

### Requirement: Assembly drawing kind
The export kind `assembly-drawing` SHALL produce a top page and, when a part sits on the bottom, a mirrored bottom page, from plot copies.
- The top page MUST be plotted by `pcb export pdf --mode-single --layers F.Fab,Edge.Cuts --include-border-title --drill-shape-opt 0 -D FENOLITE_DRAWING=<title_top> [--drawing-sheet <sheet>] <options> -o drawings/<stem>-assembly-top.pdf <stem>.kicad_pcb`, and the bottom page with `--layers B.Fab,Edge.Cuts`, `--mirror`, `<title_bottom>` and `-o drawings/<stem>-assembly-bottom.pdf`.
- `<options>` MUST be `--exclude-value` unless `values` is true, `--sketch-pads-on-fab-layers` when `pads` is true, and `--crossout-DNP-footprints-on-fab-layers` for `dnp = "crossout"`, `--hide-DNP-footprints-on-fab-layers` for `hide`, nothing for `show` (`H-K-DRAW-ASSEMBLY`).
- A side absent from `sides` MUST have no page. The bottom page MUST be left out, with one `drawing.side-empty` (info) naming `bottom`, when no footprint sits on the bottom.
- With `designators` true, each footprint of a page's side for which `shows_reference` is false on that side's fabrication layer MUST get a `PlotText` of its reference, `designator_size` high, at the centre of its courtyard's bounding box, or at its position when it has no courtyard, on `F.Fab`, or mirrored on `B.Fab`; under `dnp = "hide"` a do-not-populate footprint MUST get none; a page that adds any MUST give one `drawing.designators-added` (info) with the count.
- The notes of `[assembly]` MUST be placed on the top page, on `F.Fab`.
- Artefacts MUST have the kind `assembly-drawing` and the layer `None`; `VOLATILE_PREFIXES["assembly-drawing"]` MUST be `/CreationDate`.

#### Scenario: Default arguments
- **GIVEN** a board with parts on both sides and `DEFAULT`
- **WHEN** `uv run pytest tests/unit/exports/test_drawings.py -k assembly` runs `run_assembly_drawing` with a fake `kicad-cli`
- **THEN** two `pcb export pdf` runs are made: the top one with `--layers F.Fab,Edge.Cuts`, `--exclude-value` and `--crossout-DNP-footprints-on-fab-layers` and without `--mirror`, the bottom one with `--layers B.Fab,Edge.Cuts` and `--mirror`

#### Scenario: Options of the spec
- **GIVEN** a spec with `values = true`, `pads = true` and `dnp = "hide"`
- **WHEN** the kind runs
- **THEN** no run holds `--exclude-value`, and each holds `--sketch-pads-on-fab-layers` and `--hide-DNP-footprints-on-fab-layers`

#### Scenario: No part on the bottom
- **GIVEN** a board whose parts all sit on the top
- **WHEN** the kind runs
- **THEN** only `drawings/<stem>-assembly-top.pdf` is an artefact, and one `drawing.side-empty` info names `bottom`

#### Scenario: References added where none is shown
- **GIVEN** a board with a catalog resistor `R1` and a library capacitor `C1` whose footprint shows `${REFERENCE}` on `F.Fab`, both on the top
- **WHEN** the top copy is built
- **THEN** it holds one added `gr_text` `R1` on `F.Fab` at the centre of `R1`'s courtyard box and none for `C1`, and `drawing.designators-added` gives 1

### Requirement: Drawing kinds in the manifest
The artefacts of `fab-drawing` and `assembly-drawing` SHALL enter `fenolite-artifacts.json` as derived entries under "Artefact states" and "Manifest merging", like the files of the other kinds that `kicad-cli` writes from the board.
- An entry of either kind MUST be written by `manifest.merge` with the state `generated`, `tool` `kicad-cli <version>`, `layer` `null` (a page plots several layers), `from` holding the SHA-256 of the board and nothing else, and `evidence` the level of `exports.drawings.EVIDENCE`.
- `from` MUST NOT name the drawing spec or the drawing sheet: a changed spec does not mark a drawing stale, and `docs/drawings.md` MUST say so.
- `exports.states.DERIVED` MUST hold both kinds, and `manifest.design_kind` MUST NOT return either.

#### Scenario: Drawings join the manifest
- **GIVEN** a folder in which `export --gerbers --manifest --confirm` ran, and a fake `kicad-cli`
- **WHEN** `uv run pytest tests/unit/cli/test_export_drawings.py -k manifest` runs `fenolite export <board> --out <folder> --fab-drawing --assembly-drawing --manifest --confirm`
- **THEN** the manifest lists the Gerbers and every file under `drawings/` with kind `fab-drawing` or `assembly-drawing`, `layer` `null`, the board's hash in `from` and the state `generated`

## MODIFIED Requirements

### Requirement: Artefact states
Every manifest entry SHALL carry one `state` of `manifest.STATES = ("generated", "checked", "roundtrip-ok", "oracle-verified", "native-verified")`, in rising order, and `fenolite.exports.states.assign(entries, *, stages, sheets_ok, current) -> tuple[ArtifactEntry, ...]` SHALL assign it: the highest rung a file reaches together with every lower rung that applies to its kind, with `held` saying what the next rung is missing (`<state>: <reason>`, or `""` when no higher rung applies). `stages` maps a stage name to its status and evidence level, `sheets_ok` a sheet path to its RT1 verdict, and `current` a path to the file's present SHA-256.
- **Current.** An entry is current when `current[path]` equals its `sha256` and every hash of its `from` equals the present hash of that source. A derived entry that is not current MUST be `generated` with `stale` true. A design entry whose file has another hash MUST be `generated`; `stale` is only ever true for a derived entry.
- **`generated`.** Every entry reaches it.
- **`checked`.** `model.validate` and `copper.clearance` are in `stages` with status `ok`. A derived entry (kinds `gerbers`, `drill`, `pos`, `ipcd356`, `ipc2581`, `odb`, `step`, `pdf`, `dxf`, `sch-pdf`, `fab-drawing`, `assembly-drawing`, `bom`, `pnp`, `render`) reaches it when it is current and the sources its `from` names (`board`: the entry of kind `kicad_pcb`; `schematic`: an entry of kind `kicad_sch`) are `checked`, and reaches no higher rung. A derived entry whose `from` is empty or names another source MUST stay `generated`: nothing says what it was made from.
- **`roundtrip-ok`.** Applies to kinds `kicad_pcb` and `kicad_sch` only: the board needs `roundtrip` with status `ok`, and a sheet needs `sheets_ok[path]` true. Every other design kind skips the rung.
- **`oracle-verified`.** No rule assigns it; every kind skips the rung. The state is reserved for a tool that is neither the producer of a file nor its format's own application.
- **`native-verified`.** The board needs `drc.kicad` with status `ok` and level exactly `KICAD-VERIFIED`. The files KiCad loads to judge the board (kinds `kicad_pro`, `kicad_dru`, `kicad_mod`, `kicad_wks`, and a `lib-table` other than `sym-lib-table`) reach it exactly when the board does. A file of kind `file` (any other file of a library folder) stops at `checked`: no tool is known to load it. A file of kind `3d-model` (a model vendored below `3dmodels/`, "Project manifest") stops at `checked` too: the DRC does not load it, and the `step` export that reads it judges nothing about it.
- **Schematic side.** A sheet (`kicad_sch`), a symbol library (`kicad_sym`) and the `lib-table` named `sym-lib-table` are judged by KiCad's ERC, not by its DRC. Each reaches `native-verified` when `erc.kicad` (change c0062) is in `stages` with status `ok` and level exactly `KICAD-VERIFIED`: the ERC loaded the sheets with the libraries the table names. A sheet needs `roundtrip-ok` first; a symbol library and the symbol table skip that rung. Without that stage, or with an ERC error, a sheet stops at `roundtrip-ok` and a symbol library and the symbol table at `checked`, and `held` names `erc.kicad`. `states.PENDING` MUST be empty: no role waits for a stage that `check` lacks.
- A stage that is missing from `stages`, skipped, or below the level its rule names MUST NOT give its rung, and a rung that is not reached MUST stop the ladder for that file.
- `assign` MUST be pure, MUST import nothing from `checks`, and with an empty `stages` MUST leave every entry `generated`.

#### Scenario: Board up the ladder
- **GIVEN** a board entry that is current, and `stages` with `model.validate`, `copper.clearance` and `roundtrip` `ok` and `drc.kicad` `ok` at `KICAD-VERIFIED`
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k ladder` calls `assign`
- **THEN** the board's state is `native-verified`

#### Scenario: A failed rung stops the ladder
- **GIVEN** the same stages with `roundtrip` `errors`
- **WHEN** `assign` runs
- **THEN** the board's state is `checked`, although `drc.kicad` is `ok`

#### Scenario: DRC below KICAD-VERIFIED
- **GIVEN** the stages of the first scenario with `drc.kicad` `ok` at `UNVERIFIED`
- **WHEN** `assign` runs
- **THEN** the board's state is `roundtrip-ok`

#### Scenario: Derived file of a checked board
- **GIVEN** a Gerber entry whose `from` holds the board's present hash, and a board that reaches `native-verified`
- **WHEN** `assign` runs
- **THEN** the Gerber's state is `checked`

#### Scenario: Stale artefact
- **GIVEN** a Gerber entry whose `from` holds another hash than the board's present one
- **WHEN** `assign` runs
- **THEN** its state is `generated` and `stale` is true

#### Scenario: Schematic follows the ERC
- **GIVEN** the stages of the first scenario, with and without an `erc.kicad` entry that is `ok` at `KICAD-VERIFIED`, and a sheet whose RT1 verdict is true
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k erc` calls `assign`
- **THEN** with the entry the sheet, the symbol library and `sym-lib-table` are `native-verified` with an empty `held`; without it, with status `errors`, or at another level, the sheet is `roundtrip-ok`, the other two are `checked`, and each `held` names `erc.kicad`

#### Scenario: No check, no claim
- **WHEN** `assign` runs with `stages` empty
- **THEN** every entry is `generated`, and none is `oracle-verified` under any input of the test's generator

#### Scenario: Documents follow their source
- **GIVEN** a `step` entry whose `from` holds the board's present hash, a `sch-pdf` entry whose `from` holds the root sheet's present hash, a board and a sheet that are `checked`, and a `3d-model` entry
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k documents` calls `assign` with the stages of the first scenario
- **THEN** the two documents are `checked` with an empty `held`, the model is `checked`, and after the board's hash changes the `step` entry is `generated` and stale while the `sch-pdf` entry stays `checked`

#### Scenario: A drawing follows its board
- **GIVEN** a `fab-drawing` entry whose `from` holds the board's present hash, and a board that reaches `native-verified`
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k drawing` calls `assign`, and again after the board's hash changed
- **THEN** the drawing is `checked` the first time, and `generated` and stale the second
