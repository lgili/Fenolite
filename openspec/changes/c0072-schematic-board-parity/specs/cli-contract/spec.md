## ADDED Requirements

### Requirement: Parity command
`fenolite parity PATH [--netlist auto|own|kicad]` SHALL be registered by `src/fenolite/cli/cmd_parity.py` with `mutates=False`, and SHALL compare the schematic and the board of a KiCad project (`verification-loop`, "Parity comparison").
- **Input.** `PATH` MUST resolve with `projectset.resolve_board`; the schematic is `<board stem>.kicad_sch` beside the board, read with every sheet it names. A missing schematic MUST exit 3 with `FEN-3001` naming it.
- **Netlist.** `auto` (default) MUST use the own netlist when the sheet tree is inside Fenolite's grammar and `kicad-cli`'s netlist export otherwise; `own` MUST refuse a tree outside the grammar with exit 3 (`FEN-3004`) carrying the grammar issues; `kicad` MUST always run the export. A needed `kicad-cli` that is missing MUST exit 6.
- **Result.** `result` MUST hold `board`, `schematic` (the file names), `netlist` (`own` or `kicad`), `summary` and `findings` (the report's findings as objects); `issues` MUST hold one issue per finding.
- **Exit.** 5 when a finding has severity `error`, 0 otherwise.
- No file MUST be written, and the input folder MUST be unchanged.
- `example_args` MUST be `(EXAMPLE_PARITY,)`, a committed folder `tests/data/kicad/parity/agree/` holding a board and a schematic authored for Fenolite that agree, so the example runs without a tool.

#### Scenario: Agreeing project
- **WHEN** `fenolite parity tests/data/kicad/parity/agree --json` runs
- **THEN** the exit code is 0, `result.netlist` is `own`, and `result.summary.refs_one_side` is 0

#### Scenario: Edited board
- **GIVEN** a copy of that folder whose board has one footprint's reference renamed
- **WHEN** `fenolite parity <copy> --json` runs
- **THEN** the exit code is 5, and `issues` hold `parity.missing-footprint` and `parity.extra-footprint`

#### Scenario: Third-party schematic without the tool
- **GIVEN** a project whose schematic holds wires, and no `kicad-cli`
- **WHEN** `fenolite parity <dir> --json` runs
- **THEN** the exit code is 6, and stderr names `kicad-cli`

#### Scenario: Example is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `parity` with its `example_args`
- **THEN** the exit code is 0
