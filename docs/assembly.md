# Assembly tables: bill of materials and placement

An assembly service asks for two tables: which parts go on the board (the bill of materials, BOM) and
where each one sits (the placement, or pick-and-place, table). Every service has its own column names,
column order, units and rotation convention.

Fenolite does not know those conventions and does not guess them. It gives you two **neutral tables**
and renders them through a **column template that you write**:

- `fenolite bom PATH` gives the bill of materials;
- `fenolite pnp PATH` gives the placement table.

**Fenolite ships no template of any assembly service, distributor, manufacturer or company.** The only
template inside the package is the built-in default, whose column names are Fenolite's own field names.
Whether a template you write matches what a service expects is yours to check: load the first files of an
order into the service's own viewer before you rely on them. The normative text is the openspec
capability `assembly-outputs`; the commands are in `docs/cli-contract.md`.

```bash
fenolite pnp build/blink --json                       # the table, as JSON; nothing is written
fenolite pnp build/blink --template my.toml --out pnp.csv --dry-run   # the plan
fenolite pnp build/blink --template my.toml --out pnp.csv --confirm   # write the file
fenolite bom build/blink --source model --template my.toml --out bom.csv --confirm
```

Both commands print the table in the JSON envelope (`result.lines` or `result.rows`, one object per row,
keyed by your column names, holding the same text the file would hold). They write a file only with
`--out`, through the usual protocol: `--dry-run` shows the plan, `--confirm` writes. Neither runs a tool,
and neither changes the project folder. With `--manifest` the file also joins `fenolite-artifacts.json`
in its folder, beside the exported files ([`docs/exports.md`](exports.md), "The manifest").

## The neutral tables

### Bill of materials

A **part** is one component that has a footprint on the board. Left out: a footprint with the attribute
`board_only` or `exclude_from_bom`, and a reference that starts with `#`. A part is DNP ("do not
populate") when the component or its footprint says so.

A **line** is the parts that share the values of the template's `group_by` fields. References inside a
line, and lines among themselves, are in natural order (`R2` before `R10`).

| field | what a column holds |
|---|---|
| `refs` | the references of the line, joined with `ref_separator` |
| `quantity` | how many parts the line has |
| `item` | the line's number, from 1 |
| `value` | the component's value |
| `footprint` | the footprint's lib id, `Library:Name` |
| `footprint_name` | the lib id without its library, `Name` |
| `description`, `datasheet` | those two properties of the component |
| `dnp` | `DNP`, or nothing |
| `property:<NAME>` | the user property `NAME` of the component, or nothing |

When the parts of a line differ in a field that is not in `group_by`, the column holds each distinct
value once, in reference order, joined with `ref_separator`.

### Placement

A **row** is one footprint of the board file. Left out: a footprint with the attribute
`exclude_from_pos_files`. Rows are in natural order of the reference.

| field | what a column holds |
|---|---|
| `ref`, `value` | the component's reference and value |
| `footprint`, `footprint_name` | as in the bill of materials |
| `x`, `y` | the footprint's position, after the template's origin and Y direction, in its `units` |
| `rotation` | the footprint's rotation in degrees, after the template's rotation rule |
| `side` | the name the template gives to the top or the bottom side |
| `property:<NAME>` | the user property `NAME` of the component, or nothing |

`fenolite pnp` always reads the positions from the **board file**, also in a project that Fenolite built:
`place`, `route` and `fill` write the board and not the `.fenolite/` model, so the board is the one
description of where the parts are.

## The template

A template is a TOML file. Every table and every key is optional; what you leave out has the value of
the built-in default. Any other table or key is an error, and so is a value outside its set: every
problem of a file is reported at once, each with the path of its key (`assembly.template-invalid`), and
the command exits 3.

| key | values | default |
|---|---|---|
| `schema` | `"fenolite.assembly-template.v0"` | |
| `[csv]` `delimiter` | one character, not a quote or a line break | `","` |
| `[csv]` `quote` | `"minimal"` (only fields that need it) or `"all"` | `"minimal"` |
| `[csv]` `line_end` | `"lf"` or `"crlf"` | `"lf"` |
| `[csv]` `header` | `true` or `false` | `true` |
| `[csv]` `encoding` | `"utf-8"` or `"utf-8-sig"` (with a byte order mark) | `"utf-8"` |
| `[bom]` `columns` | a list of `{ name, field }`, with distinct names | `refs`, `quantity`, `value`, `footprint` |
| `[bom]` `group_by` | a list of fields a single part has (not `refs`, `quantity`, `item`) | `["value", "footprint"]` |
| `[bom]` `ref_separator` | a string | `","` |
| `[bom]` `exclude_dnp` | `true` leaves DNP parts off the bill | `true` |
| `[placement]` `columns` | a list of `{ name, field }`, with distinct names | `ref`, `value`, `footprint_name`, `x`, `y`, `rotation`, `side` |
| `[placement]` `units` | `"mm"`, `"in"` or `"mil"` | `"mm"` |
| `[placement]` `decimals` | 0 to 6, for `x` and `y` | `4` |
| `[placement]` `rotation_decimals` | 0 to 6 | `2` |
| `[placement]` `origin` | `"page"` or `"outline"` | `"page"` |
| `[placement]` `y_axis` | `"up"` or `"down"` | `"up"` |
| `[placement]` `sides` | `{ top = "…", bottom = "…" }` | `top`, `bottom` |
| `[placement]` `exclude_dnp` | `true` leaves DNP parts out | `true` |
| `[placement]` `smd_only` | `true` keeps only footprints with the attribute `smd` | `false` |
| `[placement.rotation]` `top`, `bottom` | `{ sign = 1 or -1, offset = degrees }` | `sign = 1`, `offset = 0` |
| `[[placement.rotation.footprint]]` | `match` (a pattern) and `offset` (degrees) | none |

In the default template each column is named by its field. Numbers are printed as exact decimals, rounded
half to even, with trailing zeros kept; no floating-point number is involved. An `offset` must be a whole
number of microdegrees.

CSV follows the usual rule (RFC 4180): a field that holds the delimiter, a quote or a line break is put
in double quotes, and a quote inside it is doubled. Every line ends with the line end, the last one
included. Two runs on an unchanged project write the same bytes.

### A worked example

The column names, the side names, the property `Bin` and every number below are made up for this page.
They are not the columns of any service.

```toml
schema = "fenolite.assembly-template.v0"

[csv]
delimiter = ";"
line_end = "crlf"

[bom]
columns = [
  { name = "Parts", field = "refs" },
  { name = "Count", field = "quantity" },
  { name = "Marking", field = "value" },
  { name = "Shape", field = "footprint_name" },
  { name = "Bin", field = "property:Bin" },
]
group_by = ["value", "footprint", "property:Bin"]
ref_separator = " "

[placement]
columns = [
  { name = "Part", field = "ref" },
  { name = "Across", field = "x" },
  { name = "Up", field = "y" },
  { name = "Turn", field = "rotation" },
  { name = "Face", field = "side" },
]
units = "mm"
decimals = 3
origin = "outline"
y_axis = "up"
sides = { top = "upper", bottom = "lower" }

[placement.rotation]
bottom = { sign = -1, offset = 180 }

[[placement.rotation.footprint]]
match = "Mini:Mini_QFP*"
offset = 90
```

For the blink example (`examples/blink_2layer`), whose resistor was given `Bin = A7`, the two files are:

```text
Parts;Count;Marking;Shape;Bin
D1;1;LED;Mini_LED_THT_3mm;
R1;1;330;Mini_R_0603;A7
U1;1;MCU;Mini_QFP-32_7x7mm_P0.8mm;
```

```text
Part;Across;Up;Turn;Face
D1;38.000;10.000;180.00;lower
R1;32.000;21.000;0.00;upper
U1;14.000;15.000;90.00;upper
```

A column that names a property no part has stays empty, and the command says so with the note
`bom.property-missing`.

## Positions and angles

The neutral row is in the **board frame**, which is the KiCad file frame (`docs/design-model.md`): X to
the right, Y down the page, and the footprint's stored angle, on the top and on the bottom side alike. A
template then applies, in this order:

1. **Filters.** `exclude_dnp` and `smd_only`.
2. **`origin`.** `"page"` subtracts nothing: the numbers are the board file's. `"outline"` subtracts the
   left edge of the bounding box of the board outline and, for `y_axis = "up"`, its lower edge on the
   page (for `"down"`, its upper edge), so a part inside the outline has positive coordinates. A board
   without a closed outline gives the error `pnp.no-outline` and no file.
3. **`y_axis`.** `"up"` negates Y, so Y grows toward the top of the page; `"down"` keeps the file's
   direction. X is never negated, on either side.
4. **The rotation rule**, below.
5. **`units`** and the decimals.

Example: the blink's outline has its upper-left corner at (100 mm, 100 mm) and is 50 mm by 30 mm. `U1`
is stored at (114 mm, 115 mm). With `origin = "page"` and `y_axis = "up"` its row is (114, −115); with
`origin = "outline"` and `y_axis = "up"` it is (14, 15), measured from the lower-left corner; with
`origin = "outline"` and `y_axis = "down"` it is (14, 15) again, measured from the upper-left corner.

### The rotation rule

```text
rotation = (sign × stored angle + side offset + footprint offset) mod 360°
```

- `sign` and `offset` come from `[placement.rotation]`, from `top` or `bottom` according to the row's
  side. `sign = -1` reverses the direction of turning on that side.
- The footprint offset is the `offset` of the **first** `[[placement.rotation.footprint]]` entry whose
  `match` fits the footprint's lib id (`Library:Name`), or 0. The pattern is a shell-style wildcard
  (`*`, `?`, `[abc]`), matched with letter case.
- The result is always in the range from 0° up to, but not including, 360°.

With numbers, for the example template above:

| part | side | stored | rule | printed |
|---|---|---|---|---|
| `R1` (`Mini:Mini_R_0603`) | top | 0° | 1 × 0 + 0 + 0 | 0.00 |
| `U1` (`Mini:Mini_QFP-32_7x7mm_P0.8mm`) | top | 0° | 1 × 0 + 0 + 90 | 90.00 |
| the same `U1`, stored at 315° | top | 315° | 1 × 315 + 0 + 90 = 405 | 45.00 |
| `D1` (`Mini:Mini_LED_THT_3mm`) | bottom | 0° | −1 × 0 + 180 + 0 | 180.00 |
| the same `D1`, stored at 30° | bottom | 30° | −1 × 30 + 180 + 0 | 150.00 |

Fenolite states what each key does. It does not state which values a given machine or service needs:
that depends on how their library draws each package, which only they can tell you.

### How this relates to KiCad's own position file

`fenolite export --pos` writes KiCad's own position file, untouched (`docs/exports.md`). The default
template of `fenolite pnp` describes the same placements, and these differences were measured against
`kicad-cli pcb export pos --format csv --units mm --side both` on KiCad 9.0.9 and 10.0.6
(`tests/kicad/assembly/test_assembly_oracle.py`, hypothesis `H-K-POS-ROWS`):

| | KiCad's file | `fenolite pnp`, default template |
|---|---|---|
| columns | `Ref`, `Val`, `Package`, `PosX`, `PosY`, `Rot`, `Side` | the same content under the names `ref`, `value`, `footprint_name`, `x`, `y`, `rotation`, `side` |
| X and Y | millimetres, Y negated, 6 decimals | the same numbers, 4 decimals |
| rotation | the stored angle, printed from above −180° to 180° (270° is `-90.000000`), on both sides | the same angle, printed from 0° up to 360° (270° is `270.00`), on both sides |
| side | `top`, `bottom` | the same |
| DNP parts | listed | left out; set `exclude_dnp = false` to list them |
| parts excluded from position files | left out | left out |
| quoting | text fields always quoted | only fields that need it; set `quote = "all"` to quote every field |

So the two files give the same angle for every part, written differently when it is above 180°.

## The two sources of a bill of materials

`fenolite bom` has a `--source` option.

- `--source kicad`, the default, asks `kicad-cli` for the parts of the project's schematic
  (`<name>.kicad_sch` next to the board). KiCad is the judge of what a schematic holds: which symbols are on
  the bill, which are DNP, what their fields say. The tool runs on a copy, so the project folder does not
  change. Fenolite asks for one row per reference and does the grouping itself, so both sources group the
  same way. Use it whenever the project has a schematic.
- `--source model` lists the parts of the model: in a project that Fenolite built, the `.fenolite/` model;
  for any other project, the board file as Fenolite reads it. It needs no tool and no schematic. Use it
  where `kicad-cli` is not installed, or for a board without a schematic.

The command never falls back from one source to the other, so a file never claims a source it did not
have: without a schematic, `fenolite bom PATH` exits with an error that names `--source model`.

For a project that Fenolite built, the two sources give the same parts: references, values, footprints,
DNP marks, descriptions and user properties. That was measured on KiCad 9.0.9 and 10.0.6
(`tests/kicad/assembly/test_assembly_oracle.py`, hypothesis `H-K-BOM-MODEL`). They can differ on a project
that was edited in KiCad afterwards, and on a board Fenolite did not build: there a part is whatever the
board file holds, a component that exists only in the schematic is not on it, and the bill from the model
is labelled `INFERRED`.

What `kicad-cli` is asked for (`sch export bom`), measured on both versions (`H-K-BOM-CSV`): one row per
reference, also for a symbol with several units; `DNP` in the DNP column of a part marked so; no power flag
and no symbol that is marked as not in the bill; an empty cell for a property a part does not have. A
property whose name holds a comma cannot be asked for (`bom.field-unsupported`); the `model` source reads
it.

`--against OTHER` also lists what changed from the project `OTHER` to `PATH`, line by line, under the same
template: `removed` (a line only `OTHER` has), `added` (a line only `PATH` has) and `changed` (the same
grouping values with different references).

## Things to watch

- **DNP parts and grouping.** With `exclude_dnp = false`, add `"dnp"` to `group_by`. Otherwise a fitted
  part and a DNP part of the same value share one line and one quantity.
- **The internal property `fenolite.path`.** A built project gives every component this property. It is
  listed only if a column names it.
- **Units.** `"in"` is 25.4 mm and `"mil"` is 0.0254 mm, exactly.
- **One file for both sides.** `--side top` or `--side bottom` keeps one side, so two calls give two
  files.

## Counts in the result

`result.counts` of `bom`: `parts` (the parts on the lines), `lines`, `dnp` (the DNP parts the source has,
listed or not) and `left_out` (the footprints of the board that are not parts of the bill; `null` for the
`kicad` source, because KiCad does not say what it leaves out). Of `pnp`:
`rows`, `top`, `bottom`, `dnp` (the DNP footprints the board has, listed or not) and `left_out` (the
footprints of the board that have no row, for any reason: a filter, `--side`, or the attribute).

## Evidence

- Grouping, column mapping, unit conversion, the rotation rule and CSV rendering are mechanical: Fenolite
  claims that the file holds the neutral table under your template.
- The placement rows rest on `H-K-PCB-POS` (positions and stored angles equal KiCad's, verified) and on
  `H-K-POS-ROWS` (the whole rows, as above). The envelope carries the level recorded for them in
  `docs/hypotheses.md`, combined with the level of the board read.
- The bill from `kicad-cli` rests on `H-K-BOM-CSV`: what the export writes for the call Fenolite makes.
- The bill from the model rests on `H-K-BOM-MODEL`: on a built project it equals the bill from
  `kicad-cli`. For any other input it is `INFERRED`.

Sources: RFC 4180 (S-0365) and the Python `csv` documentation (S-0366) for the CSV rules; the observed
output of `kicad-cli` (S-0020) and its manuals (S-0022, S-0037) for the position file. They are listed in
`docs/evidence/sources.md`.
