## MODIFIED Requirements

### Requirement: Sync command
`fenolite sync DESIGN --out DIR --to-source [--check]` SHALL be registered by `src/fenolite/cli/cmd_sync.py` with `mutates=True`, and SHALL write the source-tree copies of a built project's layout beside the design script (`layout-lens`, "Sync of the source tree").
- **Direction.** `--to-source` MUST be given (exit 2, `FEN-2001` without it), so that a later direction cannot change what a bare `sync` does.
- **Script.** `DESIGN` MUST run as `build` runs it; a `DslError` of the script, `moves`, `module_moves` or `net_moves` MUST exit 3 with `FEN-3004`.
- **Base and edits.** The command MUST read the base record of `DIR` (`edit-merge`, "Base record file") when it exists, `<script folder>/edits.toml` when it exists, and otherwise `<script folder>/placements.toml`, and pass them to `plan_sync`; a `FormatError` of any of them MUST exit 3 (`FEN-3004`). `--take` is a `build` option and MUST be a usage error here (exit 2, `FEN-2001`, hint "resolve the conflict with fenolite build --take, then sync").
- **Board.** `DIR/<design name>.kicad_pcb` MUST exist; otherwise the command MUST exit 3 with `FEN-3001` and the hint "run fenolite build first". The refusals of `layout-lens` "Existing project files" apply unchanged.
- **Schematic.** When `DIR/<design name>.kicad_sch` exists and the schematic reader (c0060) is present, the command MUST read it and every child sheet it names, and plan `schematic-placements.toml` too; otherwise `result.symbols` is `null`.
- **Writes.** One `PlannedWrite` per file of `SyncPlan.files`, at `<script folder>/<file name>`; none when nothing changed or a `sync.conflict` was given. The mutation protocol applies unchanged, `.bak` files included.
- **Check.** With `--check`, the command MUST plan nothing and add one `sync.would-change` (error) per file of `SyncPlan.files`, so it exits 5 when a committed file is stale or a property is in conflict (`sync.conflict`), and 0 otherwise. `--check` with `--confirm` MUST be a usage error (exit 2).
- **Result.** `result` MUST hold `design`, `out`, `script_output` and the keys of `SyncPlan.result`; `issues` MUST hold its issues. No subprocess MUST run, and two runs on equal inputs MUST plan equal bytes.
- `example_args` MUST be `(str(MINIMAL), "--out", EXAMPLE_SYNC_OUT, "--to-source", "--dry-run")`, where `MINIMAL` is the packaged script of `build`'s example and `EXAMPLE_SYNC_OUT` is `tests/data/lens/sync_minimal/`, a committed target-10 build of it, without the ignored cache folder `.fenolite/`, that a test keeps byte-equal to a fresh build. `mutation_example_args` MUST be `None`: the command writes beside the design script, not under the working directory, so a mutation example would write into the package folder; `tests/unit/cli/test_sync_cmd.py` MUST run the mutation protocol on a copy of a design instead.

#### Scenario: Placements written beside the script
- **GIVEN** a copy of `examples/blink_2layer/` built with `--out B --confirm`, whose board was then edited by `edit_blink`
- **WHEN** `fenolite sync <copy>/design.py --out B --to-source --confirm --json` runs
- **THEN** the exit code is 0, `receipt.written` lists `<copy>/edits.toml`, and the file places `D1` 4 mm right of its `place()` position

#### Scenario: Stale file found by check
- **GIVEN** the same copy after that sync, whose board then gets `R1` moved 1 mm by token edit
- **WHEN** `fenolite sync <copy>/design.py --out B --to-source --check --json` runs
- **THEN** the exit code is 5, `issues` hold one `sync.would-change` naming `edits.toml` and the table of `R1`, and no file changes

#### Scenario: Current file passes check
- **GIVEN** the same copy right after the sync
- **WHEN** the command runs with `--check`
- **THEN** the exit code is 0 and `issues` hold no `sync.would-change`

#### Scenario: No board yet
- **WHEN** `fenolite sync examples/blink_2layer/design.py --out <empty folder> --to-source --dry-run` runs
- **THEN** the exit code is 3, stderr carries `FEN-3001`, and its hint says to run `fenolite build` first

#### Scenario: Direction required
- **WHEN** `fenolite sync examples/blink_2layer/design.py --out B --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Example is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `sync` with its `example_args`
- **THEN** the exit code is 0, the plan names `edits.toml` beside the packaged script, and nothing is written


#### Scenario: Conflict found by check
- **GIVEN** the same copy after that sync, whose board then gets `R1`'s value `4k7` by token edit, after which `design.py` sets `R1`'s value to `470`
- **WHEN** the command runs with `--check`
- **THEN** the exit code is 5, `issues` hold one `sync.conflict` naming `R1#value`, and no file changes

#### Scenario: Take is a build option
- **WHEN** `fenolite sync <copy>/design.py --out B --to-source --take cad --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001` with a hint that names `fenolite build --take`
