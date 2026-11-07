## ADDED Requirements

### Requirement: Board comparison of placed components
The verification of a conversion that wrote a schematic SHALL compare the written board with the
components that have a footprint on the board, and SHALL leave the other components to the comparison of
the written schematic. A component without a footprint that the written schematic lacks SHALL still be
reported. A conversion without a written schematic SHALL compare every component with the board.

#### Scenario: A schematic-only component
- **WHEN** an Altium project holds a component that no footprint of its PCB places, and `fenolite convert --to kicad` runs
- **THEN** no `convert.unexplained` names that component
- **AND** the written schematic holds it

### Requirement: Several footprints of one component
The KiCad direction SHALL count each footprint of a source component that more than one footprint links
as a changed `shared-footprint` item (class `report`), and the explanation SHALL explain a
`ref-ambiguous` difference at its reference.

#### Scenario: One component linked to two footprints
- **WHEN** a source board links two footprints to one component and the conversion runs
- **THEN** the report lists both footprints under `shared-footprint`
- **AND** the `ref-ambiguous` difference of that reference is explained
