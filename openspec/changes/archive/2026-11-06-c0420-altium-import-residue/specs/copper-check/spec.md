## ADDED Requirements

### Requirement: Hole clearance within the tool tolerance
`copper.hole-clearance` SHALL judge the gap to a hole's wall against the hole clearance in force less the `clearance_tolerance` of the rules source (500 nm with KiCad rules, `H-K-COPPER-EPSILON`), as `copper.clearance` does, so a gap that differs from the limit by a declared rounding is no finding; KiCad's hole clearance test allows the same tolerance (change c0420, N4).

#### Scenario: Gaps at the tolerance
- **WHEN** `uv run pytest tests/unit/checks/test_copper_holes.py -k tolerance -q` judges gaps of 5 nm and 500 nm below the limit with a tolerance of 500 nm, 501 nm below it, and 5 nm below it with no tolerance
- **THEN** the first two give no finding and the last two give one each

#### Scenario: KiCad at the same boundary
- **WHEN** `uv run pytest tests/kicad/checks/test_hole_clearance_epsilon.py -q` checks a track beside an unplated hole at 400 nm and 600 nm below a 0.25 mm minimum hole clearance
- **THEN** KiCad reports no `hole_clearance` for the first and one for the second
