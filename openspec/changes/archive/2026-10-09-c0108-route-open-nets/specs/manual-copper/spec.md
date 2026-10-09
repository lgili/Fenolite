## ADDED Requirements

### Requirement: Locked script copper
`resolve_copper` SHALL give every track, arc and via that it creates from an intent whose `locked` is true `locked=True`, and `locked=False` otherwise. An intent without the attribute MUST be read as unlocked, so the intents of earlier scripts and tests keep their meaning. `merge_copper` SHALL compare `locked` with the fields that "Script copper is regenerated" compares, so script copper whose lock was changed in KiCad is regenerated with one `kicad.copper.regenerated` info. The duplicate rule of that requirement MUST ignore `locked`: an item that differs from script copper only by its lock is a duplicate.

#### Scenario: Locked track written
- **GIVEN** the blink built for target 10 and the track intent `led_a` of `examples/blink_routed/design.py` with `locked=True`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_merge.py -k locked` resolves it and writes the board
- **THEN** every item of `led_a` has `locked == True`, and each `segment` of the text holds `(locked yes)` after `width`

#### Scenario: A lock changed in KiCad is regenerated
- **GIVEN** the resolved blink whose track with locator `seg[0]` of an unlocked intent was locked in KiCad, keeping its uuid
- **WHEN** it is resolved again with the same intents
- **THEN** the track is unlocked again, and one `kicad.copper.regenerated` info names its uuid

#### Scenario: A locked copy is a duplicate
- **GIVEN** the resolved blink plus a locked copy of a script track with a version-4 uuid
- **WHEN** it is resolved again with the same intents
- **THEN** the copy is removed with one `kicad.copper.duplicate` info
