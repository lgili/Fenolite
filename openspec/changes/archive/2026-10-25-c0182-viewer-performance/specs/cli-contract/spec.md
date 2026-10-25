## ADDED Requirements

### Requirement: View command caches scenes
`fenolite view` SHALL cache scenes in the user's cache folder by default (`--cache user`), under `.fenolite/view-cache/` of the project with `--cache project`, and not at all with `--cache off`, and SHALL reply with `result.cache`. `--export` SHALL accept `--docs ID,...` to embed only those documents.

#### Scenario: Export of one document
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k docs` exports an Altium project with `--docs` naming its board
- **THEN** `result.export.documents` lists only that board
