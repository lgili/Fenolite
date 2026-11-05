## MODIFIED Requirements

### Requirement: Staged plans
The dispatcher SHALL give every plan that is returned and not written an id, SHALL keep the planned bytes in a state folder outside the user's tree, and SHALL write them on `--confirm --plan ID` without running the command again, after checking that nothing a review relied on has changed.
- **Id.** `cli.plans.plan_id(…)` MUST be the first 16 hex digits of the SHA-256 of the canonical JSON of: the command name; its arguments without the run flags; the working folder; the SHA-256 of every file the command names in `Result.depends`; and, for each planned write, its path, kind, size, SHA-256 and the SHA-256 of the file it would replace (`null` when there is none). No clock, seed or state folder takes part, so the same dry run on the same files gives the same id.
- **Run flags.** `plans.RUN_FLAGS` MUST be `--dry-run`, `--confirm`, `--plan`, `--json`, `--text`, `--fields`, `--limit`, `--cursor`, `--format`, `--progress`, `--seed`, `--timestamp`, `--no-backup`, `--timeout` and `--kicad-cli`: they change how a run happens, not what it plans.
- **Declared inputs.** `fenolite.cli.api.Result` MUST gain `depends: tuple[str, ...] = ()`, the inputs of the command that are not its targets, each as `fenolite.cli.api.depends_on` spells it: relative to the working folder in POSIX form when the file lies inside it, absolute otherwise; sorted and without repeats. Every registered mutating command MUST set it: `build` the design script and, when it reads one, the copper source; `place`, `route`, `fill`, `export`, `render`, `pnp` and `sync` the board and the other files of its copy set that it read; `bom` the board or the root schematic it read; `manifest` every design file and every artefact manifest it hashed; `kit` the documents it packs; `fmt` and `template` their input file; `restore` the receipt file (none for `-`), every file of `written` and every `.bak` it reads; `models` (c0116) the board and every model file it copies; `fetch` (c0078) the file of `--from`, and nothing without it; `_echo` nothing. A target is not declared: it is checked through its own digest.
- **State folder.** `fenolite.core.state.state_dir()` MUST be `FENOLITE_STATE_DIR` when it is an absolute path, `None` when it is `off`, and `~/.cache/fenolite/state` otherwise. A plan MUST be staged under `plans/<id>/` in a temporary folder renamed into place, and MUST hold nothing the command did not plan. The store MUST keep at most `PLAN_KEEP` = 16 plans of one working folder, and `PLAN_KEEP_ALL` = 128 plans and `PLAN_BYTES` = 512 MiB in all, dropping the oldest first; a plan of another working folder MUST NOT count against a folder's `PLAN_KEEP` (change c0403), MUST drop a plan older than `PLAN_DAYS` = 7 days, and MUST remove a plan once it is written. No file MUST be created in the working folder, the project or the output folder by a run that writes nothing.
- **Not staged.** A plan that cannot be staged (the store is `off`, full beyond one plan, or not writable) MUST give one `plan.not-staged` warning with the reason, from the table `fenolite.cli.codes.ISSUE_CODES`, and the run MUST go on with its id. A plan that holds a deferred write ("Deferred writes") has no bytes before `--confirm`: it MUST NOT be staged, MUST give no warning, and is planned again.
- **Replay.** `--confirm --plan ID` with a staged plan MUST NOT call the command. It MUST refuse with `FEN-4002` (exit 4), naming the first reason, when the working folder, the command or its arguments without the run flags differ from the plan's; when a file of `depends` or a target has another SHA-256 than at review (a target that did not exist must still not exist); or when a staged file does not have its planned SHA-256. Otherwise it MUST write the staged bytes through "All-or-nothing writes" and reply with the reviewed `result`, `issues`, `evidence` and `input`, the receipt, and `receipt.plan` set to ID; as after any confirmed write, `result` then holds neither `plan` nor `plan_id`, and the run flags of the call (`--fields`, `--limit`, `--format`) shape the reply. A refusal writes nothing and keeps the stage, except a damaged one, which it removes.
- **Planned again.** When ID names no staged plan, `--confirm --plan ID` MUST run the command once and write only when the id of the new plan equals ID; otherwise `FEN-4002`. So the id always binds what is written, and the store only saves the second run.
- **Receipt.** `Receipt` MUST gain `plan: str | None = None`, in `schemas/fenolite.envelope.v0.json` with a default; it takes no part in `receipt.id` ("Receipt identity"), so `fenolite restore` reads the receipt of a replayed plan as any other.
- A command that planned no write MUST get no `plan_id`.
- `docs/cli-contract.md` MUST describe the id, the checks, the state folder with its bounds and `FENOLITE_STATE_DIR`, and `AGENTS.md` MUST name `--confirm --plan` in its line about writing commands.

#### Scenario: The reviewed bytes are written without a second run
- **GIVEN** a fake `kicad-cli` that stamps each run with a counter, and `fenolite export <board> --out fab --all --manifest --dry-run --json`, whose `result.plan_id` is P
- **WHEN** `uv run pytest tests/unit/cli/test_plans.py -k replay` runs `fenolite export <board> --out fab --all --manifest --confirm --plan P`
- **THEN** the fake saw no further run, every written file has the SHA-256 of its plan row, `receipt.plan` is P, and `plans/P` is gone from the state folder

#### Scenario: A target changed after the review
- **GIVEN** `_echo --write out.txt --dry-run` over an existing `out.txt`, giving the id P, and `out.txt` then edited by hand
- **WHEN** `_echo --write out.txt --confirm --plan P` runs
- **THEN** the exit code is 4, stderr carries `FEN-4002` naming `out.txt`, the file keeps the hand edit, and the stage stays

#### Scenario: An input changed after the review
- **GIVEN** a dry-run `build` of an authored design, giving the id P, and the design script then edited
- **WHEN** `fenolite build design.py --out proj --confirm --plan P` runs
- **THEN** the exit code is 4 and stderr carries `FEN-4002` naming `design.py`

#### Scenario: Another command line
- **GIVEN** the id P of `_echo --write a.txt --dry-run`
- **WHEN** `_echo --write b.txt --confirm --plan P` runs
- **THEN** the exit code is 4 with `FEN-4002`, and neither file exists

#### Scenario: A plan that was not staged is planned again
- **GIVEN** `FENOLITE_STATE_DIR=off` and `_echo --write out.txt --dry-run`, whose reply holds the id P and one `plan.not-staged` warning
- **WHEN** `_echo --write out.txt --confirm --plan P` runs with the same setting, and then `_echo --write out.txt --confirm --plan 0000000000000000`
- **THEN** the first writes `out.txt` with `receipt.plan` P, and the second exits 4 with `FEN-4002`

#### Scenario: The id is a digest of the inputs
- **WHEN** the same dry run is made twice, with different `--seed`, `--timestamp` and `FENOLITE_STATE_DIR`
- **THEN** both replies hold the same `plan_id`

#### Scenario: Another project's plans leave a plan under review
- **GIVEN** a staged plan of one working folder and `PLAN_KEEP` + 4 later plans of another
- **WHEN** `uv run pytest tests/unit/cli/test_plans.py -k other_projects` stages them
- **THEN** the first folder's plan is kept, the other folder keeps its 16 newest, and with `PLAN_KEEP_ALL` lowered the oldest plan in all goes

#### Scenario: The store is bounded
- **GIVEN** 17 staged plans in a state folder
- **WHEN** `uv run pytest tests/unit/cli/test_plans.py -k prune` stages the seventeenth
- **THEN** the store holds 16 plans and the oldest is gone

#### Scenario: Every mutating command declares its inputs
- **WHEN** `uv run pytest tests/consistency -k depends` runs the mutation example of every registered mutating command with `--dry-run`
- **THEN** each reply that holds a plan holds a `plan_id` of 16 hex digits, and each path of the command's `depends` names an existing file, inside the working folder when the path is relative

#### Scenario: A replayed plan can be undone
- **GIVEN** `out.txt` holding `one`, and `_echo --write out.txt` planned and then written with `--confirm --plan P`, the envelope saved as `r.json`
- **WHEN** `fenolite restore r.json --confirm` runs
- **THEN** `out.txt` holds `one` again and the exit code is 0

