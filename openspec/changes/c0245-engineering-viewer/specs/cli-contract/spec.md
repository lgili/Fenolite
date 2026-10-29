## ADDED Requirements

### Requirement: View command workbench options
`fenolite view` SHALL accept:
- `--workspace board|roles`;
- `--keymap fenolite|altium|kicad|FILE`;
- `--layout FILE`;
- `--roles FILE`;
- `--edit`, with `--serve` only;
- `--window`, with `--serve` only and the optional `view-app` extra.

With `--workspace roles --json` it MUST add `result.roles` with role counts by state and findings by severity, and write nothing. A bad keymap or layout file MUST be `FEN-3004`. `--edit` without `--serve`, or `--workspace roles` on a document that is not a board, MUST be `FEN-2001`.

#### Scenario: Roles summary for an agent
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k workspace` runs `fenolite view <bad buck> --workspace roles --json`
- **THEN** the exit code is 0, `result.roles.counts` holds the inferred and confirmed counts, `evidence.level` is `INFERRED`, and nothing is written

#### Scenario: Edit needs the server
- **WHEN** `fenolite view <board> --edit --json` runs
- **THEN** the exit code is 2 with `FEN-2001` naming `--edit`

#### Scenario: Optional native window
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k window` requests `--serve --window`
- **THEN** the lazy optional native host opens the loopback page, closing it stops the server, and no
  ordinary browser opens; without the extra the reply is exit 6 / `FEN-6001` with its install hint
- **AND** `--window` without `--serve` returns `FEN-2001`
