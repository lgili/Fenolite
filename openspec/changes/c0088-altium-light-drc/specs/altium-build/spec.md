## ADDED Requirements

### Requirement: Copper guard in an Altium build
`fenolite build --target altium` SHALL check the copper it is about to write with `checks.copper` and the design's rules before it returns any file, and a `copper.short` MUST stop the build with exit 5 and no file written. Other copper findings MUST be reported and MUST NOT stop it.
- `--no-copper-guard` MUST skip the check, as for the KiCad target.

#### Scenario: Short refused
- **GIVEN** a script whose two routed tracks of different nets cross on one layer
- **WHEN** it is built for Altium
- **THEN** the exit code is 5, `copper.short` names the nets, and the output folder holds no file
