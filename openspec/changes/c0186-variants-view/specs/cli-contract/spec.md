## ADDED Requirements

### Requirement: View command shows a variant
`fenolite view` SHALL accept `--variant NAME` for an Altium project, reply with the count of fitted and not-fitted parts, and refuse an unknown name with `FEN-2001`.

#### Scenario: Unknown variant
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k variant` runs `fenolite view` with `--variant Nope`
- **THEN** the exit code is 2 and the error code is `FEN-2001`
