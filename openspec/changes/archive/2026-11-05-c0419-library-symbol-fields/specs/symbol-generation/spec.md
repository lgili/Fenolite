## ADDED Requirements

### Requirement: Library symbol fields
`SymbolDef.fields` SHALL hold where a definition shows its standard fields (`Reference`, `Value`, `Footprint`, `Datasheet`, `Description`): a `SymbolField` with `name`, `at`, `rotation`, `justify` (`left`, `right` or centred) and `hidden`. `write_symbol_library` MUST write a placed field's property at its `at` and rotation, with `(justify …)` when it is not centred and `(hide yes)` when hidden. A standard field without an entry MUST be written as before, so a definition without `fields` keeps its bytes. An empty `fields` MUST be left out of the canonical JSON.

#### Scenario: Placed and hidden fields
- **GIVEN** a resistor symbol whose `fields` place `Reference` at (2.54 mm, 1.27 mm) left-justified and hide `Footprint`, `Datasheet` and `Description`
- **WHEN** it is written and the library is saved by `kicad-cli sym upgrade --force` (KiCad 10.0.6)
- **THEN** the saved `Reference` property is at (2.54, 1.27) with `(justify left)`, and `Footprint`, `Datasheet` and `Description` carry `(hide yes)`

#### Scenario: Definitions without fields keep their bytes
- **WHEN** a definition without `fields` is written
- **THEN** the text equals the text written before this change

### Requirement: Symbol lines keep every point
`write_symbol_library` SHALL write a `line` graphic as one open polyline of all its points in order. A line of two points MUST keep its bytes.

#### Scenario: A three-point line
- **WHEN** a symbol with a `line` through (0, 0), (1.27 mm, 1.27 mm) and (2.54 mm, 0) is written and saved by `kicad-cli sym upgrade --force`
- **THEN** the saved polyline holds the three points
