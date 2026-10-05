## Context

- **Scope.** Plan v0.2a: "`bom` via `kicad-cli sch export bom` with neutral columns mapped; PnP", acceptance "BOM with neutral columns". Roadmap, v0.2a: "BOM and pick-and-place files with a user-supplied column template: names, order, units, rotation offset per footprint, side naming, grouping by value, footprint and part number. No template for any assembly house ships with Fenolite." Plan appendix A, item 12: "BOM + diff".
- **What exists.**
  - `Component` with `ref`, `value`, `dnp`, `lib_footprint_ref` and `properties` (user properties included, c0027); `FootprintInstance` with `position`, `rotation`, `side` and `attributes` (`smd`, `through_hole`, `board_only`, `exclude_from_pos_files`, `exclude_from_bom`, `dnp`).
  - `export --pos` writes KiCad's own position CSV (c0024). `H-K-PCB-POS` is `KICAD-VERIFIED (9.0.x, 10.0.x)`: model placements equal `pcb export pos` in reference, x, y, side and rotation modulo 360° on both sides.
  - `outline.board_outline` gives the board outline as rings (c0028).
  - c0061 puts the component's properties on its symbol, so the schematic's BOM sees them.
  - The row `exports` of the layering test allows `model`, `geometry` and any backend.
- **Observed at proposal time** (2026-10-04):
  - `sch export bom` exists on 9.0.9 and 10.0.6 with `--fields`, `--labels`, `--group-by`, `--sort-field`, `--exclude-dnp`, `--field-delimiter`, `--string-delimiter`, `--ref-delimiter` and `--ref-range-delimiter`. Its default fields are `Reference,Value,Footprint,${QUANTITY},${DNP}` on 9.0.9 and the same without `${}` on 10.0.6, which accepts both spellings. `--include-excluded-from-bom` works on 9.0.9 and is deprecated without effect on 10.0.6.
  - On 10.0.6, for the hand-made blink sheet: the default call writes the header `"Refs","Value","Footprint","Qty","DNP"` and one row per part, every field quoted; `--fields` with a user property (`fenolite.path`) and `${ITEM_NUMBER}` gives those columns; a field that no symbol has gives an empty column and exit 0; an empty `--string-delimiter` with a tab as field delimiter gives unquoted tab-separated rows; the power flags are not listed.
  - On 10.0.6, `pcb export pos --format csv --units mm --side both` writes `Ref,Val,Package,PosX,PosY,Rot,Side`: the package is the footprint name without its library, Y is negated, the side is `top` or `bottom`, and `--smd-only` leaves out the through-hole part.
- **Constraints.** Stdlib only (`tomllib`, `csv`, `decimal`). No float: lengths in nm, angles in µdeg, printed as exact decimals. No name of a company in code, tests, docs or examples.

## Goals / Non-Goals

**Goals:**
- One neutral BOM and one neutral placement table per project, the same whatever file they are rendered to.
- A template a user can write in a few lines to get the columns their assembly service asks for.
- KiCad as the judge of the content: which parts, which fields, which positions.
- Tables an agent can read without a file: JSON in the envelope.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Guessing a rotation convention. A template states it; the default is KiCad's own.

## Decisions

1. **Probe first.** Task group 2 pins on both majors what `sch export bom` writes for the argument list of Decision 4 (header, quoting, one row per reference, multi-unit symbols, DNP, parts left out of the BOM, an unknown field), before the reader is final.

2. **Neutral BOM.** `exports/bom.py`:
   - `BomPart(ref, value, footprint, description, datasheet, dnp, properties)`: one per part that goes on the bill.
   - `parts_from_model(design) -> tuple[BomPart, ...]`: each component that has a placed footprint, except those whose footprint has `board_only` or `exclude_from_bom`, and references that start with `#`; `dnp` is `Component.dnp` or the footprint attribute; `properties` are the component's properties without `Reference`, `Value`, `Footprint`, `Datasheet` and `Description`.
   - `group(parts, template) -> tuple[BomLine, ...]`: parts with equal values of every `group_by` field form one `BomLine(refs, quantity, fields)`; references inside a line and lines among themselves are in natural order of the reference. With `exclude_dnp`, DNP parts are left out before grouping.
   - `difference(a, b) -> tuple[BomChange, ...]`: lines matched by their `group_by` values; `added`, `removed`, or `changed` with both reference lists.

3. **Neutral placement rows.** `exports/placement.py`:
   - `rows_from_model(design) -> tuple[PlacementRow, ...]`: one `PlacementRow(ref, value, footprint, position, rotation, side, dnp, mount, properties)` per footprint without `exclude_from_pos_files`, in natural order of the reference; `position` is the footprint's position in the board file's frame, in nm; `mount` is `smd`, `through_hole` or `other` from the attributes.
   - `apply(rows, template, *, outline) -> tuple[PlacedRow, ...]` applies, in this order: the DNP and `smd_only` filters; the origin (`page`: none; `outline`: the left edge of the outline's bounding box and, for `y_axis = "up"`, its lower edge, else its upper edge); the Y axis (`up` negates Y, as KiCad's position file does); the rotation rule; the unit.
   - **Rotation rule.** `rotation' = (sign × rotation + side offset + footprint offset) mod 360°`, with `sign` 1 or −1 and an offset per side, and the offset of the first `[[placement.rotation.footprint]]` entry whose `match` (a `fnmatch` pattern on the footprint's lib id) fits. One affine rule per side covers the conventions of position files without naming any.
   - Rejected: reading KiCad's position CSV as the source. The model already equals it (`H-K-PCB-POS`), and a model source needs no tool and no schematic.

4. **The `kicad` source of a BOM.** `KicadCli.export_bom(schematic, *, fields, files=None) -> CliRun` runs `sch export bom` with `--fields Reference,Value,Footprint,Datasheet,Description,${DNP}` followed by each property a template column or `group_by` names, `--labels` equal to the fields, no `--group-by`, an empty `--ref-range-delimiter`, `,` as field delimiter and `"` as string delimiter, `-o <out>`.
   - `backends/kicad/bom.py::read_bom_csv(text, *, fields) -> tuple[BomPart, ...]` reads the rows with the stdlib `csv` reader and the header it asked for; a header that differs raises `FormatError`.
   - A property name that holds `,` cannot be passed in `--fields`: `bom.field-unsupported` (error) names it.
   - Fenolite groups; KiCad lists. Grouping in one place keeps the two sources comparable.

5. **Sources of `fenolite bom`.** `--source kicad` (the default) needs a schematic and the tool; `--source model` needs neither. No silent fallback: without a schematic the default exits 3 with a hint that names `--source model`.
   - On a built project the two sources must give equal parts (`H-K-BOM-MODEL`). They differ by design on a project whose board has parts the schematic lacks; `docs/assembly.md` says which source to trust for what.

6. **Template** (`exports/assembly.py`, a TOML file read with `parse_float=Decimal`):

   ```toml
   schema = "fenolite.assembly-template.v0"

   [csv]
   delimiter = ","      # one character
   quote = "minimal"    # minimal | all
   line_end = "lf"      # lf | crlf
   header = true
   encoding = "utf-8"   # utf-8 | utf-8-sig

   [bom]
   columns = [
     { name = "Parts", field = "refs" },
     { name = "Count", field = "quantity" },
     { name = "Marking", field = "value" },
     { name = "Shape", field = "footprint_name" },
     { name = "Bin", field = "property:Bin" },
   ]
   group_by = ["value", "footprint", "property:Bin"]
   ref_separator = ","
   exclude_dnp = true

   [placement]
   columns = [
     { name = "Part", field = "ref" },
     { name = "Across", field = "x" },
     { name = "Up", field = "y" },
     { name = "Face", field = "side" },
     { name = "Turn", field = "rotation" },
   ]
   units = "mm"         # mm | in | mil
   decimals = 4
   rotation_decimals = 2
   origin = "page"      # page | outline
   y_axis = "up"        # up | down
   sides = { top = "top", bottom = "bottom" }
   exclude_dnp = true
   smd_only = false

   [placement.rotation]
   top = { sign = 1, offset = 0 }
   bottom = { sign = 1, offset = 0 }

   [[placement.rotation.footprint]]
   match = "Mini:Mini_QFP*"
   offset = 90
   ```

   - BOM fields: `refs`, `quantity`, `value`, `footprint`, `footprint_name`, `description`, `datasheet`, `dnp`, `item` (the line number from 1) and `property:<NAME>`. Placement fields: `ref`, `value`, `footprint`, `footprint_name`, `x`, `y`, `rotation`, `side` and `property:<NAME>`.
   - Every key is optional; a missing table or key takes the value of `assembly.DEFAULT`. The default BOM is `refs`, `quantity`, `value`, `footprint` grouped by `value` and `footprint`; the default placement is `ref`, `value`, `footprint_name`, `x`, `y`, `rotation`, `side` in millimetres, origin `page`, Y up, signs 1 and offsets 0, which is the content of KiCad's own position file.
   - An unknown key, an unknown field, a duplicate column name, a `group_by` field outside the vocabulary, or a value outside its set gives `assembly.template-invalid` (error) naming the key, and the command exits 3 (`FEN-3004`).
   - The column names of the example above are invented for this document. No other template is in the repository.

7. **Rendering.** `assembly.render_csv(header, rows, csv_options) -> bytes` with the stdlib `csv` writer: quoting `minimal` or `all` as RFC 4180 describes it (S-0365), the delimiter and line end of the template, UTF-8.
   - Lengths are printed from nm as exact decimals rounded half to even at `decimals`; rotations from µdeg at `rotation_decimals`; never through a float.
   - `dnp` prints `DNP` or an empty field; `quantity` and `item` print integers.
   - Two renderings of one table under one template are byte-identical.

8. **Commands.** Both are `mutates=True` and write only with `--out`:
   - `fenolite bom PATH [--source kicad|model] [--template FILE] [--out FILE] [--against OTHER] [--kicad-cli PATH] [--timeout S]`. `result`: `source`, `template`, `columns`, `lines` (each line as an object by field), `counts` (`parts`, `lines`, `dnp`, `left_out`), and with `--against`, `changes`. `--out` plans one file of kind `bom`.
   - `fenolite pnp PATH [--template FILE] [--side top|bottom|both] [--out FILE]`. `result`: `template`, `columns`, `rows`, `counts`, `units`, `origin`. `--out` plans one file of kind `pnp`. No tool is ever run.
   - `PATH` resolves as `check`'s does; built input reads the `.fenolite/` model for `--source model`, native input the board.
   - A column that names a property no part has gives `bom.property-missing` (info) and an empty column.
   - `origin = "outline"` on a board without a closed outline gives `pnp.no-outline` (error) and no file.
   - `example_args` use the authored board and no tool; `bom`'s example passes `--source model`.

9. **Evidence.** `bom.EVIDENCE_KICAD` (`H-K-BOM-CSV`) with the oracle `kicad-cli <version>`; `bom.EVIDENCE_MODEL` (`H-K-BOM-MODEL`); `placement.EVIDENCE` (`H-K-PCB-POS`, `H-K-POS-ROWS`). Each starts `INFERRED` and is raised with its rows. The envelope carries the level of the source it used; the template adds no claim.

10. **No model change, no FEN code.** `bom.*`, `pnp.*` and `assembly.*` codes join `exports.codes.ISSUE_CODES`.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/exports/assembly.py` (new) | `AssemblyTemplate`, `BomTemplate`, `PlacementTemplate`, `Column`, `CsvOptions`, `RotationRule`; `read_template(text, *, file="") -> AssemblyTemplate`; `DEFAULT`; `BOM_FIELDS`, `PLACEMENT_FIELDS`; `render_csv(header, rows, options) -> bytes`; `format_length(nm, units, decimals) -> str`; `format_angle(udeg, decimals) -> str` |
| `src/fenolite/exports/bom.py` (new) | `BomPart`, `BomLine`, `BomChange`; `parts_from_model(design) -> tuple[BomPart, ...]`; `group(parts, template) -> tuple[BomLine, ...]`; `table(lines, template) -> tuple[tuple[str, ...], ...]`; `difference(a, b) -> tuple[BomChange, ...]`; `EVIDENCE_KICAD`, `EVIDENCE_MODEL` |
| `src/fenolite/exports/placement.py` (new) | `PlacementRow`, `PlacedRow`; `rows_from_model(design) -> tuple[PlacementRow, ...]`; `apply(rows, template, *, outline=None) -> tuple[PlacedRow, ...]`; `table(rows, template) -> tuple[tuple[str, ...], ...]`; `EVIDENCE` |
| `src/fenolite/backends/kicad/bom.py` (new) | `read_bom_csv(text, *, fields) -> tuple[BomPart, ...]`; `bom_fields(template) -> tuple[str, ...]` |
| `src/fenolite/backends/kicad/cli.py` (extended) | `KicadCli.export_bom(schematic, *, fields, files=None) -> CliRun` |
| `src/fenolite/exports/codes.py` (extended) | `assembly.template-invalid`, `bom.property-missing`, `bom.field-unsupported`, `pnp.no-outline` |
| `src/fenolite/cli/cmd_bom.py`, `cmd_pnp.py` (new) | `COMMAND`s (`mutates=True`) |
| `tests/data/assembly/columns.toml`, `rotated.toml`, `invalid.toml`, `bom_export.csv` (new, authored) | templates with invented column names; a BOM export in the shape `kicad-cli` writes |
| `tests/unit/exports/test_assembly.py`, `test_bom.py`, `test_placement.py`; `tests/unit/backends/kicad/test_bom_csv.py`; `tests/unit/cli/test_bom_cmd.py`, `test_pnp_cmd.py` (new) | hermetic |
| `tests/kicad/assembly/_asmcases.py`, `test_bom_probes.py`, `test_assembly_oracle.py` (new) | oracle, both majors |
| `docs/assembly.md` (new); `docs/cli-contract.md`, `docs/exports.md`, `docs/formats/kicad/cli.md` (extended) | template reference and guide; the two commands; the BOM export facts |

## Sources registered by this change

| id | URL | used for |
|---|---|---|
| S-0365 | https://www.rfc-editor.org/rfc/rfc4180 | CSV: fields that hold the delimiter, a quote or a line break are quoted, and a quote inside a quoted field is doubled |
| S-0366 | https://docs.python.org/3/library/csv.html | the stdlib writer's `QUOTE_MINIMAL` and `QUOTE_ALL`, `delimiter` and `lineterminator` |

Rows of other changes cited here: S-0020 (observed `kicad-cli` behaviour), S-0022 and S-0037 (`sch export bom` and `pcb export pos` with their options). Task 9.1 widens S-0020, S-0022 and S-0037 for `sch export bom`. The proposal reserved S-0340 to S-0344; c0076 registered those ids first, so this change takes S-0365 and S-0366, above every block that a pending change reserves.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-BOM-CSV | With the arguments of Decision 4, `sch export bom` writes a header equal to the labels and one row per reference: a multi-unit symbol once, no reference that starts with `#`, no symbol left out of the BOM; `${DNP}` prints `DNP` or nothing; a field no symbol has is an empty column (S-0020, S-0022, S-0037) | `tests/kicad/assembly/test_bom_probes.py` | on 9.0.9 and 10.0.6: probes `bom-csv-header`, `bom-csv-rows`, `bom-csv-units`, `bom-csv-dnp`, `bom-csv-left-out`, `bom-csv-unknown-field` = `equal` |
| H-K-BOM-MODEL | For a built project, `parts_from_model` gives the parts that `read_bom_csv` reads from `kicad-cli`: same references, values, footprints, DNP flags and user properties | `tests/kicad/assembly/test_assembly_oracle.py::test_bom_sources` | on both majors, for the blink with user properties and for the units design: equal parts; probes `bom-model-blink`, `bom-model-units` = `equal` |
| H-K-POS-ROWS | The placement table under the default template, with DNP parts kept, has the rows of `pcb export pos --format csv --units mm --side both`: reference, value, package, X, Y to the micrometre, rotation modulo 360° and side | `tests/kicad/assembly/test_assembly_oracle.py::test_pos_rows` | on both majors, for the built blink (one bottom-side part) and the authored board: equal row sets; probe `pos-rows` = `equal` |

Ids used without changing their level: `H-K-PCB-POS`, `H-K-EXPORT-FILES`, `H-K-SCH-MINIMAL`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Parts from `kicad-cli` | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-BOM-CSV` | `test_bom_probes.py` |
| Parts from the model | KICAD-VERIFIED on built projects, `H-K-BOM-MODEL`; INFERRED otherwise | `test_assembly_oracle.py::test_bom_sources` |
| Placement rows | KICAD-VERIFIED, `H-K-PCB-POS`, `H-K-POS-ROWS` | `::test_pos_rows` |
| Template, grouping, units, rotation rule, CSV | mechanical | `tests/unit/exports` |
| Commands | mechanical with the fake; observed on both majors | `test_bom_cmd.py`, `test_pnp_cmd.py`, `test_assembly_oracle.py` |

## Budget (7 days)

| work | days |
|---|---|
| registers, fact rows | 0.5 |
| probes on both majors | 0.75 |
| template, validation, CSV rendering | 1.25 |
| BOM: parts, grouping, runner, CSV reader | 1.25 |
| placement rows and rules | 1.0 |
| `bom` command, with `--against` | 0.75 |
| `pnp` command | 0.5 |
| oracle tests on both majors | 0.5 |
| guide, closing | 0.5 |
| **total** | **7.0** |

Cut order: (1) `bom --against`; (2) `origin = "outline"`; (3) `--source kicad` (the model source alone, labelled `INFERRED`, with `H-K-BOM-MODEL` left open). Not optional: both tables from the model, the template with columns, units, sides and the rotation rule, CSV rendering, the placement proof against `pcb export pos`.

## Risks / Trade-offs

- [A template that does not match what a service expects] → Fenolite cannot know; `docs/assembly.md` tells the user to check the first order's files with the service's own viewer, and states what each rule does with one worked example.
- [Rotation of bottom-side parts] → the rule is explicit per side, and the default equals KiCad's file, proved by `H-K-POS-ROWS` with a bottom-side part.
- [A user property with a comma in its name] → refused for the `kicad` source; the `model` source handles it.
- [KiCad lists a part the model leaves out, or the reverse] → `H-K-BOM-MODEL` fails on the examples and the rule of Decision 2 is corrected; on native projects the difference is documented.
- [Examples that look like a real service's columns] → the example names are generic words, reviewed against the residue rules; the residue scan runs on the new files.

## Migration Plan

Additive: three modules, a backend reader, one runner helper, two commands. `export --pos` is unchanged. To roll back, remove them.

## Open Questions

- **One file per side for placement.** Default: one file with a side column; `--side` filters, so two calls give two files.
- **Should `export --all` also write the two tables?** Default: no; `export` stays KiCad's raw files. c0065's manifest lists every file whatever command wrote it.
- **A unit suffix on lengths** (`12.7mm`). Default: no; a template key can be added when a user needs it.
- **Maintainer:** is an example template with generic column names in `docs/assembly.md` acceptable under the clean-room rule? Default: yes, the names are common English words and belong to no one.

## Implementation notes (2026-10-05, first run: everything except the `kicad` BOM source)

What the code does today, where it differs from the text above, and why.

1. **Scope.** The `kicad` source of the bill (Decision 4, `KicadCli.export_bom`, `backends/kicad/bom.py`, `bom.EVIDENCE_KICAD`, `bom.field-unsupported`, the six `bom-csv-*` probes and the two `bom-model-*` probes) needs a schematic that `kicad-cli` can export from. The schematic writer (c0061) is not started, so those tasks stay open (tasks 2.1, 2.2, 4.2 and group 9). This is cut 3 of the cut order.
2. **`--source` meanwhile.** The option keeps both values and its default `kicad`, so no script changes meaning when the source arrives. Until then the `kicad` source refuses and never falls back: without `<stem>.kicad_sch` it exits 3 with `FEN-3001` (as specified), with one it exits 2 with `FEN-2001`; both hints name `--source model`. `--kicad-cli` and `--timeout` are not registered yet.
3. **`pnp` reads the board file, never the `.fenolite/` model.** The proposal said that built input reads the model. `place`, `route` and `fill` write the board and leave the model as it was, so after a move the model's positions are older than the board's, and a placement file from the model would disagree with the board that is fabricated. `tests/unit/cli/test_pnp_cmd.py::test_the_board_is_read_not_the_model` shows it. The spec delta of "Pnp command" is corrected. `bom --source model` still reads the model of a built project: `place` does not change parts.
4. **Example column names.** The proposal's example used names that are common in real assembly files. Every example now uses names made up for Fenolite (`Parts`, `Count`, `Marking`, `Shape`, `Bin`; `Part`, `Across`, `Up`, `Turn`, `Face`), and the example property is `Bin`. Each authored template says so in its header, and a test checks the header.
5. **Source ids.** S-0365 and S-0366, see "Sources registered by this change".
6. **Signatures.** `bom.group` and `bom.table` take the template's `[bom]` table (`BomTemplate`), `placement.apply` and `placement.table` its `[placement]` table. `BomLine` has a fourth field, `key`, the values of the `group_by` fields (the reference when `group_by` is empty), which `difference` matches on. `placement.apply` takes `issues=`, a list that receives `pnp.no-outline`; without it the function raises `NoOutlineError`, so the empty result is never silent. `TemplateError` is defined in `exports/assembly.py`: the layering test does not let `exports` import `templates`.
7. **`group_by`** accepts the fields a single part has; `refs`, `quantity` and `item` belong to a line and are refused.
8. **The default template is not exactly KiCad's file.** Measured on 9.0.9 and 10.0.6: KiCad lists DNP parts, and the default has `exclude_dnp = true`; KiCad prints a rotation within (−180°, 180°] (`-90.000000`) and Fenolite within [0°, 360°) (`270.00`). `docs/assembly.md` has the table. `H-K-POS-ROWS` compares with DNP kept and angles modulo 360°, as specified.
9. **Probe files.** `pos-rows` is `equal` on 10.0.6 (local binary; the whole of `tests/kicad/test_probe_results.py` passes with it) and on 9.0.9 (the pinned image, started by the package's own `docker:` runner from a scratch script, not by pytest inside the image). The 9.0.9 file was not regenerated: the one key was added. The `kicad-9` job is the first full run of that test on 9.0.9, so `H-K-POS-ROWS` and `placement.EVIDENCE` stay `INFERRED` until it passes (task 8.2).
10. **Open design question for the maintainer.** With `exclude_dnp = false` and the default `group_by`, a fitted part and a DNP part of one value share a line and a quantity. The spec asks for exactly that; the guide tells the user to add `dnp` to `group_by`. Splitting by DNP always would be safer.
