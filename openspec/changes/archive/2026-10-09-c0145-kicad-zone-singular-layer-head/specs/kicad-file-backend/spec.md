## ADDED Requirements

### Requirement: Singular and plural layer heads of a zone
The layers of a `zone` (a copper zone or a rule area) SHALL be read from its `layer` or its `layers` child alike, and `write_board` SHALL treat the two heads as one family when it compares a kept child with the model.
- The reader MUST take every name of the child, under either head, and MUST expand a wildcard or a mask (`*.Cu`, `*.X`, `F&B.X`) as "Zones, fills and rule areas" states. A child that holds a wildcard or a mask MUST be a projected slot under either head, so the file keeps its spelling.
- For a kept `layer` or `layers` child of a `Zone` or a `Keepout`, the writer MUST compare the layers the child names, wildcards expanded against the board's copper rows, with the model's `layers`, whichever head the emitter would pick for the model's value. When they are equal, the child MUST be kept as written, under the head the file used, and the writer MUST NOT write a second layer child.
- When the model's `layers` differ and the child holds only plain names, the layers MUST be written from the model as the rule "Projected fields on write" allows: `(layer "NAME")` for one layer and `(layers "NAME" …)` for several, the forms `kicad-cli` 10.0.6 saves again unchanged (`H-K-ZONE-LAYER-HEAD`).
- When the model's `layers` differ and the child holds a wildcard or a mask, the writer MUST give `kicad.board.projection-read-only` naming `layers`, under either head.
- A child that holds several plain names under `layer` MUST NOT be kept for a changed value: the layers are written from the model when the number of names is the same, and `kicad.board.projection-read-only` is given otherwise.
- A zone or rule area that has no kept child, one that a script declares (`design.rule_area`, c0103) or that the API created, is written by the emitter as before this change: `(layer "NAME")` for one layer and `(layers "NAME" …)` with every name for several, never a wildcard. Only a zone that was read keeps the head and the spelling of its file.
- No other entity's `layer` or `layers` child is compared differently: the family holds for `Zone` and `Keepout` only.
- `docs/formats/kicad/board.md` MUST state what the corpus holds under each head and what `kicad-cli` 10.0.6 loads and saves, each fact with its source and label. A board whose zone holds a wildcard, a mask or several names under `layer` is read by Fenolite and refused by `kicad-cli` 10.0.6; the page MUST say so.

#### Scenario: Singular head with one layer
- **GIVEN** the authored board `two_layer.kicad_pcb`, whose zone holds `(layer "B.Cu")` and whose rule area holds `(layer "F.Cu")`
- **WHEN** it is read and written back unchanged
- **THEN** the zone has `layers == ("B.Cu",)`, the rule area `layers == ("F.Cu",)`, and both `zone` nodes of the written text equal the source nodes

#### Scenario: Singular head with a wildcard is read
- **GIVEN** that board with the layer child of its rule area replaced by `(layer "*.Cu")`, and the same for its zone
- **WHEN** it is read
- **THEN** the rule area (the zone) has `layers == ("F.Cu", "B.Cu")` and its `(layer "*.Cu")` child is an `Opaque` slot; the same holds for `(layer "F&B.Cu")`

#### Scenario: An unchanged board keeps its layer child
- **GIVEN** that board with the layer child of its zone or of its rule area replaced by one of `(layer "*.Cu")`, `(layer "F&B.Cu")`, `(layers "*.Cu")`, `(layers "F&B.Cu")`, `(layers "F.Cu" "B.Cu")`, `(layers "B.Cu")` and `(layer "F.Cu" "B.Cu")`
- **WHEN** it is read and written for target 9
- **THEN** the three RT1 conditions hold, no warning or error is raised, the written `zone` node equals the source node, and it holds exactly one layer child, the source's

#### Scenario: Plural head with a wildcard or a mask
- **GIVEN** the board with `(layers "*.Cu")` or `(layers "F&B.Cu")` on its zone
- **WHEN** the zone's `name` is changed and the board is written
- **THEN** the written zone holds the source's layer child and no other; the same holds under `layer`

#### Scenario: A changed layer set is written by the number of layers
- **GIVEN** the board as authored, and the board with `(layers "F.Cu" "B.Cu")` on its zone and its rule area
- **WHEN** the layers of the first are changed to `("F.Cu", "B.Cu")`, those of the second to `("F.Cu",)`, and each is written for target 10
- **THEN** the first holds `(layers "F.Cu" "B.Cu")` and the second `(layer "F.Cu")` on both, `kicad-cli` 10.0.6 loads each written board, and its re-save holds the same layer children (probes `pcb-zone-layers-write-widened` and `pcb-zone-layers-write-narrowed` are `equal`)

#### Scenario: A rule area declared in the script
- **GIVEN** the blink design with `design.rule_area("ANT", …)` on every copper layer of its two-layer board (`layers=None`), and the same with `layers=("B.Cu",)`
- **WHEN** each is built for target 9 and for target 10
- **THEN** the rule area of the first holds `(layers "F.Cu" "B.Cu")` and that of the second `(layer "B.Cu")`, and reading the built board and writing it back keeps that child

#### Scenario: A changed layer set of a wildcard child is refused
- **GIVEN** the board with one of `(layer "*.Cu")`, `(layer "F&B.Cu")`, `(layers "*.Cu")`, `(layers "F&B.Cu")` and `(layer "F.Cu" "B.Cu")` on its zone or its rule area
- **WHEN** that entity's `layers` are changed to `("F.Cu",)` and the board is written
- **THEN** `LossyWriteError` is raised with `droppable == False` and one issue `kicad.board.projection-read-only` whose message names `layers` and the kept child

#### Scenario: Route rewrites the board
- **GIVEN** the two-pad routing board with a rule area far from the pads whose layers are written `(layer "*.Cu")`
- **WHEN** `fenolite route --router direct --out routed.kicad_pcb --confirm` runs on it
- **THEN** the exit code is 0, the net is routed, and the written board holds `(layer "*.Cu")` once and reads with the rule area on `F.Cu` and `B.Cu`

#### Scenario: What KiCad 10 loads and saves
- **WHEN** the probes `pcb-zone-layers-load-*` and `pcb-zone-layers-save-*` run on `kicad-cli` 10.0.6
- **THEN** the boards with `(layer "*.Cu")`, `(layer "F&B.Cu")` and `(layer "F.Cu" "B.Cu")` are `reject`, the boards with `(layers "*.Cu")`, `(layers "F&B.Cu")` and `(layers "B.Cu")` are `load`, and the re-saves of the three plural boards hold `(layers "F.Cu" "B.Cu")`, `(layers "F.Cu" "B.Cu")` and `(layer "B.Cu")` (`equal`)
