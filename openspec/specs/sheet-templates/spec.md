# sheet-templates Specification

## Purpose
Specify the closed `*.sheet.toml` format for drawing sheets (frame, reference zones, title-block grid and optional logo) with per-number provenance, the builder that turns it into a neutral `DrawingSheet`, the layout prediction of what a backend draws, the `fenolite template build` command, the CC0 examples shipped with Fenolite and the decision record that governs them.
## Requirements
### Requirement: Sheet specification files
`fenolite.templates.load_spec(source, *, file="", require_provenance=False)` SHALL read a `*.sheet.toml` specification, given as an `os.PathLike` or as text, with `tomllib.loads(text, parse_float=Decimal)` and return a `SheetSpec` whose lengths are integer nanometres converted exactly from millimetres.
- The key set MUST be closed:

| table | keys |
|---|---|
| `[provenance]` | `sources`, `licence`, and the table `[provenance.values]` |
| `[sheet]` | `name`, `sizes`, `width`, `height`, `orientation`, `text_size`, `line_width`, `text_line_width` |
| `[margins]` | `left`, `right`, `top`, `bottom` |
| `[frame]` | `line_width`, `zones`, `zone_pitch`, `zone_band`, `zone_line_width`, `zone_text_size` |
| `[bitmap]` (optional) | `path`, `corner`, `x`, `y`, `scale` |
| `[title_block]` (optional) | `corner`, `columns`, `rows`, `line_width`, `label_size`, and the array `[[title_block.cell]]` with `row`, `col`, `span`, `label`, `token`, `font_size`, `justify` |

- `sizes` MUST be a non-empty list of `A0` … `A5`, `Letter`, `Legal`, `Tabloid` and `custom`. `width` and `height` MUST be given exactly when `custom` is listed. `orientation` MUST be `landscape` (the default) or `portrait`. `corner` MUST be `lt`, `lb`, `rt` or `rb` (the default). `justify` MUST be `left` (the default), `center` or `right`. A cell `token` MUST be one name of `SHEET_TOKENS` or `param:NAME`; the builder writes it as `{token}`. A `label` MUST be accepted by `split_tokens`.
- Lengths MUST be millimetres. A length that is not a whole number of micrometres MUST be the error `template.resolution`. The format has no expressions and no includes.
- Every problem MUST be collected, and the loader MUST raise one `TemplateError` (a subclass of `fenolite.core.errors.FormatError`) whose `locator` is the TOML key path of the first problem in file order (`frame.zone_pitch`, `title_block.cell[2].token`), whose message names every code and key path, and whose `issues` is a tuple of `Issue`, one per problem. A TOML syntax error MUST raise `TemplateError` at once with the code `template.bad-value` and the parser's line and column in the message.
- `fenolite.templates.ISSUE_CODES` SHALL be the closed table of template codes:

| code | severity | when |
|---|---|---|
| `template.unknown-key` | error | a key or table outside the closed set |
| `template.bad-value` | error | a value of the wrong type or outside its set, or a TOML syntax error |
| `template.resolution` | error | a length that is not a whole number of micrometres |
| `template.unknown-token` | error | a cell `token` or a `label` that `split_tokens` refuses |
| `template.unproven-value` | error | a numeric key path missing from `[provenance.values]` when provenance is required |
| `template.cell-overlap` | error | two title-block cells covering the same grid position |
| `template.cell-outside` | error | a cell whose row, column or span leaves the grid |
| `template.zone-letters` | error | a zoned specification whose largest size needs more than 8 letter rows |
| `template.bitmap-not-png` | error | a `[bitmap]` file that does not start with the PNG signature |
| `template.too-wide` | warning | a title-block grid wider or taller than the margin box of a listed size |

#### Scenario: Exact millimetres
- **GIVEN** a specification with `[margins]` `left = 20`, `right = 10.005`, `top = 10`, `bottom = 10`
- **WHEN** `load_spec(text)` is called
- **THEN** `spec.margins == (20_000_000, 10_005_000, 10_000_000, 10_000_000)` and no float is created

#### Scenario: Every problem reported at once
- **GIVEN** a specification whose problems, in file order, are the unknown key `frame.colour`, `margins.left = 0.0005` and a cell with `token = "owner"`
- **WHEN** `load_spec(text)` is called
- **THEN** `TemplateError` is raised with `locator == "frame.colour"` and `issues` holding `template.unknown-key`, `template.resolution` and `template.unknown-token`, each naming its key path

#### Scenario: Custom size needs its dimensions
- **GIVEN** a specification with `sizes = ["custom"]` and no `height`
- **WHEN** `load_spec(text)` is called
- **THEN** `TemplateError` is raised with an issue `template.bad-value` naming `sheet.height`

#### Scenario: Malformed input exit code
- **GIVEN** a specification file with an unknown key
- **WHEN** `fenolite template build bad.sheet.toml --target kicad --out out.kicad_wks --dry-run --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3004`, the error's `where` names the file and the key path, and the envelope's `issues` hold `template.unknown-key` naming the key path

### Requirement: Template values carry provenance
`load_spec(..., require_provenance=True)` SHALL require that every key path whose value is a number or an array of numbers, except the grid indices `row`, `col` and `span`, is a key of `[provenance.values]`.
- A key path MUST name array-of-table items by index (`title_block.cell[2].font_size`); a numeric array counts as one path (`title_block.columns`).
- Each value MUST be `fenolite-choice` or an id of the form `S-NNNN` that is listed in `[provenance] sources`. Any other value, and a missing path, MUST give `template.unproven-value` naming the key path.
- `[provenance] licence` MUST be present when provenance is required.
- With `require_provenance=False`, the default for user specifications, `[provenance]` is optional and is not checked.

#### Scenario: Missing number refused
- **GIVEN** a specification whose `[provenance.values]` lists every number except `frame.zone_pitch`
- **WHEN** `load_spec(text, require_provenance=True)` is called
- **THEN** `TemplateError` is raised with one issue `template.unproven-value` naming `frame.zone_pitch`

#### Scenario: Unlisted source refused
- **GIVEN** a specification whose `[provenance.values]` maps `margins.left` to `S-0077` while `[provenance] sources` lists only `S-0079`
- **WHEN** `load_spec(text, require_provenance=True)` is called
- **THEN** `TemplateError` is raised with an issue `template.unproven-value` naming `margins.left`

#### Scenario: User specification without provenance
- **GIVEN** a specification without a `[provenance]` table
- **WHEN** `load_spec(text)` is called
- **THEN** it returns a `SheetSpec` whose `provenance` is empty

### Requirement: Frame, reference zones and title-block grid
`fenolite.templates.build_sheet(spec, *, base_dir=None, issues=None)` SHALL return a `DrawingSheet` built only from corner-anchored points, so that one sheet serves every listed size.
- `setup` MUST hold the specification's text size, line widths and margins.
- The frame MUST be one `SheetShape` of kind `rect` from `SheetPoint("lt", 0, 0)` to `SheetPoint("rb", 0, 0)`, with width `frame.line_width`.
- With `zones = true`, the builder MUST add an inner `SheetShape` of kind `rect` inset by `zone_band`, and a zone band of tick lines and labels repeated at `zone_pitch`. Number ticks and labels MUST run along x from the `lt` and `lb` corners, and letter ticks and labels along y from the `lt` and `rt` corners. The label of field k (k = 0, 1, …) MUST be centred at `k × zone_pitch + zone_pitch / 2` from its corner along the band and centred across the band, with size `zone_text_size`. Number labels MUST start at `1` and letter labels at `A`, stepped with `SheetRepeat.label_step = 1`. Each repeat count MUST cover the largest listed size; KiCad does not draw copies whose start point leaves the margin box (`H-K-WKS-REPEAT`). The zone origin at the frame corners is a Fenolite choice: ISO 5457 measures fields from the centring axes (S-0077), and centring marks are not drawn.
- `load_spec` MUST give `template.zone-letters` for a zoned specification with a listed size whose margin-box height divided by `zone_pitch`, rounded up, exceeds 8, so that the letters stop at `H` and `I` and `O` never occur. Sizes up to A3 in either orientation, and A2 landscape, pass with 10 mm top and bottom margins and a 50 mm pitch.
- The title block MUST be a grid anchored at `title_block.corner`, with `columns` widths left to right and `rows` heights top to bottom, whatever the corner. Row 0 is the top row and column 0 the leftmost column. The builder MUST draw the outer rectangle and the cell borders with `title_block.line_width`, without lines inside a spanned cell. Each cell MUST get its `label` at `label_size` and its value text `{token}` at `font_size` (the setup text size when absent) with its `justify`; every text of a cell MUST lie inside the cell's rectangle.
- A grid wider or taller than the margin box of a listed size MUST add the warning `template.too-wide` to `issues`; the sheet is still built.

#### Scenario: Zone labels on A4 and A3
- **GIVEN** a test specification with sizes `A4` and `A3` landscape, margins 20 mm left and 10 mm elsewhere, `zones = true` and `zone_pitch = 50`
- **WHEN** it is built and `layout` predicts it on 297 x 210 mm and on 420 x 297 mm pages
- **THEN** the A4 prediction holds the number labels `1` to `5` on each of the two bands and the letters `A` to `D` on each side, and the A3 prediction holds `1` to `8` and `A` to `F`

#### Scenario: Too many letter rows
- **GIVEN** a zoned specification with sizes `A2` portrait and `zone_pitch = 50`
- **WHEN** `load_spec(text)` is called
- **THEN** `TemplateError` is raised with an issue `template.zone-letters`

#### Scenario: Overlapping cells
- **GIVEN** a title block with cells `{row = 0, col = 0, span = 2}` and `{row = 0, col = 1}`
- **WHEN** the specification is loaded
- **THEN** `TemplateError` is raised with an issue `template.cell-overlap` naming `title_block.cell[1]`

#### Scenario: Cell texts inside their cells
- **GIVEN** the shipped example `iso5457_generic`
- **WHEN** it is built and laid out on an A4 landscape page
- **THEN** every predicted text of a title-block cell lies inside the rectangle of that cell

### Requirement: Optional logo bitmap
When a specification has a `[bitmap]` table, `build_sheet` SHALL read the file named by `bitmap.path`, relative to `base_dir` (the folder of the specification file), and add one `SheetBitmap` at `SheetPoint(corner, x, y)` with the file's bytes as base64 text and `scale` as integer parts per million.
- Problems MUST be raised as one `TemplateError`, as for the loader. A `path` that is absolute or holds a `..` segment, or a file that cannot be read, MUST give `template.bad-value` naming `bitmap.path`.
- A file whose first eight bytes are not the PNG signature MUST give `template.bitmap-not-png`.
- A `scale` that is not a whole number of parts per million MUST give `template.bad-value` naming `bitmap.scale`.
- Only loading is verified for bitmaps; KiCad plots them to PDF and PostScript only (S-0075), so `layout` counts them and draws nothing for them.

#### Scenario: PNG logo embedded
- **GIVEN** a specification with `[bitmap]` `path = "logo.png"`, `corner = "lt"`, `x = 5`, `y = 5`, `scale = 1`, beside a 1x1 authored PNG
- **WHEN** it is built with `base_dir` set to that folder
- **THEN** the sheet holds one `SheetBitmap` with `pos == SheetPoint("lt", 5_000_000, 5_000_000)`, `scale_ppm == 1_000_000` and `base64.b64decode(png)` equal to the file's bytes

#### Scenario: Not a PNG
- **GIVEN** the same specification whose `logo.png` holds the text `GIF89a`
- **WHEN** it is built
- **THEN** `TemplateError` is raised with an issue `template.bitmap-not-png`

### Requirement: Sheet layout prediction
`fenolite.templates.layout(sheet, *, width, height, page=1)` SHALL return a `SheetLayout(texts, lines, bitmaps)` that predicts what KiCad draws for `sheet` on a page of `width` x `height` nm, and `resolve_text(text, block, *, paper, filename, sheet=1, sheets=1)` SHALL return the string KiCad shows for a neutral text on a board.
- A `SheetPoint` MUST map to page coordinates inside the margins: `lt` to (left + x, top + y), `rt` to (width − right − x, top + y), `lb` to (left + x, height − bottom − y) and `rb` to (width − right − x, height − bottom − y) (`H-K-WKS-CORNER`).
- Copy i of a repeated item MUST be offset by i times its steps in the same corner frame. Copies MUST stop at `count` or at the first copy whose start point leaves the margin box. A one-letter text MUST step through the alphabet by `label_step` per copy, and a decimal-integer text by adding `label_step` per copy (`H-K-WKS-REPEAT`: S-0075 states the step for one letter or one digit, and `wks-repeat` measures stepping past `9`).
- On page 1, items of scope `all` and `first_only` MUST be drawn and items of scope `not_first` MUST NOT (`H-K-WKS-PAGE1`).
- `texts` MUST hold one `PlacedText(text, x, y, size)` per drawn text, with the neutral text after the label step. `lines` MUST hold one `PlacedLine` per drawn line and four per drawn rectangle. `bitmaps` MUST count the drawn bitmaps. All values are exact integers.
- `resolve_text` MUST replace `{title}`, `{date}`, `{revision}`, `{organization}`, `{doc_id}`, `{responsible}` and `{approver}` with the fields of `block`, `{paper}` with `paper` (the board's paper name as written), `{filename}` with `filename`, `{sheet}` and `{sheets}` with their numbers, `{param:NAME}` with `block.params[NAME]`, and `{{`/`}}` with single braces. A parameter absent from `block.params` MUST stay as written (`{param:NAME}`).
- The caller MUST pass the page size. The oracle uses the size read from KiCad's SVG, so no KiCad size table is copied. `layout` and `resolve_text` MUST import only `fenolite.model` and `fenolite.core`.

#### Scenario: Default corner is bottom-right
- **GIVEN** a sheet with margins of 10 mm and a `SheetText` at `SheetPoint("rb", 5_000_000, 3_000_000)`
- **WHEN** `layout(sheet, width=297_000_000, height=210_000_000)` is called
- **THEN** the text is placed at (282_000_000, 197_000_000)

#### Scenario: Copies stop at the margin box
- **GIVEN** a sheet with margins of 10 mm and a `SheetText` `"A"` at `SheetPoint("lt", 0, 10_000_000)` with `SheetRepeat(count=10, step_y=50_000_000, label_step=1)`
- **WHEN** it is laid out on a 297 x 210 mm page
- **THEN** exactly four copies are predicted, with the texts `A`, `B`, `C` and `D`

#### Scenario: Tokens resolved
- **GIVEN** `TitleBlock(title="Bench", revision="B", params={"LOT": "7"})`
- **WHEN** `resolve_text("{title} rev {revision} lot {param:LOT} {sheet}/{sheets} {{x}}", block, paper="A4", filename="b.kicad_pcb")` is called
- **THEN** it returns `"Bench rev B lot 7 1/1 {x}"`

### Requirement: Sheets built from templates are deterministic
`build_sheet` SHALL use no random generator, no clock and no environment value, and SHALL produce no date.
- Building the same specification twice MUST give `DrawingSheet`s with equal canonical JSON, and writing them with `write_drawing_sheet` MUST give byte-identical text.
- `DrawingSheet.id` MUST be `derived_id("wks", "template", spec.name)`, and items MUST carry no ids.
- A built sheet written with `write_drawing_sheet` and read back with `read_drawing_sheet` MUST have `setup` and `items` equal to the built sheet's.

#### Scenario: Same specification, same bytes
- **GIVEN** the shipped example `iso5457_generic`
- **WHEN** it is loaded, built and written twice in separate processes
- **THEN** both texts are byte-identical, and both sheets have the same id

#### Scenario: Built sheet survives a round trip
- **GIVEN** the sheet built from `letter_generic`
- **WHEN** it is written for target 10 and read back
- **THEN** the read sheet's `setup` and `items` equal the built sheet's

### Requirement: Template build command
`fenolite template build SPEC --target kicad --out OUT` SHALL be a mutating command (`fenolite.cli.cmd_template.COMMAND`, name `template`, schema `fenolite.template.v0`) that loads `SPEC` with `load_spec`, builds it with `build_sheet` and writes `OUT` with `write_drawing_sheet` through the mutation protocol of `cli-contract`.
- `--target` and `--out` MUST be given; `--out` MUST also accept the short form `-o`, and `--target` with any value other than `kicad` MUST exit 2. The global `--kicad-version {9,10}` MUST select the emit-check target only; the written bytes do not depend on it. The global `--allow-lossy` MUST be passed to the writer.
- `result` MUST hold `sheet` (`name`, `sizes`, `items`, `tokens`), `target`, `kicad_version`, `drawn` and `output`, and also `plan` on a `--dry-run` or unconfirmed run, as the dispatcher adds it; a confirmed run carries the `receipt` instead. `drawn` MUST give, per listed size, the text and line counts that `layout` predicts on that size's page, and the texts resolved by `resolve_text` with an empty `TitleBlock`. The page of a named size is its `PAPER_SIZES` entry in the specified orientation; the page of `custom` is the specification's `sheet.width` by `sheet.height`.
- Exit codes MUST be: 0 ok; 2 usage; 3 with `FEN-3004` for a malformed specification and with `FEN-3001` for a missing or unreadable one; 4 without `--confirm` (`FEN-4001`); 7 for a writer refusal (`FEN-7001`). No new FEN code is added.
- The command MUST NOT run `kicad-cli`. Its envelope evidence MUST be `INFERRED` with the hypothesis `H-K-WKS-CORNER`.
- `build` MUST be a positional argument of the `template` parser with the single choice `build`, followed by `SPEC`, `--target` and `--out`, not a nested sub-parser: the dispatcher adds the global options, `--dry-run` and `--confirm` to the command's own parser only, so they MUST parse after `build SPEC …`.
- `example_args` and `mutation_example_args` MUST resolve `example_path("iso5457_generic")`, so that the consistency test stays hermetic. `example_args` MUST end with `--dry-run`, because the consistency test expects exit 0 from them; `mutation_example_args` MUST NOT hold `--dry-run` or `--confirm`. `fenolite capabilities` MUST list `template` with `mutates` true.

#### Scenario: Confirmation required
- **WHEN** `uv run fenolite template build src/fenolite/templates/examples/iso5457_generic.sheet.toml --target kicad --out out.kicad_wks --json` runs
- **THEN** the exit code is 4, stderr carries `FEN-4001`, and `out.kicad_wks` does not exist

#### Scenario: Dry run predicts the drawing
- **WHEN** the same command runs with `--dry-run`
- **THEN** the exit code is 0, `result.plan` lists `out.kicad_wks`, `result.drawn` has entries for `A4` and `A3`, and nothing is written

#### Scenario: Confirmed write
- **WHEN** the same command runs with `--confirm`, then again with `-o out.kicad_wks` in place of `--out out.kicad_wks` and `--confirm --kicad-version 9`
- **THEN** both runs exit 0, `result` holds no `plan`, `receipt.written[0].sha256` is the SHA-256 of the file, the file starts with `(kicad_wks (version 20231118) (generator "fenolite")`, and both runs write byte-identical files

#### Scenario: Unknown target
- **WHEN** the same command runs with `--target other --dry-run`
- **THEN** the exit code is 2

### Requirement: Shipped sheet examples
`fenolite.templates.EXAMPLES` SHALL be `("iso5457_generic", "letter_generic")`, and `example_path(name)` SHALL return the path of `src/fenolite/templates/examples/<name>.sheet.toml`, shipped as package data.
- `iso5457_generic` MUST list sizes `A4` and `A3` landscape, with a zoned frame and a title block whose labels are ISO 7200 data field names (S-0078). Its geometry MUST come from S-0077, S-0078 and S-0079 or be `fenolite-choice`. The naming gate (c0012 task 1.3) checks each value against the preview it cites. If a value is not visible on S-0077 as registered, the example MUST be named `a_series_generic`, every value MUST be `fenolite-choice`, and `EXAMPLES` MUST name it instead. S-0078 is gated fact by fact: the labels MAY be ISO 7200 data field names only when those names are visible on the S-0078 preview, and MUST otherwise be Fenolite-choice labels listed as such in `docs/formats/sheets.md`; the title-block width MAY cite S-0078 only when the preview text gives it, and MUST otherwise be `fenolite-choice`. No example claims ISO conformance.
- `letter_generic` MUST list sizes `Letter` and `Tabloid` landscape, with no zones and 12.7 mm margins labelled `fenolite-choice`.
- Each example MUST start with the line `# SPDX-License-Identifier: CC0-1.0` and MUST load with `require_provenance=True`.
- `tests/residue/test_template_residue.py` MUST check, as an allowlist, that every `[provenance.values]` entry of an example is `fenolite-choice` or one of S-0077, S-0078 and S-0079, and that each cited id is registered in `docs/evidence/sources.md`; that every text is a neutral token, a label listed in `docs/formats/sheets.md` (as an ISO 7200 label, or as a Fenolite-choice label after the naming gate), or a one-character zone label; and that `tools/residue/scan.py` finds nothing in the written `.kicad_wks`. No test of this change reads a kicad-templates sheet or KiCad's default sheet.

#### Scenario: Examples load with provenance
- **WHEN** `load_spec(example_path(name), require_provenance=True)` is called for each name of `EXAMPLES`
- **THEN** each returns a `SheetSpec` and no issue is produced

#### Scenario: Residue check
- **WHEN** `uv run pytest tests/residue/test_template_residue.py` runs
- **THEN** it passes, and it fails when a test copy of an example maps one value to `S-0066`, maps one value to `S-0058` (the KiCad demo files), or adds a text that is not a token, a listed label or a zone label

### Requirement: Sheet templates decision record
`docs/adr/0005-sheet-templates.md` SHALL record the decisions of this change: the neutral `DrawingSheet` in the model, neutral tokens with the KiCad map in the backend, the closed TOML format, per-number provenance, the corner-anchored zone origin as a Fenolite choice, the use of the ISO 5457 and ISO 7200 public previews for facts only (S-0077, S-0078), and the absence of any conformance claim.
- The change MUST write the ADR with `Proposed` under `## Status`. Only the maintainer MAY set `Accepted (<date>)`, in their own commit, after reviewing the ADR, both examples and their provenance tables, and adding a `LEGAL-ANNEX.md` row for the review. The change MUST NOT be archived before that commit.
- `tests/unit/test_adrs.py` MUST list `0005-sheet-templates.md` in `REQUIRED`, and the ADR index in `docs/adr/README.md` MUST have its row.

#### Scenario: ADR present
- **WHEN** `uv run pytest tests/unit/test_adrs.py` runs
- **THEN** it passes with `0005-sheet-templates.md` in `REQUIRED`

#### Scenario: Status set by the maintainer only
- **GIVEN** the change's own commits
- **WHEN** `grep -A1 '^## Status' docs/adr/0005-sheet-templates.md` runs on them
- **THEN** it prints `Proposed`; `Accepted (<date>)` appears only in the maintainer's commit, together with a matching `LEGAL-ANNEX.md` row

