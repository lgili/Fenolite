## ADDED Requirements

### Requirement: Board difference overlay
`fenolite view NEW --compare OLD` SHALL draw the primitives NEW adds in green, those it removes in red, and each moved part with an arrow, its distance and its angle, and SHALL list the changes in a panel.

#### Scenario: A moved part and a new track
- **GIVEN** an authored board and a copy with one part moved 1 mm and one track added
- **WHEN** `uv run pytest tests/unit/view/test_compare.py -k board` compares them
- **THEN** the overlay holds one moved part of 1 mm and one added track, and nothing else
