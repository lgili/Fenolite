## ADDED Requirements

### Requirement: View command allows writing actions
`fenolite view --serve --allow-actions` SHALL serve the writing actions of `board-viewer`; without the option the server MUST refuse them. `--allow-actions` without `--serve` MUST be `FEN-2001`. The option's help MUST say that the page can then write the project's files through reviewed plans, and `result.serve.writes` MUST list the receipts of the session.

#### Scenario: Option without serve
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k allow_actions` runs `fenolite view <board> --allow-actions --json`
- **THEN** the exit code is 2 with `FEN-2001` naming `--allow-actions`

#### Scenario: Receipts in the reply
- **GIVEN** a served view with actions allowed, stopped by the test's event after one confirmed `silk` action
- **WHEN** `uv run pytest tests/unit/cli/test_view_actions.py -k reply` reads the reply
- **THEN** `result.serve.writes` holds one receipt naming the board
