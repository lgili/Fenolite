## ADDED Requirements

### Requirement: Script layer counts in an Altium build
The Altium build SHALL write the PCB document of a script declared with any count of `fenolite.dsl.design.COPPER_COUNTS` (`design-dsl`, "Board and placements in the DSL"), 6 and 8 included, with the stack of `altium-pcb-writer`, "Layer stacks of any even count", and SHALL NOT refuse a script for its count.
- When `design.board` names no copper layer, `lens.altium_copper.board_layers(design, copper)` MUST give `F.Cu`, `In1.Cu` … `In<copper − 2>.Cu`, `B.Cu` (`layer_names(copper)`) and no issue for every count of `COPPER_COUNTS`. These are the names of `Design.copper_layers`, so a zone, a plane or script copper on an inner layer of the script lies on a layer of the document. This extends the layer sentence of "Copper in an Altium build", which names the lists of `copper=2` and `copper=4`.
- A plane on any inner layer of the count MUST be written as an internal plane on its net ("Internal planes in an Altium build"), and a zone or script copper on any copper layer of the count as "Copper in an Altium build" and "Script copper in an Altium build" state. The in-memory KiCad build of script copper MUST run with the script's count (`design-dsl`, "Copper layer counts in a build").
- `altium.copper-stack` keeps its rows ("Copper issue codes"): a board whose own copper layers repeat or differ in count from the script's, and a plane on a wrong layer or net. It MUST NOT be given for a count of `COPPER_COUNTS` as such. `lens.altium_copper.STACK_HINT` MUST read "make design.board(..., copper=…) equal to the board's copper layer count, or give the board its copper layers", and MUST NOT name 2 and 4 as the only counts.
- This requirement adds no record, layer id or format fact: the stack, its layer map and its evidence are those of "Layer stacks of any even count", and the evidence of the build does not change.

#### Scenario: Six layers with a plane and a zone
- **GIVEN** a blink variant declared with `design.board(mm(50), mm(30), copper=6, planes={"In4.Cu": gnd})` and `d.zone(vin, layers=("In3.Cu",))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, the PCB document is planned, `result.copper.layers` is 6, `result.copper.planes` is `{"In4.Cu": "GND"}`, `result.copper.zones` is 1, and `issues` holds no `altium.copper-stack` and no `altium.not-lowered` whose `where` is `stackup`

#### Scenario: Eight layers read back
- **GIVEN** a blink variant declared with `copper=8` and no copper intent
- **WHEN** `build_altium` runs on its model with `copper=8` and the planned PCB document is read back
- **THEN** the board holds the eight copper layers `F.Cu`, `In1.Cu` to `In6.Cu` and `B.Cu` in that order, and no issue is an error

#### Scenario: Hint without the old counts
- **GIVEN** a model whose `board.layers` holds the copper layers `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu`
- **WHEN** `build_altium` runs with `copper=6`
- **THEN** `files` is empty and `issues` holds one `altium.copper-stack` that names 4 and 6, whose hint holds neither "copper=2" nor "copper=4"
