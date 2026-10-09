# Fabrication and assembly drawings

`fenolite export PATH --out DIR --fab-drawing --assembly-drawing [--drawing-spec FILE]` writes the drawings
a contract manufacturer gets beside the Gerber and drill files (change c0117). KiCad draws them: Fenolite
writes tables, notes, dimensions and missing designators as board items into a copy of the board, and
`kicad-cli pcb export pdf` plots that copy with the drawing sheet and its title block. The board, its
project and its folder never change, and the items exist only in the copy, which is built again on every
export.

The drawing kinds take a KiCad board. An Altium document or project is refused with exit 2 (`FEN-2001`),
as for every export kind: an Altium project gets its drawings from Altium, through the output job that
`fenolite build --target altium` writes (`docs/altium.md`) or through Draftsman. `--all` does not select
a drawing kind, and no `--preset` reaches one.

## Files

Everything is written under `DIR/drawings/`:

| kind | file | content |
|---|---|---|
| `fab-drawing` | `<stem>-fab.pdf` | the outline with its overall dimensions, your drawings on `Dwgs.User`, the board, stack-up and drill tables and the numbered notes |
| `fab-drawing` | `<stem>-PTH-drl_map.pdf`, `<stem>-NPTH-drl_map.pdf`, and one map per drill file of a layer pair | KiCad's drill maps: the outline, one symbol per tool and a legend; they carry no frame |
| `fab-drawing` | `<stem>-drill.rpt` | KiCad's drill report: per drill file, each tool with its diameter and hole count |
| `assembly-drawing` | `<stem>-assembly-top.pdf` | `F.Fab` and the outline, the notes of `[assembly]` |
| `assembly-drawing` | `<stem>-assembly-bottom.pdf` | `B.Fab` and the outline, mirrored; left out when no part sits on the bottom |

Each page is its own PDF, and KiCad prints 1/1 as its sheet number. The maps under `drawings/` are the
same maps that the preset key `drill.map` makes the `drill` kind write under `drill/`
(`docs/exports.md`, "Presets"): an export that selects both keeps both sets, each under its own kind. The
`.drl` files of the map run are not artefacts; the `drill` kind owns them.

Every page defines the variable `FENOLITE_DRAWING` for its run, holding the page's title. A drawing sheet
shows it with a text `${FENOLITE_DRAWING}`; KiCad's default sheet does not.

## The pages

A page is plotted at 1:1 and the board stays where the board file puts it, so a coordinate on the page is
the coordinate in the board. No scale is ever passed: `kicad-cli` 9.0 has none for a PDF. A board built
by Fenolite starts at (100 mm, 100 mm).

- **Paper.** With `paper = "auto"` (the default) a page takes the first of A4, A3, A2, A1 and A0, landscape,
  on which its board box and its blocks fit. A named paper is taken as it is.
- **Board box.** Fabrication: the bounding box of the outline, grown at the top and at the left by
  `dimension_offset` + 2 × `text_size` for the dimensions, joined with everything already drawn on
  `Dwgs.User`. Assembly: the outline's box joined with the courtyards of the side's parts and the items on
  the side's fabrication layer; the bottom page is mirrored (x becomes W − x for the page width W).
- **Sheet.** The drawing sheet is the one `drawing_sheet` names, else the one the project names, else
  KiCad's default. Content lies inside the sheet's margins and keeps `gap` from its lines and texts; for
  KiCad's default sheet, from the borders 10 mm and 12 mm inside the page and from the title block in
  the bottom-right corner (108 mm wide, 32 mm high).
- **Blocks.** The blocks are placed in the order board, stack-up, drill, impedance, notes. Each takes the
  first free corner, going right and then down, among the left edge of the margins, the right edges of
  the sheet's items, of the board box and of the blocks placed before it, and their bottom edges, each
  plus `gap`. `at` fixes the corner of a block; a fixed block that meets anything is an error.
- **Holes.** No hole is drawn on a page (`--drill-shape-opt 0`): the default would draw pad holes
  without via holes, and the drill maps show them all.

`result.drawings` lists each page with its paper, its sheet (`spec`, `project` or `kicad-default`) and its
blocks with corner and size in nanometres.

## The tables

Every value comes from the model read from the board. Lengths are millimetres with at least three
decimals. Text is `text_size` high with strokes of 0.15 × the size.

- **Board**: copper layers; the outline's width and height; with a stack-up its thickness, its finish
  and whether it is impedance-controlled; the smallest drill.
- **Stack-up**: one row per entry from the top, paste entries left out: layer, type, material,
  thickness, Dk, Df, colour; a column that is empty in every row is dropped; the last row is the total
  thickness. A board without a stack-up gets no such table (`drawing.stackup-missing`). Until a KiCad
  stack-up is read into the model (change c0101), every KiCad board is such a board.
- **Drill**: one row per plating, span (first and last copper layer), drill and slot length, with the
  count and what makes the holes (`via`, `pad`); through holes first, plated before unplated; the last
  row is the total.
- **Impedance**: no table yet. The name is valid in `tables`, so that the file format need not change
  when Fenolite models impedance targets.
- **Notes**: your notes, numbered `1.`, `2.`, …, without border. Fenolite breaks a note at spaces into
  lines that fit `notes_width`; a line feed in a note is kept. `${…}` variables are left to KiCad: a
  note that names a variable nothing defines is printed as written, and Fenolite does not report it.

Fenolite ships no note text and no tolerance, class, material or finish: a drawing states what the board
and your specification say.

A column is as wide as its widest line by a bound of KiCad's glyph widths (1.45 × the size per character
of printable ASCII and `±µ°×ΩÄÖÜßéèçñ–—…`, twice the size for any other, plus 0.25 × the size per line),
so KiCad never wraps a cell. The bound is far above an average line, so tables carry blank space.

### The drill table is checked

On every run the fabrication kind reads KiCad's drill report and compares, per drill file and diameter,
the report's hole count with the table's. KiCad counts a slot with the round holes of its width and
prints three decimals; the table's rows are joined the same way for the comparison. A difference is
`drawing.drill-mismatch`, an error: no file of the export is written. A report in which Fenolite finds no
drill file is `drawing.drill-report-unread`, a warning, and the drawing is written.

## Assembly drawings

Both pages hide the value texts (`--exclude-value`) unless `values = true`, and cross out a
do-not-populate part (`dnp = "crossout"`); `hide` removes it and `show` draws it like any other part.
`pads = true` adds pad outlines and numbers.

A footprint whose fabrication layer shows no reference (no `${REFERENCE}` text and no visible
`Reference` field on that layer) gets a text of its reference, `designator_size` high, at the centre of
its courtyard, in the copy only. `drawing.designators-added` counts them. The footprints of Fenolite's
catalog show their reference on the silkscreen, so they get one; the footprints of KiCad's libraries
usually show `${REFERENCE}` on the fabrication layer and are left alone. The notes of `[assembly]` go on
the top page.

## The specification file

`--drawing-spec FILE` names a TOML file. Without it every default below applies and no note is drawn.
The key set is closed, a length is a string with a unit, and a path is relative to the file's folder.
Every problem of a file is reported at once (exit 3, `FEN-3004`) before any tool runs.

```toml
schema = "fenolite.drawing-spec.v0"

[page]
paper = "auto"            # or A0, A1, A2, A3, A4, A5, Letter, Legal, Tabloid
portrait = false          # needs a named paper
# drawing_sheet = "frame.kicad_wks"   # or a .sheet.toml template; default: the project's, else KiCad's
text_size = "1.5mm"
gap = "5mm"
notes_width = "120mm"

[fab]
title = "Fabrication drawing"
tables = ["board", "stackup", "drill", "impedance", "notes"]
dimensions = true
dimension_offset = "8mm"
dimension_precision = 2   # 0 to 4 decimals
notes = []                # texts; none is shipped
# at = { notes = ["300mm", "20mm"] }  # a fixed top-left corner per block

[assembly]
title_top = "Assembly drawing, top side"
title_bottom = "Assembly drawing, bottom side"
sides = ["top", "bottom"]
dnp = "crossout"          # or "hide", "show"
values = false
pads = false
designators = true
designator_size = "1mm"
notes = []
# at = { notes = ["300mm", "20mm"] }
```

A note may hold line feeds and no other control character.

## Issue codes

| code | severity | when |
|---|---|---|
| `drawing.no-room` | error | a page's paper does not hold the board box or a block at 1:1; the message names it, its corners and the smallest paper that holds the page. A board that lies outside every page must be moved in KiCad |
| `drawing.drill-mismatch` | error | the drill table and KiCad's drill report give different counts for a diameter of a drill file |
| `drawing.sheet-unread` | error | the drawing sheet of the specification or of the project cannot be read or built |
| `drawing.drill-report-unread` | warning | KiCad's drill report names no drill file, so the table was not checked |
| `drawing.stackup-missing` | info | the board has no stack-up, so there is no stack-up table |
| `drawing.side-empty` | info | no part sits on the bottom, so there is no bottom assembly drawing |
| `drawing.designators-added` | info | references were added to an assembly page; the message gives the count |

An error plans no write, for any selected kind; an info or a warning never changes the exit code.

## The manifest

With `--manifest` each drawing file is an entry of its kind with `layer` `null`, `tool`
`kicad-cli <version>`, the board's SHA-256 in `from` and the level of the drawing kinds as `evidence`. A
drawing follows its board like a Gerber does: it is `checked` when the board is, and stale when the board
changes. `from` names neither the specification nor the drawing sheet, so a changed specification does
not mark a drawing stale: export again after you edit it.

Two exports of an unchanged board give equal `content_sha256` for every drawing file: the hash leaves
out the `/CreationDate` line of a PDF and the `Created on` line of the report (`result.repeat` is
`content` for both kinds).

## Limits

- Landscape A4 to A0 with `auto`; a board outside every page fails.
- 1:1 only, and one PDF per page.
- Tables are wider than their text needs.
- Assembly notes go on the top page only; drill maps carry no frame.
- No impedance table, no via-protection row and no bill of materials on a drawing.
- No hole positions or datums: your own dimensions on `Dwgs.User` are plotted.

## Evidence

The drawing kinds are `KICAD-VERIFIED`: the probes of `docs/evidence/kicad-drawings.md` hold on `kicad-cli`
9.0.9 and 10.0.6 (CI run 37772583226, 2026-10-08). The level covers that KiCad draws the items Fenolite writes where
the layout puts them and that the drill table agrees with KiCad's report; the tables state model values.
