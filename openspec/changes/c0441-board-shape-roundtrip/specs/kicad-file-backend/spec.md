## ADDED Requirements

### Requirement: Corner ratio of a created board pad
The KiCad board writer SHALL write the `roundrect_rratio` of every created board pad of shape `roundrect`
whose `Pad.corner_ratio` is set (change c0441), not only beside a chamfer: read back, the pad holds the same
ratio. A pad read or embedded keeps its shape children in its slots, as before.

#### Scenario: Rounded pads converted from Altium
- **GIVEN** the authored Altium `routed` sample, whose rounded-rectangle pads have the corner ratio 0.25
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_shape.py -k vias` converts it to KiCad and back
- **THEN** every rounded-rectangle pad of the round trip has the corner ratio of its source, and no pad is
  lost
