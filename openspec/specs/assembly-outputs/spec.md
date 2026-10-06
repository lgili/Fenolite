# assembly-outputs Specification

## Purpose
The bill of materials and the placement table of a board, written through a column template that the user supplies: the `bom` and `pnp` commands, their sources (`model` and `kicad`), grouping, units, rotation offsets and side names. No template of any assembly house ships with Fenolite.
## Requirements
### Requirement: Neutral BOM parts and lines
`fenolite.exports.bom` SHALL define `BomPart(ref, value, footprint, description, datasheet, dnp, properties)`, `BomLine(refs, quantity, fields, key)`, `parts_from_model(design) -> tuple[BomPart, ...]` and `group(parts, template) -> tuple[BomLine, ...]`, where `template` is the `[bom]` table of an assembly template and `key` holds the line's values of the `group_by` fields (its reference when `group_by` is empty), with `DNP` after them for a line of DNP parts as said below.
- `parts_from_model` MUST give one part per component that has a placed footprint, leaving out a component whose footprint has the attribute `board_only` or `exclude_from_bom` and a reference that starts with `#`. `footprint` MUST be `Component.lib_footprint_ref`; `dnp` MUST be true when `Component.dnp` is true or the footprint has the attribute `dnp`; `properties` MUST be the component's properties without `Reference`, `Value`, `Footprint`, `Datasheet` and `Description`; `description` and `datasheet` MUST be those two properties, or `""`.
- Parts MUST be sorted by the natural order of the reference (`R2` before `R10`).
- `group` MUST first leave out DNP parts when the template's `exclude_dnp` is true, then put into one line the parts whose values are equal for every field of `group_by` and whose `dnp` flags are equal, with `refs` in natural order and `quantity` their count. Lines MUST be sorted by the natural order of their first reference. An empty `group_by` MUST give one line per part.
- A DNP part MUST NOT share a line with a part that is not DNP, whether or not `group_by` names `dnp`: every line is all DNP or all fitted. A line of DNP parts has no place of its own in the order: it stands where its first reference puts it.
- When `group_by` is not empty and does not name `dnp`, the `key` of a line of DNP parts MUST be its values of the `group_by` fields followed by `DNP`, so that no two lines of one bill have one key. Every other `key` MUST hold the values of the `group_by` fields and nothing else.
- The value of a field for a line MUST be: `refs` joined with `ref_separator`; `quantity`; `item`, the line's number from 1; and for every other field the value its parts share, or the values of its parts in reference order, without repeats, joined with `ref_separator` when they differ.
- The functions MUST NOT read a file or run a tool, and MUST use no float.

#### Scenario: Grouping by value and footprint
- **GIVEN** the parts `R1` and `R2` with value `10k` and footprint `Mini:Mini_R_0603`, `R10` with value `330` and the same footprint, and `D1`
- **WHEN** `group` runs with `group_by = ("value", "footprint")`
- **THEN** it returns three lines whose `refs` are (`D1`), (`R1`, `R2`) and (`R10`), in this order, with quantities 1, 2 and 1

#### Scenario: A property splits a group
- **GIVEN** the same parts, where `R1` has the property `Bin` `A` and `R2` has `B`
- **WHEN** `group` runs with `group_by = ("value", "footprint", "property:Bin")`
- **THEN** `R1` and `R2` are on two lines

#### Scenario: DNP parts
- **GIVEN** a model whose `R2` has `dnp == True`
- **WHEN** `group` runs with `exclude_dnp` true, and again with false
- **THEN** the first result does not list `R2`, and in the second the line of `R2` has the `dnp` field `DNP`

#### Scenario: DNP parts never share a line with fitted parts
- **GIVEN** the parts `R1`, `R2`, `R3` and `R4` with value `10k` and footprint `Mini:Mini_R_0603`, of which `R2` and `R4` are DNP, and a DNP part `D1`, once as `parts_from_model` gives them and once as `parts_from_kicad` gives them
- **WHEN** `group` runs with `group_by = ("value", "footprint")` and `exclude_dnp` false, and again with `exclude_dnp` true
- **THEN** the first result has three lines whose `refs` are (`D1`), (`R1`, `R3`) and (`R2`, `R4`), in this order, with quantities 1, 2 and 2, the `dnp` fields `DNP`, an empty text and `DNP`, and the keys (`LED`, the footprint, `DNP`), (`10k`, the footprint) and (`10k`, the footprint, `DNP`); the second result has the one line (`R1`, `R3`) with quantity 2

#### Scenario: Parts that are not on the bill
- **GIVEN** a model with a footprint `H1` that has `board_only`, and a component `R3` whose footprint has `exclude_from_bom`
- **WHEN** `parts_from_model` runs
- **THEN** neither `H1` nor `R3` is a part

### Requirement: BOM difference
`bom.difference(a, b) -> tuple[BomChange, ...]` SHALL compare two tuples of lines grouped under one template, matching lines by their `key` (the values of their `group_by` fields, and `DNP` after them for a line of DNP parts as "Neutral BOM parts and lines" says), and SHALL return `BomChange(key, change, a_refs, b_refs)` sorted by key: `added` for a key only in `b`, `removed` for a key only in `a`, and `changed` when the references differ. Equal BOMs MUST give `()`.

#### Scenario: One part more
- **GIVEN** two BOMs equal except that the second has one more `10k` resistor `R3`
- **WHEN** `difference` runs
- **THEN** it returns one `changed` entry whose `a_refs` are (`R1`, `R2`) and whose `b_refs` are (`R1`, `R2`, `R3`)

#### Scenario: A value changed
- **GIVEN** two BOMs in which `R10` goes from `330` to `470`
- **WHEN** `difference` runs
- **THEN** it returns one `removed` entry for the `330` line and one `added` entry for the `470` line

#### Scenario: A DNP part becomes fitted
- **GIVEN** two BOMs grouped with `exclude_dnp` false and without `dnp` in `group_by`, in which the `10k` resistor `R2` is DNP in the first and fitted in the second
- **WHEN** `difference` runs
- **THEN** it returns two `changed` entries, one for the key of the fitted `10k` line, which gains `R2`, and one for the key of the DNP `10k` line, which loses it

### Requirement: Neutral placement rows
`fenolite.exports.placement` SHALL define `PlacementRow(ref, value, footprint, position, rotation, side, dnp, mount, properties)`, `rows_from_model(design) -> tuple[PlacementRow, ...]` and `apply(rows, template, *, outline=None, issues=None) -> tuple[PlacedRow, ...]`, where `template` is the `[placement]` table of an assembly template.
- `rows_from_model` MUST give one row per footprint that lacks the attribute `exclude_from_pos_files`, in natural order of the reference. `position` MUST be the footprint's position in the board file's frame, in nm; `rotation` its stored angle in µdeg; `side` `top` or `bottom`; `mount` `smd` or `through_hole` from the attributes, else `other`.
- `apply` MUST, in this order: leave out DNP rows when `exclude_dnp` is true and rows whose `mount` is not `smd` when `smd_only` is true; subtract the origin; turn the Y axis; apply the rotation rule; leave lengths in nm and angles in µdeg for the renderer.
- **Origin.** `page` MUST subtract nothing. `outline` MUST subtract the left edge of the bounding box of the board outline and, on the Y axis, its lower edge on the page when `y_axis` is `up` and its upper edge when it is `down`; without a closed outline it MUST give no row and the issue `pnp.no-outline` (error), appended to `issues`, or raised as `NoOutlineError` when the caller passes no list.
- **Y axis.** `up` MUST negate Y after the origin is subtracted, so Y grows upward on the page, as in KiCad's position file; `down` MUST keep the file's direction.
- **Rotation rule.** The rotation MUST become `(sign × rotation + side offset + footprint offset) mod 360°`, with the `sign` and `offset` of the row's side, and the `offset` of the first `rotation.footprint` entry whose `match` fits the footprint's lib id by `fnmatch.fnmatchcase`, or 0.
- The functions MUST use no float.

#### Scenario: KiCad's frame by default
- **GIVEN** a footprint at (132 mm, 109 mm) in the board file, on top, with rotation 0
- **WHEN** `apply` runs with the default template
- **THEN** the row has X 132 mm and Y −109 mm

#### Scenario: Origin at the outline
- **GIVEN** a board whose outline is a 50 mm × 30 mm rectangle with its upper-left corner at (100 mm, 100 mm), and a footprint at (114 mm, 115 mm)
- **WHEN** `apply` runs with `origin = "outline"` and `y_axis = "up"`
- **THEN** the row has X 14 mm and Y 15 mm

#### Scenario: Rotation rule
- **GIVEN** a bottom-side footprint `Mini:Mini_QFP-32_7x7mm_P0.8mm` with rotation 90°, and a template with `bottom = { sign = -1, offset = 180 }` and a footprint entry matching `Mini:Mini_QFP*` with offset 90
- **WHEN** `apply` runs
- **THEN** its rotation is 180°

#### Scenario: Filters
- **GIVEN** a through-hole part and a DNP part
- **WHEN** `apply` runs with `smd_only` and `exclude_dnp` true
- **THEN** neither is in the result

#### Scenario: No outline
- **GIVEN** a board without `Edge.Cuts` graphics
- **WHEN** `apply` runs with `origin = "outline"`
- **THEN** it gives one `pnp.no-outline` error and no row

### Requirement: Assembly template
`fenolite.exports.assembly.read_template(text, *, file="") -> AssemblyTemplate` SHALL read a TOML template with `tomllib` and `parse_float=Decimal`, and `assembly.DEFAULT` SHALL be the template used when none is given.
- The file MAY hold `schema` (`fenolite.assembly-template.v0`), `[csv]` (`delimiter`, one character; `quote`, `minimal` or `all`; `line_end`, `lf` or `crlf`; `header`, a boolean; `encoding`, `utf-8` or `utf-8-sig`), `[bom]` (`columns`, `group_by`, `ref_separator`, `exclude_dnp`) and `[placement]` (`columns`, `units` in `mm`, `in` or `mil`, `decimals` from 0 to 6, `rotation_decimals` from 0 to 6, `origin` in `page` or `outline`, `y_axis` in `up` or `down`, `sides` with `top` and `bottom`, `exclude_dnp`, `smd_only`, and `rotation` with `top`, `bottom` and `footprint` entries of `match` and `offset`).
- A column MUST be `{ name, field }`. `BOM_FIELDS` MUST be `refs`, `quantity`, `value`, `footprint`, `footprint_name`, `description`, `datasheet`, `dnp`, `item` and `property:<NAME>`; `PLACEMENT_FIELDS` MUST be `ref`, `value`, `footprint`, `footprint_name`, `x`, `y`, `rotation`, `side` and `property:<NAME>`. `footprint_name` is the lib id without its library.
- Every table and key is optional and takes the value of `DEFAULT`: BOM columns `refs`, `quantity`, `value`, `footprint`, each named by its field, grouped by `value` and `footprint`, `ref_separator` `,`, `exclude_dnp` true; placement columns `ref`, `value`, `footprint_name`, `x`, `y`, `rotation`, `side`, `units` `mm`, `decimals` 4, `rotation_decimals` 2, `origin` `page`, `y_axis` `up`, sides `top` and `bottom`, `exclude_dnp` true, `smd_only` false, signs 1 and offsets 0; CSV `,`, `minimal`, `lf`, header, `utf-8`.
- `sign` MUST be 1 or −1; an `offset` MUST be a number of degrees that is a whole number of µdeg.
- An unknown table or key, a field outside the vocabulary, two columns with one name, an empty `columns` list, a `group_by` field that a single part does not have (`refs`, `quantity`, `item`), or a value outside its set MUST raise `TemplateError` (`cli_code` `FEN-3004`) carrying one `assembly.template-invalid` issue per problem, each naming the key.
- No template other than `DEFAULT` MUST be packaged with Fenolite, and no file of the repository MUST hold a template that names a company, a service or a product.

#### Scenario: Default without a file
- **WHEN** `assembly.DEFAULT` is read
- **THEN** its BOM columns are `refs`, `quantity`, `value` and `footprint`, and its placement has `units` `mm`, `origin` `page` and `y_axis` `up`

#### Scenario: Authored template
- **WHEN** `read_template` reads `tests/data/assembly/columns.toml`
- **THEN** the BOM has the columns `Parts`, `Count`, `Marking`, `Shape` and `Bin`, names made up for Fenolite, the last with the field `property:Bin`, and every key the file leaves out has the default value

#### Scenario: Invalid template
- **WHEN** `read_template` reads `tests/data/assembly/invalid.toml`, which has an unknown key, a field `price` and `units = "cm"`
- **THEN** `TemplateError` is raised with three `assembly.template-invalid` issues, in file order, naming `price`, the unknown key and `units`

#### Scenario: Only the default ships
- **WHEN** `uv run pytest tests/unit/exports/test_assembly.py -k packaged tests/residue` runs
- **THEN** the package holds no `.toml` template, and each template under `tests/data/assembly/` and in `docs/assembly.md` uses column names made up for Fenolite and says so

### Requirement: CSV rendering
`assembly.render_csv(header, rows, options) -> bytes` SHALL write a table as CSV with the stdlib writer under the template's `[csv]` options, and `bom.table` and `placement.table` SHALL give it the cells as text.
- With `quote = "minimal"`, a field MUST be quoted only when it holds the delimiter, a quote or a line break; with `all`, every field. A quote inside a field MUST be doubled (S-0365).
- Lines MUST end with LF or CRLF as `line_end` says, the last line included; `header` false MUST leave the header line out; `utf-8-sig` MUST put a byte order mark first.
- `assembly.format_length(nm, units, decimals)` MUST print a length from integer nm in `mm`, `in` (25.4 mm) or `mil` (0.0254 mm) as a decimal rounded half to even at `decimals` places, with trailing zeros kept; `assembly.format_angle(udeg, decimals)` MUST do the same for degrees. Neither MUST create a float.
- `dnp` MUST print `DNP` or an empty field; `quantity` and `item` MUST print integers; `side` MUST print the name of `sides`.
- Two renderings of one table under one template MUST be byte-identical.

#### Scenario: Quoting
- **GIVEN** the row (`R1,R2`, `2`, `10k "1%"`)
- **WHEN** it is rendered with `quote = "minimal"` and `,` as delimiter
- **THEN** the line is `"R1,R2",2,"10k ""1%"""`

#### Scenario: Lengths without floats
- **WHEN** `format_length(132_000_000, "mm", 4)`, `format_length(25_400_000, "in", 3)` and `format_length(1_270_000, "mil", 0)` are called
- **THEN** they return `132.0000`, `1.000` and `50`

#### Scenario: Line ends and header
- **GIVEN** a two-row table
- **WHEN** it is rendered with `line_end = "crlf"` and `header = false`
- **THEN** the bytes hold exactly two CRLF pairs and no header line

### Requirement: BOM parts from kicad-cli
`fenolite.backends.kicad.bom.read_bom_csv(text, *, fields, file="") -> tuple[BomRow, ...]` SHALL read the CSV that `KicadCli.export_bom` asks `kicad-cli` to write, one `BomRow(ref, value, footprint, datasheet, description, dnp, properties)` per row in file order, and `fenolite.exports.bom.parts_from_kicad(rows) -> tuple[BomPart, ...]` SHALL give the same `BomPart`s that `parts_from_model` gives. The reader returns rows and not parts because a backend may not import `exports`.
- `backends.kicad.bom.bom_fields(properties) -> tuple[str, ...]` MUST return `BASE_FIELDS` (`Reference`, `Value`, `Footprint`, `Datasheet`, `Description`, `${DNP}`) and then the property names, sorted and without repeats.
- `exports.bom.kicad_fields(template) -> tuple[str, ...]` MUST return `bom_fields` of the name of each `property:<NAME>` that a BOM column or `group_by` of the template names. A property name that holds `,` MUST raise `TemplateError` with one `bom.field-unsupported` issue per name, before any tool runs.
- The header MUST equal `fields`; any other header, a row with another number of cells, or a row without a reference MUST raise `FormatError` (`FEN-3004`) naming the first difference and its line.
- A row MUST give one `BomRow`: `dnp` true when the `${DNP}` cell is not empty, `properties` holding the property cells that are not empty.
- `parts_from_kicad` MUST sort the parts by natural order of the reference and drop a reference that starts with `#`.

#### Scenario: Rows to parts
- **GIVEN** the authored `tests/data/assembly/bom_export.csv` with the header `"Reference","Value","Footprint","Datasheet","Description","${DNP}","Bin"` and the rows of `D1`, `R1` and `R10`, the last with `DNP`
- **WHEN** `read_bom_csv` reads it with those fields and `parts_from_kicad` takes the rows
- **THEN** there are three parts in the order `D1`, `R1`, `R10`, `R10.dnp` is true, and `R1.properties == {"Bin": "A"}`

#### Scenario: Unexpected header
- **GIVEN** the same text with the header's second cell `Val`
- **WHEN** it is read
- **THEN** `FormatError` is raised naming `Val`

### Requirement: Assembly issue codes and evidence
`fenolite.exports.codes.ISSUE_CODES` SHALL gain `assembly.template-invalid` (error), `bom.property-missing` (info), `bom.field-unsupported` (error) and `pnp.no-outline` (error), and `docs/cli-contract.md` MUST document them.
- `bom.EVIDENCE_KICAD` (`H-K-BOM-CSV`; the evidence that `backends.kicad.bom` declares), `bom.EVIDENCE_MODEL` (`H-K-BOM-MODEL`) and `placement.EVIDENCE` (`H-K-PCB-POS`, `H-K-POS-ROWS`) MUST each carry the level of the weakest row it names in `docs/hypotheses.md`: `INFERRED` until that row is `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- `bom.EVIDENCE_MODEL` MUST be used as `KICAD-VERIFIED` only for a built project that has a schematic; for any other input the envelope MUST carry `INFERRED`.
- `docs/assembly.md` MUST hold the template reference, one worked example with invented column names, what each rotation key does with numbers, which BOM source to use when, and the sentence that Fenolite ships no template of any assembly service and that a template's fit to a service is the user's to check.

#### Scenario: Codes documented
- **WHEN** `uv run pytest tests/unit/exports tests/consistency` runs
- **THEN** every `assembly.`, `bom.` and `pnp.` code literal under `src/fenolite/` is a key of `exports.codes.ISSUE_CODES` and appears in `docs/cli-contract.md`

#### Scenario: Guide present
- **WHEN** `uv run pytest tests/unit/test_repo_layout.py tests/residue` runs
- **THEN** it passes with `docs/assembly.md` present and linked from `README.md` and `docs/exports.md`

