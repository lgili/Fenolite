## ADDED Requirements

### Requirement: Altium rule file export
`fenolite export` SHALL offer the kind `altium-rul`, which writes `<name>.RUL` with `write_rule_file` from the rules of the project, with no external tool.
- The kind MUST NOT be part of the default kinds. Its artifact MUST name the rules that were not lowered in its `notes`.
- The export MUST follow "Writing files" of the CLI contract (dry run, confirm, receipt).

#### Scenario: Rule file from a built project
- **GIVEN** a project built from the blink script
- **WHEN** `fenolite export <dir> --kinds altium-rul --confirm --json` runs
- **THEN** the receipt lists `blink.RUL`, and reading it gives the rules that the Altium build of the same script writes
