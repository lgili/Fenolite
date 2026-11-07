## MODIFIED Requirements

### Requirement: Render command
`fenolite render PATH --out DIR [--svg] [--png] [--width PX] [--height PX] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_render.py` with `mutates=True`, and SHALL write the review views of the board that `PATH` names. With `--region` (`manufacturing-exports`, "Region renders") or `--net` (`manufacturing-exports`, "Net renders") it SHALL instead draw the board from the model with no tool, and `PATH` MAY then be a design script (`manufacturing-exports`, "Design scripts as render input").
- A call with neither `--svg` nor `--png`, nor `--region` nor `--net`, MUST exit 2 with `FEN-2001`. `--width` MUST default to 1600 and `--height` to 1200; both MUST be between 64 and 8192.
- The tool errors, the copy set and the mutation protocol MUST be `export`'s.
- The command MUST return one `PlannedWrite` per view produced, at `DIR/<view name>`.
- `result` MUST hold `board`, `out`, `views` (`path`, `kind`, `bytes`, `sha256`; sorted by path) and `tool_version`.
- A view that fails MUST give `render.failed` (warning) and the exit code MUST stay 0.
- `example_args` MUST be `(EXAMPLE_BOARD, "--out", "views", "--svg", "--png", "--dry-run")`, `mutation_example_args` the same without `--dry-run`, and `example_tools` MUST be `("kicad-cli",)`.

#### Scenario: Plan, then write
- **GIVEN** a fake `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/unit/cli/test_render_cmd.py -k plan` runs `fenolite render <board> --out views --svg --dry-run` and then `--confirm`
- **THEN** the first plans `views/front.svg` and `views/back.svg` and writes nothing, and the second writes both

#### Scenario: Size out of range
- **WHEN** `fenolite render <board> --out views --png --width 10 --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Highlight needs no tool
- **GIVEN** no `kicad-cli` on `PATH` and no `FENOLITE_KICAD_CLI`
- **WHEN** `uv run pytest tests/unit/cli/test_render_net.py -k no_tool` runs `fenolite render <board> --net GND -o views --dry-run`
- **THEN** the exit code is 0 and the plan holds `views/net-GND.svg` only
