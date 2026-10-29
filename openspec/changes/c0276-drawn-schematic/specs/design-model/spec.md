## ADDED Requirements

### Requirement: Drawn schematic entities
`fenolite.model.schematic` SHALL define `Junction(position, diameter=0)`, `BusWire(start, end)`, `BusEntry(position, size)` and `BusAlias(name, members)`, entities with the common header, and `SchematicSheet` SHALL gain `junctions`, `buses`, `bus_entries` and `bus_aliases`, ordered tuples omitted when empty. Only created sheets hold them; a read sheet keeps them as opaque slots.

#### Scenario: Older sheet data
- **GIVEN** a canonical schematic text written before this change
- **WHEN** it is loaded and written again
- **THEN** the bytes are equal

#### Scenario: Read sheets stay opaque
- **WHEN** `tests/data/kicad/schematic/flat.kicad_sch` is read
- **THEN** `sheet.junctions` is empty and its `junction` children are opaque slots

#### Scenario: No float
- **WHEN** a `Junction` with a float diameter is built
- **THEN** `TypeError` or `ValueError` is raised

### Requirement: Drawn schematic value
`fenolite.model.drawn` SHALL define the frozen value of a drawn schematic: `DrawnSchematic(root, sheets)`, `DrawnSheet`, `DrawnSymbol`, `DrawnField`, `DrawnPower`, `DrawnLabel`, `DrawnSheetRef`, `DrawnPin` and `DrawnOpaque`, with positions in integer nm and angles in integer µdeg. A drawn symbol MUST name its component by path relative to its instance's module and never by reference.

#### Scenario: Equality and hashing
- **WHEN** `uv run pytest tests/unit/model/test_drawn_value.py` builds two equal drawn values
- **THEN** they are equal, hash equally, and no field holds a float

#### Scenario: Instances from paths
- **GIVEN** the repeated drawn fixture
- **WHEN** `DrawnSchematic.instances()` is called
- **THEN** it gives `("", "root")`, `("ch0", "channel")` and `("ch1", "channel")` in page order
