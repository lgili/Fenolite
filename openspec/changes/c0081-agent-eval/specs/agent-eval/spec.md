## ADDED Requirements

### Requirement: Evaluation tasks
`tools/agent_eval/tasks/` SHALL hold tasks that state a board as a requirement and say what a correct result holds, authored for Fenolite.
- A task MUST be a folder `<name>/` with `task.toml`, an optional `files/` and a `solution/` that holds `commands.txt` (one `fenolite` line each) and an optional `files/`. `tools/agent_eval/tasks.py::load(name) -> Task` MUST read it and `names()` MUST list the tasks sorted.
- `task.toml` MUST hold `title`, `prompt`, `[budget] minutes` (1 to 60) and `[expect]` with `project` (a folder relative to the work folder), `copper_layers`, `max_size` (two lengths with units), `outputs` (file patterns relative to the work folder, `**` for any depth) and `[expect.nets]`, a table from a label to a list of `REF-PIN`; it MAY hold `prepare`, a list of `fenolite` command lines. `REF-PIN` is a part's reference and a pin number of its symbol, as the nets of the design model name it, not a pad number; a pin that takes several pads of the footprint is listed once. A missing key, an unknown key, a length without a unit and a `REF-PIN` listed in two nets MUST raise `ValueError` naming the task and the key.
- A prompt MUST be at most 300 words, MUST name every reference of `expect.nets` and the folders of `expect.project` and `expect.outputs`, and MUST NOT hold the word `fenolite`, a command line or the name of a guide page.
- The tasks MUST be `led-indicator`, `regulator-zone`, `custom-footprint`, `fix-short` and `two-sided`, with the abilities of the design's Decision 2. Every part of every solution MUST come from the built-in catalog or be authored in the solution's script, and no solution MUST need an external router. The prompt of `custom-footprint` MUST give the part's pins by number and say which pads each pin takes.
- No task folder MUST hold a built project. A task that starts from one (`fix-short`) MUST hold the design script under `files/` and the `prepare` lines that build it, so that the starting project is written by the code under test.
- No task, prompt or expected result MUST come from a private project or an organisation; the folder holds a `README.md` that says so and names the licence of the tasks, `CC0-1.0`.

#### Scenario: Tasks load
- **WHEN** `uv run pytest tests/unit/test_agent_eval.py -k tasks` loads every task
- **THEN** `names()` returns the five names, each prompt is within 300 words and names every reference of its expected nets, and no prompt holds `fenolite`

#### Scenario: Malformed task is refused
- **GIVEN** a copy of a task, made in the test, whose `max_size` is `[40, 30]`, and another that lists `R1-1` in two nets
- **WHEN** `load` reads each copy
- **THEN** it raises `ValueError` naming the task and the key

#### Scenario: Starting project is built on the code under test
- **WHEN** `uv run pytest tests/unit/test_agent_eval.py -k prepare` copies the `files/` of `fix-short` into an empty folder and runs its `prepare` lines with subprocess creation patched to raise
- **THEN** each line exits 0, the folder holds a board, `fenolite check --stages model.validate,copper.clearance` on it exits 5 with `copper.short`, and `git ls-files` lists no `.kicad_pcb` under `tools/agent_eval/tasks`

### Requirement: Judge
`tools/agent_eval/judge.py::judge(workdir, task, fenolite) -> Verdict` SHALL decide a run from the files in the work folder, with Fenolite's own commands and model, and SHALL be deterministic.
- It MUST run every check and return `Verdict(status, checks, evidence_level)`, `checks` being `Check(name, passed, detail)` in this order:
  - `project`: `expect.project` exists and holds exactly one `.kicad_pcb` and a `.fenolite/` folder;
  - `check`: `<fenolite> check <project> --json` exits 0; `evidence_level` is the `evidence.level` of its envelope;
  - `nets`: the nets of the model loaded with `fenolite.model.canonical.load_dir(<project>/.fenolite)`, as sets of `REF-PIN` (reference and pin number of the model, "Evaluation tasks"), equal the sets of `expect.nets`, whatever the net names; a pin of a listed part that is in no expected net MUST be on no net; the pads of the board are not read by this check, because the `check` check has compared them with the model;
  - `board`: the bounding box of the outline is within `max_size` in both axes, in either orientation, and the number of copper layers equals `copper_layers`;
  - `outputs`: every pattern of `expect.outputs` matches at least one file.
- `status` MUST be `passed` when every check passed; `unjudged` when the `check` check could not run KiCad's stages because no `kicad-cli` was found (its exit code is 6, or its `drc.kicad` stage is skipped for that reason) and every other check passed; `failed` otherwise.
- `fenolite` names the executable to run; the judge MUST NOT run the call-log shim, MUST write nothing in the work folder, and MUST NOT read a transcript.
- A check that cannot run because an earlier one failed MUST be reported as not passed with a `detail` that says so.

#### Scenario: A correct project passes
- **GIVEN** the reference solution of `led-indicator` built and checked in a temporary folder on `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/acceptance/test_eval_solutions.py -k led_indicator` runs the judge
- **THEN** the verdict is `passed` and `evidence_level` is the level of `check`

#### Scenario: Wrong nets fail
- **GIVEN** a built project, made in the test, whose `R1-2` is on the net of `J1-2`
- **WHEN** `uv run pytest tests/unit/test_agent_eval.py -k judge_nets` applies the judge's `nets` check
- **THEN** it does not pass, and its `detail` names `R1-2`

#### Scenario: Names do not matter
- **GIVEN** a built project whose nets have the expected groups under other names
- **WHEN** the `nets` check runs
- **THEN** it passes

#### Scenario: A pin with two pads is one entry
- **GIVEN** a built project, made in the test, whose part `U1` has a pin `3` that its `pad_map` gives the pads `3` and `5`, on the net of `R1-1`
- **WHEN** the `nets` check runs with the expected group `["U1-3", "R1-1"]`
- **THEN** it passes, and with the expected group `["U1-5", "R1-1"]` it does not pass and names `U1-5`

#### Scenario: Without KiCad a run is not judged
- **GIVEN** a correct built project and no `kicad-cli`
- **WHEN** the judge runs
- **THEN** the status is `unjudged`, and the checks `project`, `nets`, `board` and `outputs` are reported as they are

#### Scenario: Board too large
- **GIVEN** a built project whose outline is 50 mm by 30 mm for a task with `max_size` 40 mm by 30 mm
- **WHEN** the judge runs
- **THEN** the check `board` does not pass and names both sizes

### Requirement: Call log
`tools/agent_eval/shim.py` SHALL record every `fenolite` call of a run without changing what the caller sees.
- Installed as an executable named `fenolite`, it MUST start the program named by `FENOLITE_EVAL_REAL` with the same arguments, standard input, standard output and standard error, and MUST exit with its exit code.
- It MUST append one line of JSON to the file named by `FENOLITE_EVAL_LOG` with exactly `n` (the call's number, from 1), `argv`, `exit`, `elapsed_ms` and `error_code`: the `code` of the JSON object on the last line of standard error when the exit code is not 0 and that line is such an object, else `null`.
- The bytes that the caller receives on standard output and standard error MUST equal those of the real program.
- The log MUST hold no environment value and no path outside the work folder: in `argv` of the log, and nowhere else, an argument that is an absolute path is written relative to the current folder when it lies in it, and as `<outside>/NAME` otherwise. The real program receives every argument as given.
- Without either variable it MUST exit 2 with a message naming the variable.

#### Scenario: Call is logged and passed through
- **GIVEN** `FENOLITE_EVAL_REAL` naming the test environment's `fenolite`
- **WHEN** `uv run pytest tests/unit/test_agent_eval.py -k shim` runs the shim with `capabilities --json --no-tools`, and then with `build nothing.py --out x --confirm --json`
- **THEN** the first call's standard output equals the real command's apart from `elapsed_ms`, and the log holds two lines: `exit` 0 with `error_code` `null`, and `exit` 3 with `error_code` `FEN-3004`

### Requirement: Runner
`tools/agent_eval/run.py --task NAME --runner NAME [--repeat N] [--keep] [--record] [--yes]` SHALL run one task with one runner in a clean place and SHALL write the result.
- **Place.** It MUST build the wheel of the checkout, install it with no extra in a new virtual environment under a new temporary folder outside the repository, and create there an empty work folder into which it copies the task's `files/`. It MUST then run the task's `prepare` lines there, in order, with the installed `fenolite` and not through the call log, and MUST stop with exit 1 before any agent starts when one of them fails. The solution folder MUST NOT be copied.
- **Skill.** It MUST install the guide as the runner's row says: `agent:<name>` runs `fenolite skill install --agent <name> --confirm` in the work folder; `agents-md` runs `fenolite skill install --agents-md --confirm`; `none` installs nothing.
- **Start.** Before it starts the agent it MUST print the task, the runner, the time budget in minutes and the runner's cost cap when the row has one. It MUST start the agent in the work folder, with `PATH` holding the shim's folder first and the environment's second, and with a prompt made of the line "The `fenolite` command line is installed. Work only in this folder." followed by the task's prompt.
- **Budget.** It MUST stop the agent's process group when `budget.minutes` have passed, and MUST then judge what the folder holds.
- **Result.** It MUST write `result.json` beside the work folder with `task`, `runner`, `runner_version`, `model`, `isolated`, `fenolite_version`, `commit`, `verdict` (status and checks), `minutes`, `timed_out`, `calls`, `calls_by_exit`, `first_failure` (the first call with a non-zero exit: its number, its command name and its `error_code`, or `null`) and `turns`, `tokens` and `cost` (each `null` when the runner does not report it). It MUST print one line with the verdict and the counts.
- **Runners.** `runners.toml` MUST hold `replay` and MAY hold rows for real agents, each with `argv`, `version_argv`, `skill`, `source` (an id of `docs/evidence/sources.md`), and optionally `budget_flag`, `report` and `isolation`. A row for a real agent without `isolation` MUST give `isolated: false` in the result; `replay` starts no agent and gives `true`. A row MAY hold `unconfigured`, a text that says what the row still lacks: such a row MAY leave `version_argv` out and MUST be refused with exit 2 and that text.
- **Prompt delivery.** `argv` MUST hold `{prompt}` (the prompt as one argument) or `{prompt_file}` (the path of `prompt.txt`, written beside the work folder in UTF-8), unless the row holds `prompt_stdin = true`: then the prompt MUST be written to the agent's standard input in UTF-8, which is then closed, and `argv` MUST hold neither. On Windows the program MUST be started as the file that `PATH` and `PATHEXT` give; when that file is a batch launcher (`.cmd`, `.bat`), which `cmd.exe` runs and which ends the command line at the first line break of an argument, a row with `{prompt}` MUST be refused with exit 2 before anything is built, with a message that names the launcher and the two other ways. Elsewhere the command line MUST stay the row's, its program name as written.
- **Replay.** The runner `replay` MUST copy `solution/files/` into the work folder and run each line of `solution/commands.txt` there through the shim, in order, stopping at the first non-zero exit.
- **Guards.** A runner other than `replay` MUST be refused with exit 2 when the environment variable `CI` is set, whatever the options. Outside CI, a runner other than `replay` MUST NOT start without `--yes`: the runner prints the task, the runner, the time budget and the cost cap, starts nothing and exits 2. `--task all` MUST be refused without `--yes`. Every refusal happens before anything is built. `--repeat N` MUST run the task N times, each in its own place.
- The temporary folder MUST be removed at the end unless `--keep` is given; with `--keep` its path is printed.
- `make agent-eval TASK=<name> RUNNER=<name>` MUST run the runner with those two values.

#### Scenario: Replay of a solution on KiCad
- **WHEN** `uv run pytest tests/kicad/acceptance/test_eval_solutions.py -rA` runs every task with the runner `replay` on `kicad-cli` 10.0.6
- **THEN** every line of every `commands.txt` exits 0, every verdict is `passed`, and each `result.json` has `calls` equal to the number of lines and `first_failure` `null`

#### Scenario: Solutions build with the expected nets
- **WHEN** `uv run pytest tests/unit/test_agent_eval.py -k solutions` builds the design script of every solution in a temporary folder with subprocess creation patched to raise
- **THEN** each build has no error issue, and the judge's `project`, `nets` and `board` checks pass on it

#### Scenario: Real agents never run in CI
- **GIVEN** `CI=true` and a row `fake-agent` added to a copy of `runners.toml`
- **WHEN** `uv run pytest tests/unit/test_agent_eval.py -k ci_guard` runs the runner with it
- **THEN** it exits 2 before building anything, and the message names `CI`

#### Scenario: A real agent needs consent
- **GIVEN** no variable `CI`, and a row `fake-agent` with a `budget_flag` added to a copy of `runners.toml`
- **WHEN** the runner runs it without `--yes`
- **THEN** it prints the task, the runner, the time budget and the cost cap, exits 2 with a message that names `--yes`, and has built and started nothing; the committed row `claude-code`, which is `unconfigured`, exits 2 with `--yes` as well

#### Scenario: The whole prompt on Windows
- **GIVEN** a row whose program `claude` resolves to `claude.cmd` on a simulated Windows `PATH`, and a prompt of several lines
- **WHEN** `uv run pytest tests/unit/test_agent_eval.py -k "batch_launcher or executable_on_windows or posix_launch or standard_input or otherwise"` runs
- **THEN** the row with `{prompt}` is refused naming the first line break, the row with `prompt_stdin` starts `claude.cmd` with the whole prompt on its standard input, the row with `{prompt_file}` names a file that holds the whole prompt, an `.exe` gets the prompt as one argument, and on POSIX the command line is unchanged

#### Scenario: Time budget
- **GIVEN** a test runner whose program sleeps, and a task copy with a budget of one minute patched to two seconds
- **WHEN** the runner runs it
- **THEN** the program is stopped, `timed_out` is true, and the verdict is `failed` with the check `project` not passed

#### Scenario: Summary of calls
- **GIVEN** a call log with five lines, the third with `exit` 3 and `error_code` `FEN-3004`
- **WHEN** `run.summarise` reads it
- **THEN** `calls` is 5, `calls_by_exit` maps 0 to 4 and 3 to 1, and `first_failure` names call 3 and `FEN-3004`

### Requirement: Evaluation record
`docs/evidence/agent-eval.md` SHALL hold the dated results of runs with real agents, and SHALL claim no more than they show.
- The page MUST have the sections `How to read this page`, `Runs`, `Findings` and `Not measured`, in this order.
- `Runs` MUST be a table with the columns `date`, `commit`, `runner`, `model`, `task`, `verdict`, `calls`, `failed calls`, `minutes` and `first failure`. `run.py --record` MUST append one row per run and change nothing else. A row from a runner without isolation MUST carry the mark `not isolated` in its `runner` cell.
- `Findings` MUST hold one row per distinct first failure of the recorded runs, with the change that addressed it or the word `open`.
- The page MUST say that a row is one sample, that verdicts come from `fenolite check` and the expected nets, that the tasks prescribe the netlist, and that no row supports a release claim.
- The page MUST hold no absolute path, no prompt and no transcript.
- `tests/unit/test_agent_eval.py` MUST check the sections, the table's columns, and that every row has ten cells.

#### Scenario: Page is well formed
- **WHEN** `uv run pytest tests/unit/test_agent_eval.py -k record` reads the page
- **THEN** the four sections exist in order, the table has the ten columns, and no cell holds a path that starts with `/` or a drive letter

#### Scenario: Recording a run
- **GIVEN** a `result.json` of a replay, and a copy of the page
- **WHEN** the record function appends it to the copy
- **THEN** the copy has one more row with ten cells, and every other line is unchanged
