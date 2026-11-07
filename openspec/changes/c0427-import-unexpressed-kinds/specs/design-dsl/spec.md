## ADDED Requirements

### Requirement: Negative silk clearance
`design.rules.rule(name, "silk_clearance", min=...)` SHALL accept a `min` below zero, which lets silkscreen
overlap by up to that much; every other kind SHALL refuse a negative `min` with `DslError` (change c0427,
`H-K-DRU-NEG-SILK`).

#### Scenario: KiCad reads it
- **WHEN** `uv run pytest tests/kicad/rules/test_negative_silk.py -q` runs DRC on two footprints whose silkscreen lines overlap by 0.05 mm, on 9.0.9 and 10.0.6
- **THEN** a board-wide minimum of 0 reports `silk_overlap`, -0.1 mm reports none, and the canary fires both times

#### Scenario: The import says it
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k negative -q` imports a rule `silk_clearance (min -0.254mm)`
- **THEN** the script holds `design.rules.rule("silk", "silk_clearance", ...)` and the built rules file holds -0.254 mm

### Requirement: Drawings on paste layers
A drawing call (`line`, `rect`, `circle`, `arc`, `polygon`, `text`) SHALL accept `F.Paste` and `B.Paste`
(change c0427, `H-K-PASTE-DRAWING`).

#### Scenario: A paste polygon builds
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k paste -q` builds the imported script
- **THEN** the board holds a filled `gr_poly` on `B.Paste`
