## MODIFIED Requirements

### Requirement: Reserved id families
`docs/hypotheses.md` SHALL state, above the register table, the following rules:
- ids keep the prefixes `H-A-` (second backend), `H-G-` (general) and `H-K-` (KiCad);
- rows about a tool acting on KiCad files use `H-K-`, and routing rows use the `H-K-KRT-` prefix;
- Specctra rows use `H-G-DSN-*`, with backend `specctra`.

It SHALL also hold a reserved-families table with the header `| family | backend | rows for | owner |`. `fenolite.verify.load_families(path)` SHALL return the families of that table as written.
- Family cells MUST be written in backticks. A family cell, stripped and with one pair of enclosing backticks removed, MUST fully match an id stem followed by `-*`. Otherwise `load_families` MUST raise `ValueError` naming `<path>:<line>`.
- A file without a reserved-families table MUST give the empty tuple. A file with two such tables MUST raise `ValueError` naming the path.
- The table MUST list `H-A-WRITE-*`, `H-A-PH-*` and `H-G-DSN-*`; families MUST be removed once their rows are registered.

#### Scenario: Families of the live register
- **WHEN** `load_families("docs/hypotheses.md")` is called
- **THEN** the result contains `"H-A-WRITE-*"`, `"H-A-PH-*"` and `"H-G-DSN-*"`, but not `"H-K-KRT-*"` after c0016 registers its rows

#### Scenario: Reserved family
- **GIVEN** a temporary register holding only `H-K-UNIT`, whose reserved-families table lists `H-A-WRITE-*`, and `docs/x.md` citing `H-A-WRITE-*`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns no problem
