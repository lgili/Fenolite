## ADDED Requirements

### Requirement: Staged plans
The dispatcher SHALL give every plan that is returned and not written an id, SHALL keep the planned bytes in a state folder outside the user's tree, and SHALL write them on `--confirm --plan ID` without running the command again, after checking that nothing a review relied on has changed.
- **Id.** `cli.plans.plan_id(…)` MUST be the first 16 hex digits of the SHA-256 of the canonical JSON of: the command name; its arguments without the run flags; the working folder; the SHA-256 of every file the command names in `Result.depends`; and, for each planned write, its path, kind, size, SHA-256 and the SHA-256 of the file it would replace (`null` when there is none). No clock, seed or state folder takes part, so the same dry run on the same files gives the same id.
- **Run flags.** `plans.RUN_FLAGS` MUST be `--dry-run`, `--confirm`, `--plan`, `--json`, `--text`, `--fields`, `--limit`, `--cursor`, `--format`, `--progress`, `--seed`, `--timestamp`, `--no-backup`, `--timeout` and `--kicad-cli`: they change how a run happens, not what it plans.
- **Declared inputs.** `fenolite.cli.api.Result` MUST gain `depends: tuple[str, ...] = ()`, the inputs of the command that are not its targets, each as `fenolite.cli.api.depends_on` spells it: relative to the working folder in POSIX form when the file lies inside it, absolute otherwise; sorted and without repeats. Every registered mutating command MUST set it: `build` the design script and, when it reads one, the copper source; `place`, `route`, `fill`, `export`, `render`, `pnp` and `sync` the board and the other files of its copy set that it read; `bom` the board or the root schematic it read; `manifest` every design file and every artefact manifest it hashed; `kit` the documents it packs; `fmt` and `template` their input file; `restore` the receipt file (none for `-`), every file of `written` and every `.bak` it reads; `models` (c0116) the board and every model file it copies; `fetch` (c0078) the file of `--from`, and nothing without it; `_echo` nothing. A target is not declared: it is checked through its own digest.
- **State folder.** `fenolite.core.state.state_dir()` MUST be `FENOLITE_STATE_DIR` when it is an absolute path, `None` when it is `off`, and `~/.cache/fenolite/state` otherwise. A plan MUST be staged under `plans/<id>/` in a temporary folder renamed into place, and MUST hold nothing the command did not plan. The store MUST keep at most `PLAN_KEEP` = 16 plans and `PLAN_BYTES` = 512 MiB, dropping the oldest first, MUST drop a plan older than `PLAN_DAYS` = 7 days, and MUST remove a plan once it is written. No file MUST be created in the working folder, the project or the output folder by a run that writes nothing.
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

### Requirement: All-or-nothing writes
The dispatcher SHALL write the files of one command with `core.io.atomic_write_all` (`core-primitives`, "Atomic writes of several files"), so that a command writes every file of its plan or none, and a failed write SHALL end in an envelope and one error object.
- When the write raises `WriteError`, the dispatcher MUST print the envelope with `ok` false, the command's `result` (with `plan` and `plan_id`) and `receipt` `null`, and one `FEN-1002` object: exit 1, `retryable` true, a message that names the failing path relative to the working folder and the system's reason, and the hint "nothing was written; fix the cause and run the same command again". Neither MUST hold an absolute path or a traceback.
- After such a failure every target MUST hold the bytes it held before the command, every `.bak` that existed MUST be unchanged, and no target, temporary file or folder that the command created MUST remain. A receipt returned by an earlier command MUST therefore still restore.
- Under `--plan`, the stage MUST stay for the retry.
- `main()` MUST map every exception that is not a `CliError` to `FEN-1001` through "Library errors map to registered codes", printing no traceback.

#### Scenario: A build that fails in the middle changes nothing
- **GIVEN** an authored design and an output folder `proj` that already holds a built project, whose `proj/lib` is made read-only
- **WHEN** `uv run pytest tests/unit/cli/test_write_failures.py -k build` runs `fenolite build design.py --out proj --confirm --json` after a change of one value in the design
- **THEN** the exit code is 1, stderr carries `FEN-1002` naming a path under `proj/lib`, and every file of `proj` has the SHA-256 it had before, `.fenolite/` included

#### Scenario: A first build into a blocked folder leaves nothing
- **GIVEN** an empty folder in which `proj/lib` cannot be created because `proj` is read-only
- **WHEN** the same build runs
- **THEN** the exit code is 1 with `FEN-1002`, and `proj` holds no file and no folder that the command made

#### Scenario: The plan survives the failure
- **GIVEN** a plan P whose replay fails with `FEN-1002`
- **WHEN** the cause is removed and `--confirm --plan P` runs again
- **THEN** the files are written with the reviewed bytes

### Requirement: Error findings plan no write
The dispatcher SHALL plan, stage and write nothing for a command whose issues hold one of severity `error`, unless the command sets `Result.write_on_error`.
- `fenolite.cli.api.Result` MUST gain `write_on_error: bool = False`. Only three commands MAY set it: `place`, and only under `--force`, where writing beside an error is what the flag asks for; `manifest`, whose one write is the report of the findings ("Manifest command": the manifest is planned whether or not the check found errors); and `kit record`, whose record holds the failed steps of the run.
- With an error issue and without `write_on_error`, `result.plan` and `result.plan_id` MUST be absent, `receipt` MUST be `null`, no file MUST change, and the exit code MUST be 5 with `FEN-5001`, with `--dry-run`, with `--confirm` and with neither.
- The rule holds in the dispatcher, so a command need not empty its own writes; the commands that do so today MUST keep their replies.
- `docs/cli-contract.md` MUST state the rule under the mutation protocol, with its exceptions.

#### Scenario: No write beside an error
- **WHEN** `uv run pytest tests/unit/cli/test_write_failures.py -k error_finding` runs `_echo --issue error --write x.txt --confirm --json` in an empty folder
- **THEN** the exit code is 5, the folder is still empty, `receipt` is `null`, and `result` holds neither `plan` nor `plan_id`

#### Scenario: Forced placement still writes
- **GIVEN** an authored project in which `place --move` puts a part outside the outline
- **WHEN** `fenolite place <dir> --move R1=200mm,200mm --force --confirm` runs
- **THEN** the board is written, the exit code is 5, and the receipt lists the board

#### Scenario: The rule holds for every mutating command
- **WHEN** `uv run pytest tests/consistency -k error_no_write` reads the registry
- **THEN** it fails for a mutating command other than `place`, `manifest` and `kit` whose module sets `write_on_error`

### Requirement: Interrupted commands write nothing and stop their tools
On POSIX, `main()` SHALL turn SIGTERM and SIGINT into `fenolite.cli.main.Interrupted`, raised in the main thread, and a command stopped so SHALL stop the tool processes it started, write nothing, and end in one error object.
- `Interrupted` MUST be a `KeyboardInterrupt`, so that no handler of `Exception` catches it and code that lets Ctrl+C pass lets it pass. After the first signal both signals MUST be ignored until the command has ended, so that a second one cuts neither the roll back nor the error object; `main()` MUST put the caller's handlers back when it returns.
- Every tool process that Fenolite starts through `subprocess.run`, the KiCad runner or a routing plugin MUST be killed when the exception passes through its call, so that no `kicad-cli`, `java` or router process outlives the `fenolite` process that started it.
- A write in progress MUST roll back ("All-or-nothing writes"). The job record of a route MUST keep the runs that finished ("Resumable route jobs").
- The dispatcher MUST print the envelope with `ok` false and `receipt` `null`, and one `FEN-1003` object: exit 1, `retryable` true, the message "stopped by a signal; nothing was written".
- On Windows a Ctrl+C MUST be handled the same way; a forced stop of the process cannot be handled, and `docs/cli-contract.md` MUST say so. A stop by SIGKILL is outside this requirement on every system.

#### Scenario: A stopped route stops its router
- **GIVEN** a fake router process that sleeps and records its process id, started by `fenolite route <board> --router <fake> --confirm`
- **WHEN** `uv run pytest tests/unit/cli/test_interrupt.py -k router` sends SIGTERM to the `fenolite` process alone
- **THEN** `fenolite` exits 1 with `FEN-1003` as the last line of stderr, the fake's process no longer exists, and the board file is unchanged

#### Scenario: A signal during the write
- **GIVEN** `_echo --write a.txt --write b.txt --confirm` with a hook that raises `Interrupted` after the first replacement
- **WHEN** it runs over two existing files
- **THEN** both files hold their previous bytes, no `.bak` was added, and stderr carries `FEN-1003`

### Requirement: Progress on stderr
The global flag `--progress` SHALL make a command write progress records on stderr while it runs: one when a unit of work starts, one when it ends, and one at least every 10 seconds, so that a caller can tell a long step from a dead one.
- In JSON mode a record MUST be one line `{"progress": {"command", "event", "step", "index", "total", "detail", "elapsed_ms"}}` with `event` `step` (a unit starts), `done` (it ends) or `alive`; `index` and `total` are integers or `null`. In text mode it MUST be one line that starts with `progress: <command>: `. A record MUST hold no absolute path, home directory or temporary path.
- **Units.** `check`: one per stage that runs, named by the stage. `route`: one per router process ("Resumable route jobs"). `fill`: the refill. `export`: one per kind. `render`: one per view. Every other command gives `alive` records only.
- **Heartbeat.** While the command runs, at least one record MUST be written every `interval` seconds (10 by default), from a daemon thread that stops before the envelope is printed; writes to stderr MUST be serialised.
- `fenolite.core.progress` MUST define the protocol `Progress` with `step(name, *, index=None, total=None)` and `done(name, *, detail="")`, and `NULL_PROGRESS`, which does nothing. `fenolite.cli.api.Context` MUST gain `progress`. `run_checks` MUST take `progress=NULL_PROGRESS`. `checks`, `routing` and the backends MUST reach the reporter only through this protocol.
- Without `--progress`, a command MUST write nothing on stderr but its error object, as today, and stdout MUST be the same with and without the flag apart from `elapsed_ms`.
- `capabilities` MUST list `--progress` among the global flags (`result.global_flags`, the long flags every command accepts; `result.mutation_flags` holds `--dry-run`, `--confirm` and `--plan`), and `docs/cli-contract.md` MUST describe the records and say that they are not covered by the determinism rule.

#### Scenario: Units of a check
- **WHEN** `uv run pytest tests/unit/cli/test_progress.py -k check` runs `fenolite check <board> --stages model.validate,roundtrip --progress --json`
- **THEN** stderr holds, in order, a `step` and a `done` record for `model.validate` and for `roundtrip`, each a JSON line, and stdout equals the stdout of the same call without `--progress` apart from `elapsed_ms`

#### Scenario: A long step stays alive
- **GIVEN** `_echo --steps 1 --sleep 1.0 --progress` with the reporter's interval set to 0.1 s
- **WHEN** it runs
- **THEN** stderr holds at least three `alive` records between the `step` and the `done` record

#### Scenario: Silent by default
- **WHEN** `_echo --steps 3` runs without `--progress`
- **THEN** stderr is empty

#### Scenario: Records hold no path of the machine
- **WHEN** `fenolite export <board> --out fab --all --dry-run --progress --json` runs with a fake `kicad-cli`
- **THEN** there is one `step` and one `done` record per kind, and no record holds the temporary folder of a run or the home directory

### Requirement: Resumable route jobs
`fenolite route` SHALL keep the copper of each router process that finished in a job record in the state folder, and the same call made again SHALL reuse it instead of routing those nets again.
- **Key.** `cli.jobs.route_job_key(…)` MUST be the first 16 hex digits of the SHA-256 of the canonical JSON of the Fenolite version, the router's name and version, the SHA-256 of the board, of its project file and of its rules file (the rules file joins the key only when there is one: the router is given its rules), and the route arguments without the run flags and without `--out`. The record lives under `jobs/<key>/` of `state_dir()`, one file per finished run, each written with `atomic_write`; with the state folder `off` no record is kept and the command routes as today.
- **Recording.** `route` MUST pass `on_run` in the job (`routing`, "Router runs reported for progress and resumption") and MUST add each `FinishedRun` to the record before the next process starts.
- **Reuse.** When a record exists for the key, the command MUST read the board, apply `--rip`, merge the recorded copper, and only then select nets, so that the recorded nets are not routed again. It MUST then give one `route.resumed` info and `result.resumed` (`runs`, `nets`), and `result.tracks` and `result.vias` MUST count the reused copper with the new; without a record `result.resumed` MUST be `null`. A record that cannot be read MUST be removed and MUST NOT fail the command.
- **End.** `fenolite.cli.api.Result` MUST gain `written: Callable[[], None] | None = None`, which the dispatcher calls once after the writes of the result were all written; `route` removes its record through it. The record MUST be removed after a confirmed write of the routed board, and after a dry run that attempted every selected net. It MUST stay after a stop by a signal, after a failed write (`FEN-1002`) and after a run that wrote nothing and that a time limit cut, a dry run included (`result.budget.exhausted`): the same call made again then goes on with the nets that were not attempted. It MUST also stay after a dry run that reports an error finding, which plans no write. A confirmed run that a time limit cut writes the copper of its finished runs (`routing`, "Routing time budget"), and its record is removed as after any confirmed write. At most `JOB_KEEP` = 8 records are kept and none older than 7 days.
- `fenolite.routing.codes.ISSUE_CODES` MUST gain `route.resumed` (info), with its table in `explain.toml`. The envelope evidence stays `UNVERIFIED`.
- `docs/routing.md` MUST say what is kept, when it is reused and when it is removed, and that copper made in two calls need not equal the copper of one.

#### Scenario: A stopped route goes on
- **GIVEN** the fake per-net router of `tests/unit/cli/test_route_jobs.py`, set to end the process after its second net of five
- **WHEN** `fenolite route <board> --router <fake> --confirm` runs, is stopped, and runs again with the same arguments
- **THEN** the second call starts three router processes, its reply holds one `route.resumed` info and `result.resumed.nets` of 2, the written board holds the copper of all five nets, and the record is gone

#### Scenario: Another board, another record
- **GIVEN** the record of the first call
- **WHEN** one byte of the board changes and the same command runs
- **THEN** `result.resumed` is `null` and five router processes start

#### Scenario: A failed run is routed again
- **GIVEN** a fake router whose third process ends without copper
- **WHEN** the command runs twice
- **THEN** the record of the first call holds two runs, and the second call routes the third net again

## MODIFIED Requirements

### Requirement: Mutation protocol
A command declared as mutating MUST accept `--dry-run` and `--confirm`. With `--dry-run` it MUST return the plan of intended writes in `result.plan` with exit 0 and write nothing. Without `--confirm` it MUST return the plan with exit 4 and error `FEN-4001` and write nothing. With `--confirm` it MUST write atomically (temporary file then rename), keep a `.bak` of any overwritten file unless `--no-backup` is given, and fill `receipt.written` with `{path, sha256}` for every file written.
- Whenever a plan is returned and not written (`--dry-run`, and the refusal of exit 4), `result.plan_id` MUST name it ("Staged plans"), and the hint of `FEN-4001` MUST name `--confirm --plan <id>`.
- `--confirm` without `--plan` MUST keep its meaning: one run that plans and writes. `--confirm --plan ID` MUST write the plan that a review saw, under the checks of "Staged plans". `--plan` without `--confirm`, and `--plan` with `--dry-run`, MUST exit 2 with `FEN-2001`.
- The files of one command MUST be written all or none ("All-or-nothing writes"), and a command whose issues hold an error MUST write none ("Error findings plan no write").

#### Scenario: Dry run writes nothing
- **GIVEN** `_echo --write out.txt --dry-run`
- **WHEN** it runs in an empty directory
- **THEN** exit code is 0, `result.plan` lists `out.txt`, and the directory is still empty

#### Scenario: Missing confirmation
- **GIVEN** `_echo --write out.txt`
- **WHEN** it runs
- **THEN** exit code is 4, stderr carries `FEN-4001`, and nothing is written

#### Scenario: Confirmed write with receipt and backup
- **GIVEN** `out.txt` already exists
- **WHEN** `_echo --write out.txt --confirm` runs
- **THEN** `out.txt` has the new content, `out.txt.bak` holds the previous content, and `receipt.written[0].sha256` equals the SHA-256 of the new file

#### Scenario: Conflicting flags
- **WHEN** `_echo --write out.txt --dry-run --confirm` runs
- **THEN** the exit code is 2

#### Scenario: The refusal names the plan
- **WHEN** `uv run pytest tests/unit/cli/test_plans.py -k refusal` runs `_echo --write out.txt --json` in an empty folder
- **THEN** the exit code is 4, `result.plan_id` is 16 hex digits, and the hint of `FEN-4001` on stderr holds `--confirm --plan` followed by that id

#### Scenario: A plan needs a confirmation
- **WHEN** `_echo --write out.txt --plan 0123456789abcdef` runs without `--confirm`, and again with `--dry-run`
- **THEN** both exit 2 with `FEN-2001`, and nothing is written

### Requirement: Typed errors on stderr
Whenever a command exits with a non-zero code, stderr MUST carry exactly one error object `{code, message, hint, retryable, where}` (JSON in JSON mode, one line `error <code>: <message> (<hint>)` in text mode). `code` MUST match `FEN-[1-7][0-9]{3}` and its first digit MUST equal the exit code.
- Without `--progress`, the error object MUST be the only thing Fenolite writes on stderr. With `--progress`, stderr MAY hold progress records before it ("Progress on stderr"), each on a line of its own, and the error object MUST be the last line.
- No exit MUST leave stderr without an error object or with a traceback: an exception that no handler maps, a failed write and a signal each end in one registered code (`FEN-1001`, `FEN-1002`, `FEN-1003`).
- The registry MUST hold `FEN-1002` (exit 1, `retryable` true: a write failed and nothing was changed), `FEN-1003` (exit 1, `retryable` true: the command was stopped by a signal and nothing was written) and `FEN-4002` (exit 4, `retryable` false: the plan named by `--plan` cannot be written as reviewed). `src/fenolite/cli/data/explain.toml` MUST hold one table for each, and `docs/cli-contract.md` MUST say that exit 1 is a bug only when `retryable` is false.

#### Scenario: Internal exception
- **GIVEN** the hidden `_echo` command is invoked with `--raise`
- **WHEN** it runs
- **THEN** the exit code is 1 and stderr carries `FEN-1xxx` with a non-empty `message`

#### Scenario: Usage error
- **WHEN** `fenolite capabilities --no-such-flag` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2xxx`

#### Scenario: A blocked write ends in an error object
- **GIVEN** a folder in which `blocker` is a file
- **WHEN** `uv run pytest tests/unit/cli/test_write_failures.py -k blocked` runs `_echo --write blocker/x.txt --confirm --json`
- **THEN** the exit code is 1, stderr is one JSON object with `code` `FEN-1002` and `retryable` true, and it holds no traceback and no absolute path

#### Scenario: The error is the last line under progress
- **GIVEN** `_echo --steps 3 --raise --progress --json`
- **WHEN** it runs
- **THEN** every line of stderr but the last parses as `{"progress": …}`, and the last is the error object `FEN-1001`

#### Scenario: The three codes are registered and explained
- **WHEN** `uv run pytest tests/unit/cli/test_exitcodes.py tests/unit/cli/test_explain_cmd.py` runs
- **THEN** `FEN-1002`, `FEN-1003` and `FEN-4002` are in the registry with exit codes 1, 1 and 4, and each has a table in `explain.toml`
