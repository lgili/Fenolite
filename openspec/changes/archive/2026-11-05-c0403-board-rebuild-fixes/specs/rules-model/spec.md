## ADDED Requirements

### Requirement: Rule passes accept pads without copper
The shadowed-rule pass of `fenolite check` (`checks.specificity.shadowed_rules`) SHALL build its subjects from every pad of the board, and a pad that no copper record can hold (a circular pad of size 0, of any kind) MUST stay a pad without copper entries instead of ending the command with `FEN-1001` (change c0403, F5).

#### Scenario: A zero-size pad beside two overlapping clearance rules
- **GIVEN** an authored board with an SMD and a plated circular pad of size 0, and two clearance rules where the broader one governs
- **WHEN** `uv run pytest tests/unit/checks/test_specificity.py -k zero_size` runs the pass
- **THEN** it returns one `rules.shadowed` and raises nothing
