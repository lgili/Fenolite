# KiCad ERC reports (JSON) and the parity test of a DRC run

`kicad-cli sch erc --format json --severity-all -o <out> <schematic>` writes a report of the electrical
rules check of a schematic and of every sheet its hierarchy reaches.
`fenolite.backends.kicad.erc.read_erc_report` reads it into the neutral `ErcReport` of
`fenolite.backends.base`. `kicad-cli pcb drc --schematic-parity` adds the comparison of a board with its
schematic to a DRC report (`drc.md`).

This page describes both in Fenolite's own words. Key names of the ERC report come from the schema files
S-0450 (tag 10.0.6) and S-0451 (tag 9.0.9.1), which are in KiCad's GPL tree: only the names were recorded
when the change was proposed, and the files are never vendored or read at runtime. Everything else was
measured by running `kicad-cli` 9.0.9 and 10.0.6 as a subprocess (S-0020) on projects that Fenolite built
and on sheets authored for Fenolite. Sources are listed in `docs/evidence/sources.md`.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| `sch erc` writes the JSON report with `--format json`, includes every severity with `--severity-all`, takes the output path with `-o`, and exits with a code that says whether violations exist only with `--exit-code-violations` (10.0 and 9.0) | S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-JSON |
| A report is one object with the keys `source` (the schematic path as the tool was given it), `date`, `kicad_version` and `sheets`, and with `$schema`, `coordinate_units` and `included_severities` | S-0450, S-0451, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-JSON |
| `sheets` is a list with one object per sheet of the hierarchy, the root first: `path` is the readable path of the sheet (`/` for the root, `/<sheet name>/` below it), `uuid_path` is the path of uuids that the symbols of the schematic use for that sheet, and `violations` is a list | S-0450, S-0451, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-JSON |
| A violation has `type`, `description`, `severity` and `items`, and the optional boolean `excluded`; an item has `uuid` (the uuid of a pin, a symbol, a label or a wire of a sheet file), `description` and `pos`, an object with the numbers `x` and `y` | S-0450, S-0451, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-JSON |
| At 10.0.6 a report also holds `ignored_checks`: a list of objects with `key` (the settings key of a check whose severity is set to ignore) and `description`; a 9.0.9 report has no such key | S-0450, S-0451, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-JSON |
| The run exits 0 and writes the report whenever the schematic loads, with or without violations; a schematic that does not load (a broken file, an unknown root child) gives exit 3, the line `Failed to load schematic` and no report | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-JSON |
| With `coordinate_units` `mm`, the `pos` of an item is its position on the sheet in millimetres divided by 100: the pin at (29.21, 27.94) mm is reported at `x` 0.2921 and `y` 0.2794, on 9.0.9 and on 10.0.6 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-POS |
| A pin on no net and without a no-connect flag is reported as `pin_not_connected` (error), with the pin as its item at the pin's connection point | S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-TYPES |
| A net of input pins without a driving pin is reported as `pin_not_driven` (error), once for the net | S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-TYPES |
| A power input pin on a net without a power output pin or a power flag is reported as `power_pin_not_driven` (error) | S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-TYPES |
| A symbol whose library the project's `sym-lib-table` does not name is reported as `lib_symbol_issues` (warning), with the symbol as its item | S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-TYPES |
| A global label that is the only one of its name and sits on one pin is reported as `isolated_pin_label` (warning) on 10.0.6 and as `global_label_dangling` (warning) on 9.0.9 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-TYPES |
| The severity of a type is the value of the key of that name under `/erc/rule_severities` of the project file: `error`, `warning` or `ignore`. With `ignore` the report holds no entry of the type, and on 10.0.6 its key joins `ignored_checks` | S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-TYPES |
| A check that looks at a sheet file and not at one use of it (a pin off the connection grid, a missing library) is listed under the root sheet `/` even when its item lies in a child file, and names the item by the reference of one of its uses | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-JSON |
| `sch erc` reads the root schematic, the sheet files its hierarchy reaches, the project file of the schematic's stem, the project `sym-lib-table` and the symbol libraries it names; a run on these files gives the violations of a run on the whole project folder | S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-COPYSET |
| Beside its report, `sch erc` writes `<stem>.kicad_prl` next to its input on 10.0.6 and nothing on 9.0.9 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-COPYSET |
| Two runs of `sch erc` on one unchanged project give the same violations by sheet, type, severity and exclusion, counts included. The item named for one violation can differ: where several pins or labels are involved, the report names one of them, and not the same one in every run (seen on `power_pin_not_driven` on 9.0.9 and on `multiple_net_names` on 10.0.6) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-REPEAT-2 |
| A project and the same project with every sheet file re-dumped by Fenolite give the same violations by sheet, type, severity and exclusion, counts included | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-ERC-RT2-2 |
| `pcb drc --schematic-parity` fills the `schematic_parity` list of the DRC report with entries of the violation shape (`net_conflict`, `footprint_symbol_mismatch`, `missing_footprint`, `extra_footprint`, all warnings by default); without the flag the list is empty | S-0022, S-0037, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PARITY-RUN |
| With the flag and no schematic beside the board, the run writes its report with an empty `schematic_parity` and prints `Failed to fetch schematic netlist for parity tests.`; with a schematic that does not load, the run exits 255 and writes no report | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PARITY-RUN |

## How Fenolite reads it

These are decisions of the reader, not facts about KiCad.

- **Strict JSON.** The text is parsed with numbers kept as text; `NaN`, `Infinity` and `-Infinity` raise
  `FormatError`, and no float is ever created.
- **Keys.** A missing key of `erc.REQUIRED_KEYS` raises `FormatError` naming it. Unknown keys are
  ignored. `excluded` defaults to false. `ignored_checks` is kept as the `key` string of each entry, and
  `included_severities` is kept when present. A report without `coordinate_units` is read as millimetres.
- **Positions.** `x` and `y` are converted to integer nanometres from `coordinate_units` with exact
  rational arithmetic, then multiplied by `erc.POSITION_SCALE[<major>]`, so that a position is the
  position on the sheet. A major without a proved factor keeps the converted value, and the reader says so
  with the info `kicad.erc.position-unscaled`.
- **Sheets.** Every violation keeps the readable `path` of its sheet as `sheet` and the `uuid_path` as
  `sheet_id`. Violations keep file order, sheet by sheet; `ErcReport.sheets` lists the readable paths.
- **Locations.** `erc.item_locations` maps the uuid of an item to `REF-PIN` for a pin, `REF` for a symbol
  and the label text for a label, from the sheet files of the copy set. The reference is the one the
  symbol's `instances` give for the sheet of the violation. When the report lists a violation under
  another sheet than the one the item lies on, the reference is used only if every use of the item gives
  the same one; otherwise the item is located by its position.
- **Parity.** `KicadOracle.drc` passes `--schematic-parity` only when the copy set holds the board's
  schematic. When that run writes no report, DRC runs again without the flag, so that the copper verdict
  does not depend on the schematic; parity is then reported as not judged. A run that prints the line
  about the schematic netlist is also reported as not judged.
