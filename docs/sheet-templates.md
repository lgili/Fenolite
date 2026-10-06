# Sheet templates (`*.sheet.toml`)

A sheet template describes a drawing sheet (frame, reference zones, title block, optional logo) in a
small, closed TOML format. `fenolite template build` turns it into a `.kicad_wks` that KiCad 9.0 and 10.0
load, with the same bytes for both. The normative text is the openspec capability `sheet-templates`; the
decision record is [ADR-0005](adr/0005-sheet-templates.md).

```bash
fenolite template build my.sheet.toml --target kicad --out my.kicad_wks --dry-run   # plan and prediction
fenolite template build my.sheet.toml --target kicad --out my.kicad_wks --confirm   # write it
```

The command runs no `kicad-cli`, so its evidence is `INFERRED`; the constructs it writes are verified by
the drawing-sheet oracle in `tests/kicad/sheets/`. To use the sheet on a board, name it in the board's
project (`Board.sheet.drawing_sheet`, written to `pcbnew.page_layout_descr_file` by `write_triad`) or pass
it to `kicad-cli pcb export … --drawing-sheet`.

## How a sheet fits several sizes

Every point is an offset from one corner of the **margin box** (the page minus the margins), positive
toward the interior: `lt` (left-top), `lb`, `rt` and `rb` (right-bottom). So one sheet serves every size
it lists. Reference-zone labels are counted **from the frame corners**: this is a Fenolite choice, because
ISO 5457 counts fields from the centring axes, which no corner can express for two sizes, and centring
marks are not drawn. No example claims conformance with any standard.

## Tables and keys

Lengths are millimetres, read exactly; a length must be a whole number of micrometres. There are no
expressions and no includes, and any key outside this table is an error.

| table | keys |
|---|---|
| `[provenance]` | `sources` (list of `S-NNNN`), `licence`, and the table `[provenance.values]` |
| `[sheet]` | `name`, `sizes` (`A0` … `A5`, `Letter`, `Legal`, `Tabloid`, `custom`), `width` and `height` (only with `custom`), `orientation` (`landscape`, the default, or `portrait`), `text_size`, `line_width`, `text_line_width` |
| `[margins]` | `left`, `right`, `top`, `bottom` |
| `[frame]` | `line_width`, `zones` (`true`/`false`), and with zones `zone_pitch`, `zone_band`, `zone_line_width`, `zone_text_size` |
| `[bitmap]` (optional) | `path` (relative to the specification, no `..`), `corner`, `x`, `y`, `scale` |
| `[title_block]` (optional) | `corner`, `columns` (widths left to right), `rows` (heights top to bottom), `line_width`, `label_size`, and `[[title_block.cell]]` items with `row`, `col`, `span`, `label`, `token`, `font_size`, `justify` (`left`, `center`, `right`) |

- **Zones.** With `zones = true`, an inner rectangle is drawn `zone_band` inside the frame, numbers run
  along the top and bottom bands and letters along the left and right bands, one field every
  `zone_pitch`. The letters stop at `H`, so a size needing more than 8 letter rows is refused
  (`template.zone-letters`); A3 in either orientation and A2 landscape pass with a 50 mm pitch.
- **Title block.** A grid anchored at `title_block.corner` (inside the zone band when there are zones).
  Row 0 is the top row and column 0 the leftmost column, whatever the corner. A cell may `span` columns;
  no line is drawn inside a spanned cell. A cell shows its `label` (small, at the top) and its `token`
  (`title`, `doc_id`, `revision`, `sheet`, `sheets`, `date`, `organization`, `responsible`, `approver`,
  `filename`, `paper`, or `param:NAME`).
- **Tokens.** Texts hold neutral tokens; KiCad shows the board's title block, its paper name, its file
  name, the sheet numbers, and project text variables for `{param:NAME}`. Write `{{` and `}}` for literal
  braces.

## Provenance

User specifications need no provenance. The examples shipped with Fenolite are loaded with
`require_provenance=True`: every number (and every array of numbers, such as `title_block.columns`) must
appear in `[provenance.values]` as `fenolite-choice` or as a source id listed in `[provenance] sources`;
grid indices (`row`, `col`, `span`) are exempt. The shipped examples may cite only S-0077, S-0078 and
S-0079 (see `docs/formats/sheets.md`).

## Examples

`fenolite.templates.EXAMPLES` names the CC0 examples; `example_path(name)` gives their path.

- `iso5457_generic`: A4 and A3 landscape, a zoned frame (20 mm filing margin, 10 mm elsewhere, 0.7 mm
  frame, 50 mm fields, 3.5 mm labels) and a 180 mm title block with ISO 7200 data field names as labels.
- `letter_generic`: Letter and Tabloid landscape, a plain frame with 12.7 mm margins and the same title
  block.

## Problems and exit codes

Every problem is reported at once: the command exits 3 with `FEN-3004`, the error's `where` names the file
and the key path of the first problem, and the envelope's `issues` hold one `template.*` issue per problem:

| code | when |
|---|---|
| `template.unknown-key` | a key or table outside the closed set |
| `template.bad-value` | a wrong type or value, a missing required key, or a TOML syntax error |
| `template.resolution` | a length that is not a whole number of micrometres |
| `template.unknown-token` | a cell `token` or a `label` that is not a valid token text |
| `template.unproven-value` | a number missing from `[provenance.values]` when provenance is required |
| `template.cell-overlap` / `template.cell-outside` | cells covering one grid position, or leaving the grid |
| `template.zone-letters` | more than 8 letter rows on a listed size |
| `template.bitmap-not-png` | a `[bitmap]` file without the PNG signature |
| `template.too-wide` (warning) | a title block wider or taller than the margin box of a listed size |

## Importing an Altium sheet template

Change c0046 reads a sheet template of the second backend. It does not build from a `*.sheet.toml`: an
Altium template is free graphics, so it becomes a neutral drawing sheet directly (ADR-0005, "a
second-backend token map").

```
fenolite template import SRC --target kicad --out OUT [--dry-run | --confirm] [--allow-lossy]
```

`SRC` is a `.SchDot`, or a `.SchDoc` with an applied template, in the binary or the ASCII form; the form is
taken from the content, never from the extension. `OUT` is the `.kicad_wks` to write. In Python,
`fenolite.backends.altium.read.sheet.import_sheet(data, name=…, allow_lossy=…)` returns the neutral
`DrawingSheet` with the same report and writes nothing. The command exits 3 with `FEN-3004` when the file is
not an Altium schematic or its record 0 is not the sheet record, and 7 with `FEN-7001` for a loss.

**What is imported.**

- The size: the 18 sheet styles, the custom size and the orientation. The drawing area of a style is a
  little smaller than its paper; the importer centres it, so the sheet fits the paper of the same name (A4
  to A0, Letter, Legal, Tabloid). Any other style and a custom sheet give the paper `custom`.
- Lines, rectangles, polylines and polygons (as lines), and text labels with their justification, quarter-turn
  rotation, bold and italic. Each item is anchored to the corner nearest to it, so a title block stays in
  its corner on another page size.
- Special strings: `=Title`, `=DocumentNumber`, `=Revision`, `=SheetNumber`, `=SheetTotal`, `=Date`,
  `=Organization`, `=DrawnBy`, `=ApprovedBy` and `=DocumentName` become `{title}`, `{doc_id}`, `{revision}`,
  `{sheet}`, `{sheets}`, `{date}`, `{organization}`, `{responsible}`, `{approver}` and `{filename}`, without
  regard to letter case. Any other parameter name becomes `{param:NAME}`: give it a value as a title-block
  parameter of the board.
- An embedded PNG image, at the centre of its box.
- The border and the reference zones of a custom sheet, drawn from the sheet flags by Fenolite's own rule.

**What is reported.** Every record of the template is imported or named in an issue with its record number
(`where` is `record[<n>]`, counted from the sheet record, which is 0). A warning is a loss: without
`--allow-lossy` the command writes nothing and exits 7; with it, the sheet is written without the reported
parts. An info never blocks.

| code | severity | when |
|---|---|---|
| `altium.sheet.not-representable` | warning | an arc, an ellipse, a Bézier, a rounded rectangle, a text frame or a note: the neutral sheet has lines, rectangles, texts and bitmaps only |
| `altium.sheet.not-template-content` | warning | a record that is not sheet graphics (a component, a wire, a port, a harness record), with the records it owns |
| `altium.sheet.builtin-not-drawn` | warning | the border or zones of a standard style, a border without a margin, or the built-in title block: no public source gives that geometry |
| `altium.sheet.outside` | warning | a record with a point outside the drawing area |
| `altium.sheet.image-not-kept` | warning | a linked image, an embedded image whose file is missing, or one that is not a PNG; only the base name of the file is shown |
| `altium.sheet.image-size` | warning | a kept image: the neutral bitmap has no box, so it is drawn at its own size |
| `altium.sheet.unknown-string` | warning | a text that starts with `=` without a parameter name (a space, an expression); kept as literal text |
| `altium.sheet.dynamic-string` | warning | a string whose value the source tool computes, such as `=CurrentDate`; kept as `{param:NAME}` |
| `altium.sheet.style-dropped` | warning | a fill, a line style, a line-end shape, an underline, a mirror or an unknown line width or justification |
| `altium.sheet.appearance` | info | colours and font names are not kept (once) |
| `altium.sheet.rounded` | info | lengths rounded to the micrometre, with their count (once) |
| `altium.sheet.builtin-drawn` | info | a border drawn from the sheet flags (once) |

**Adding a frame.** Most templates use a standard style with the border switched on, and that border is the
tool's, not the file's: it is reported and not drawn. Either draw the frame in the template with four lines
or a rectangle before importing, or use a custom sheet size with a margin width, whose border the importer
draws. Text widths differ between tools, since neither model holds font metrics: check the plot of a long
value.

**Not included.** Writing a `.SchDot` from a sheet specification is not part of this change; it is the
roadmap item "Sheet templates for the second backend, from the same sheet spec as c0012" (`docs/roadmap.md`,
v0.4). No template is shipped, and no template of any organisation is committed: the tests build theirs in
memory. Facts and Fenolite's own rules are in `docs/formats/altium/sheet-template.md`; every format fact is
`INFERRED`, and the command's evidence stays `INFERRED` (`H-A-RD-SHT-SAME`, `H-K-WKS-CORNER`).
