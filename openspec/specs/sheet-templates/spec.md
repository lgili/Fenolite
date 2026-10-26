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
`fenolite template build SPEC --target kicad|altium --out OUT` SHALL be a mutating command (`fenolite.cli.cmd_template.COMMAND`, name `template`, schema `fenolite.template.v0`) that loads `SPEC` with `load_spec`, builds it with `build_sheet` and writes `OUT` through the mutation protocol of `cli-contract`: with `write_drawing_sheet` for the target `kicad`, and as requirement "Template build for Altium" says for the target `altium`.
- `--target` and `--out` MUST be given; `--out` MUST also accept the short form `-o`, and `--target` with any value other than `kicad` and `altium` MUST exit 2. The global `--kicad-version {9,10}` MUST select the emit-check target only; the written bytes do not depend on it. The global `--allow-lossy` MUST be passed to the writer.
- `result` MUST hold `sheet` (`name`, `sizes`, `items`, `tokens`), `target`, `kicad_version`, `drawn` and `output`, and also `plan` on a `--dry-run` or unconfirmed run, as the dispatcher adds it; a confirmed run carries the `receipt` instead. `drawn` MUST give, per listed size, the text and line counts that `layout` predicts on that size's page, and the texts resolved by `resolve_text` with an empty `TitleBlock`. The page of a named size is its `PAPER_SIZES` entry in the specified orientation; the page of `custom` is the specification's `sheet.width` by `sheet.height`.
- Exit codes MUST be: 0 ok; 2 usage; 3 with `FEN-3004` for a malformed specification and with `FEN-3001` for a missing or unreadable one; 4 without `--confirm` (`FEN-4001`); 7 for a writer refusal (`FEN-7001`). No new FEN code is added.
- The command MUST NOT run `kicad-cli`. Its envelope evidence MUST be `INFERRED` with the hypothesis `H-K-WKS-CORNER` for the target `kicad`.
- `build` MUST be a value of the positional argument `action` of the `template` parser, whose choices are `build` and `import` (requirement "Template import command"), followed by the positional file (`SPEC` for `build`, `SRC` for `import`), `--target` and `--out`. It MUST NOT be a nested sub-parser: the dispatcher adds the global options, `--dry-run` and `--confirm` to the command's own parser only, so they MUST parse after `build SPEC …`. Any other action MUST exit 2.
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

#### Scenario: Unknown action
- **WHEN** `uv run fenolite template export x --target kicad --out out.kicad_wks --dry-run --json` runs
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

### Requirement: Altium sheet template reading
`fenolite.backends.altium.read.sheet.import_sheet(data, *, file="", name="imported", allow_lossy=False)` SHALL read the bytes of an Altium sheet template with `fenolite.backends.altium.read.sch.read_schematic` (change c0040) and return a `SheetImport(sheet, source, issues, imported, reported, strings, parameters)` whose `sheet` is a neutral `DrawingSheet`.
- The form (binary compound file or ASCII) MUST be taken from the content, as the reader does. The importer MUST NOT read the file extension: a `.SchDot` is a schematic document saved under another file type (`H-A-RD-SHT-SAME`).
- Record 0 MUST be the sheet record (`RECORD=31`). Otherwise the importer MUST raise `fenolite.core.errors.FormatError` with the locator `record[0]`. A reader error MUST pass through unchanged.
- The *template records* MUST be every record other than record 0 that has no owner, and every record whose owner is a template record of kind 39 (`H-A-RD-SHT-OWNER`). A record of kind 39 itself and a sheet-level parameter (kind 41) are template records that draw nothing. A record owned by any other record belongs to its top-level owner and is reported with it.
- `source` MUST be a `SheetSource(form, style, paper, portrait, width, height)`: `form` is `binary` or `ascii`, `style` is the `SHEETSTYLE` number or `None` for a custom sheet, and `width` and `height` are the drawing area in nanometres as oriented.
- `sheet.name` MUST be `name`, `sheet.id` MUST be `derived_id("wks", "altium", name)`, and items MUST carry no ids.
- `parameters` MUST hold the names of the sheet-level parameters, sorted, without their values. `strings` MUST be a tuple of pairs (special string, neutral text).
- `import_sheet` MUST write nothing, MUST NOT open any other file, and MUST use no clock, random generator or environment value. Two calls on the same bytes MUST return sheets with equal canonical JSON.
- The module MUST import only `fenolite.core`, `fenolite.model`, `fenolite.backends.altium` and the standard library.

#### Scenario: The extension does not matter
- **GIVEN** the bytes of the authored template `title_block` in the binary form
- **WHEN** `import_sheet(data, file="t.SchDot")` and `import_sheet(data, file="t.SchDoc")` are called
- **THEN** both return sheets with equal canonical JSON and `source.form == "binary"`

#### Scenario: Binary and ASCII forms agree
- **GIVEN** the authored template `title_block` encoded in the binary form and in the ASCII form
- **WHEN** both are imported
- **THEN** the two sheets have equal `setup` and `items`, and `source.form` is `binary` and `ascii`

#### Scenario: Graphics of an applied template
- **GIVEN** an authored schematic whose record 1 is a template record (kind 39) that owns two lines and one label
- **WHEN** it is imported
- **THEN** the sheet holds two `SheetShape` and one `SheetText`, and `imported == {13: 2, 4: 1}`

#### Scenario: No sheet record
- **GIVEN** an authored ASCII file whose first record after the header is a line (kind 13)
- **WHEN** it is imported
- **THEN** `FormatError` is raised with the locator `record[0]`

### Requirement: Altium sheet size and margins
The importer SHALL derive the paper, the orientation and the `SheetSetup` from the sheet record.
- `fenolite.backends.altium.read.sheet.SHEET_STYLES` MUST be the closed table of the 18 styles, in units of 10 mil (`H-A-RD-SHT-AREA`):

| style | area | paper | style | area | paper | style | area | paper |
|---|---|---|---|---|---|---|---|---|
| 0 | 1150 × 760 | `A4` | 6 | 1500 × 950 | `custom` | 12 | 1700 × 1100 | `Tabloid` |
| 1 | 1550 × 1110 | `A3` | 7 | 2000 × 1500 | `custom` | 13 | 990 × 790 | `custom` |
| 2 | 2230 × 1570 | `A2` | 8 | 3200 × 2000 | `custom` | 14 | 1540 × 990 | `custom` |
| 3 | 3150 × 2230 | `A1` | 9 | 4200 × 3200 | `custom` | 15 | 2060 × 1560 | `custom` |
| 4 | 4460 × 3150 | `A0` | 10 | 1100 × 850 | `Letter` | 16 | 3260 × 2060 | `custom` |
| 5 | 950 × 750 | `custom` | 11 | 1400 × 850 | `Legal` | 17 | 4280 × 3280 | `custom` |

- A sheet record without `SHEETSTYLE` MUST read as style 0. A style above 17 MUST raise `FormatError` with the locator `record[0].SHEETSTYLE`.
- With `USECUSTOMSHEET=T`, the area MUST be `CUSTOMX` × `CUSTOMY`, the paper `custom` and `source.style` `None`. Without it, `CUSTOMX` and `CUSTOMY` MUST be ignored.
- `WORKSPACEORIENTATION=1` MUST swap the area's width and height and set `source.portrait`.
- For a named paper, the margins MUST centre the area on the page of `PAPER_SIZES` in the same orientation: left and right are half the width difference, top and bottom half the height difference. A named paper whose difference is negative or is not a whole number of micrometres per side MUST fall back to `custom` with four zero margins. A `custom` paper MUST have four zero margins.
- `setup.text_size` MUST be the size of the system font (`SYSTEMFONT`, converted as a text size; size 10 when the font table has no such entry), `setup.line_width` 254 000 nm and `setup.text_line_width` 127 000 nm. Every imported item MUST carry its own width or size, so these defaults change no drawing.
- Every length MUST be converted with the reader's exact unit and then rounded to the nearest micrometre, half to even. The number of rounded lengths of the imported records, of the custom size and of a drawn border's margin MUST be reported once as `altium.sheet.rounded`; the font-size rule, the divisions of the zones and the centre of an image box are not counted.

#### Scenario: A4 style centred on the paper
- **GIVEN** an authored ASCII template whose sheet record has `SHEETSTYLE=0` and no orientation key
- **WHEN** it is imported
- **THEN** `source` is `SheetSource("ascii", 0, "A4", False, 292_100_000, 193_040_000)`, the left and right margins are 2 450 000 nm and the top and bottom margins are 8 480 000 nm

#### Scenario: Custom portrait sheet
- **GIVEN** a sheet record with `USECUSTOMSHEET=T`, `CUSTOMX=1000`, `CUSTOMY=700` and `WORKSPACEORIENTATION=1`
- **WHEN** it is imported
- **THEN** `source.paper == "custom"`, `source.portrait` is true, `source.width == 177_800_000`, `source.height == 254_000_000` and the four margins are 0

#### Scenario: Unknown style refused
- **GIVEN** a sheet record with `SHEETSTYLE=18`
- **WHEN** it is imported
- **THEN** `FormatError` is raised with the locator `record[0].SHEETSTYLE`

#### Scenario: Fractional coordinate rounded and counted
- **GIVEN** an authored template with one line whose `LOCATION.X_FRAC` is `12345`
- **WHEN** it is imported
- **THEN** the line's start is a whole number of micrometres and `issues` holds one `altium.sheet.rounded` of severity `info` whose message gives the count 1

### Requirement: Altium border and reference zones
The importer SHALL draw the border and the reference zones that the sheet flags ask for only when the file gives their numbers, and SHALL report them otherwise (`H-A-RD-SHT-BORDER`).
- With `BORDERON=T`, `USECUSTOMSHEET=T` and `CUSTOMMARGINWIDTH` = m > 0, m being less than half the shorter side of the drawing area, the first two items MUST be a `SheetShape` of kind `rect` from `SheetPoint("lt", 0, 0)` to `SheetPoint("rb", 0, 0)` and one from `SheetPoint("lt", m, m)` to `SheetPoint("rb", m, m)`, both 254 000 nm wide.
- With also `REFERENCEZONESON=T`, `CUSTOMXZONES` = nx ≥ 1 and 1 ≤ `CUSTOMYZONES` = ny ≤ 26, the importer MUST add, after the two rectangles:
  - tick lines across the top and bottom bands at `i × width / nx` for i = 1 … nx − 1, and across the left and right bands at `j × height / ny` for j = 1 … ny − 1, each division rounded down to a micrometre;
  - the numbers `1` … `nx`, left to right, centred in each field of the top and of the bottom band;
  - the letters `A` … from the top, centred in each field of the left and of the right band;
  - labels of size m / 2, rounded down to a micrometre, justified `center` and `center`.
- The drawn border MUST be reported once as `altium.sheet.builtin-drawn` (info).
- A border asked for on a standard style, a border with m = 0 or with m not less than half the shorter side, zones with nx < 1, ny < 1 or ny > 26, zones asked for with a border that is asked for and not drawn, and `TITLEBLOCKON=T` MUST each give one `altium.sheet.builtin-not-drawn` (warning) whose message names `border`, `zones` or `title-block`, and MUST draw nothing for it: no public source gives that geometry.
- The ticks and labels MUST be anchored as every other item ("Altium sheet graphics"); only the two rectangles span two corners.

#### Scenario: Custom border with zones
- **GIVEN** a custom sheet of 1000 × 700 units with `BORDERON=T`, `CUSTOMMARGINWIDTH=20`, `REFERENCEZONESON=T`, `CUSTOMXZONES=4` and `CUSTOMYZONES=2`
- **WHEN** it is imported
- **THEN** the sheet starts with two rectangles, the second inset by 5 080 000 nm, followed by 8 tick lines and 12 labels (`1` to `4` twice, `A` and `B` twice), and `issues` holds `altium.sheet.builtin-drawn`

#### Scenario: Border of a standard style reported
- **GIVEN** a sheet record with `SHEETSTYLE=0`, `BORDERON=T` and `TITLEBLOCKON=T` and no other record
- **WHEN** it is imported with `allow_lossy=True`
- **THEN** the sheet has no item and `issues` holds two `altium.sheet.builtin-not-drawn` warnings, one naming `border` and one naming `title-block`

### Requirement: Altium sheet graphics
The importer SHALL turn the drawable template records into `SheetShape` and `SheetText` items, in record order, after the border items.
- The record kinds MUST map as follows:

| kind | record | neutral items |
|---|---|---|
| 13 | line | one `SheetShape` of kind `line` from `LOCATION` to `CORNER` |
| 14 | rectangle | one `SheetShape` of kind `rect` from `LOCATION` to `CORNER` |
| 6 | polyline | one `line` per pair of consecutive points |
| 7 | polygon | one `line` per pair of consecutive points, and one from the last point to the first |
| 4 | text label | one `SheetText` at `LOCATION` |

- `LINEWIDTH` 0 (or missing), 1, 2 and 3 MUST give the widths 102 000, 254 000, 508 000 and 1 016 000 nm (`H-A-RD-SHT-WIDTH`); any other value MUST give 254 000 nm and one `altium.sheet.style-dropped`.
- A point (x, y) of the drawing area, measured from its bottom-left corner with y upwards, MUST become, for the item's corner: `lb` (x, y), `rb` (width − x, y), `lt` (x, height − y), `rt` (width − x, height − y).
- The corner of an item MUST be chosen once for all its points from the centre (cx, cy) of the bounding box of its points: `l` when 2 × cx < width and `r` otherwise; `b` when 2 × cy < height and `t` otherwise (an item centred on the area therefore takes the right, top corner). A polyline or polygon MUST use one corner for all its lines. The sheet is therefore exact on its own size, and each item keeps its distance to the nearest corner on another size.
- A record with a point outside the drawing area MUST NOT be imported and MUST give `altium.sheet.outside`. A polyline or polygon with fewer than two points MUST NOT be imported and MUST give `altium.sheet.not-representable`.
- A label MUST map `JUSTIFICATION` 0 to 8 to (`vjustify`, `justify`) in the order bottom, center, top by left, center, right (0 is bottom-left, 4 center-center, 8 top-right; a missing key is 0), and `ORIENTATION` 0 to 3 to a rotation of 0, 90, 180 and 270 degrees in microdegrees (`H-A-RD-SHT-TEXT`). A `JUSTIFICATION` outside 0 to 8 MUST read as 0 and give `altium.sheet.style-dropped`; an `ORIENTATION` outside 0 to 3 MUST be taken modulo 4.
- A label's `size` MUST be (s, s) with s = `SIZE<FONTID>` of the sheet's font table × 25 400 000 / 72 nm, rounded to the nearest micrometre; `bold` and `italic` MUST come from `BOLD<FONTID>` and `ITALIC<FONTID>`. A `FONTID` outside the table MUST use the system font. The size rule is a Fenolite choice (`H-A-RD-SHT-TEXT`).
- A filled rectangle or polygon (`ISSOLID=T`), a line style other than solid, a line-end shape of a polyline (`STARTLINESHAPE`, `ENDLINESHAPE`), an underlined font and a mirrored label MUST be imported without that property and MUST each give `altium.sheet.style-dropped` naming the record and the property.
- Colours and font names MUST be reported once, as one `altium.sheet.appearance` (info) that gives the number of imported records with a colour key (`COLOR`, `AREACOLOR`, `TEXTCOLOR`) and the sorted font names of the sheet's font table. A template with neither MUST give no such issue.
- Every other graphic kind (Bézier 5, ellipse 8, pie 9, rounded rectangle 10, elliptical arc 11, arc 12, text frame 28, note 209) MUST give `altium.sheet.not-representable`, and every other record kind (a component, a wire, a port, …) MUST give `altium.sheet.not-template-content`. Neither is imported.

#### Scenario: Line near the bottom-right corner
- **GIVEN** an A4 template (style 0) with a line from (900, 10) to (1140, 10) units and `LINEWIDTH=1`
- **WHEN** it is imported
- **THEN** the item is `SheetShape("line", SheetPoint("rb", 63_500_000, 2_540_000), SheetPoint("rb", 2_540_000, 2_540_000), width=254_000)`

#### Scenario: Label with justification and rotation
- **GIVEN** the same template with a label at (20, 700) units, `JUSTIFICATION=8`, `ORIENTATION=1`, `TEXT=Notes`, and a font table whose font 1 has `SIZE1=10` and `BOLD1=T`
- **WHEN** it is imported
- **THEN** the item is a `SheetText` with text `Notes`, `pos == SheetPoint("lt", 5_080_000, 15_240_000)`, `size == (3_528_000, 3_528_000)`, `bold` true, `justify == "right"`, `vjustify == "top"` and `rotation == 90_000_000`

#### Scenario: Polygon closed with lines
- **GIVEN** a polygon record with three points and `ISSOLID=T`
- **WHEN** it is imported with `allow_lossy=True`
- **THEN** the sheet holds three lines with one corner, and `issues` holds one `altium.sheet.style-dropped` naming the record and `fill`

#### Scenario: Arc reported, not drawn
- **GIVEN** a template with one arc record (kind 12) at record index 3
- **WHEN** it is imported with `allow_lossy=True`
- **THEN** the sheet has no item for it and `issues` holds `altium.sheet.not-representable` with `where == "record[3]"`

### Requirement: Altium special strings
A label whose text starts with `=` SHALL be read as a special string, and the importer SHALL map its parameter name to a neutral token (`H-A-RD-SHT-STRINGS`).
- `fenolite.backends.altium.read.sheet.ALTIUM_SHEET_TOKENS` MUST be the closed map, matched without regard to letter case:

| special string | neutral token |
|---|---|
| `=Title` | `{title}` |
| `=DocumentNumber` | `{doc_id}` |
| `=Revision` | `{revision}` |
| `=SheetNumber` | `{sheet}` |
| `=SheetTotal` | `{sheets}` |
| `=Date` | `{date}` |
| `=Organization` | `{organization}` |
| `=DrawnBy` | `{responsible}` |
| `=ApprovedBy` | `{approver}` |
| `=DocumentName` | `{filename}` |

- Any other name that matches `PARAM_NAME` MUST become `{param:NAME}` with the name as written (`=CheckedBy` gives `{param:CheckedBy}`). No Altium string gives `{paper}`.
- The names of `DYNAMIC_STRINGS` (`CurrentDate`, `CurrentTime`, `ModifiedDate`, `Time`, `DocumentFullPathAndName`, `ImagePath`, `Application_BuildNumber`, `VariantName`, `Rule`), matched without regard to case, MUST also become `{param:NAME}` and MUST give `altium.sheet.dynamic-string`: the neutral model has no value that a tool computes.
- A text that starts with `=` and whose rest does not match `PARAM_NAME` (a space, an expression, an empty name) MUST be kept as literal text and MUST give `altium.sheet.unknown-string`.
- A text that does not start with `=` MUST be kept as literal text. Every literal `{` and `}` MUST be doubled, so that `split_tokens` accepts every imported text.
- `SheetImport.strings` MUST list each distinct special string with its neutral text, sorted by the Altium string.

#### Scenario: Title-block strings mapped
- **GIVEN** a template with the labels `=Title`, `=documentnumber`, `=SheetNumber`, `=CheckedBy` and `Rev {A}`
- **WHEN** it is imported
- **THEN** the texts are `{title}`, `{doc_id}`, `{sheet}`, `{param:CheckedBy}` and `Rev {{A}}`, and `strings` holds the four special strings with these texts

#### Scenario: Dynamic string reported
- **GIVEN** a template with the label `=CurrentDate`
- **WHEN** it is imported with `allow_lossy=True`
- **THEN** the text is `{param:CurrentDate}` and `issues` holds one `altium.sheet.dynamic-string` naming the record

#### Scenario: Name with a space kept as text
- **GIVEN** a template with the label `=Drawn By`
- **WHEN** it is imported with `allow_lossy=True`
- **THEN** the text is `=Drawn By` and `issues` holds one `altium.sheet.unknown-string`

### Requirement: Altium sheet images
The importer SHALL keep an embedded PNG image (record kind 30) as a `SheetBitmap` and SHALL report every other image (`H-A-RD-SHT-IMAGE`).
- An image with `EMBEDIMAGE=T` whose embedded file, found in the `Storage` stream under the image's `FILENAME`, starts with the eight bytes of the PNG signature MUST give one `SheetBitmap` whose `png` is the base64 text of those bytes, whose `pos` is the centre of the box from `LOCATION` to `CORNER`, anchored as a one-point item, and whose `scale_ppm` is 1 000 000.
- Each kept image MUST give one `altium.sheet.image-size` (warning) whose message gives the box width and height in nanometres: `SheetBitmap` has no box, so the drawn size is the backend's.
- An image that is not embedded, whose embedded file is missing or cannot be decompressed, or whose bytes are not a PNG MUST NOT be imported and MUST give `altium.sheet.image-not-kept` naming the record, the reason (`linked`, `missing` or `not-png`) and the base name of `FILENAME` without its folders.
- The importer MUST NOT open the path of a linked image, and MUST NOT convert an image.

#### Scenario: Embedded PNG kept
- **GIVEN** an authored binary A4 template (style 0) with an image from (100, 100) to (300, 200) units, `EMBEDIMAGE=T`, and a `Storage` stream holding an authored 1×1 PNG under the image's file name
- **WHEN** it is imported with `allow_lossy=True`
- **THEN** the sheet holds one `SheetBitmap` with `pos == SheetPoint("lb", 50_800_000, 38_100_000)`, `base64.b64decode(png)` equal to the PNG bytes, and `issues` holds one `altium.sheet.image-size`

#### Scenario: Linked image reported
- **GIVEN** a template with an image whose `FILENAME` is a Windows path ending in `logo.bmp` and no `EMBEDIMAGE` key
- **WHEN** it is imported with `allow_lossy=True`
- **THEN** the sheet has no bitmap, and `issues` holds one `altium.sheet.image-not-kept` whose message holds `linked` and `logo.bmp` and no folder name

### Requirement: Sheet import report
The importer SHALL account for every template record: each is imported or named in an issue, and none is dropped silently.
- `fenolite.backends.altium.read.sheet.ISSUE_CODES` MUST be the closed table:

| code | severity | when |
|---|---|---|
| `altium.sheet.not-representable` | warning | a graphic record with no neutral item |
| `altium.sheet.not-template-content` | warning | a record that is not sheet graphics, with its children |
| `altium.sheet.builtin-not-drawn` | warning | a border, zones or the built-in title block whose geometry no source gives |
| `altium.sheet.outside` | warning | a record with a point outside the drawing area |
| `altium.sheet.image-not-kept` | warning | a linked, missing or non-PNG image |
| `altium.sheet.image-size` | warning | a kept image, whose box the model cannot hold |
| `altium.sheet.unknown-string` | warning | a special string whose name is not a parameter name |
| `altium.sheet.dynamic-string` | warning | a special string whose value a tool computes |
| `altium.sheet.style-dropped` | warning | a fill, a line style, a line-end shape, an underline, a mirror, or an unknown line width or justification |
| `altium.sheet.appearance` | info | colours and font names, once |
| `altium.sheet.rounded` | info | lengths rounded to the micrometre, once |
| `altium.sheet.builtin-drawn` | info | a border drawn from the sheet flags, once |

- Every warning about a record MUST carry `where == "record[<n>]"`, n being the record's number in file order, and a message that names the record kind. A warning about a sheet flag MUST carry `where == "record[0].<KEY>"`. A record of the `Additional` stream (a harness record) that no record of `Additional` owns MUST give `altium.sheet.not-template-content` with `where == "additional[<n>]"`. The two once-only infos `appearance` and `rounded` carry an empty `where` and come last.
- `imported` MUST map each record kind to the number of its records that gave at least one item, and `reported` MUST be the `where` values of the records that gave none and are named in a warning, in record order (by record number, then the `Additional` records). Every template record other than kind 39 and sheet-level kind 41 MUST be counted in exactly one of the two.
- A warning is a loss. With `allow_lossy=False`, the default, `import_sheet` MUST raise `SheetLossError` (a `fenolite.core.errors.FenoliteError` with `cli_code = "FEN-7001"`) when at least one warning exists; its `issues` MUST hold every issue, in record order, and its hint MUST name `--allow-lossy`. With `allow_lossy=True` it MUST return the same issues in `SheetImport.issues`.
- An import without a warning MUST return whatever `allow_lossy` is.

#### Scenario: Every record accounted for
- **GIVEN** the authored template `mixed`, whose records after the sheet record are, in this order, two lines, one label, one arc, one wire and one sheet-level parameter
- **WHEN** it is imported with `allow_lossy=True`
- **THEN** `imported == {13: 2, 4: 1}`, `reported` holds `record[4]` and `record[5]`, the arc and the wire, `parameters` holds the parameter's name, and the counts add up to the five records that are not the parameter

#### Scenario: Loss refused by default
- **GIVEN** the same template
- **WHEN** `import_sheet(data)` is called
- **THEN** `SheetLossError` is raised with two issues, `altium.sheet.not-representable` and `altium.sheet.not-template-content`, in record order

#### Scenario: Clean template needs no flag
- **GIVEN** the authored template `title_block`, which holds only lines, rectangles and labels of solid style
- **WHEN** `import_sheet(data)` is called
- **THEN** it returns, and every issue has severity `info`

### Requirement: Template import command
`fenolite template import SRC --target kicad --out OUT` SHALL import `SRC` with `import_sheet` and write `OUT` with `write_drawing_sheet` through the mutation protocol of `cli-contract`. It is the action `import` of the command `template` (requirement "Template build command").
- `SRC` is a `.SchDot` or `.SchDoc` file in either form. The sheet's name MUST be the stem of `SRC`. The global `--allow-lossy` MUST be passed to `import_sheet` and to the writer.
- `result` MUST hold `sheet` (`name`, `items`, `tokens`), `source` (`form`, `style`, `paper`, `portrait`, `width`, `height`), `imported` (an object keyed by the record kind as a decimal string), `reported`, `strings` (an object from each special string to its neutral text), `parameters`, `target`, `kicad_version`, `drawn` and `output`, and also `plan` on a `--dry-run` or unconfirmed run. `drawn` MUST hold one entry, keyed by `source.paper`, with the text and line counts that `layout` predicts on the source's own page and the texts resolved by `resolve_text` with an empty `TitleBlock`.
- The envelope's `issues` MUST hold the importer's issues, then the writer's, also when the writer refuses. `input.kind` MUST be `altium-sheet`.
- Exit codes MUST be: 0 ok; 2 usage; 3 with `FEN-3001` for a missing or unreadable file and with `FEN-3004` for a file the reader or the importer refuses; 4 without `--confirm` (`FEN-4001`); 7 with `FEN-7001` for a loss without `--allow-lossy` and for a writer refusal. A refusal MUST carry its issues, on a `--dry-run` too. No new FEN code is added.
- The command MUST NOT run `kicad-cli` and MUST NOT write any file other than `OUT`. Its envelope evidence MUST be `INFERRED` with the hypotheses `H-A-RD-SHT-SAME` and `H-K-WKS-CORNER`.
- `fenolite capabilities` MUST keep one `template` entry with `mutates` true. `example_args` and `mutation_example_args` of the command stay those of `build`.

#### Scenario: Dry run reports the import
- **GIVEN** the authored template `title_block` written to `t.SchDot` under `tmp_path`
- **WHEN** `fenolite template import t.SchDot --target kicad --out t.kicad_wks --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `t.kicad_wks`, `result.source.paper` is `A4`, `result.sheet.tokens` holds `title` and `doc_id`, `result.drawn` has the entry `A4`, and nothing is written

#### Scenario: Confirmed write
- **WHEN** the same command runs with `--confirm` in place of `--dry-run`, twice
- **THEN** both runs exit 0, `receipt.written[0].sha256` is the SHA-256 of `t.kicad_wks`, the file starts with `(kicad_wks (version 20231118) (generator "fenolite")`, both runs write byte-identical files, and `read_drawing_sheet` of the file gives the imported `setup` and `items`

#### Scenario: Loss refused without the flag
- **GIVEN** the authored template `mixed` written to `m.SchDot`
- **WHEN** `fenolite template import m.SchDot --target kicad --out m.kicad_wks --dry-run --json` runs, then again with `--allow-lossy`
- **THEN** the first run exits 7 with `FEN-7001` on stderr and the two warnings in the envelope's `issues`; the second exits 0 with the same two warnings and a plan

#### Scenario: Not an Altium schematic
- **GIVEN** a file `x.SchDot` holding the text `hello`
- **WHEN** `fenolite template import x.SchDot --target kicad --out x.kicad_wks --dry-run --json` runs
- **THEN** the exit code is 3 and stderr carries `FEN-3004`

### Requirement: Authored sheet fixtures and corpus rows
Tests of the import SHALL use templates authored for Fenolite, and no template of any organisation SHALL be committed or shipped.
- `tests/_altium_sheet.py` MUST build every test template in memory, from records written in the test code, with Fenolite's own encoders (`fenolite.backends.altium.ascii`, `binary` and `cfb`). Its texts MUST be special strings, the generic words listed in the module, or one-character zone labels. No test MUST read a template file from the repository.
- `tests/residue/test_template_residue.py` MUST fail when a tracked file has the extension `.SchDot`, in any letter case, and when `src/fenolite/templates/` or `src/fenolite/backends/altium/` holds a file that starts with the compound-file signature.
- The corpus manifest MUST gain three rows for Altium-saved sheet templates of two public repositories under the MIT licence (S-0264, S-0265). Each row MUST follow "Second-backend corpus rows" (change c0039) and "Altium schematic corpus rows" (change c0040) of `corpus-policy`: the ids `altium-third-party-schdot-01` to `-03`, a URL that holds the 40-digit commit, the SHA-256 of the fetched bytes, `embeddable = false`, the uses `altium`, `origin:third-party` and `altium-sch`, and `notes` without names. Each MUST also carry the use `altium-sheet`, by which the tests of this change select them, and MUST NOT carry `cfb`.
- The rows come from two repositories. As `corpus-policy` requires three for a `CORPUS-VERIFIED` label on these rows, `H-A-RD-SHT-SAME` stays `INFERRED` and the corpus result is recorded as supporting data until a row of a third repository is added.
- `tests/corpus/test_schdot_corpus.py` (`needs_corpus`) MUST import each row with `allow_lossy=True` and assert only: the form, the paper, that every template record is counted in `imported` or `reported`, and that the written `.kicad_wks` reads back. It MUST NOT assert, print or store any text, name, coordinate or image of a row.
- The census of the rows MAY be recorded in `docs/formats/altium/sheet-template.md` as counts per record kind and per key name only.

#### Scenario: Corpus templates import
- **WHEN** `uv run pytest tests/corpus/test_schdot_corpus.py` runs with the three `altium-sheet` rows fetched
- **THEN** each row imports with `source.form == "binary"`, every template record is accounted for, and the check of `H-A-RD-SHT-SAME` passes on each

#### Scenario: A committed template is refused
- **GIVEN** a test copy of the repository's file list with `docs/a4.SchDot` added
- **WHEN** the residue check runs on it
- **THEN** it fails naming the file

#### Scenario: Corpus absent
- **WHEN** `uv run pytest tests/corpus/test_schdot_corpus.py` runs without the fetched rows
- **THEN** the tests are skipped with the `needs_corpus` reason, and the unit tests of the import still pass

### Requirement: Altium sheet template writing
`fenolite.backends.altium.schdot.write_template(sheet, *, width, height, paper, form="binary", allow_lossy=False)` SHALL write a `DrawingSheet`, as it is drawn on the first page of a `width` by `height` page (nm), as an Altium schematic template: a schematic document without components whose sheet record is a custom sheet of exactly that size with the built-in border, title block and reference zones off, and whose root records are the lines, rectangles and texts of the sheet. It SHALL return a `TemplateWrite` with the bytes, the issues and the counts of what was written.
- The frame and the reference zones of the sheet MUST be written as the drawn lines and texts they are in the neutral sheet, and the margins as the positions of the items on the page: the Altium form of a border with equal divisions cannot hold the zone pitch of a specification.
- An item with a repeat MUST be written once per copy, by the rule of `templates.layout` (`H-K-WKS-REPEAT`): copies stop at the count or when a copy's start leaves the margin box, and a one-letter or number text steps. An item of the scope `not_first` MUST NOT be written.
- A line MUST be a polyline record of two points and a rectangle one of five; a text MUST be a label record with its font, justification and quarter turns. Lengths MUST be written to the nearest 1/100 000 of a unit, so that a length of whole micrometres is read back exactly.
- `SPECIAL_STRINGS` MUST be the table that maps the neutral tokens to Altium's special strings, the inverse of the import's table ("Altium special strings"). A text that is one token MUST be written as `=<Name>`; a text that is one parameter token `{param:NAME}` MUST be written as `=NAME`, and the template MUST hold a sheet parameter record of that name without a value. The token `{paper}`, which has no special string, MUST be written as the text `paper`: a template has one size.
- `sheet_frame(sheet, *, width, height, paper, …)` MUST return the same records and the changes to a sheet record as a `SheetFrame`, which the schematic writers take ("Drawing sheet in an Altium build"), and `written_scope(sheet, *, width, height, paper)` MUST return the written scope of a sheet on a page.
- The written scope, which `docs/sheet-templates.md` MUST define, is: the position of every drawn line and text on that page; the neutral text of every text, with `{paper}` read as `paper`; the justification, the quarter turns, bold and italic of every text; the height of a text as the nearest whole number of points, at least 1; the width of a line as the nearest of 4, 10, 20 and 40 mil. `import_sheet(write_template(sheet, …).data)` MUST give a drawing sheet that is equal to `sheet` inside that scope.
- A part the form cannot carry MUST be reported with the import's `altium.sheet.*` codes: `altium.sheet.image-not-kept` for a bitmap, which is not written; `altium.sheet.not-representable` for a text that mixes a token with other text or holds several tokens, for a text outside printable 7-bit ASCII, with `|` or with a space at an end, for a text that starts with `=` without being a token, and for a parameter token whose name is a special string; `altium.sheet.outside` for a line or a text anchor that reaches past the page; `altium.sheet.style-dropped` for a rotation that is not a quarter turn, `max_len` and `max_height`. These are warnings, and any of them MUST raise `SheetLossError` (`FEN-7001`) unless `allow_lossy` is set; with it the item is left out or written without the style. A width or a size that is replaced by the nearest one the form has MUST be counted in one `altium.sheet.rounded` info.
- The bytes MUST depend only on the arguments: no clock, random value or environment value. The module MUST declare `EVIDENCE` as `INFERRED` with `H-A-SCHDOT-READBACK`, `H-A-SCHDOT-OPEN` and `H-A-SCHDOT-STRINGS`.

#### Scenario: Shipped example
- **WHEN** `write_template(build_sheet(iso5457_generic), …)` for an A4 landscape page is imported again
- **THEN** the drawing sheet equals the built one inside the written scope, the write reports no warning, and the import reports no warning

#### Scenario: Unknown variable
- **GIVEN** a sheet with a text `{param:PROJECT_CODE}`
- **WHEN** it is written
- **THEN** the label record holds `=PROJECT_CODE`, and a sheet parameter record named `PROJECT_CODE` is written

#### Scenario: A bitmap is a loss
- **GIVEN** a sheet with a logo
- **WHEN** it is written without `allow_lossy`
- **THEN** `SheetLossError` is raised with `altium.sheet.image-not-kept`; with `allow_lossy` the template is written without the image

### Requirement: Template build for Altium
`fenolite template build SPEC --target altium --out FILE` SHALL write the template of a `.sheet.toml` with `write_template`, under the rules of the template build command (dry run, confirm, receipt, determinism).
- `--size NAME` MUST select the page among the sizes the specification lists; without it the first listed size is used. A size the specification does not list MUST exit 2. `--altium-format binary|ascii` (default `binary`) MUST select the form. Both options MUST be a usage error with `--target kicad` and with the action `import`.
- `result` MUST hold `sheet`, `target`, `drawn` (for the one size written) and `output` as for the target `kicad`, and `altium`: `format`, `size`, `width`, `height`, `lines`, `texts`, `parameters` and `strings`. It MUST NOT hold `kicad_version`. The write kind MUST be `altium_schdot`.
- The envelope evidence MUST be `INFERRED` with `H-A-SCHDOT-READBACK`, `H-A-SCHDOT-OPEN` and `H-A-SCHDOT-STRINGS`. The global `--allow-lossy` MUST be passed to the writer.

#### Scenario: Both targets from one specification
- **WHEN** `fenolite template build iso5457_generic.sheet.toml --target altium --out t.SchDot --confirm` and the same command with `--target kicad --out t.kicad_wks` run
- **THEN** both exit 0, and the two files import or read to drawing sheets that are equal inside the written scope on an A4 landscape page

#### Scenario: A listed size
- **WHEN** the Altium command runs with `--size A3 --dry-run`, and again with `--size A0 --dry-run`
- **THEN** the first exits 0 with `result.altium.size` `A3`, and the second exits 2
