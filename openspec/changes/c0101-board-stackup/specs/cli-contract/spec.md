## ADDED Requirements

### Requirement: Stack-up in inspect
`fenolite inspect` SHALL report the stack-up of a board it reads, as an addition to the `result` of "Inspect command".
- For a board, `result.stackup` MUST be `null` when `Board.stackup` is `None`, and otherwise hold `thickness` (`Stackup.thickness()`, in nm), `finish`, `impedance_controlled` and `layers`: one object per entry, top to bottom, with `name`, `kind` and `thickness`, and with `dielectric_kind`, `material`, `epsilon_r`, `loss_tangent` and `color` when they are set. Footprint files and symbol libraries MUST NOT carry the key.
- The `kicad.board.stackup-*` issues of the reader MUST be reported as reader issues, as "Inspect command" requires of every reader issue.
- `docs/cli-contract.md` MUST describe the key under `inspect`.

#### Scenario: Board with a stack-up
- **WHEN** `uv run fenolite inspect tests/data/kicad/board/stackup_four.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.stackup.thickness` is 2025000, `result.stackup.finish` is `ENIG`, and `result.stackup.layers` holds 14 objects, the first named `F.SilkS` with kind `silkscreen` and thickness 0

#### Scenario: Board without a stack-up
- **WHEN** `uv run fenolite inspect tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** `result.stackup` is `null`, and the other keys are those of "Authored board summary"
