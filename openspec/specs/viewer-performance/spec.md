# viewer-performance Specification

## Purpose
Large boards open fast in the viewer: scenes are cached by input and code digest and sent in a compact form, with size budgets measured on the largest public board (change c0182).

## Requirements

### Requirement: Scene cache
`fenolite view` SHALL reuse a cached scene when the SHA-256 of every input file, the Fenolite version and the theme match the cache entry, and SHALL rebuild it otherwise.

#### Scenario: A second open
- **GIVEN** a board viewed once
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k second_open` views it again, then changes one byte of it and views it once more
- **THEN** the second view reads the cache and the third rebuilds the scene

### Requirement: Compact board scenes
Board scenes SHALL be written in the `fenolite.view_scene.v1` encoding, and the page SHALL draw a v1 scene exactly as the same scene in v0.

#### Scenario: Same drawing
- **GIVEN** the scene of an Altium and of a KiCad test board in v0 and in v1
- **WHEN** `uv run pytest tests/unit/view/test_scene_v1.py` decodes the v1 scene in Python and in the page's decoder under Node
- **THEN** the decoded primitives equal the v0 primitives

#### Scenario: Budget of the largest public board
- **GIVEN** the board of S-0187 in the corpus cache
- **WHEN** `uv run pytest tests/corpus/test_view_budget.py` builds its scene
- **THEN** the v1 primitives are at most half the size of the v0 primitives and the packed scene at most a tenth of the v0 scene
