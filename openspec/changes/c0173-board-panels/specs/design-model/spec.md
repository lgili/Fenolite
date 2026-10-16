## ADDED Requirements

### Requirement: Panels in the model
`model.panel.Panel` SHALL be a frozen entity with `name`, `source` (path, SHA-256, backend), `array` (rows, cols, gaps, rotation a multiple of 90° in µdeg, `mirrored`), `frame` (four rail widths), `separations`, `tabs`, `vscore`, `fiducials`, `tooling_holes` and `limits`, lengths in `Nm`. It SHALL be written as canonical JSON `panel.json`; the writer MUST omit defaults.

#### Scenario: A panel round-trips
- **GIVEN** a `Panel` of a 2 × 4 grid with rails, tabs between columns and V-score between rows
- **WHEN** `uv run pytest tests/unit/model/test_panel.py` dumps it with `canonical.dump_dir` and loads it again
- **THEN** the loaded panel equals the original, and its schema check passes

#### Scenario: A rotation that is no quarter turn
- **WHEN** a `PanelArray` with rotation 45 000 000 µdeg is made
- **THEN** it raises `ValueError` naming the rotation
