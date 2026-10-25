## ADDED Requirements

### Requirement: View command opens at a selection and reads review marks
`fenolite view` SHALL accept `--select REF` to open at a part or net, and `--marks FILE` to reply with the review marks of that file in `result.marks`.

#### Scenario: Marks for an agent
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k marks` passes an authored review file
- **THEN** `result.marks` lists its marks with their document, position and note
