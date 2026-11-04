## ADDED Requirements

### Requirement: Clearance tolerance of the tool
`check_copper` SHALL take `tolerance=0` (nm, not negative) and judge a pair too close when its shapes are closer than the value in force minus `tolerance`; edge clearance keeps the strict rule. `DesignRules.clearance_tolerance` SHALL give it: 500 nm from the KiCad rules source (`H-K-COPPER-EPSILON`), 0 from others; the build's copper guard and the `copper.clearance` stage MUST pass it.

#### Scenario: KiCad's tolerance
- **GIVEN** two tracks of nets `A` and `B` whose edges are 500 nm closer than a 0.2 mm class clearance, written as a KiCad project
- **WHEN** `uv run pytest tests/unit/checks/test_copper_tolerance.py` runs the build's copper guard
- **THEN** it reports no finding, and at 501 nm closer it reports one `copper.clearance`; `check_copper` without `tolerance` reports both

#### Scenario: Measured against KiCad
- **WHEN** `uv run pytest tests/kicad/copper/test_drc_tolerance.py -rA` runs in the `kicad-9` and `kicad-10` jobs
- **THEN** KiCad's DRC is clean at `c − 500 nm` and reports `clearance` at `c − 501 nm` for track pairs under a rule, a class, a board minimum and a class pair gap, and the copper guard agrees on every row
