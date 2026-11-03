## ADDED Requirements

### Requirement: Generated bodies are known volumes
A body produced by a footprint generator SHALL carry signed `z_min`/`z_max` bounds and `projection_unknown == False`, computed from the package record's height, standoff and lead lengths, so that volume and height analyses treat it as known geometry. A record without a body height MUST give no body at all rather than invented ones.

#### Scenario: Height read from a generated body
- **GIVEN** a placed footprint generated from `soic8.toml` (height max 1.75 mm)
- **WHEN** `outward_height` is computed for it
- **THEN** it returns `1750000`

#### Scenario: No height, no body
- **WHEN** a record without `body.height` is generated
- **THEN** the footprint has no body and its outward height is `None`
