## ADDED Requirements

### Requirement: Findings on the board
`fenolite view BOARD --check FILE` SHALL draw a marker for each finding of the `check` reply that has a position, on its layer, and SHALL list every finding in a Messages panel grouped by rule.

#### Scenario: Two findings
- **GIVEN** an authored `check` reply with one clearance error at a point and one finding without a position
- **WHEN** `uv run pytest tests/unit/view/test_check_overlay.py` builds the overlay
- **THEN** one marker is drawn and the panel lists two findings
