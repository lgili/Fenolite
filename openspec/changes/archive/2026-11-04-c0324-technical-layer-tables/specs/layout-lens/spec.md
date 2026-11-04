## ADDED Requirements

### Requirement: Exact technical rows without hidden references
A fresh build SHALL preserve explicit technical layer selections and refuse any modeled item referencing an undeclared layer. It MUST retain strict native layer-table checks, ordinary default bytes and existing model/schema definitions. It SHALL NOT drop or reassign items to satisfy a shorter table.

#### Scenario: Referenced omitted layer
- **GIVEN** a drawing, footprint field/pad or image references an omitted technical layer
- **WHEN** the design is built
- **THEN** the build refuses with the existing undeclared-layer error and writes no candidate

#### Scenario: Default board
- **WHEN** technical_layers is absent or None
- **THEN** model defaults and all recorded ordinary native file bytes remain unchanged
