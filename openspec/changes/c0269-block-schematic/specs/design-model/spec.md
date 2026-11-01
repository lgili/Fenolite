## ADDED Requirements

### Requirement: Sheet pins in the schematic model
`fenolite.model.schematic` SHALL define `SheetPin(Entity)` with `name`, `shape` (`input`, `output` or `bidirectional` for a block's pins; a drawn sheet of change c0276 may also give `tri_state` or `passive`), `position` and `rotation`, and `SheetRef` SHALL gain `pins: tuple[SheetPin, ...] = ()`, ordered and omitted when empty. Only created sheets hold sheet pins; a sheet read from a file keeps them as opaque slots of its reference.

#### Scenario: Older sheet data
- **GIVEN** a canonical schematic text written before this change
- **WHEN** it is loaded and written again
- **THEN** the bytes are equal

#### Scenario: Refused shape
- **WHEN** a `SheetPin` with `shape="clock"` is built
- **THEN** `ValueError` is raised naming the shape
