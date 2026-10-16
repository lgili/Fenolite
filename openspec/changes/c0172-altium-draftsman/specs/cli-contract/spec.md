## ADDED Requirements

### Requirement: Draftsman options of the build command
`fenolite build` SHALL accept `--altium-draftsman {off,on}` (default `off`) and `--drawing-spec FILE`, the `fenolite.drawing-spec.v0` file of `export`. Either MUST be a usage error (exit 2, `FEN-2001`) with `--target kicad`, and `--drawing-spec` MUST be one without `--altium-draftsman on`. A malformed specification MUST exit 3 with `FEN-3004` before anything is planned.

#### Scenario: KiCad target refuses the option
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --altium-draftsman on --dry-run --json` runs with the default target
- **THEN** the exit code is 2 and stderr holds `FEN-2001` naming `--altium-draftsman`

#### Scenario: Malformed specification
- **GIVEN** a drawing specification with `[page] gap = 5`
- **WHEN** the routed blink is built with `--target altium --altium-draftsman on --drawing-spec` naming it
- **THEN** the exit code is 3, stderr holds `FEN-3004` naming `page.gap`, and nothing is planned
