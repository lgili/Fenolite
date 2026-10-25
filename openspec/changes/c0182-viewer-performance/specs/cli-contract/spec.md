## ADDED Requirements

### Requirement: View command caches scenes
`fenolite view` SHALL cache scenes under `.fenolite/view-cache/` of the project, or the user cache with `--cache user`, and `--cache off` SHALL disable it. `--export` SHALL accept `--docs ID,...` to embed only those documents.

#### Scenario: Export of one document
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k docs` exports an Altium project with `--docs` naming its board
- **THEN** `result.export.documents` lists only that board
