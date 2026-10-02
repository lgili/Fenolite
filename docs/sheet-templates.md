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
