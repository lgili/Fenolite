## ADDED Requirements

### Requirement: ERC report reading
`fenolite.backends.kicad.erc.read_erc_report(text, *, file="", major=None, issues=None) -> ErcReport` SHALL return an `ErcReport` (`backend-protocol`, "Neutral ERC report") for the JSON text that `kicad-cli sch erc --format json` writes.
- The text MUST be parsed as strict JSON with numbers kept as text. `NaN`, `Infinity` and `-Infinity` MUST raise `FormatError`, and no float is ever created.
- `erc.REQUIRED_KEYS` MUST map `report`, `sheet` and `violation` to the keys required at that level, and a missing one MUST raise `FormatError` naming the key: at the root `source`, `date`, `kicad_version` and `sheets`; in a sheet `path`, `uuid_path` and `violations`; in a violation `type`, `description`, `severity` and `items`. Unknown keys MUST be ignored.
- `excluded` MUST default to false. `ignored_checks`, present at 10.0.6 only, MUST be kept as the `key` string of each entry, and `included_severities` MUST be kept when present. A report without `coordinate_units` MUST be read as millimetres.
- **Positions.** Each `pos` MUST be converted to integer nanometres from `coordinate_units` (`mm`, `mils`, `in`) with exact rational arithmetic, and then multiplied by `erc.POSITION_SCALE[<major>]`, the major being `major` or, when it is `None`, the first number of `kicad_version`. `POSITION_SCALE` MUST hold 100 for each major whose probe `erc-position-scale` is `equal` (`H-K-ERC-POS`). For a major it does not hold, the position MUST stay as converted, and the reader MUST add the info `kicad.erc.position-unscaled` to `issues` when a list is given.
- Each violation's `sheet` MUST be the `path` of its sheet and its `sheet_id` the `uuid_path`; `ErcReport.sheets` MUST list the `path` of every sheet of the file; and violations MUST keep file order, sheet by sheet. `type` and `severity` MUST stay KiCad's strings.
- `docs/formats/kicad/erc.md` MUST describe the report structure in Fenolite's own words, in a table with the header `| fact | source | label | hypothesis |`, with the key names the tool writes (S-0020), which S-0450 and S-0451 also hold; `erc.v1.json` MUST NOT be vendored or read at run time.

#### Scenario: Report of 10.0
- **GIVEN** the authored `tests/data/kicad/erc/report_10.json`, whose first violation is a `pin_not_connected` on sheet `/` with an item at `x` 1.397 and `y` 0.5969, and whose `ignored_checks` holds one entry
- **WHEN** `read_erc_report` reads it
- **THEN** `report.violations[0].type == "pin_not_connected"`, its `sheet` is `/`, `report.sheets` is `("/", "/Child/")`, its first item has `position == Point(139_700_000, 59_690_000)`, and `report.ignored_checks` holds that entry's key

#### Scenario: Report of 9.0
- **GIVEN** the authored `tests/data/kicad/erc/report_9.json`, without `ignored_checks`
- **WHEN** `read_erc_report` reads it
- **THEN** `report.ignored_checks == ()`, and its positions are scaled as in the 10.0 report

#### Scenario: Missing required key
- **GIVEN** `report_10.json` without `sheets`
- **WHEN** `read_erc_report` reads it
- **THEN** `FormatError` is raised naming `sheets`

#### Scenario: Non-strict number rejected
- **GIVEN** `report_10.json` with one coordinate replaced by `NaN`
- **WHEN** `read_erc_report` reads it
- **THEN** `FormatError` is raised

#### Scenario: Unknown major
- **GIVEN** `report_10.json` with `kicad_version` `11.0.0`
- **WHEN** `read_erc_report(text, issues=[])` reads it with an `issues` list
- **THEN** the first item's position is `Point(1_397_000, 596_900)`, and the list holds one `kicad.erc.position-unscaled` info

#### Scenario: Fact table checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** it passes with `erc.md` present
