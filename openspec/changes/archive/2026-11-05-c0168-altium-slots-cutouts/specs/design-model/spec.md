## ADDED Requirements

### Requirement: Slotted board holes
`Hole` SHALL hold `length: Nm | None = None` and `rotation: Udeg = 0`. With `length`, the hole is a drilled slot of width `drill` and overall length `length`, its length axis turned by `rotation` in the model frame; `length` MUST exceed `drill`. The canonical writer MUST omit both at their defaults, so a document without slotted holes keeps its bytes; release 0.4.x cannot read a document that carries them.

#### Scenario: A slotted hole round-trips
- **GIVEN** a board `Hole` of drill 2 mm, length 12 mm and rotation 90°
- **WHEN** `uv run pytest tests/unit/model/test_hole_slots.py` dumps and loads it
- **THEN** it is equal, and a round hole's document keeps its bytes
