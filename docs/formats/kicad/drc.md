# KiCad DRC reports (JSON)

`kicad-cli pcb drc --format json --severity-all -o <out> <board>` writes a report of the design rule
check. `fenolite.backends.kicad.drc.read_drc_report` reads it into the neutral `DrcReport` of
`fenolite.backends.base`. This page describes the report in Fenolite's own words. Key names come from
the schema files S-0055 (tag 10.0.6) and S-0056 (tag 9.0.9.1), which are in KiCad's GPL tree: only the
names were recorded, and the files are never vendored or read at runtime. Sources are listed in
`docs/evidence/sources.md`.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| `pcb drc` writes the JSON report with `--format json`, includes every severity with `--severity-all`, and takes the output path with `-o` (10.0 and 9.0) | S-0022, S-0037 | INFERRED | H-K-DRC-JSON |
| A report is one object with the required keys `source` (board path), `date`, `kicad_version`, `violations`, `unconnected_items`, `schematic_parity` and `coordinate_units`, and the optional keys `$schema` and `included_severities` | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| At 10.0.6 a report may also hold `ignored_checks`: a list of objects with `key` (the settings key of a check whose severity is set to ignore) and `description`; the 9.0.9.1 schema has no such key | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| `violations`, `unconnected_items` and `schematic_parity` are lists of violations; a violation has `type`, `description`, `severity` and `items` (required), and `excluded` (a boolean, false by default) and `comment` (optional) | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| An item of a violation has `uuid` (the uuid of the board item), `description` and `pos`, an object with the numbers `x` and `y` | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| `coordinate_units` is `mm`, `mils` or `in`, and every position of the report is in that unit | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| A violation's `severity` is `error` or `warning`; `included_severities` may also list `exclusion` | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| `type` has no enumeration in the schema, and no number of the report holds a measured distance | S-0055, S-0056 | INFERRED | H-K-DRC-JSON |
| The schema file itself has a trailing comma in its list of required keys at both tags, so it is not strict JSON | S-0055, S-0056, S-0057 | INFERRED | H-K-DRC-JSON |
| Strict JSON allows no trailing comma and no number such as `NaN` or `Infinity` | S-0057 | INFERRED | H-K-DRC-JSON |
| The library checks report `lib_footprint_issues` (footprint not found in an active library) and `lib_footprint_mismatch` (footprint differs from its library copy) | S-0038, S-0058 | INFERRED | H-K-LIB-DRC |
| `kicad-cli` 9.0.9 and 10.0.6 write strict JSON reports that hold the 7 required keys; `ignored_checks` appears in the 10.0.6 report and not in the 9.0.9 one | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRC-JSON |

## How Fenolite reads it

These are decisions of the reader, not facts about KiCad.

- **Strict JSON.** The text is parsed with numbers kept as text; `NaN`, `Infinity` and `-Infinity`
  raise `FormatError`, and no float is ever created.
- **Keys.** A missing required key raises `FormatError` naming it. Unknown keys are ignored.
  `ignored_checks` is kept as the `key` string of each entry; `included_severities` is kept when present.
- **Positions.** `x` and `y` are converted to integer nanometres from `coordinate_units` (1 mm =
  1 000 000 nm, 1 mil = 25 400 nm, 1 in = 25 400 000 nm) with exact rational arithmetic, rounded half to
  even when the value is not a whole number of nm. They are report positions, not model geometry. Any
  other unit raises `FormatError`.
- **Strings.** `type` and `severity` stay KiCad's strings. Violations, unconnected items and parity
  items keep the order of the report.
- **Verdicts.** Every DRC verdict is read from the report. The exit code of `pcb drc` is only a load
  signal, and `--exit-code-violations` is never passed. A report without violations is never evidence
  that a library table or a rules file was loaded; such proofs carry a control that fires only when the
  file was loaded.

`drc.EVIDENCE` is `KICAD-VERIFIED` (`H-K-DRC-JSON`, settled on 9.0.9 and 10.0.6 by `tests/kicad/board/test_drc_report.py`).
