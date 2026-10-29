## ADDED Requirements

### Requirement: Workbench references
The visual tests SHALL hold references for the workbench (board dark, board light), the Net Roles workspace (normal and colour-blind palette), the Messages panel with a selected finding, and the narrow window, rendered from fixtures authored for Fenolite. They SHALL be rewritten only by `tools/update_view_refs.py`, after review.

#### Scenario: A changed panel colour fails
- **WHEN** `uv run pytest tests/visual -k workbench_board_dark` runs with the panel title colour changed
- **THEN** the test fails and writes a difference image

### Requirement: Deterministic screenshots
Two renders of the same fixture in the pinned Chromium and fonts SHALL give identical PNG bytes. Animations, the caret and timers MUST be frozen in the visual mode.

#### Scenario: Twice the same bytes
- **WHEN** `uv run pytest tests/visual/test_screens.py -k deterministic` renders every fixture twice
- **THEN** each pair of PNG files has equal SHA-256
