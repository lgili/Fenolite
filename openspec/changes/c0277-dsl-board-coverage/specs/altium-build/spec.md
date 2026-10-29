## ADDED Requirements

### Requirement: Signal and plane limits in an Altium build
An Altium build of a script whose signal layers (copper count minus declared planes) exceed 16, or whose planes exceed 16, SHALL give `altium.stack-signal-limit` (error) with the hint "declare planes= for the layers beyond 16 signal layers, or build for KiCad", exit 5 and write nothing, instead of the default stack of `altium.not-lowered`. Any other count of `COPPER_COUNTS` builds as "Script layer counts in an Altium build" states.

#### Scenario: Twenty layers without planes
- **GIVEN** a blink variant with `copper=20` and no plane
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 5, `issues` hold one `altium.stack-signal-limit` naming 18 signal layers, and nothing is planned

#### Scenario: Twenty layers with four planes
- **GIVEN** the same variant with planes on `In1.Cu`, `In6.Cu`, `In12.Cu` and `In18.Cu`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0 and the planned document has 20 copper layers, four of them planes

### Requirement: Coverage items in an Altium build
An Altium build SHALL write the coverage items of change c0277 that a record of the writer holds (copper texts and graphics with their net, pad shapes the writer maps, zone arcs, overrides with a rule form) and SHALL report each other item: `altium.group-skipped`, `altium.image-skipped`, `altium.verbatim-skipped` (warnings), teardrops, dimension kinds and model references as `altium.not-lowered`, and arcs written as segments as `altium.zone-arc-flattened` (info). No item is dropped silently.

#### Scenario: Every item accounted for
- **GIVEN** the coverage example `examples/board_coverage/design.py`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** each item of the script is either in the planned document or named by exactly one of these issues
