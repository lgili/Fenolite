## ADDED Requirements

### Requirement: Stack-up thicknesses in analyze
`fenolite analyze` SHALL take the copper thickness of "Track and arc capacity" and the board thickness of "Board boundary" from the stack-up that the board's reader gives when no option sets them, and SHALL say where each value came from. An option keeps winning.
- A KiCad board whose `setup` holds a complete node (`kicad-file-backend` "Stack-up on boards") MUST give `analyze_current` the copper thickness of each copper layer, and `board_boundary` the board thickness `Stackup.thickness()`, with no option.
- `result.inputs` MUST gain, as additions to the `inputs` of "Analyze command": `board_thickness_source`, which is `option` when `--board-thickness` was given, `stackup` when the thickness is `Stackup.thickness()`, and `null` otherwise; and `stackup`, `null` without a stack-up and otherwise `{"thickness": <nm>, "copper": {<layer>: <nm>}}`, the copper thickness of each copper entry.
- The `analysis.input-missing` warnings keep their rules: a board without a stack-up and without options gets them as before, and Fenolite still assumes no thickness.

#### Scenario: Thicknesses from the stack-up
- **GIVEN** a copy of `tests/data/kicad/board/two_layer.kicad_pcb` whose `setup` gets, by token edit, a complete node of 35 µm copper, a 1.5 mm core and 10 µm masks, with `general` thickness 1.59
- **WHEN** `fenolite analyze <board> --kinds current --temp-rise 10 --json` runs
- **THEN** every row has `thickness == 35000`, `inputs.board_thickness` is 1590000, `inputs.board_thickness_source` is `stackup`, `inputs.stackup.copper` maps `F.Cu` and `B.Cu` to 35000, and no `analysis.input-missing` names `copper thickness`

#### Scenario: An option wins
- **WHEN** the same command runs with `--board-thickness 1.6mm --copper-thickness 70um`
- **THEN** `inputs.board_thickness` is 1600000 with source `option`, and every row has `thickness == 70000`

#### Scenario: A board without a stack-up
- **WHEN** the command runs on `two_layer.kicad_pcb` itself
- **THEN** `inputs.board_thickness_source` and `inputs.stackup` are `null`, and the issues hold the `analysis.input-missing` warning naming `copper thickness`
