## ADDED Requirements

### Requirement: Drawn schematic stage
`fenolite.checks.drawn.drawn_stage(netlist, circuit) -> StageResult` SHALL be the stage `schematic.drawn`, which compares an injected drawn netlist with the built circuit through `drawn_connect.compare`. `cmd_check` MUST compute the netlist from the sheets on disk for built input whose build record names a drawn schematic, and only then list the stage, in the default set. The stage MUST write nothing and run no tool.

#### Scenario: Unchanged project passes
- **GIVEN** a confirmed build of `examples/drawn/design.py` in `B`
- **WHEN** `fenolite check B --json` runs
- **THEN** `result.stages` holds `schematic.drawn` with status `ok` and no issue

#### Scenario: Connectivity edited in KiCad
- **GIVEN** the same build whose sheet then gets, by token edit, one wire end moved from `R1` pin 1 to `R1` pin 2
- **WHEN** `fenolite check B --json` runs
- **THEN** the exit code is 5 and one `drawn.netlist-differs` error names `R1-1`

#### Scenario: Not listed elsewhere
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** `result.stages` holds no `schematic.drawn`

### Requirement: Drawn schematic stage issue codes
The stage `schematic.drawn` SHALL report the codes of `drawn_connect.ISSUE_CODES` with their severities, and `checks.codes.ISSUE_CODES` MUST gain them. An error makes the stage `failed` and the exit code 5; warnings leave it `ok`.

#### Scenario: Warning only
- **GIVEN** the build of the example whose label `SDA` is renamed by token edit
- **WHEN** `fenolite check B --json` runs
- **THEN** the exit code is 0 and the stage holds one `drawn.net-name-differs` warning
