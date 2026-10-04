## ADDED Requirements

### Requirement: Zone fill stage
`fenolite.checks.fill.fill_stage(oracle, project, design) -> StageResult` SHALL be the stage `zone.fill`, inserted in `STAGE_ORDER` directly before `drc.kicad`, and SHALL say whether the board's zone fills are what a refill gives.
- `run_checks` MUST take `fill_oracle: FillOracle | None = None` and MUST call `fill_oracle.refill(project)` at most once.
- For each zone of the board model with a net, the stage MUST compare the board's fills with the oracle's as sets of `(layer, island, normalised ring)`:
  - `zone.unfilled` (warning, `where` = the zone name or id): the oracle has fills and the board has none;
  - `zone.fill-stale` (warning): both have fills and the sets differ.
- When `FillOutcome.supported` is false, the stage MUST be `skipped` with reason `oracle-unsupported` and MUST add one `zone.fill-unchecked` (info) to the input issues of the report. This skip MUST NOT count for the envelope evidence.
- When two independent refills differ, the oracle sets `stable == false`; the stage MUST be skipped with reason `oracle-unstable` and add `zone.fill-unchecked`, without judging a stale fill.
- When the oracle gives no zones for another reason, the stage MUST report `check.oracle-failed` (error; `retryable: true` on a timeout).
- A refused board read MUST skip the stage with reason `read-refused`.
- Stage evidence MUST be `FillOutcome.evidence`, and `UNVERIFIED` when the stage reports `zone.unfilled` or `zone.fill-stale`.
- `summary` MUST hold `tool_version`, `zones`, `current`, `unfilled` and `stale`.
- `checks.codes.ISSUE_CODES` MUST gain `zone.unfilled` (warning), `zone.fill-stale` (warning) and `zone.fill-unchecked` (info).
- `cmd_check` MUST pass its `KicadOracle` as `fill_oracle` when `zone.fill` is selected, with the pre-flight of `drc.kicad`.

#### Scenario: Current fills
- **GIVEN** a fake `FillOracle` whose zones equal the model's
- **WHEN** `uv run pytest tests/unit/checks/test_fill_stage.py -k current` runs the stage
- **THEN** the status is `ok`, there is no issue, and `summary.current` equals the number of zones

#### Scenario: Unfilled and stale zones
- **GIVEN** a model with one zone without fills and one whose fill differs from the fake oracle's
- **WHEN** the stage runs
- **THEN** it reports one `zone.unfilled` and one `zone.fill-stale`, both warnings, the status is `ok`, and the stage evidence is `UNVERIFIED`

#### Scenario: Tool cannot refill
- **GIVEN** a fake oracle with `supported == False`
- **WHEN** `run_checks` runs with `stages=("zone.fill", "roundtrip")`
- **THEN** `zone.fill` is skipped with reason `oracle-unsupported`, the issues hold `zone.fill-unchecked`, and the envelope evidence is `roundtrip`'s

#### Scenario: Filled blink is current
- **GIVEN** the blink built for the running target and filled with `fenolite fill --confirm`
- **WHEN** `uv run pytest tests/kicad/fill/test_fill_oracle.py -k stage` runs `fenolite check` on 10.0.6
- **THEN** `zone.fill` has status `ok` with no issue; before the fill it reports `zone.unfilled`

#### Scenario: Stage order
- **WHEN** `STAGE_ORDER` is read
- **THEN** `zone.fill` comes after `erc.lite` and directly before `drc.kicad`
