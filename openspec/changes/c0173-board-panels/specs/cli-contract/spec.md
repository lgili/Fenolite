## ADDED Requirements

### Requirement: Panel command
`fenolite panel PANEL.py --out DIR --target {9,10,altium} [--altium-panel {auto,embedded,flat}]` SHALL be a writing command: `--dry-run` plans, `--confirm --plan ID` writes, `result.panel` gives rows, cols, copies, size, unused and form. Exits: 3 (`FEN-3001`, `FEN-3004`, `FEN-3005`), 5 for error findings `panel.*` with nothing planned, 7 (`FEN-7001`) for a form the target cannot hold.

#### Scenario: Dry run of a panel
- **WHEN** `fenolite panel tests/data/panels/tabs.py --out P --target 10 --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `P/tabs.kicad_pcb`, `P/tabs.kicad_pro`, `P/tabs.panel.json` and the generated footprints, `result.panel.copies` is 8, and nothing is written

#### Scenario: Error findings plan no write
- **GIVEN** `tests/data/panels/vscore.py`, whose track lies 0.3 mm from a scored edge
- **WHEN** it runs with `--dry-run`
- **THEN** the exit code is 5, `issues` holds `panel.vscore-copper` errors, and `result.plan` is empty

#### Scenario: Embedded form while the gate is off
- **WHEN** a panel of a `.PcbDoc` runs with `--target altium --altium-panel embedded` while `EMBEDDED_ARRAYS` is false
- **THEN** the exit code is 7 with `FEN-7001` and a hint naming `--altium-panel flat`, and nothing is written
