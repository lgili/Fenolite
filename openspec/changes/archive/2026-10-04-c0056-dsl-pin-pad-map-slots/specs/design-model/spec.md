## ADDED Requirements

### Requirement: Persist per-component pin-to-pad maps
`Component` SHALL carry a canonical `pin_pad_map` of ordered `(symbol pin number, physical pad number)` pairs. Each source and target SHALL be non-empty and unique within its side. An empty map SHALL mean identity assignment.

#### Scenario: Serialize an explicit map
- **GIVEN** a component maps pin `1` to pad `2`
- **WHEN** the model is serialized and read back
- **THEN** the pair remains `("1", "2")` in `pin_pad_map`

#### Scenario: Preserve identity default
- **GIVEN** a component with no explicit map
- **WHEN** it is serialized and read back
- **THEN** `pin_pad_map` is empty and the build applies identity mapping
