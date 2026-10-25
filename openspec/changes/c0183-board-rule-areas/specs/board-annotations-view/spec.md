## ADDED Requirements

### Requirement: Keep-outs in the board scene
The board scene SHALL draw each keep-out of the model on its layers, hatched, and the Properties panel SHALL list what it forbids.

#### Scenario: An authored keep-out
- **GIVEN** an authored KiCad board with a rule area that forbids vias and footprints on `F.Cu`
- **WHEN** `uv run pytest tests/unit/view/test_board_annotations.py -k keepout` builds its scene
- **THEN** the scene holds a hatched outline on `F.Cu` whose properties name vias and footprints

### Requirement: Courtyard overlaps
The board scene SHALL mark each pair of overlapping courtyards on a `Checks` view layer, with both parts named.

#### Scenario: Two overlapping parts
- **GIVEN** an authored board with two parts whose courtyards overlap
- **WHEN** `uv run pytest tests/unit/view/test_board_annotations.py -k overlap` builds its scene
- **THEN** the `Checks` layer holds one mark naming both parts
