## MODIFIED Requirements

### Requirement: Typed errors on stderr
Whenever a command exits with a non-zero code, stderr MUST carry exactly one error object `{code, message, hint, retryable, where}` (JSON in JSON mode, one line `error <code>: <message> (<hint>)` in text mode). `code` MUST match `FEN-[1-7][0-9]{3}` and its first digit MUST equal the exit code.
- Without `--progress`, the error object MUST be the only thing Fenolite writes on stderr. With `--progress`, stderr MAY hold progress records before it ("Progress on stderr"), each on a line of its own, and the error object MUST be the last line.
- No exit MUST leave stderr without an error object or with a traceback: an exception that no handler maps, a failed write and a signal each end in one registered code (`FEN-1001`, `FEN-1002`, `FEN-1003`, or `FEN-1004` for incomplete rollback).
- The registry MUST hold `FEN-1002` (exit 1, `retryable` true: a write failed and nothing was changed), `FEN-1003` (exit 1, `retryable` true: the command was stopped by a signal and nothing was written) and `FEN-4002` (exit 4, `retryable` false: the plan named by `--plan` cannot be written as reviewed). `src/fenolite/cli/data/explain.toml` MUST hold one table for each, and `docs/cli-contract.md` MUST distinguish FEN-1001 (software bug) from FEN-1004 (incomplete rollback requiring manual recovery). The registry MUST also hold FEN-1004 with exit 1 and retryable false, with an explain table and agent-guide entry.

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

### Requirement: All-or-nothing writes
The dispatcher SHALL write the files of one command with `core.io.atomic_write_all` (`core-primitives`, "Atomic writes of several files"), so that a command writes every file of its plan or rolls back, with incomplete rollback reported separately, and a failed write SHALL end in an envelope and one error object.
- When the write raises `WriteError`, the dispatcher MUST print the envelope with `ok` false, the command's `result` (with `plan` and `plan_id`) and `receipt` `null`, and one `FEN-1002` object: exit 1, `retryable` true, a message that names the failing path relative to the working folder and the system's reason, and the hint "nothing was written; fix the cause and run the same command again". Neither MUST hold an absolute path or a traceback.
- After such a failure every target MUST hold the bytes it held before the command, every `.bak` that existed MUST be unchanged, and no newly written target MUST remain. Cleanup of temporary and kept files is best effort if the filesystem refuses deletion; it MUST NOT replace or conceal a failed target or backup restoration. A receipt returned by an earlier command MUST therefore still restore.
- On RecoveryError the dispatcher MUST return ok=false, receipt=null and FEN-1004 (exit 1, retryable false), with result.recovery.failed and result.recovery.preserved path lists and an instruction to inspect and recover manually before a new review. Recovery result paths MUST resolve from cwd, including ../ for locations outside cwd; when Windows volumes differ, they MUST retain the absolute path in the structured result. Error text MUST hold no absolute path or traceback, and MUST NOT claim nothing changed.
- Under `--plan`, the stage MUST stay for the retry after complete rollback, or inspection after incomplete rollback.
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

#### Scenario: Incomplete rollback is not retryable
- **GIVEN** a staged command whose write and restoration both fail
- **WHEN** the dispatcher handles RecoveryError
- **THEN** stderr ends in FEN-1004 with retryable false, stdout has ok=false and receipt=null, and recovery files remain listed for manual review

### Requirement: Interrupted commands write nothing and stop their tools
On POSIX, `main()` SHALL turn SIGTERM and SIGINT into `fenolite.cli.main.Interrupted`, raised in the main thread, and a command stopped so SHALL stop the tool processes it started, roll back its writes, and end in one error object; an incomplete rollback follows FEN-1004 instead.
- `Interrupted` MUST be a `KeyboardInterrupt`, so that no handler of `Exception` catches it and code that lets Ctrl+C pass lets it pass. After the first signal both signals MUST be ignored until the command has ended, so that a second one cuts neither the roll back nor the error object; `main()` MUST put the caller's handlers back when it returns.
- Every tool process that Fenolite starts through `subprocess.run`, the KiCad runner or a routing plugin MUST be killed when the exception passes through its call, so that no `kicad-cli`, `java` or router process outlives the `fenolite` process that started it.
- A write in progress MUST roll back ("All-or-nothing writes"). The job record of a route MUST keep the runs that finished ("Resumable route jobs").
- After a completed rollback the dispatcher MUST print the envelope with `ok` false and `receipt` `null`, and one `FEN-1003` object: exit 1, `retryable` true, the message "stopped by a signal; nothing was written".
- On Windows a Ctrl+C MUST be handled the same way; a forced stop of the process cannot be handled, and `docs/cli-contract.md` MUST say so. A stop by SIGKILL is outside this requirement on every system.

#### Scenario: A stopped route stops its router
- **GIVEN** a fake router process that sleeps and records its process id, started by `fenolite route <board> --router <fake> --confirm`
- **WHEN** `uv run pytest tests/unit/cli/test_interrupt.py -k router` sends SIGTERM to the `fenolite` process alone
- **THEN** `fenolite` exits 1 with `FEN-1003` as the last line of stderr, the fake's process no longer exists, and the board file is unchanged

#### Scenario: A signal during the write
- **GIVEN** `_echo --write a.txt --write b.txt --confirm` with a hook that raises `Interrupted` after the first replacement
- **WHEN** it runs over two existing files
- **THEN** both files hold their previous bytes, no `.bak` was added, and stderr carries `FEN-1003`

### Requirement: Mutation protocol
A command declared as mutating MUST accept `--dry-run` and `--confirm`. With `--dry-run` it MUST return the plan of intended writes in `result.plan` with exit 0 and write nothing. Without `--confirm` it MUST return the plan with exit 4 and error `FEN-4001` and write nothing. With `--confirm` it MUST write atomically (temporary file then rename), keep a `.bak` of any overwritten file unless `--no-backup` is given, and fill `receipt.written` with `{path, sha256}` for every file written.
- Whenever a plan is returned and not written (`--dry-run`, and the refusal of exit 4), `result.plan_id` MUST name it ("Staged plans"), and the hint of `FEN-4001` MUST name `--confirm --plan <id>`.
- `--confirm` without `--plan` MUST keep its meaning: one run that plans and writes. `--confirm --plan ID` MUST write the plan that a review saw, under the checks of "Staged plans". `--plan` without `--confirm`, and `--plan` with `--dry-run`, MUST exit 2 with `FEN-2001`.
- The files of one command MUST be written together or rolled back ("All-or-nothing writes"). If rollback itself fails, RecoveryError / FEN-1004 MUST report incomplete recovery and preserve remaining recovery files; no receipt or no-change claim is allowed. A command whose issues hold an error MUST write none ("Error findings plan no write").

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


#### Scenario: Recovery files outside the working directory remain locatable
- **WHEN** incomplete rollback affects output outside cwd, including names also present in other folders
- **THEN** result.recovery names each file unambiguously with paths relative to cwd, or absolute paths only when volumes differ; error text still holds no absolute path
