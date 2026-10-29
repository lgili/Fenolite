## ADDED Requirements

### Requirement: Pick package
`fenolite.pick` SHALL hold queries, pickable rows, series values, matching, the `[picks]` table of the design lock, resolution, proposals and generators. It MUST import only `core`, `model` and `catalog`, open no network connection and run no subprocess. Equal queries, lock and catalog MUST give equal picks, findings and bytes.

#### Scenario: Deterministic picks
- **GIVEN** `examples/picks/divider.py` and an empty lock
- **WHEN** `uv run pytest tests/unit/pick/test_resolve.py -k deterministic` resolves it twice, once under another `PYTHONHASHSEED`
- **THEN** both runs give the same picks and the same planned the design lock bytes

### Requirement: Query value matching
A query's value SHALL match a row of its kind when it is a `Quantity` equal to the row's nominal, or a c0246 range that contains the row's worst-case span (the nominal minus and plus the row's tolerance).

#### Scenario: A range value admits a neighbouring value
- **GIVEN** a catalog with the 1 % E96 0603 family
- **WHEN** `resistor(ohm("10k").pct(5), case="0603")` is matched
- **THEN** the 9.76 kΩ, 10 kΩ and 10.2 kΩ rows match, and the 9.53 kΩ and 10.5 kΩ rows do not (their spans 9.43–9.63 kΩ and 10.40–10.61 kΩ leave 9.5–10.5 kΩ)

### Requirement: Query constraint matching
A row SHALL meet `power`, `voltage`, `rating`, `current` and `saturation` with a rating at least as large, `tolerance`, `tempco` and `dcr` with a value at most as large, and `case`, `series` and `dielectric` by equality, a tuple meaning any of its members. A row that does not state a constrained attribute MUST NOT match, and when no row matches, each row left out only for that reason MUST give `pick.attribute-unknown`.

#### Scenario: An unknown rating never matches
- **GIVEN** a capacitor row that states no voltage rating
- **WHEN** `capacitor(farad("100n"), rating=volt(16))` is matched against a catalog holding only that row
- **THEN** no row matches, the result holds `pick.no-match` and one `pick.attribute-unknown` naming the row and `rating`

### Requirement: Query ranking
Among the rows that match, the pick SHALL be the first in this order: the smaller distance of the row's nominal to the query's nominal; the larger tolerance; the smaller case in `pick.rows.CASE_ORDER`; a project row before a shipped row; the device id in code-point order.

#### Scenario: Ties are broken in order
- **GIVEN** project and shipped families that both offer 10 kΩ 1 % in 0603, and a 10 kΩ 5 % 0603 family
- **WHEN** `resistor(ohm("10k").pct(5), case="0603")` is resolved
- **THEN** the 5 % row is picked; with `tolerance=pct(1)` added, the project row is picked over the shipped one

### Requirement: Defaults cascade
The effective constraints of a query SHALL be the design's defaults for its kind, then those of each enclosing block from the outermost to the innermost, then the call's keywords; a later level replaces a key and `None` removes it.

#### Scenario: The block and the call win in turn
- **GIVEN** `design.defaults(resistor={"case": "0603", "tolerance": pct(1)})`, a block whose body calls `b.defaults(resistor={"case": "0402"})`, and in it `b.part("R", device=resistor(ohm("10k"), tolerance=None))`
- **WHEN** the canonical text of that query is read
- **THEN** it is `resistor(10kΩ, case=0402)`

### Requirement: Canonical query text
The effective query SHALL print as its kind, the value text, then the constraints in the fixed key order of the kind as `<key><op><value>`, quantities in `Quantity.text()` and ranges in c0246's canonical text. The lock MUST compare these texts, never script objects.

#### Scenario: Spellings give one text
- **WHEN** the texts of `capacitor(farad("10u"), rating=volt(25))` and `capacitor(farad("10 uF"), rating=volt("25.0"))` are compared
- **THEN** they are both `capacitor(10uF, rating>=25V)`

### Requirement: Family rows
A family record of schema `fenolite.family.v0` SHALL state `id`, `kind`, `summary`, `symbol`, `footprint`, `case`, `series`, `values` (`min`, `max`), `tolerance`, optional ratings, `evidence` and `sources` per attribute. It MUST expand to one candidate per series value within `values`, both ends included, with the device id `<family id>@<IEC 60062 value code>`.

#### Scenario: A family expands to its series
- **GIVEN** a family `Fenolite:R_0603_E24_5pct` with `values = { min = "10", max = "100" }`
- **WHEN** it is expanded
- **THEN** it yields 25 candidates from `Fenolite:R_0603_E24_5pct@10R` to `@100R`, in value order

### Requirement: Discrete rows and row sources
A c0248 device record that states `kind` and `value` SHALL be a pickable row. Shipped rows come from `fenolite.catalog`, project rows from `devices/` beside the script (c0248). A malformed family or device record MUST raise `FormatError` (`FEN-3004`) naming the file and the key.

#### Scenario: A malformed family
- **GIVEN** a project family whose `values.min` is `"ten"`
- **WHEN** the build reads `devices/`
- **THEN** the exit code is 3 with `FEN-3004` naming the file and `values.min`, and nothing is written

### Requirement: Series values
`pick.series.SERIES` SHALL hold the mantissas of E6, E12, E24, E48, E96 and E192 as integers, transcribed from the registered public source; a test MUST check E48, E96 and E192 against the rounding rule the source states, naming each exception the source lists.

#### Scenario: Series agree with their rule
- **WHEN** `uv run pytest tests/unit/pick/test_series.py` runs
- **THEN** E96 has 96 increasing three-digit mantissas from 100 to 976, and every listed exception of E192 is named by the test

### Requirement: Picks in the lock
Each pick SHALL be the entry `[picks."<component path>"]` of the design lock with the string keys `query`, `device`, `row`, `catalog`, `sha256`, `by`, and `achieved` for a generator's part, in this order, entries in component-path order. Reading and writing MUST round-trip byte for byte.

#### Scenario: Round trip of the picks
- **WHEN** `uv run pytest tests/unit/pick/test_lockpicks.py -k round_trip` runs its property test over generated entries
- **THEN** every printed table reads back to its entries and prints again to the same bytes

### Requirement: Pick entry values
`catalog` SHALL be `fenolite-catalog <CATALOG_VERSION>` for a shipped row and `project:<path relative to the script>` for a project row; `sha256` the SHA-256 of the row's canonical text; `achieved` the generator's range in integer micro-units, the minimum rounded down and the maximum rounded up.

#### Scenario: A project row in the lock
- **GIVEN** a query resolved to a row of `devices/caps.toml` beside the script
- **WHEN** the lock entry is read
- **THEN** `catalog` is `project:devices/caps.toml` and `sha256` is the digest of that row's canonical text

### Requirement: Picks resolved by the build
`fenolite build` SHALL resolve every query part after the script ran and before the model is made, using the lock beside the script and `design.md`, decision 9: an absent entry is resolved with `pick.new`; equal query text and row hash give the locked device; a changed row hash still meeting the query gives `pick.row-changed`; a missing row `pick.row-missing`; no matching row `pick.no-match`. Lock changes MUST be planned writes of the build, refused under `--frozen` as c0249 specifies.

#### Scenario: A cosmetic edit keeps the part
- **GIVEN** a confirmed build whose lock holds `C_in`, after which the script writes `farad("10 uF")` instead of `farad("10u")`
- **WHEN** the build runs with `--dry-run`
- **THEN** the canonical query text is unchanged, no lock write is planned, and the device is the locked one

### Requirement: Changed queries
A changed query text that the locked part still meets SHALL keep the device with `pick.query-changed`; one it no longer meets MUST give `pick.stale` with the hint `fenolite pick --update <path>`, and the build MUST write nothing. A locked pick MUST NOT be replaced by a better match.

#### Scenario: A changed query is not a silent swap
- **GIVEN** a confirmed build whose lock holds `C_in` as `Fenolite:C_0805_X7R_25V@10u`, after which the script asks `rating=volt(50)`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 5, `issues` hold `pick.stale` naming `C_in`, the old device and the failed constraint `rating>=50V`, and nothing is written

#### Scenario: A better match does not replace a lock
- **GIVEN** a lock that picked a shipped row, and a project row added since that ranks first
- **WHEN** the build runs with `--dry-run`
- **THEN** the locked device is used and no lock write is planned

### Requirement: Supplier proposals
`fenolite pick --propose` SHALL write candidate rows only under the `devices/proposed/` folder beside the script, each with `evidence = "UNVERIFIED"` and the line of the file or plugin it came from, and MUST NOT write the design lock. Rows come from `--from FILE` (CSV or JSON with documented columns) or a plugin of the entry-point group `fenolite.suppliers`.

#### Scenario: Proposals from a file
- **GIVEN** an authored CSV of three capacitor rows
- **WHEN** `fenolite pick examples/picks --propose "capacitor(10uF, rating>=25V)" --from rows.csv --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` names three files under `devices/proposed/` and no the design lock, and nothing is written

### Requirement: Unverified rows
A query SHALL NOT pick an `UNVERIFIED` row unless it names that row, and a row ranked out for that reason MUST give `pick.row-unverified`. A supplier plugin that sends data offsite MUST require `--allow-offsite` (exit 2 without).

#### Scenario: A proposal is not picked by itself
- **GIVEN** a proposed `UNVERIFIED` row that would rank first for a query
- **WHEN** the build runs with `--dry-run`
- **THEN** the next verified row is picked and `issues` hold one `pick.row-unverified` naming the proposed row

### Requirement: Generators
A generator SHALL create its parts as query parts carrying a generator request, and its build function MUST be pure over the request and the rows: exact rational arithmetic, each irrational constant replaced by a rational enclosure of 12 decimal digits, a bounded search in a fixed order and explicit tie rules.

#### Scenario: The achieved range encloses the exact one
- **WHEN** `uv run pytest tests/unit/pick/test_generators.py -k enclosure` evaluates every generator on generated inputs
- **THEN** each reported range contains the range computed by brute force with exact arithmetic

### Requirement: Generator results
Each solution SHALL give `gen.achieved` (info) with the achieved range and the inputs, the same text in `result.generators` and in `achieved` of each pick. No accepted combination MUST give `gen.unachievable` (error) naming the combination that overshoots least and by how much.

#### Scenario: Results are reported in one text
- **GIVEN** `examples/picks/divider.py`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the `gen.achieved` message, the entry of `result.generators` and the planned `achieved` keys of both parts state the same range

### Requirement: Locked generator picks
When a generator's inputs change, its locked values SHALL be evaluated with the new inputs: still within the target gives `pick.query-changed` and the new achieved text, otherwise `pick.stale`. A generator MUST NOT search again by itself.

#### Scenario: A wider target keeps the pair
- **GIVEN** a locked divider of 61.9 kΩ over 13.7 kΩ for 3.3 V ± 5 %, after which the target becomes ± 6 %
- **WHEN** the build runs with `--dry-run`
- **THEN** the pair is kept, `issues` hold `pick.query-changed`, and the planned lock holds the new query text

### Requirement: Voltage divider search
`voltage_divider` SHALL search every series value `Rb` of the resistor family whose nominal current lies in `current`, with the one or two series values bracketing the ideal `Rt`, and accept a pair whose worst-case output over the reference (or input) range and both tolerances lies within `target`. The output is `VREF · (1 + Rt / Rb)` at `hi` with `ref`, else `VIN · Rb / (Rt + Rb)` at `mid`.

#### Scenario: A feedback divider with E96 1 %
- **GIVEN** `voltage_divider(b, out, fb, gnd, target=volt("3.3").pct(5), ref=volt("0.6").pct(1), current=between(ua(40), ua(100)))` in block `buck1`, resistor defaults E96 1 % 0603
- **WHEN** it is built with `--dry-run`
- **THEN** `buck1/FB_top` is 61.9 kΩ and `buck1/FB_bot` 13.7 kΩ, and `gen.achieved` says `VOUT 3.224694–3.399373 V within 3.135–3.465 V`

#### Scenario: Unachievable by a hair
- **GIVEN** the same call with `target=volt("3.3").pct(3)`
- **WHEN** it is built with `--dry-run`
- **THEN** the exit code is 5, `gen.unachievable` names 61.9 kΩ over 13.7 kΩ, the range 3.224694–3.399373 V and 373 µV above the target, and nothing is planned

### Requirement: Voltage divider choice
Among accepted pairs, `voltage_divider` SHALL choose the smallest distance of the nominal output to the target's nominal, then the narrowest achieved range, then the smaller `Rb`, then the smaller `Rt`. Its parts MUST be `<name>_top` and `<name>_bot` in the caller's block, `name` defaulting to the name of `mid`.

#### Scenario: A tighter family succeeds
- **GIVEN** the ± 3 % target and resistor defaults `tolerance=pct("0.1")` with a 0.1 % E96 family in the catalog
- **WHEN** it is built with `--dry-run`
- **THEN** the pair is 61.9 kΩ over 13.7 kΩ and `gen.achieved` says `VOUT 3.272477–3.349540 V`

### Requirement: Filter and LED generators
`rc_lowpass` SHALL search the corner `1 / (2πRC)` with π enclosed and choose the nominal corner closest to the target's nominal. `led_resistor` SHALL bound the LED current `(VS − VF) / R` within its range, check the resistor's power rating against the worst `I²R` with c0253's derating, and choose the nominal current closest to the range's nominal.

#### Scenario: An RC corner
- **GIVEN** `rc_lowpass(b, inp, out, gnd, corner=hertz(1000).pct(10), c=capacitor(farad("100n")))`, resistor defaults E24 5 %, a C0G 5 % capacitor family
- **WHEN** `uv run pytest tests/unit/pick/test_generators.py -k rc` builds it
- **THEN** the resistor is the E24 value whose worst-case corner lies within 900–1100 Hz with the nominal closest to 1 kHz, and `gen.achieved` states the corner range

### Requirement: Pull-up and shunt generators
`i2c_pull_ups` SHALL compute the window from the constants of the registered I2C specification for the bus's speed mode and choose the largest series value whose span lies inside it. `shunt` SHALL choose the largest row value whose worst-case drop at the maximum current stays within the minimum full-scale input, check its power rating with the derating, and declare its part class `shunt` for net roles.

#### Scenario: Pull-ups inside the window
- **GIVEN** an I2C bus in fast mode on a 3.3 V ± 3 % rail with `bus_capacitance=between(pf(50), pf(100))`, resistor defaults E24 5 %
- **WHEN** `uv run pytest tests/unit/pick/test_generators.py -k pull_ups` builds it
- **THEN** both lines get one value, the largest E24 value whose worst-case span lies inside the window, and `gen.achieved` states the window and the value

#### Scenario: A shunt with its dissipation
- **GIVEN** `shunt(b, hi, lo, current=between(amp(0), amp(5)), full_scale=volt("0.1").pct(2))` and project shunt rows
- **WHEN** it is built with `--dry-run`
- **THEN** the picked row is the largest value whose worst-case drop at 5 A is at most 98 mV, its power rating covers the worst dissipation with the design's derating, and `.fenolite/rules.json` declares its part class `shunt`

### Requirement: Pick and generator codes
`pick.no-match`, `pick.stale`, `pick.row-missing`, `gen.unachievable` (error), `pick.row-changed` (warning), `pick.query-changed`, `pick.new`, `pick.attribute-unknown`, `pick.row-unverified` and `gen.achieved` (info) SHALL be the table `fenolite.pick.codes.ISSUE_CODES`, each explained by `fenolite explain` and listed in `docs/cli-contract.md`, "Picks".

#### Scenario: Every code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** every `pick.*` and `gen.*` code has an entry whose `see` is the heading `pick`
