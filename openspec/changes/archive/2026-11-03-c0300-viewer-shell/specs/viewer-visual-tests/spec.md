## ADDED Requirements

### Requirement: Shell references in both themes
The screenshot references SHALL include the board fixture drawn in the light interface theme next to the existing references in the dark theme, and every reference SHALL be regenerated in the environment of the `viewer` CI job, never on another platform.

#### Scenario: The light shell has its own reference
- **GIVEN** the reference `tests/visual/refs/kicad_board_light.png`
- **WHEN** `uv run pytest tests/visual -k kicad_board_light` runs with a toolbar colour token changed in the page
- **THEN** the test fails and writes a difference image
