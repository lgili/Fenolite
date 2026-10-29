## MODIFIED Requirements

### Requirement: Requirement tables supplied by the user
`fenolite.analysis.requirements.load_requirements(text, *, file="") -> Requirements` SHALL parse a TOML document (`tomllib`) whose top-level key `schema` equals `fenolite.requirements.v0` and which holds any of the arrays `current`, `distance`, `step`, `path`, `decoupling`, `body_copper`, `neck` and `loop`.

**Numbers.** Every quantity MUST be given in one of two forms:
- the raw key, whose name carries the unit, with a TOML integer: `clearance_nm`, `creepage_nm`, `embedded_nm`, `insulation_nm`, `groove_nm`, `max_distance_nm`, `min_width_nm`, `max_area_nm2`, `milliamps`, `temp_rise_mk`, `millivolts`, `up_to_mv`, `drop_mv`;
- or its unit key, with a TOML string that holds a number and a unit: `clearance`, `creepage`, `embedded`, `insulation`, `groove`, `max_distance`, `min_width` (lengths), `max_area` (`mm2`), `current` (amperes), `temp_rise` (kelvin), `voltage`, `up_to` and `drop` (volts).

A unit value MUST be parsed exactly by the parsers of `fenolite.core.units`, and MUST be a whole number of the raw key's unit. Each of the following MUST raise `FormatError` naming the file and the key:
- a float;
- a unit string that is malformed, has no unit, has the wrong unit or is not a whole number of the raw unit;
- both forms of one quantity in a row;
- an unknown key, a missing key or another `schema`.

Every row MAY hold `source`, a non-empty string that names where the user's number comes from. It is shown as the basis of the row's limits and changes no value.

**Rows.**
- A selector is a table with exactly one of the keys `net` and `netclass`, whose value is a glob matched as `model.rules.Selector` matches it. A net without a class has the class `Default`.
- `[[current]]`: a selector under `select`, `milliamps` and `temp_rise_mk`. The governing row of a net MUST be the matching row with the largest `milliamps`.
- `[[distance]]`: selectors `a` and `b`; either any of `clearance_nm`, `creepage_nm`, `embedded_nm` and `insulation_nm`, or `millivolts`; and optionally `groove_nm`, the groove width of "Creepage grooves". A row matches a pair of different nets when `a` matches one and `b` the other, in either order. When several rows match a pair, the largest value of each quantity governs, `groove_nm` included.
- `[[step]]`: `up_to_mv` and any of `clearance_nm`, `creepage_nm`, `embedded_nm` and `insulation_nm`: the user's own table from voltage to distance. A distance row with `millivolts` takes its values from the step with the smallest `up_to_mv` that is at least its `millivolts`. Fenolite MUST NOT interpolate between steps. A voltage above every step gives no requirement and one `analysis.requirement-unmatched` warning naming the row.
- `[[path]]`: `from` and `to`, each a non-empty array of pad names `REF-PIN` (split at the last `-`, both parts non-empty), `milliamps` and `temp_rise_mk`, and optionally `drop_mv`: the current the copper between the two sets of pads must carry, the temperature rise the user accepts and the largest voltage drop ("Power path current", "Power path voltage drop"). A pad name of another form MUST raise `FormatError` naming the key.
- A row whose selectors match no net of the design MUST give one `analysis.requirement-unmatched` warning.
- `embedded_nm` MUST be judged against the gaps on inner layers, `clearance_nm` against `clearance`, `creepage_nm` against `creepage` and `insulation_nm` against `insulation`.

**Unit keys.** In the rows above, a raw key MAY be replaced by its unit key with the same meaning. The loaded `Requirements` MUST be equal whichever form the file uses.

#### Scenario: Step lookup without interpolation
- **GIVEN** steps `up_to_mv = 50_000` with `creepage_nm = 1_000_000` and `up_to_mv = 300_000` with `creepage_nm = 3_000_000`, and a distance row with `millivolts = 230_000`
- **WHEN** `uv run pytest tests/unit/analysis/test_requirements.py -k step` resolves the row
- **THEN** the creepage requirement is 3 mm, and with `millivolts = 400_000` there is none and one `analysis.requirement-unmatched` warning

#### Scenario: Floats refused
- **GIVEN** a document with `milliamps = 2.5`
- **WHEN** `load_requirements` parses it
- **THEN** a `FormatError` names `current[0].milliamps`

#### Scenario: Largest row governs
- **GIVEN** two distance rows that match the pair `L`, `N` with `creepage_nm` 2 mm and 4 mm
- **WHEN** the pair is resolved
- **THEN** the creepage requirement is 4 mm

#### Scenario: Path rows
- **GIVEN** a document with a `[[path]]` row `from = ["J1-1"]`, `to = ["Q1-2", "Q2-2"]`, `milliamps = 20000`, `temp_rise_mk = 10000` and `drop_mv = 50`
- **WHEN** `uv run pytest tests/unit/analysis/test_requirements.py -k path` parses it
- **THEN** `paths` holds one row with those values, and the same row with `from = []` or with `from = ["J1"]` raises a `FormatError` naming `path[0].from`

#### Scenario: Insulation and groove keys
- **GIVEN** two distance rows that match the pair `HV`, `LV`, one with `insulation_nm = 400_000` and `groove_nm = 1_000_000`, the other with `millivolts = 230_000`, and a step `up_to_mv = 300_000` with `insulation_nm = 200_000`
- **WHEN** `uv run pytest tests/unit/analysis/test_requirements.py -k insulation` resolves the pair
- **THEN** the insulation requirement is 0.4 mm and the groove width is 1 mm

#### Scenario: Unit keys equal raw keys
- **GIVEN** one document with `clearance = "1.2mm"`, `current = "2A"`, `temp_rise = "10K"` and `drop = "50mV"` in its rows, and a second with `clearance_nm = 1200000`, `milliamps = 2000`, `temp_rise_mk = 10000` and `drop_mv = 50` in the same rows
- **WHEN** `uv run pytest tests/unit/analysis/test_requirements.py -k units` loads both
- **THEN** the two `Requirements` are equal

#### Scenario: Unit errors
- **WHEN** documents with `clearance = "1.2"`, `clearance = "1.2A"`, `clearance = "0.0001nm"`, and both `clearance = "1.2mm"` and `clearance_nm = 1200000` in one `[[distance]]` row are loaded
- **THEN** each raises `FormatError` naming `distance[0].clearance`

#### Scenario: Source text
- **GIVEN** a `[[distance]]` row with `source = "project insulation decision"`
- **WHEN** it is loaded
- **THEN** the row keeps the text, and a row with `source = ""` raises `FormatError` naming `distance[0].source`
