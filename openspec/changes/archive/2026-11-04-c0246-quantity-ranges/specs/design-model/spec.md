## ADDED Requirements

### Requirement: Value range object in the model
`fenolite.model.circuit` SHALL define the frozen value objects `Decimal10(m, e)`, the exact value m·10^e, and `ValueRange(unit, low=None, nominal=None, high=None)`, with no id and no entity header. `unit` MUST be a unit of the DSL's `Quantity` (`ohm`, `farad`, `henry`, `volt`, `ampere`, `hertz`, `watt`, `second`); `low`, `nominal` and `high` MUST be `Decimal10` or `None`. At least one bound MUST be given, `low <= high`, and a nominal MUST lie within the bounds; otherwise `ValueError`.

#### Scenario: Refused ranges
- **WHEN** `ValueRange("ohm")`, `ValueRange("ohm", low=Decimal10(2, 0), high=Decimal10(1, 0))`, `ValueRange("ohm", low=Decimal10(1, 0), nominal=Decimal10(5, 0), high=Decimal10(2, 0))` and `ValueRange("uohm", low=Decimal10(1, 0))` are built
- **THEN** each raises `ValueError`

### Requirement: Canonical exact decimals
A `Decimal10` SHALL hold integers with `|m| <= 10^15 − 1` and `−30 <= e <= 30`, `m` without a trailing zero digit, and zero as `Decimal10(0, 0)`; any other pair MUST raise `ValueError`. One value thus has one form, every integer stays below 2⁵³, and `docs/design-model.md` MUST describe the form and the table of quantity ranges it covers (0.1 mΩ to 10 TΩ, 0.1 pF to 3 000 F, 1 pA to 10 kA, 1 µV to 50 kV, 0.1 nH to 10 H, 1 mHz to 100 GHz, 1 nW to 100 kW, 1 fs to 10⁶ s).

#### Scenario: Refused pairs
- **WHEN** `Decimal10(10, 0)`, `Decimal10(0, 3)`, `Decimal10(10**15, 0)` and `Decimal10(1, 31)` are built
- **THEN** each raises `ValueError`

#### Scenario: Extreme realistic values are exact
- **WHEN** `to_model` lowers part values `ohm("0.1m").pct(1)`, `ohm("10000G").pct(10)`, `farad("0.1p").pct(10)` and `farad(3000).pct(-10, 20)`
- **THEN** the stored nominals are `Decimal10(1, -4)`, `Decimal10(1, 13)`, `Decimal10(1, -13)` and `Decimal10(3, 3)`, and every bound equals its exact value

### Requirement: Outward rounding of value ranges
Lowering a DSL `Range` to a `ValueRange` SHALL store every value with at most 15 significant digits exactly, and SHALL round any other value to 15 significant digits: `low` down, `high` up, the nominal to nearest with ties to even, so the stored interval contains the exact one. A value whose exponent would leave −30..30 MUST raise `DslError`.

#### Scenario: Outward rounding
- **GIVEN** a part whose value is `between(ohm("1"), ohm("2"), nominal=ohm("1.5")) / 3`
- **WHEN** `to_model` lowers it
- **THEN** the stored range is `ValueRange("ohm", Decimal10(333333333333333, -15), Decimal10(5, -1), Decimal10(666666666666667, -15))`

### Requirement: Value ranges on components
`Component` SHALL gain `value_range: ValueRange | None = None` as its last field. The change MUST be additive: `canonical` omits `None`, a `circuit.json` without the key MUST load with `None`, `SCHEMA_VERSION` stays `"0"`, and `schemas/fenolite.model.v0/circuit.json` MUST be regenerated with `tools/gen_schemas.py`, `value_range` optional.

#### Scenario: Ranges survive the canonical round trip
- **GIVEN** a design whose component `R1` has `value_range == ValueRange("ohm", Decimal10(99, 2), Decimal10(1, 4), Decimal10(101, 2))`
- **WHEN** it is written with `canonical.dump_dir`, loaded with `canonical.load_dir` and its `circuit.json` validated against the regenerated schema
- **THEN** the loaded range equals the original, validation passes, and `circuit.json` holds it under the key `value_range` of `R1`

#### Scenario: Circuits without ranges are unchanged
- **GIVEN** a `circuit.json` written before this change, and the same design dumped after it
- **WHEN** the old file is loaded and the two texts are compared
- **THEN** loading succeeds with every `value_range` `None`, and the texts are equal byte for byte

#### Scenario: Schema is regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` and `uv run pytest tests/unit/test_schema_drift.py` run
- **THEN** both pass, and `schemas/fenolite.model.v0/circuit.json` names `value_range` outside the `required` list of a component

### Requirement: Value ranges stay out of backend files
No backend SHALL write or read `Component.value_range`. A KiCad or Altium build MUST keep it in `.fenolite/circuit.json` only, and every written file outside `.fenolite/` MUST be byte for byte that of the same design with the nominal given as a `Quantity`.

#### Scenario: Written KiCad files do not change
- **GIVEN** the blink with `R1` given `value=ohm("330").pct(5)`, and the blink with `value=ohm("330")`
- **WHEN** both are built with the same `--seed` and `--timestamp`
- **THEN** every planned file outside `.fenolite/` has the same SHA-256 in both receipts, and only `.fenolite/circuit.json` differs, by the `value_range` of `R1`
