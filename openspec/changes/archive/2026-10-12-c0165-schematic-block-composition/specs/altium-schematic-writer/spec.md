## ADDED Requirements

### Requirement: Opt-in composed native schematic output
`project.write_project` and `lens.altium.build_altium` SHALL accept optional composition intent.
`project.plan_sheet` and `hierarchy.plan_sheets` SHALL integrate it after existing sheet assignment.
Both native forms MUST preserve IDs, symbols, pins, footprint maps, parameters, no-connects, class
directives, buses and harnesses while applying verified presentation transforms and local wires.
Absent intent MUST retain the existing deterministic cell-layout requirements.

#### Scenario: ASCII and binary electrical agreement
- **GIVEN** an authored composed project with rotated passives, text, no-connects and net classes
- **WHEN** it is written in ASCII and binary and read back
- **THEN** both forms have the source circuit's electrical signature and equivalent emitted geometry

#### Scenario: Module hierarchy with composition
- **GIVEN** an authored module tree with ports and harness entries
- **WHEN** its sheets are composed
- **THEN** each unit retains its original sheet and hierarchy connectivity, and interface geometry
  is included in placement collision checks

#### Scenario: Unsupported transform
- **GIVEN** a symbol primitive whose requested transformation cannot be preserved by the writer
- **WHEN** the composed plan is lowered
- **THEN** it reports the unsupported transform without dropping or substituting symbol geometry
