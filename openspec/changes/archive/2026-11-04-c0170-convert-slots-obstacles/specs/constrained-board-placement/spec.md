## ADDED Requirements

### Requirement: Slots are placement obstacles
The constrained placer's hard checks and its preview, and the body-volume analysis, SHALL take the rings of `model.outline.outline_items`, so a slot is an obstacle as a cut-out is.

#### Scenario: A footprint over a slot
- **GIVEN** the shared fixture and a footprint whose courtyard overlaps slot `S1`
- **WHEN** `uv run pytest tests/unit/placement/test_slot_obstacles.py` runs the hard checks
- **THEN** the footprint is reported as overlapping a cut-out, as it is for the same ring drawn with `cutout()`
