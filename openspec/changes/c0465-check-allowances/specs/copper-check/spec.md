## ADDED Requirements

### Requirement: Allowed shorts
`check_copper` SHALL judge each `copper.short` against the governing `short` rule of its two items: the last
rule of kind `short` in `checks.clearance.rule_precedence` order whose selectors match the two items'
subjects in either order (change c0465).
- Governed by a rule of severity `ignore`, the finding MUST stay listed with severity `info`, its message
  ending with ` (allowed by rule <name>)`.
- Governed by a rule of severity `warning`, it MUST have severity `warning`.
- With no governing rule, or one of severity `error`, it MUST stay an `error`, as before.
- `summary["allowed"]` MUST count, per code, the findings a rule allowed, and MUST be absent when none was.
- A design without `short` rules MUST give the report it gave before, byte for byte; a test pins the bytes of
  an existing report.

#### Scenario: Two grounds joined
- **GIVEN** an authored board where copper of `AGND` touches copper of `DGND` and copper of `VIN` touches
  copper of `DGND`, and one `short` rule of nets `AGND` and `DGND` of severity `ignore`
- **WHEN** `uv run pytest tests/unit/checks/test_copper_allowances_c0465.py -q -n 0` runs `check_copper`
- **THEN** the `AGND`–`DGND` short is `info` and ends with `(allowed by rule GND_JOIN)`, the `VIN`–`DGND` short
  is an `error`, and `summary["allowed"]` is `{"copper.short": 1}`

#### Scenario: A narrower rule forbids again
- **GIVEN** the same board, a `short` rule `all`/`all` of severity `ignore` at priority 2, and a `short` rule
  of net `VIN` against `all` of severity `error` at priority 1
- **WHEN** the same test runs `check_copper`
- **THEN** the `AGND`–`DGND` short is `info` and the `VIN`–`DGND` short is an `error`
