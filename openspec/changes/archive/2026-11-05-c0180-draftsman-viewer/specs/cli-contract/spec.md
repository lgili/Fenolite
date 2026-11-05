## ADDED Requirements

### Requirement: View command shows Draftsman drawings
`fenolite view` SHALL show the Draftsman documents of a project (`draftsman-viewer`): `PATH` may be a `.PCBDwf`, and `--doc` may name one. For a drawing, `result.summary` SHALL hold `kind` `drawing`, `counts.sheets` and the count of items per kind.

#### Scenario: Summary of a drawing
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k drawing` runs `fenolite view <authored>.PCBDwf --json`
- **THEN** the exit code is 0, `result.summary.kind` is `drawing` and `result.summary.counts.sheets` is 1
