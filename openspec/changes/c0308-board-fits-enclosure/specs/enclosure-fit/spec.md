## ADDED Requirements

### Requirement: Fit record document
`fenolite.model.enclosure` SHALL define `Fit` and `FaceRule` and read and write `fenolite.enclosure-fit.v0` canonically, with the schema `schemas/fenolite.enclosure-fit.v0.json`. The reader MUST refuse a record whose `box_sha256` does not match its embedded box, with `FormatError` naming `/box_sha256`.

#### Scenario: Round trip
- **WHEN** `uv run pytest tests/unit/model/test_enclosure_fit.py` loads and dumps the record of `examples/enclosure/fit_box.py`
- **THEN** the text is byte-identical, and a copy with one box length changed is refused naming `/box_sha256`

### Requirement: Fit pose transform
A box point (x, y) SHALL map to `at + (x', −y')`, where (x', y') is (x, y) turned counter-clockwise by the fit's rotation in the box's Y-up frame; `Fit.to_board` MUST expose it. At rotation 0 the `front` face MUST lie at the largest board Y.

#### Scenario: Four rotations
- **WHEN** `uv run pytest tests/unit/dsl/test_fit.py -k pose` maps boss `B1` of the fixture at (−45 mm, −25 mm) with `at=(mm(60), mm(40))` for the four rotations
- **THEN** the points are (15, 65), (85, 85), (105, 15) and (35, −5) in mm for 0, 90, 180 and 270, as written by hand in the test

### Requirement: Fitted board loads in KiCad
A board built with `fit.outline`, `fit.holes()` and `fit.zones()` SHALL load in `kicad-cli` 9.0.x and 10.0.x with no `invalid_outline`, and its DRC SHALL give no violation type that the board without `fit.holes()` and `fit.zones()` lacks.

#### Scenario: Example board
- **WHEN** `uv run pytest tests/kicad/enclosure/test_fit_build.py` builds `examples/enclosure/fit_box.py` and runs `pcb drc` in the jobs `kicad-9` and `kicad-10`
- **THEN** there is no `invalid_outline` and no new violation type (`H-K-ENCL-FIT-BUILD`)
