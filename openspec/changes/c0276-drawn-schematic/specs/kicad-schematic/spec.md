## ADDED Requirements

### Requirement: Drawn sheets written
`sch.write_schematic` SHALL write the junctions, buses, bus entries, bus aliases, local labels, power symbols and opaque items of a created sheet in the form of S-0367 for both targets, in the root order bus aliases, no-connect flags, junctions, bus entries, wires, buses, labels, symbols, sheet references, opaque items, `sheet_instances`. Opaque items MUST pass `versions.check_emittable` like every other node.

#### Scenario: Every kind written
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_sch_write_drawn.py` writes the lowered full fixture for targets 9 and 10 and reads each text back
- **THEN** the root holds one `junction`, `bus`, `bus_entry` and `bus_alias` per drawn item, and extraction of the read sheets gives the drawn value

#### Scenario: Too-new opaque item
- **GIVEN** an opaque item whose head the inventory dates after the 9.0 constant
- **WHEN** the sheet is written for target 9
- **THEN** `LossyWriteError` (`FEN-7001`) is raised naming the head, and with `allow_lossy=True` the item is dropped with one `kicad.sch.dropped-too-new` warning

### Requirement: Drawn wires cut at junctions
`lower_drawn` MUST cut each wire at the junctions on its inside and each bus at its junctions and bus entry ends, the form KiCad's editor keeps (9.0.9 does not join the uncut form; measured on 2026-10-29).

#### Scenario: KiCad loads the drawn sheets
- **WHEN** `uv run pytest tests/kicad/schematic/test_drawn_write_oracle.py -rA` runs with `kicad-cli` 9.0.9 or 10.0.6
- **THEN** the netlist export of each written drawn fixture equals the resolver's nets, ERC reports no violation that the source lacks, and the probe `drawn-write` records `equal`

### Requirement: Repeated sheets written
A drawn sheet that several references name SHALL be written once, and each of its symbols MUST hold one `instances` path per reference with the reference and unit of that instance's component. Each reference MUST name the same file, and the board's footprint paths MUST use the sheet uuids of their instance (`H-K-SCH-HIER-PATH`).

#### Scenario: Two channels
- **WHEN** the repeated fixture is built for target 10
- **THEN** one file `sheets/channel.kicad_sch` is written, its `R1` holds two instance paths with the references of `ch0/R1` and `ch1/R1`, and the two footprints' paths differ in their sheet uuid only

### Requirement: Drawn content of a read sheet
`sch.opaque_drawing(sheet) -> OpaqueDrawing` SHALL give, from the opaque root slots of a read sheet, the points of each `wire` and `bus`, the position and size of each `bus_entry`, the position and diameter of each `junction` and the name and members of each `bus_alias`, in file order, and the remaining slots verbatim. A slot whose numbers are not whole nanometres MUST stay among the remaining slots. The reader's slot rules are unchanged.

#### Scenario: Junctions of a read sheet
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_sch_opaque_drawing.py` reads `tests/data/kicad/schematic/flat.kicad_sch`
- **THEN** the junctions and wires equal the `junction` and `wire` children of the file, and `opaque_wires` gives the same wire points
