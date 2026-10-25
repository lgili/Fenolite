## ADDED Requirements

### Requirement: View command compares two revisions
`fenolite view NEW --compare OLD` SHALL reply with `result.compare`, the count of each kind of change, and SHALL refuse two documents of different families with `FEN-2001`.

#### Scenario: Compare counts
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k compare` compares an authored board with its edited copy
- **THEN** the exit code is 0 and `result.compare.moved` is 1
