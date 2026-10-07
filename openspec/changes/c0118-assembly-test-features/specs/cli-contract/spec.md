## ADDED Requirements

### Requirement: Testpoints command
`fenolite testpoints PATH [--side top|bottom|both] [--template FILE] [--min-coverage PERCENT] [--min-pitch LENGTH] [--min-fiducials N] [-o FILE]` SHALL be registered by `src/fenolite/cli/cmd_testpoints.py`, with `mutates=True` for `--out` only, and SHALL report the test points, fiducials, holes and net coverage of a board (`assembly-test-features`).
- `PATH` is a `.kicad_pcb`, a `.kicad_pro` or a project folder, read as `pnp` reads it: from the board file, with no tool run.
- `result` MUST hold `side`; `test_points`, `fiducials` and `holes`, rows of "Test-point report rows" with lengths in integer nanometres in the board frame; `coverage` with `eligible`, `covered` and `uncovered`; `counts` with `test_points`, `fiducials_top`, `fiducials_bottom`, `holes` and `tooling_holes`; and `template`, `units`, `origin` and `y_axis`. `issues` MUST hold the findings of "Assembly and test findings", and `evidence` MUST combine `exports.testpoints.EVIDENCE` with the read's.
- `--min-coverage` MUST be an integer from 0 to 100, `--min-pitch` a positive length with a unit, and `--min-fiducials` an integer of at least 1; another value MUST exit 2 (`FEN-2001`).
- `-o FILE` MUST plan one CSV file through the mutation protocol. Its header is `kind,ref,pad,net,x,y,side,access,width,height,drill`, with `kind` `test_point`, `fiducial`, `tooling_hole` or `hole`, one row per report row in that order; positions and sizes in the origin, Y axis, units and decimals of the template's `[placement]` table, sides by its side names, and its CSV options. No file MUST be planned when a finding is an error, or when the origin needs a board outline the board lacks (`pnp.no-outline`).
- The exit code MUST be 0 without an error finding, 5 with one, and 3 for a file that cannot be read.
- The command MUST name `example_args` on the example board, and `mutation_example_args` that write `testpoints.csv`.
- `docs/cli-contract.md` MUST hold a section `testpoints` with its options, its result and its codes.

#### Scenario: A board without marks
- **WHEN** `fenolite testpoints tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** it exits 0, `result.test_points` is empty, `result.coverage.covered` is 0, and `issues` holds one `testpoint.none` info

#### Scenario: A coverage target missed
- **GIVEN** the build of "Features in a build" (`design-dsl`, "Assembly and test features in a build")
- **WHEN** `fenolite testpoints <board> --min-coverage 100 --out tp.csv --dry-run --json` runs
- **THEN** it exits 5, `issues` holds `testpoint.coverage-low`, `result.coverage.covered` is 1, and no write is planned

#### Scenario: The CSV of a build
- **GIVEN** the same build
- **WHEN** `fenolite testpoints <board> --out tp.csv --dry-run --json` runs
- **THEN** it exits 0 and plans `tp.csv`, whose first line is `kind,ref,pad,net,x,y,side,access,width,height,drill` and which holds a `test_point` row for `TP1` with the net `LED_A` and the access `top`, two `fiducial` rows and one `tooling_hole` row for `TH1`
