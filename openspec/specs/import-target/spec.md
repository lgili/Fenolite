# import-target Specification

## Purpose
TBD - created by archiving change c0356-import-explicit-kicad-target. Update Purpose after archive.
## Requirements
### Requirement: Explicit import output target is honored
Python import SHALL use an explicitly supplied supported `--kicad-version` for emission and private verification. When no target was supplied it SHALL preserve the existing source-major selection and ordinary output bytes. Unsupported source project keys SHALL still refuse, without deletion or lossy waiver.

#### Scenario: A KiCad9 board has KiCad10 project settings
- **WHEN** import explicitly targets10
- **THEN** emission and self-check target10, preserving the original project settings
- **AND** target9 and default source-major9 still refuse incompatible settings

### Requirement: Reviewed plans bind explicit targets
A changed explicit target SHALL invalidate a reviewed plan before writes. Parser option placement SHALL NOT change the selected target.

#### Scenario: Confirmation asks for a different target
- **WHEN** a target10 dry-run is confirmed with target9
- **THEN** the plan refuses and no output is written

