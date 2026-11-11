## MODIFIED Requirements

### Requirement: Copper against drilled holes
`check_copper` SHALL judge every drilled hole (pad drills, plated or not, round or slot; via drills on their span; board holes) against the copper of other items on each copper layer it passes, and report `copper.hole-clearance` when the gap to the hole's wall is below the hole clearance in force: the governing `hole_clearance` rule, else `DesignRules.min_hole_clearance` (KiCad: `board.design_settings.rules.min_hole_clearance`). A hole SHALL have the net of its pad, plated or unplated, or of its via; a board hole has none. Copper of the hole's own pad or via, copper of the hole's net, and a pair that already has a `copper.short` or `copper.clearance` finding MUST NOT be reported, unless a governing `hole_clearance` rule selects that same-net pair. Without a value the pass MUST be skipped. The build's copper guards and the `copper.clearance` stage of `fenolite check` SHALL pass the value (change c0403, F9; change c0491).

#### Scenario: Script copper across an unplated hole
- **GIVEN** an authored design script whose track crosses a 3 mm unplated hole of a footprint, on a project with a hole clearance of 0.25 mm
- **WHEN** `uv run pytest tests/unit/cli/test_build_copper_guard.py -k mounting_hole` builds it with `--dry-run`
- **THEN** the reply holds `copper.hole-clearance` and plans no write, and the same track 0.3 mm from the wall builds

#### Scenario: Copper of the net of an unplated pad
- **GIVEN** an authored board with an unplated pad of net `GND`, a `GND` zone fill and a `GND` via 0.1 mm from its wall, and a hole clearance of 0.25 mm
- **WHEN** `check_copper` judges it
- **THEN** it reports no `copper.hole-clearance`
- **AND** with the via on net `N1` it reports one `copper.hole-clearance` for the via

#### Scenario: An unplated pad without a net
- **GIVEN** the same board with the pad's net removed
- **WHEN** `check_copper` judges it
- **THEN** it reports `copper.hole-clearance` for the via, as before
