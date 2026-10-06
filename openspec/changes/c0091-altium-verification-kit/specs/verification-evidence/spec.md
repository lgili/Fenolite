## ADDED Requirements

### Requirement: Kit label rows
A register row SHALL carry `ALTIUM-VERIFIED(kit; AD <major>.<minor>; <date>; <run id>)` only when a run record under `docs/evidence/altium-kit/` with that run id holds a passing verdict for the row's id, and the row's result text names the archive digest of that run and whether the verdict rests on a typed value (`form`).
- `tests/unit/test_hypotheses_register.py` MUST fail for a kit label without such a record, for a record that is synthetic, and for a row that `stale_rows` returns.
- A row whose kit run is stale MUST go back to its previous level, with the stale run named in its result text, until a new run is recorded.
- An author-report row MUST stay an author report until a kit run covers it; a kit run MUST NOT be recorded as an author report.

#### Scenario: Label without a record
- **GIVEN** a register row labelled `ALTIUM-VERIFIED(kit; AD 26.5; 2026-11-01; 2026-11-01-abcdef12)` and no record of that run
- **WHEN** the register test runs
- **THEN** it fails, naming the row and the missing record

#### Scenario: Label with a record
- **GIVEN** the same row and a committed record of that run with a passing verdict for the row
- **WHEN** the register test runs
- **THEN** it passes
