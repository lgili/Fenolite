## ADDED Requirements

### Requirement: Library check command
`fenolite library check TARGET... [--sheets DIR] [--compare OLD] [--fail-on error|warning] [--rules CODES] [--skip CODES]` SHALL report `result.items`, `result.compare` and findings in the JSON envelope, exit 5 when a finding at or above `--fail-on` remains, and write only with `--sheets`, through dry-run, confirmation, staged plans and receipts. A missing target MUST exit 3 with `FEN-3001`.

#### Scenario: Findings exit
- **WHEN** `fenolite library check tests/data/library/bad --json` runs
- **THEN** it exits 5, writes nothing, and every finding has a `library.*` code, a severity and a `where` naming the item

#### Scenario: Warnings as failures
- **WHEN** the check runs with `--fail-on warning` on records that hold only warnings
- **THEN** it exits 5

### Requirement: Library review command
`fenolite library review TARGET... [--accept --reviewer NAME --sheet HEX | --revoke]` SHALL report the review state of each record without writing when neither flag is given, and SHALL write only through dry-run, confirmation, staged plans and receipts otherwise. `--reviewer` or `--sheet` without `--accept` MUST exit 2 with `FEN-2001`.

#### Scenario: State only
- **WHEN** `fenolite library review tests/data/library/good --json` runs
- **THEN** it exits 0, writes nothing, and lists each record's evidence, effective evidence and review

#### Scenario: Reviewer without accept
- **WHEN** `fenolite library review tests/data/library/good --reviewer jdoe` runs
- **THEN** it exits 2 with `FEN-2001` and writes nothing
