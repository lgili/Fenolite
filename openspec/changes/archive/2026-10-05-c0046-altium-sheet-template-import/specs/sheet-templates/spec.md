## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Template build command
`fenolite template build SPEC --target kicad --out OUT` SHALL be a mutating command (`fenolite.cli.cmd_template.COMMAND`, name `template`, schema `fenolite.template.v0`) that loads `SPEC` with `load_spec`, builds it with `build_sheet` and writes `OUT` with `write_drawing_sheet` through the mutation protocol of `cli-contract`.
- `--target` and `--out` MUST be given; `--out` MUST also accept the short form `-o`, and `--target` with any value other than `kicad` MUST exit 2. The global `--kicad-version {9,10}` MUST select the emit-check target only; the written bytes do not depend on it. The global `--allow-lossy` MUST be passed to the writer.
- `result` MUST hold `sheet` (`name`, `sizes`, `items`, `tokens`), `target`, `kicad_version`, `drawn` and `output`, and also `plan` on a `--dry-run` or unconfirmed run, as the dispatcher adds it; a confirmed run carries the `receipt` instead. `drawn` MUST give, per listed size, the text and line counts that `layout` predicts on that size's page, and the texts resolved by `resolve_text` with an empty `TitleBlock`. The page of a named size is its `PAPER_SIZES` entry in the specified orientation; the page of `custom` is the specification's `sheet.width` by `sheet.height`.
- Exit codes MUST be: 0 ok; 2 usage; 3 with `FEN-3004` for a malformed specification and with `FEN-3001` for a missing or unreadable one; 4 without `--confirm` (`FEN-4001`); 7 for a writer refusal (`FEN-7001`). No new FEN code is added.
- The command MUST NOT run `kicad-cli`. Its envelope evidence MUST be `INFERRED` with the hypothesis `H-K-WKS-CORNER`.
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
