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

## MODIFIED Requirements

### Requirement: Reserved id families
`docs/hypotheses.md` SHALL state, above the register table, the following rules:
- ids keep the prefixes `H-A-` (second backend), `H-G-` (general) and `H-K-` (KiCad);
- rows about a tool acting on KiCad files use `H-K-`, and routing rows use the `H-K-KRT-` prefix;
- Specctra rows use `H-G-DSN-*`, with backend `specctra`.

It SHALL also hold a reserved-families table with the header `| family | backend | rows for | owner |`. `fenolite.verify.load_families(path)` SHALL return the families of that table as written.
- Family cells MUST be written in backticks. A family cell, stripped and with one pair of enclosing backticks removed, MUST fully match an id stem followed by `-*`. Otherwise `load_families` MUST raise `ValueError` naming `<path>:<line>`.
- A file without a reserved-families table MUST give the empty tuple. A file with two such tables MUST raise `ValueError` naming the path.
- A family MUST be removed from the table once its rows are registered and each of them names its settling test. The table MUST NOT list `H-A-WRITE-*` or `H-A-PH-*`: their eight rows are registered and each names the kit steps that settle it (`altium-verification`, "Kit steps settle hypotheses"). It MUST NOT list `H-G-DSN-*` or `H-K-KRT-*`, whose rows are registered.

#### Scenario: Families of the live register
- **WHEN** `load_families("docs/hypotheses.md")` is called
- **THEN** the result contains none of `"H-A-WRITE-*"`, `"H-A-PH-*"`, `"H-G-DSN-*"` and `"H-K-KRT-*"`

#### Scenario: Reserved family
- **GIVEN** a temporary register holding only `H-K-UNIT`, whose reserved-families table lists `H-A-WRITE-*`, and `docs/x.md` citing `H-A-WRITE-*`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns no problem
