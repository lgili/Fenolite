# viewer-visual-tests Specification

## Purpose
Every change of what the viewer page draws is checked automatically: authored fixtures of each scene kind are drawn in a pinned Chromium and compared with committed references, and scripted interactions check selection, measurement, units and cross-probing (change c0191).

## Requirements

### Requirement: Screenshot references
For each scene kind the test suite SHALL render an authored fixture in Chromium and SHALL fail when more than 0.1 % of the pixels differ from the committed reference.

#### Scenario: A changed colour fails
- **GIVEN** the reference of the Altium sheet fixture
- **WHEN** `uv run pytest tests/visual -k altium_sheet` runs with the sheet colour changed in the page
- **THEN** the test fails and writes a difference image
