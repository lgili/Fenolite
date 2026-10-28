## ADDED Requirements

### Requirement: Reviewed catalog component selection

The standalone catalog browser SHALL support selection of a symbol and footprint together, geometric filters, simultaneous previews using the existing renderer and an explicit pin-to-pad map. Metadata and evidence SHALL remain tied to the exact definitions. Generic counts or dimensions SHALL NOT establish device compatibility.

#### Scenario: Search by geometry
- **WHEN** a user filters footprint candidates by mounting kind, electrical pad count or pad/centre dimensions
- **THEN** results use the embedded model facts in consistent units
- **AND** invalid numeric filters, unavailable measurements and no matches have explicit states without silently changing the selected component

#### Scenario: Preview a pair offline
- **WHEN** a symbol and footprint are selected
- **THEN** both actual definitions are rendered together by the existing library viewer
- **AND** preview frames open only the same local page, do not recursively create frames or exchange project selections

#### Scenario: Mapping has not been reviewed
- **WHEN** the mapping is missing, names an unknown pad, repeats a pad across pins, leaves an electrical pad unused or lacks user datasheet confirmation
- **THEN** no ready-to-copy Python component snippet is presented
- **AND** the reason is visible without upgrading catalog evidence

#### Scenario: A reviewed map becomes a Part
- **WHEN** every pin and numbered pad is mapped unambiguously and the user explicitly confirms their datasheet review
- **THEN** the generated Python Part snippet contains the selected symbol ID, footprint ID and exact pad_map
- **AND** changing either definition or the mapping clears confirmation before another snippet is available
