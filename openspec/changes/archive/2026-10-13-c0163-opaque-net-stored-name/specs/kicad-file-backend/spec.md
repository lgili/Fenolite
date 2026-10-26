## MODIFIED Requirements

### Requirement: Net form per target
`write_board` SHALL write every net reference in the form of the target, in modelled and opaque content alike:
- **Target 9.** The root holds `(net 0 "")` followed by `(net i "<name>")` for the model's nets sorted by name in code-point order, i = 1 … n. Pads write `(net i "<name>")`; tracks, arcs, vias and zones write `(net i)`; zones also write `(net_name "<name>")`. For a read board, the table MUST take the place of the source's table, and its row 0 MUST replace the source's opaque `(net 0 "")` slot, so the text holds exactly one row 0.
- **Target 10.** The root holds no net table, and the source's opaque `(net 0 "")` slot MUST be removed. Every reference is `(net "<name>")`, and zones write no `net_name`.
- Net 0 and the empty name mean no net. For target 9, a zone or rule area whose net is `None` MUST write `(net 0)` and `(net_name "")`, and every other item whose `net_id` is `None` MUST carry no `net` child. For target 10, an item whose net is `None` MUST NOT carry a `net` child.
- Inside opaque fragments, `(net 0)`, `(net 0 "")` and `(net "")` MUST be written `(net 0)` for target 9 and removed for target 10, and MUST NOT give `kicad.board.opaque-net-ref`.
- Inside opaque fragments, a numbered reference MUST be resolved through the source net table kept by `read_board` to the stored name of that net (`pcb.stored_net_name`, "Net names in KiCad's stored form"), never to its model name, and a named reference by its name; both MUST be re-emitted in the target's form (c0163).
- A `net` node in opaque content that matches none of `(net N)`, `(net N "name")` and `(net "name")`, or whose number N ≥ 1 is absent from the source table, MUST give `kicad.board.opaque-net-ref` (error). `allow_lossy` MUST NOT drop it.

#### Scenario: Numbered table for target 9
- **GIVEN** a design with nets `VIN`, `GND` and `LED_A`
- **WHEN** it is written for target 9
- **THEN** the root holds `(net 0 "")`, `(net 1 "GND")`, `(net 2 "LED_A")`, `(net 3 "VIN")` in that order, and a track on `GND` holds `(net 1)`

#### Scenario: Names for target 10
- **GIVEN** the same design
- **WHEN** it is written for target 10
- **THEN** a pad on `VIN` holds `(net "VIN")`, a zone on `GND` holds `(net "GND")` and no `net_name`, and the root holds no net table

#### Scenario: Opaque net reference converted
- **GIVEN** a copy of `tests/data/kicad/tokens/skeleton.kicad_pcb`, built in the test, with an added teardrop zone (an `attr` child holding `teardrop`) that holds `(net 2)` and `(net_name "B")`, where net 2 is `B` in the source table, read with `read_board`, so the teardrop zone is an opaque root slot
- **WHEN** it is written for target 10
- **THEN** the teardrop zone holds `(net "B")` and no `net_name`, and every other child of it is tree-equal to the source

#### Scenario: Opaque reference to a net stored with a slash
- **GIVEN** a copy of `skeleton.kicad_pcb`, built in the test, whose net 2 is stored `Net-(U1-P1{slash}XL1)`, with an added teardrop zone that holds `(net 2)` and `(net_name "Net-(U1-P1{slash}XL1)")`, read with `read_board` (the net's model name is `Net-(U1-P1/XL1)`)
- **WHEN** it is written for target 9 and for target 10
- **THEN** both writes succeed with no `kicad.board.opaque-net-ref`; the target-9 teardrop holds `(net i)` and `(net_name "Net-(U1-P1{slash}XL1)")`, where i is the number of the table row `Net-(U1-P1{slash}XL1)`; the target-10 teardrop holds `(net "Net-(U1-P1{slash}XL1)")`; neither text holds `Net-(U1-P1/XL1)`

#### Scenario: Unknown opaque net reference
- **GIVEN** a copy of `skeleton.kicad_pcb` whose segment holds `(net 7)` while the source table ends at 2, read with `read_board`, which keeps that reference opaque (c0009 "Nets in both forms")
- **WHEN** it is written with `allow_lossy=True`
- **THEN** `LossyWriteError` is raised with `droppable == False` and an issue `kicad.board.opaque-net-ref` whose `where` locates that node

#### Scenario: Unconnected rule area in both forms
- **GIVEN** a copy of `tests/data/kicad/board/two_layer.kicad_pcb` whose rule area holds `(net 0)` and `(net_name "")`, as KiCad 9 writes, read with `read_board`
- **WHEN** it is written for target 9 and for target 10
- **THEN** both writes succeed; the target-9 text holds exactly one root `(net 0 "")` and a rule area holding `(net 0)` and `(net_name "")`; the target-10 text holds no `net` node whose atom is `0` or `""`, and no `net_name`
