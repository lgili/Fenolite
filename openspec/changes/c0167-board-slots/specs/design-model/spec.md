## ADDED Requirements

### Requirement: Board slots
`Outline` SHALL hold `slots: tuple[OutlineSlot, ...]`, empty by default. `OutlineSlot` SHALL be a frozen entity with `center`, `length` (overall, both round ends included), `width` and `rotation`: a non-plated milled stadium whose ring is `core.stadium.stadium(...)`. `width` MUST be positive and even and `length` MUST exceed it. Overlapping slots and cut-outs mean their union. The canonical writer MUST omit empty `slots`; release 0.4.x cannot read a document that carries it.

#### Scenario: A slot round-trips
- **GIVEN** an outline of a 40 × 30 mm rectangle with one `OutlineSlot` at (115 mm, 110 mm), length 12 mm, width 2 mm, rotation 30°
- **WHEN** `uv run pytest tests/unit/model/test_outline_slots.py` dumps it with `canonical.dump_dir` and loads it again
- **THEN** the loaded outline equals the original, and a document without slots keeps its bytes

#### Scenario: The stadium of a turned slot
- **WHEN** `stadium(Point(0, 0), 12_000_000, 2_000_000, 90_000_000)` is called
- **THEN** its vertices are exact, its mids are (0, 6 mm) and (0, −6 mm) in some order, and every vertex lies 1 mm from the axis
