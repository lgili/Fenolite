## ADDED Requirements

### Requirement: Slots in design files
A Specctra design file written for a board with slots SHALL hold one `keepout` polygon per inner ring of `board_outline`, slots and merged groups included, and a Freerouting run on the shared fixture SHALL route no track across a slot (`H-G-DSN-SLOT`).

#### Scenario: Keep-outs of the fixture
- **WHEN** `uv run pytest tests/routing/test_slots_route.py -k keepouts` writes the design file of the shared fixture
- **THEN** it holds three `keepout` polygons, one of them the merged L

#### Scenario: Routed around the slot
- **GIVEN** the fixture with two pads of one net on either side of `S1`
- **WHEN** Freerouting routes it
- **THEN** no routed segment crosses the ring of `S1`
