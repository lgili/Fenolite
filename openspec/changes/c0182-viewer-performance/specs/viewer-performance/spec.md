## ADDED Requirements

### Requirement: Scene cache
`fenolite view` SHALL reuse a cached scene when the SHA-256 of every input file, the Fenolite version and the theme match the cache entry, and SHALL rebuild it otherwise.

#### Scenario: A second open
- **GIVEN** an authored board viewed once
- **WHEN** `uv run pytest tests/unit/view/test_cache.py` views it again, then changes one byte of it and views it once more
- **THEN** the second view reads the cache and the third rebuilds the scene

### Requirement: Compact board scenes
Board scenes SHALL be written in the `fenolite.view_scene.v1` encoding, and the page SHALL draw a v1 scene exactly as the same scene in v0.

#### Scenario: Same drawing
- **GIVEN** the scene of `blink.kicad_pcb` in v0 and in v1
- **WHEN** `uv run pytest tests/unit/view/test_scene_v1.py` decodes both in the page's decoder under Node
- **THEN** the decoded primitives are equal and the v1 JSON is at most half the size
