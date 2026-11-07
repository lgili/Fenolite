## ADDED Requirements

### Requirement: Not-fitted parts of a variant
With a variant chosen, the viewer SHALL cross out each part the variant does not fit on the sheets, dim it on the board, hide it in 3D, and show the variant's values of varied parameters.

#### Scenario: An authored variant
- **GIVEN** an authored `.PrjPcb` with a variant that does not fit R1 and sets C1's `Value` to `22n`
- **WHEN** `uv run pytest tests/unit/view/test_variants.py` builds the scenes with that variant
- **THEN** R1 is marked not fitted on the sheet and the board, and C1's `Value` reads `22n`
