## ADDED Requirements

### Requirement: Copy mode in verify-source
`verify-source` SHALL take `--copper-check refuse|warn` for its build. Without it the build MUST use `warn` when the provenance file read for the script holds an import record whose `copy` is not `false` (`board-to-code`, "Import record marks a copy"), and `refuse` otherwise. `result.build` MUST hold `copper_check` (the mode used) and `copy` (a boolean). Findings of the guard in `warn` stay in `issues` as warnings.

#### Scenario: Imported board with clearance findings is compared
- **GIVEN** a copy of an authored example whose built board holds a short the guard refuses, and an import record beside its script
- **WHEN** `uv run pytest tests/unit/cli/test_verify_source_copy.py -k copy` runs `verify-source` without `--copper-check`
- **THEN** no `fidelity.build-failed` is reported, the levels run, `result.build.copper_check` is `warn` and `issues` holds the `copper.clearance` warning

#### Scenario: Explicit refuse wins
- **GIVEN** the same folder
- **WHEN** the command runs with `--copper-check refuse`
- **THEN** the exit code is 5 and `issues` holds `fidelity.build-failed`

#### Scenario: Own script is refused
- **GIVEN** the same script without a provenance file
- **WHEN** the command runs without `--copper-check`
- **THEN** `issues` holds `fidelity.build-failed` and `result.build.copy` is `false`

### Requirement: Original project files
When `ORIGINAL` is a `.kicad_pro`, or a folder that resolves to one project, `verify-source` SHALL read and record only that project's files: the `.kicad_pro`, the board and `.kicad_dru` of its stem, and the sheet tree of its root sheet. Level 8 MUST render only the sheets of that tree, on both sides.

#### Scenario: Two projects in one folder
- **GIVEN** an authored folder holding the projects `amp` and `amp_v2`
- **WHEN** `uv run pytest tests/unit/cli/test_verify_source_copy.py -k project` runs the command with `--against <folder>/amp.kicad_pro`
- **THEN** `result.against.files` names no `amp_v2` file and no level-8 difference names `amp_v2`

### Requirement: Import losses in the proof
`verify-source` SHALL count the opaque root items of each side per kind and add one level-7 difference `opaque-count` per kind whose counts differ, `where` `board:opaque:<kind>`, `field` the kind, `a` and `b` the counts, before the accepted entries apply, so that a board missing copper the import left out cannot pass unaccepted.

#### Scenario: Teardrops left out
- **GIVEN** an authored original holding two teardrop zones and a script that builds the board without them
- **WHEN** `uv run pytest tests/unit/cli/test_verify_source_copy.py -k opaque` runs the command
- **THEN** the exit code is 5 and `result.differences` holds one `opaque-count` with `where` `board:opaque:teardrop`, `a` `2` and `b` `0`; with an accepted entry for it the exit code is 0

### Requirement: Skipped levels in the recorded proof
`--record` SHALL write `fidelity.proof.skipped`, mapping each skipped level to its reason, beside `fidelity.proof.levels`, and the member MUST be absent when no level was skipped.

#### Scenario: Level S recorded with its reason
- **WHEN** the command runs on the authored fixture with `--record --timestamp 2026-11-01T00:00:00Z --dry-run`
- **THEN** the planned provenance file holds `fidelity.proof.levels.S` `skipped` and `fidelity.proof.skipped.S` `drawn-unavailable`
