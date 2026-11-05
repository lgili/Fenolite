## ADDED Requirements

### Requirement: Copper against drilled holes
`check_copper` SHALL judge every drilled hole (pad drills, plated or not, round or slot; via drills on their span; board holes) against the copper of other items on each copper layer it passes, and report `copper.hole-clearance` when the gap to the hole's wall is below the hole clearance in force: the governing `hole_clearance` rule, else `DesignRules.min_hole_clearance` (KiCad: `board.design_settings.rules.min_hole_clearance`). Copper of the hole's own pad or via, copper of the same net as a plated hole, and a pair that already has a `copper.short` or `copper.clearance` finding MUST NOT be reported; without a value the pass MUST be skipped. The build's copper guards and the `copper.clearance` stage of `fenolite check` SHALL pass the value (change c0403, F9).

#### Scenario: Script copper across an unplated hole
- **GIVEN** an authored design script whose track crosses a 3 mm unplated hole of a footprint, on a project with a hole clearance of 0.25 mm
- **WHEN** `uv run pytest tests/unit/cli/test_build_copper_guard.py -k mounting_hole` builds it with `--dry-run`
- **THEN** the reply holds `copper.hole-clearance` and plans no write, and the same track 0.3 mm from the wall builds

### Requirement: Copper narrower than the governing track width
`fenolite build` SHALL judge each track and arc of the planned board against the `min` of the `track_width` rule that governs it (the last match in `rule_precedence` order, its layers holding the item's layer) and report one `copper.track-width` per net and rule, with the rule's severity, the narrowest width, the rule and its `min`. The KiCad copper guard MUST treat it as its other copper errors, so an error plans no write (change c0403, F10).

#### Scenario: A narrow script row
- **GIVEN** a design script with `design.rules.minimum(track_width=mm(0.2))` and a `track_table` row of 0.162 mm
- **WHEN** `uv run pytest tests/unit/cli/test_build_copper_guard.py -k narrow_script_copper` builds it with `--dry-run`
- **THEN** the exit code is 5, the reply holds `copper.track-width` naming the rule and 0.162 mm, and no write is planned
