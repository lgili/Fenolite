## ADDED Requirements

### Requirement: View command
`fenolite view PATH [--doc ID] [--overlay FILE]... [--serve [--port N] [--no-browser]] [--export FILE]` SHALL show the boards of a project without the native tool (`board-viewer`). `PATH` is an Altium project file, a KiCad project file, a folder or a board. The command is a writing command whose only write is `--export`.
- Without `--serve` and `--export` it MUST write nothing and reply with `project` (the tree), `document` (the id of the board shown), `summary` (its layers and the count of each item kind) and `notes`.
- `--export FILE` MUST plan one HTML file with the tree and the scene of every viewable document embedded, under the mutation protocol.
- `--serve` MUST write one progress record with the URL to stderr, serve until interrupted, and then reply with `url` and `seconds`; it MUST bind `127.0.0.1` only. `--serve` with `--export` MUST be a usage error (`FEN-2001`).
- `--overlay FILE` MUST read a JSON envelope of `fenolite analyze`; a file that is not one MUST be `FEN-3004`.
- A path that no backend and no project reader understands MUST be `FEN-2001`; a missing path `FEN-3001`.

#### Scenario: Summary of a board
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k summary` runs `fenolite view tests/data/kicad/board/two_layer.kicad_pcb --json`
- **THEN** the exit code is 0, `result.project` lists the board as viewable, `result.summary.counts.tracks` equals the board's track count, and nothing is written

#### Scenario: Export follows the protocol
- **WHEN** `fenolite view <board> --export view.html --json` runs without `--dry-run` or `--confirm`
- **THEN** the exit code is 4 with `FEN-4001`, nothing is written, and `--confirm` writes `view.html`
