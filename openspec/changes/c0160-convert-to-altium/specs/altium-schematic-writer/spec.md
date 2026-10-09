## ADDED Requirements

### Requirement: Schematic of a converted project
When a KiCad source project holds a schematic, its conversion to Altium SHALL take the circuit from that schematic (as a schematic side of `equivalent` reads it) and the graphics of each symbol from the schematic's own `lib_symbols`, written with the symbol graphics of `--altium-symbols graphics` and one Altium sheet per KiCad sheet of the tree, as `--altium-sheets modules` writes a module.

#### Scenario: Netlist kept
- **GIVEN** the KiCad 10.0.6 demo project `complex_hierarchy` in the corpus
- **WHEN** it is converted to Altium and the written project is compared with the KiCad schematic by `equivalent`
- **THEN** levels 1 and 2 report no difference, and the written project holds one schematic document per KiCad sheet

### Requirement: Positions of a converted schematic
The symbol positions and wires of a converted schematic MUST come from the writer's layout, and the report row `schematic` MUST be `changed` with the reason "positions and wires are not converted". A source without a schematic keeps the generated sheet of generic symbols.

#### Scenario: Positions reported
- **GIVEN** a KiCad project with a schematic
- **WHEN** it is converted to Altium
- **THEN** the report row `schematic` is `changed` with the reason "positions and wires are not converted"

### Requirement: Tolerant texts of a read circuit
The schematic writer SHALL write the texts of a circuit that was read from a file: a comment that starts with `=` and was read from an Altium document MUST be written as read, and one read from a KiCad file MUST be written with a leading space and counted `changed`; in the binary form, a text with a character outside Windows-1252 MUST be written with its `%UTF8%` twin holding the text and a plain value with `?` for each such character, and the ASCII form keeps refusing it.

#### Scenario: Public project sets judged
- **WHEN** `uv run pytest tests/corpus/test_altium_rta3.py -k sets -rA` runs with the corpus cached
- **THEN** the sets `altium-set:01`, `altium-set:02` and `altium-set:04` are judged, not `no-document`, and each difference is one the report counts

#### Scenario: Text outside the code page
- **GIVEN** a component whose comment holds a character outside Windows-1252
- **WHEN** it is written in the binary form and read back
- **THEN** the reader gives the comment from the `%UTF8%` twin, equal to the model's

### Requirement: One net per pin of a read circuit
A pin that the import of a circuit puts on two nets MUST be written on the net with more pins (the smaller name on a tie), and the other net MUST be counted lost under `pin-net`.

#### Scenario: Pin on two nets
- **GIVEN** a read circuit whose pin `U1.1` is a member of the nets `A` (three pins) and `B` (two pins)
- **WHEN** its schematic is written
- **THEN** the pin is on `A` alone and `pin-net` counts one lost item
