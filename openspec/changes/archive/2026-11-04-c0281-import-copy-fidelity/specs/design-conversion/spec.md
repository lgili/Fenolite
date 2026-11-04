## ADDED Requirements

### Requirement: Bottom-side angles in a derived footprint
A footprint derived from a bottom-side instance SHALL turn each stored angle of its pads, properties and texts back to `(θ − stored) mod 360°`, the inverse of the bottom placement `(−φ + θ) mod 360°`, so that placing the derived footprint where the instance was gives the instance's angles back.

#### Scenario: Reference at 270° on the bottom
- **GIVEN** the authored two-layer board with `R1` replaced by a footprint whose Reference and pad 1 stand at 90°, placed on the bottom side at 0°, 90° and 180° (at 0° the board stores the Reference at 270°)
- **WHEN** `uv run pytest tests/unit/library/test_derive.py -k bottom` derives the library from each board
- **THEN** the derived footprint holds the Reference and pad 1 at 90° again, as it was before placement
