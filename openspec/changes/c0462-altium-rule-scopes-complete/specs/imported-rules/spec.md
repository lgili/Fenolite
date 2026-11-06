## ADDED Requirements

### Requirement: Altium rooms are rule areas
An Altium import SHALL read each room of the document as a neutral rule area of the room's name, its outline and layers (change c0462), so that `WithinRoom` maps to `area`.

- A pad or a via MUST be in a room when its centre is; any other object MUST lie wholly within the room (S-2212).
- A room whose outline Fenolite does not read MUST make `WithinRoom` of it refused with the reason `undefined`.

#### Scenario: A rule within a room
- **GIVEN** an authored document with the room `PWR`, a pad inside it and a pad outside, and a Clearance rule scoped `WithinRoom('PWR')`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rooms_c0462.py -q -n 0` imports it
- **THEN** the design holds the rule area `PWR`, and the rule selects only the pad inside
