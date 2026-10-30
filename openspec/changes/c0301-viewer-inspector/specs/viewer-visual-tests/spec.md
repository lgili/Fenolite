## ADDED Requirements

### Requirement: Net emphasis reference
The screenshot references SHALL include the board fixture with one net selected, so that a change of how a selected net or the dimmed rest is drawn fails a test.

#### Scenario: A changed emphasis fails
- **GIVEN** the reference `tests/visual/refs/kicad_board_net.png`
- **WHEN** `uv run pytest tests/visual -k kicad_board_net` runs with the dim factor of the highlight changed in the page
- **THEN** the test fails and writes a difference image
