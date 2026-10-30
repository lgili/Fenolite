## ADDED Requirements

### Requirement: Limits in device definitions
`fenolite.model.library.Rating` SHALL gain `limit` (`abs_max` or `operating`, default `abs_max`). `DevicePin` SHALL hold `ratings` (sorted by key and limit) and `thresholds` (`Threshold(key, unit, value)`, the five logic keys) in place of c0248's `voltage` and `current`. `DeviceDef` SHALL gain `limits` (`PinPairLimit(between, ratings)`, sorted by `between`) and `cls`. Every value MUST be an integer in `uV`, `uA`, `uW` or `mK`.

#### Scenario: A split record round-trips
- **GIVEN** the `DeviceDef` of the illustrative record of `design.md`, decision 1
- **WHEN** `uv run pytest tests/unit/model/test_library.py -k limits` dumps it with `canonical.dumps` and loads it back
- **THEN** the loaded record is equal, `VIN` holds two ratings (`voltage`, `abs_max`) and (`voltage`, `operating`), `EN` holds two thresholds, `limits` holds `BST`-`SW`, `cls` is `controller`, and no number is a float

### Requirement: Kelvin ranges in the model
c0246's `RangeUnit` SHALL gain `kelvin`. A `ValueRange` of unit `kelvin` holds an absolute temperature or a temperature difference in kelvin, encoded like every other range. The DSL-only units `volt_squared` and `ampere_squared` MUST NOT be a `RangeUnit`, and lowering a range of either MUST raise `DslError`.

#### Scenario: An ambient range in kelvin
- **GIVEN** `between(celsius(-20), celsius(70))` stored as an operating ambient range
- **WHEN** it is written to `rules.json`
- **THEN** it is `{"high": {"e": -2, "m": 34315}, "low": {"e": -2, "m": 25315}, "unit": "kelvin"}`

## MODIFIED Requirements

### Requirement: Waivers in the findings layer
The findings layer SHALL hold a design's waivers as `fenolite.model.findings.Waiver(name: str, code: str, items: tuple[str, ...], reason: str, min_gap: Nm | None = None, digest: str | None = None)`, a frozen dataclass, in `Findings.waivers: tuple[Waiver, ...]`, sorted by name, with the default `()`, so `findings.json` files written before them still load.
- `code` is a finding code (`copper.short`, `copper.clearance`, `copper.zone-overlap`, `<oracle>.drc.<suffix>` or a `circuit.*` code of `ISSUE_CODES`); `items` are names or glob patterns of the finding's items, as `where` prints them, and for a `circuit.*` code the one row id of the finding without its code; `min_gap` is in integer nm; `digest` is the 16 lowercase hexadecimal digits of the requirement row's digest at waiver time, set for a `circuit.*` code and for no other, and omitted from `findings.json` when `None`.
- What a waiver may say is checked where it is declared (`design-dsl`, "Waivers in the DSL"); how it matches is `verification-loop`, "Waivers in the check".
- `docs/design-model.md` MUST describe `Waiver` and the field and MUST say that 0.2.x and 0.3.0 cannot read a `findings.json` that carries `waivers`, and that 0.6.x cannot read one whose waiver carries `digest`; `schemas/fenolite.model.v0/findings.json` MUST be regenerated. A design without waivers MUST write the `findings.json` bytes it wrote before.

#### Scenario: Waivers round-trip through the cache
- **GIVEN** a design whose findings hold two waivers, one with `min_gap=150_000`
- **WHEN** `uv run pytest tests/unit/model -k waivers` writes it with the canonical writer and loads it back
- **THEN** the loaded `Findings.waivers` equals the original, in name order, and `findings.json` holds no float

#### Scenario: A circuit waiver keeps its digest
- **GIVEN** a waiver of code `circuit.rating-voltage`, item `C3:voltage` and digest `9f2c4a1b0d3e5f67`, beside a copper waiver without a digest
- **WHEN** `uv run pytest tests/unit/model -k waiver_digest` writes and loads the findings
- **THEN** the loaded waivers are equal, the circuit waiver's JSON object holds `digest`, the copper waiver's holds none, and a `Waiver` of code `copper.short` with a digest, or of a `circuit.*` code without one, raises `ValueError`
