## ADDED Requirements

### Requirement: View command review and models
`fenolite view` SHALL draw the review findings and the body models of `board-viewer`, with these options: `--no-review` (no review findings and no open connections), `--no-models` (no meshing), `--silk-gap MM` and `--mask-expansion MM` (millimetres, at least 0).
- The open connections of `analysis.connectivity` MUST be drawn as lines between the two anchors of each, in the group `open_ground` for a net whose name holds `GND`, `GROUND`, `VSS`, `EARTH` or `0V` as a word, or is `PE`, `FE` or `COM`, else in `open_net`.
- The reply's `summary` MUST hold `findings`, the count per group, and `models`, the count of bodies per render (`model`, `fitted`, `outline`) and of models gmsh could not mesh; the summary-only form MUST mesh nothing and report `models` as `null`.
- With `--serve`, models MUST be meshed after the first scene is served, and the page MUST reload when they are placed. With `--export`, they MUST be meshed before the page is planned.
- A port that is in use MUST be `FEN-2001` with a hint to pass `--port 0`.
- `--overlay FILE` MUST accept an `analyze` reply or a findings file (`board-viewer`, "Findings file"); any other file MUST be `FEN-3004`.

#### Scenario: Findings in the summary
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k review_summary` runs `fenolite view tests/data/kicad/board/two_layer.kicad_pcb --json`
- **THEN** `result.summary.findings` holds a count for every group of `review.GROUPS` and for `open_ground` and `open_net`, and `result.summary.models` is `null`

#### Scenario: Port in use
- **GIVEN** a socket bound on a port of `127.0.0.1`
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k port_in_use` serves on that port
- **THEN** the exit code is 2 with `FEN-2001` and the hint names `--port 0`

## MODIFIED Requirements

### Requirement: Capabilities command
`fenolite capabilities` SHALL list every registered command with `name`, `mutates` and `schema`; the backends registered; the optional extras detected; the external tools detected (`kicad-cli`, `java`, `docker`, `gmsh`) with version strings when present; and the boolean `sends_data_offsite`.

#### Scenario: Capabilities lists commands
- **WHEN** `fenolite capabilities --json` runs
- **THEN** `result.commands` contains an entry named `capabilities` with `mutates` equal to `false`

#### Scenario: Tool detection is non-fatal
- **GIVEN** `kicad-cli` is not installed
- **WHEN** `fenolite capabilities --json` runs
- **THEN** the exit code is 0 and `result.tools.kicad-cli` is `null`
