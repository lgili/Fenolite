## ADDED Requirements

### Requirement: Altium kinds in capabilities
`fenolite capabilities` SHALL list, for the backend `altium`, the kinds whose write graduated in `write_kinds`, and the others under `experimental` with, for each, the missing conditions that `graduated` returns.
- The list MUST be computed from the evidence matrix; no kind is named in the command's code.

#### Scenario: Computed from the matrix
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_altium.py` compares `capabilities --json` with `graduated` for every Altium row
- **THEN** `write_kinds` holds exactly the graduated kinds, and each experimental kind lists what is missing
