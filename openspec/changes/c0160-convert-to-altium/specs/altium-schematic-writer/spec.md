## ADDED Requirements

### Requirement: Schematic of a converted project
When a KiCad source project holds a schematic, its conversion to Altium SHALL take the circuit from that schematic (as a schematic side of `equivalent` reads it) and the graphics of each symbol from the schematic's own `lib_symbols`, written with the symbol graphics of `--altium-symbols graphics` and one Altium sheet per KiCad sheet of the tree, as `--altium-sheets modules` writes a module. Symbol positions and wires MUST come from the writer's layout, and the report row `schematic` MUST be `changed` with the reason "positions and wires are not converted". A source without a schematic keeps the generated sheet of generic symbols.

#### Scenario: Netlist kept
- **GIVEN** the KiCad 10.0.6 demo project `complex_hierarchy` in the corpus
- **WHEN** it is converted to Altium and the written project is compared with the KiCad schematic by `equivalent`
- **THEN** levels 1 and 2 report no difference, and the written project holds one schematic document per KiCad sheet

### Requirement: Tolerant texts and nets of a read circuit
The schematic writer SHALL write a circuit that was read from a file, as follows:
- a comment that starts with `=` and was read from an Altium document MUST be written as read; one read from a KiCad file MUST be written with a leading space and counted `changed`;
- in the binary form, a text with a character outside Windows-1252 MUST be written with its `%UTF8%` twin holding the text and a plain value with `?` for each such character; the ASCII form keeps refusing it;
- a pin that the import puts on two nets MUST be written on the net with more pins (the smaller name on a tie), and the other net MUST be counted lost under `pin-net`.

#### Scenario: Public project sets judged
- **WHEN** `uv run pytest tests/corpus/test_altium_rta3.py -k sets -rA` runs with the corpus cached
- **THEN** the sets `altium-set:01`, `altium-set:02` and `altium-set:04` are judged, not `no-document`, and each difference is one the report counts

#### Scenario: Text outside the code page
- **GIVEN** a component whose comment holds a character outside Windows-1252
- **WHEN** it is written in the binary form and read back
- **THEN** the reader gives the comment from the `%UTF8%` twin, equal to the model's
