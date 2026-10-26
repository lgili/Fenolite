## MODIFIED Requirements

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

## ADDED Requirements

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
