## ADDED Requirements

### Requirement: View command runs read-only commands
`fenolite view --serve` SHALL serve the run routes of `board-viewer` with a runner whose time limit is `--run-timeout SECONDS` (default 600, above 0), and SHALL serve none with `--no-run`. Either option without `--serve` MUST be `FEN-2001`. The reply's `result.serve` MUST count the runs by final state in `runs`.

#### Scenario: Options without serve
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k run_options` runs `fenolite view <board> --run-timeout 60 --json` and `fenolite view <board> --no-run --json`
- **THEN** each exits 2 with `FEN-2001` naming the option

#### Scenario: Runs counted
- **GIVEN** a served view, stopped by the test's event after one run that ended `done` and one that was cancelled
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k runs_counted` reads the reply
- **THEN** `result.serve.runs` is `{"done": 1, "cancelled": 1}`
