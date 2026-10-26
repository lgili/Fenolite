## ADDED Requirements

### Requirement: Ready command
`fenolite ready PATH [--no-kicad] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_ready.py` with `mutates=False` and `paged = "issues"`, and SHALL report whether the KiCad project that `PATH` names is electrically ready for fabrication, without writing a file.
- `PATH` MUST resolve with `projectset.resolve_board`.
- Document input (`cli._documents.find_documents`) MUST exit 2 with `FEN-2001` and a hint that names `fenolite check`.

#### Scenario: A ready project
- **GIVEN** the fixture `tests/data/kicad/ready/` and the fake `kicad-cli` of `tests/_fakecli.py`, whose ERC and DRC reports hold no violation
- **WHEN** `uv run pytest tests/unit/cli/test_ready_cmd.py -k ready_project` runs `fenolite ready <fixture> --kicad-cli <fake> --json`
- **THEN** the exit code is 0, `result.ready` and `result.complete` are true, every check is `ok`, and no file of the fixture changes

#### Scenario: Altium input
- **WHEN** `fenolite ready <an Altium .PcbDoc> --json` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`, whose hint names `fenolite check`

### Requirement: Ready checks and their sources
The command SHALL run the checks of `checks.readiness.READY_CHECKS` in order: `nets.open`, `erc.kicad`, `drc.kicad`, `pins.unconnected`, `power.nets`, `parts.fields`.
- `nets.open` MUST come from `analysis.connectivity` on the board that `cli._boardview.load_board` reads; the issues of both MUST be passed on.
- `erc.kicad` and `drc.kicad` MUST be the stages that `cli.cmd_check.run_stages` gives, unchanged.
- The last three MUST be judged on the intent ("Ready intent").

#### Scenario: Open nets make a project not ready
- **WHEN** `fenolite ready tests/data/kicad/board/two_layer.kicad_pcb --no-kicad --json` runs
- **THEN** the exit code is 5, `result.ready` is false, `result.checks` names the six checks in order, and the issues hold one `ready.net-open` with `where` `LED_A`

### Requirement: Ready intent
The intent SHALL be the `.fenolite/` model of a built project, else the board as read with the net classes and rules of the project files (`DesignRulesSource.design_rules`); zones always come from the board as read, matched by net name.
- A `.fenolite/` that cannot be loaded MUST give one `check.cache-unreadable` warning, and the board's reading MUST stand in.

#### Scenario: A built project is judged on its model
- **GIVEN** a confirmed build of the starter of `fenolite init`, not routed
- **WHEN** `uv run pytest tests/unit/cli/test_ready_cmd.py -k built` runs `fenolite ready <build> --no-kicad --json`
- **THEN** `result.project.built` is true, the issues hold one `ready.net-open` per net of the starter, and no `ready.pin-unconnected`

#### Scenario: An unreadable model
- **GIVEN** that build whose `.fenolite/board.json` holds `{`
- **WHEN** `fenolite ready <build> --no-kicad --json` runs
- **THEN** the issues hold one `check.cache-unreadable` warning and the checks still run

### Requirement: Ready without kicad-cli
Without `--no-kicad`, a missing or unsupported `kicad-cli` SHALL exit 6 with the `FEN-6001` or `FEN-6002` of the pre-flight of `run_stages`, whose hint names `--no-kicad`.
- With `--no-kicad`, no subprocess MUST run, and `erc.kicad` and `drc.kicad` MUST be `skipped` with reason `no-kicad`.
- Each skipped check, for that option or for the stage's own reason, MUST give one `ready.check-skipped` warning.

#### Scenario: No kicad-cli
- **GIVEN** no `kicad-cli` on `PATH` and no `FENOLITE_KICAD_CLI`
- **WHEN** `fenolite ready <fixture> --json` runs
- **THEN** the exit code is 6, stderr carries `FEN-6001`, and its hint names `--no-kicad`

#### Scenario: Skipped by option
- **WHEN** `fenolite ready <fixture> --no-kicad --json` runs with `subprocess.run` and `subprocess.Popen` patched to raise
- **THEN** the exit code is 0, `result.complete` is false, `erc.kicad` and `drc.kicad` are `skipped` with reason `no-kicad`, and the issues hold two `ready.check-skipped` warnings

### Requirement: Ready result and exit codes
`result` SHALL hold `project` (`board`, `built`), `ready`, `complete`, `checks` (one `StageResult.to_json()` per check, in order) and `counts` (issues per severity).
- `ready` MUST be true exactly when no issue has severity `error`, and `complete` exactly when no check is skipped.
- The exit code MUST be 0 when `ready` is true and 5 when it is false.
- The envelope evidence MUST be `Evidence.combine` of the evidence of the checks that ran.

#### Scenario: DRC findings are passed on
- **GIVEN** the fixture and a fake `kicad-cli` whose DRC report holds one `clearance` violation of severity `error`
- **WHEN** `fenolite ready <fixture> --kicad-cli <fake> --json` runs
- **THEN** the exit code is 5, `drc.kicad` has status `errors`, `result.counts.error` is 1, and the issues hold one `kicad.drc.clearance`

### Requirement: Ready example and documentation
`example_args` SHALL be `(EXAMPLE_READY, "--no-kicad")`, with `EXAMPLE_READY` the board of `tests/data/kicad/ready/`, and SHALL run no subprocess.
- `docs/cli-contract.md` MUST describe the command, its checks, its result and its exit codes.
- The page `checks` of the agent guide MUST hold a tested line of the command, and the start page MUST name it in "The loop".

#### Scenario: Hermetic example
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py tests/consistency -k ready` runs
- **THEN** every test passes
