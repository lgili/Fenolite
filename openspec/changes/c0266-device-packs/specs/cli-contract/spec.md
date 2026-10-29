## ADDED Requirements

### Requirement: Library seed command
`fenolite library seed --from-librepcb DIR --commit SHA --library NAME --into DIR [--namespace NS]` SHALL be mutating, write one item folder per converted element under `--into` all or nothing, and report `result.items` (kind, id, origin element) and `result.skipped`. When `DIR/.git` exists its `HEAD` commit MUST equal `--commit`, else exit 3 with `FEN-3004`. `capabilities` SHALL list it as `library seed`.

#### Scenario: Commit mismatch
- **GIVEN** a fixture checkout whose `.git/HEAD` names another commit
- **WHEN** the seed runs with `--commit` of 40 zeros
- **THEN** it exits 3 with `FEN-3004` naming the commit, and plans nothing

#### Scenario: Board path form unchanged
- **WHEN** `fenolite library examples/<board> --out lib.pretty --dry-run --json` runs
- **THEN** the result is the c0223 result as on 0.6.0
