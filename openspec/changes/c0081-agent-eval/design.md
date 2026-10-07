## Context

- **Milestone.** v0.4, the agent track (c0077 to c0081). Written against `origin/dev` at `9aba2dff`.
- **What exists** (at `9aba2dff`).
  - `docs/release/v0.1.md`, "Manual checks": one session of an agent that was given the guide and the finished example, recorded as `UNVERIFIED` with its turns and exit codes. Nothing reruns it.
  - `tests/routing/test_acceptance_loop.py` runs the loop through the command line with fixed commands. It proves that the commands work in that order, not that an agent finds the order.
  - After c0079: `fenolite init`, `fenolite skill install`, `fenolite guide`, and a starter that passes `check` with the built-in catalog and router. After c0077: a catalog-only board passes `check`.
  - `fenolite check` already compares the nets of the built model with the board's and, with `kicad-cli`, with KiCad's own export, as groups and never by net name (`verification-loop`, "Assignment compare stage"). Since 0.2.1 the schematic side of that comparison is by pin number and the board side by pad number; c0123 (v0.3) lets one pin hold several pads.
  - `fenolite explain CODE` (c0066) gives every error code and issue code a meaning and a fix.
- **What a trial showed.** On 2026-10-05, on `dev` at `1882644`, the loop was run by hand from outside the repository in about ten commands. It met two defects that every test had passed (c0077, c0078), both still open at `9aba2dff`, and one weak answer (`check` findings with empty hints). The weak answer predates `explain`; whether an agent finds `explain` is one of the things the first batch shows.
- **Constraints.**
  - The maintainer's credit is limited: a run with a real agent costs money and is started by a person.
  - Tasks are authored for Fenolite. No task, prompt or expected result comes from a private project or an organisation.
  - The harness runs on the maintainer's machine (macOS or Linux). CI runs only the parts that need no agent.
  - Nothing of the harness ships in the wheel.

## Goals / Non-Goals

**Goals:**
- One command starts a fresh agent on one task and ends with a verdict that Fenolite itself computed.
- The record says where the agent lost time: which call failed first, with which code.
- Tasks cannot rot: each has a solution that the suites replay.
- The cost of a run is bounded and visible before it starts.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A benchmark for publication. The tasks measure whether Fenolite can be used, on five small boards.

## Decisions

1. **A task is a folder** `tools/agent_eval/tasks/<name>/` with `task.toml`, an optional `files/` (copied into the work folder before the agent starts) and `solution/` (Decision 6).
   ```toml
   title = "LED indicator"
   prompt = """…the requirement, in plain words…"""
   [budget]
   minutes = 20
   [expect]
   project = "board/build"
   copper_layers = 2
   max_size = ["40mm", "30mm"]
   outputs = ["board/fab/*.gbr", "board/fab/*.drl"]
   [expect.nets]
   VIN = ["J1-1", "R1-1"]
   LED_A = ["R1-2", "D1-1"]
   GND = ["D1-2", "J1-2"]
   ```
   - The prompt states the circuit by reference and pin, the board's limits, and the folders to leave. It names no command and no page: finding them is what is measured.
   - The runner puts one fixed line before the prompt: "The `fenolite` command line is installed. Work only in this folder."
   - **`REF-PIN`.** `PIN` is a pin number of the part's symbol, as the nets of the model name it, not a pad number of the footprint. A pin that the part's `pad_map` gives several pads is written once. For a catalog part the two numbers are equal; the task `custom-footprint` is the one where they can differ, and its prompt gives the pins by number and says which pads each pin takes.
   - An optional key `prepare` holds `fenolite` command lines that the runner runs in the work folder before the agent starts, with the real command and outside the call log.
   - Rejected: a functional requirement without references ("a 3.3 V supply"). Judging it needs a way to tell which part plays which role; the first version measures use of the tool, not circuit design.

2. **Five tasks**, each for a different ability, all with catalog parts and no external router:

   | task | the agent must |
   |---|---|
   | `led-indicator` | write a script from nothing, place, route with the built-in router, check, export |
   | `regulator-zone` | use a net class for the supply, pour a ground zone on one layer, fill it, and keep the board within a size |
   | `custom-footprint` | author a footprint and a symbol from dimensions given in the prompt, for a part the catalog lacks |
   | `fix-short` | start from a given project whose routed copper shorts two nets, find it with `check`, and repair it without changing a net. `files/` holds the design script only, a variant of the starter whose placement makes two straight tracks cross; `prepare` builds it and routes it with the `direct` router, so the project the agent meets is always written by the code under test |
   | `two-sided` | place parts on both sides and join them with scripted copper through a via, under minimums given in the prompt |

   - Each prompt is under 300 words. Numbers in a prompt are the task's own choices and are marked as such: round values chosen for the task, none from a product or a board.
   - Rejected for `fix-short`: committing the built project. It would hold the bytes of the day it was built, and would have to be rebuilt by hand whenever the board writer or the copper check changes (c0097 changes what a `copper.short` finding carries).

3. **The judge** (`judge.py::judge(workdir, task, fenolite) -> Verdict`) runs these checks in order and stops at none, so the record shows every failure:

   | check | passes when |
   |---|---|
   | `project` | `expect.project` holds one `.kicad_pcb` and a `.fenolite/` model |
   | `check` | `fenolite check <project> --json` exits 0; its `evidence.level` is recorded |
   | `nets` | the nets of the built model, as groups of `REF-PIN` (reference and pin number, Decision 1), equal the groups of `expect.nets`; names are ignored, and pins on no net must be on none |
   | `board` | the outline's box fits `max_size`, and the copper layer count is `copper_layers` |
   | `outputs` | every pattern of `expect.outputs` matches at least one file |

   - The verdict is `passed` when all pass; `unjudged` when `check` could not run KiCad's stages because `kicad-cli` is absent; `failed` otherwise.
   - `nets` reads the model that `check` has just compared with the board, through `fenolite.model.canonical.load_dir`. A model the agent edited by hand cannot pass both. The pads behind each pin are `check`'s business: its net comparison is what proves that the board's pads carry the nets of the model's pins.
   - The judge runs the real `fenolite` of the run's environment, not the shim, so its own calls are not in the log.

4. **The call log.** `shim.py` is installed as an executable named `fenolite` in a folder that is first on the agent's `PATH`.
   - It starts the real command with the same arguments, standard input, output and error, and returns its exit code.
   - It appends one JSON line to the log: the call's number, the arguments, the exit code, the elapsed milliseconds and, for a non-zero exit, the `code` of the error object read from the last line of standard error.
   - The agent sees the same bytes it would see without the shim.
   - The error object is the last line of standard error today. c0120 (v0.4) proposes `--progress` records on standard error; the shim's rule stays valid as long as the error object stays last, and c0120 keeps it so.
   - Rejected: reading the agent's transcript (each agent has its own format); a logging mode inside Fenolite (a hidden write on every command, the reason c0066 keeps no journal of receipts).

5. **The runner** (`run.py --task NAME --runner NAME [--repeat N] [--keep] [--record]`):
   - builds the wheel of the checkout and installs it, with no extra, in a new virtual environment under a temporary folder outside the repository;
   - makes an empty work folder there, copies the task's `files/`, runs the task's `prepare` lines with the real `fenolite`, and installs the skill the way the runner's row says: `fenolite skill install --agent <name> --confirm`, or `--agents-md`, or nothing;
   - prints the task, the runner, the time budget and, when the row has one, the cost cap, and then starts the agent in the work folder with `PATH` holding the shim's folder, then the environment's, then the system's;
   - stops the agent's process group when `budget.minutes` have passed;
   - runs the judge, and writes `result.json` beside the work folder: task, runner and its version, the model the runner reports, Fenolite's version and commit, the verdict with its checks, the minutes, the number of calls, the calls per exit code, the first call that failed, and the turns, tokens and cost when the runner reports them;
   - with `--record`, appends one row to `docs/evidence/agent-eval.md`;
   - removes the temporary folder unless `--keep` is given.
   - A runner other than `replay` is refused when the variable `CI` is set, and `--task all` needs `--yes`.

6. **Reference solutions and the `replay` runner.** `solution/` holds the files a correct run would write (`files/`) and the commands it would run (`commands.txt`, one `fenolite` line each). The runner `replay` copies the files and runs the lines through the shim, with no agent.
   - `tests/unit/test_agent_eval.py` needs no tool: it builds the design script of every solution in process and applies the judge's `project`, `nets` and `board` checks to the built project. A solution whose nets differ from `expect.nets` fails there.
   - `tests/kicad/acceptance/test_eval_solutions.py` replays every task on `kicad-cli` 10.0.6, through the shim: every line of `commands.txt` exits 0 and the verdict is `passed`.
   - So a change that breaks a task's solution fails the suites, and the tasks double as acceptance tests of the outsider's path.

7. **Runner rows.** `runners.toml` holds `replay` and one row per real agent: `argv` (with `{prompt}` and `{workdir}`), `version_argv`, `skill` (`agent:<name>`, `agents-md` or `none`), `budget_flag` (the agent's own cost or turn cap, when it has one), `report` (where its output gives turns, tokens and cost), `isolation` (the flags that keep the agent from loading the user's own settings, memory and skills) and `source`, the id of the public page that documents its non-interactive mode.
   - The first real row is `claude-code`, written from that agent's public documentation and checked against `--help` of the version recorded in the first run.
   - A row without `isolation` is allowed and is marked in every record it produces: an agent that remembers this repository from the user's own sessions would not be a fresh agent.

8. **The record.** `docs/evidence/agent-eval.md` has four parts: how to read it; `Runs`, one row per run (date, commit, runner and version, model, task, verdict, calls, failed calls, minutes, first failure); `Findings`, one row per distinct first failure with the change that addressed it or `open`; and `Not measured`.
   - A row holds no path, no prompt and no transcript. Transcripts stay in the kept temporary folder.
   - The page says that a run is one sample: an agent's behaviour varies between runs, and `--repeat` exists for that.
   - A batch is the five tasks with one runner. The first batch is run after c0079 and before c0080; the second after c0080.

9. **Cost.** A run is one agent session, bounded by the task's minutes (20 by default, 30 for `custom-footprint`), so a batch is at most 110 minutes of agent time. What a session costs is not known before the first one; the first run records it, and the maintainer decides on the rest of the batch with that number.

## Files and public API

| file | public API |
|---|---|
| `tools/agent_eval/tasks/<name>/task.toml`, `files/`, `solution/` (new, five tasks) | the tasks |
| `tools/agent_eval/tasks.py` (new) | `Task`, `Expect`; `load(name)`, `names()` |
| `tools/agent_eval/judge.py` (new) | `Check(name, passed, detail)`; `Verdict(status, checks, evidence_level)`; `judge(workdir, task, fenolite) -> Verdict` |
| `tools/agent_eval/shim.py` (new) | `main(argv)`; the log line format |
| `tools/agent_eval/run.py`, `runners.toml` (new) | `main(argv)`; `Runner`; `replay(task, workdir, fenolite)`; `summarise(calls)` |
| `docs/evidence/agent-eval.md` (new) | the record |
| `tests/unit/test_agent_eval.py` (new) | hermetic: tasks load, judge, shim, solutions build with the expected nets, refusal in CI, the record's form |
| `tests/kicad/acceptance/test_eval_solutions.py` (new) | oracle: every solution is `passed` |
| `Makefile`, `tools/README.md`, `CONTRIBUTING.md` (extended) | `make agent-eval TASK=… RUNNER=…`; how to run and record |

## Names introduced by this change

Source id S-0611. Tool `tools/agent_eval` (`run.py` with `--task`, `--runner`, `--repeat`, `--keep`, `--record`, `--yes`; `judge.py`; `shim.py`; `tasks.py`; `runners.toml`). Task names `led-indicator`, `regulator-zone`, `custom-footprint`, `fix-short`, `two-sided`; keys of `task.toml`: `title`, `prompt`, `prepare`, `budget.minutes`, `expect.project`, `expect.copper_layers`, `expect.max_size`, `expect.outputs`, `expect.nets`. Environment variables `FENOLITE_EVAL_REAL` and `FENOLITE_EVAL_LOG`. Keys of `result.json`: `task`, `runner`, `runner_version`, `model`, `isolated`, `fenolite_version`, `commit`, `verdict`, `minutes`, `timed_out`, `calls`, `calls_by_exit`, `first_failure`, `turns`, `tokens`, `cost`. Make target `agent-eval`. Page `docs/evidence/agent-eval.md`. No hypothesis id, no issue code, no error code, no flag or result key of `fenolite`, no model field. None of these names is in the tree at `9aba2dff`.

## Sources registered by this change

One, S-0611 (of the block S-0610 to S-0619 that the coordinator gave the agent track; c0079 takes S-0610): the public documentation page of the non-interactive mode of the agent in the first real row of `runners.toml`, read for its command-line flags.

## Hypotheses registered by this change

None. A run is a dated measurement in `docs/evidence/agent-eval.md`, not a fact about a format or a tool.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Tasks load and are well formed | mechanical | `test_agent_eval.py -k tasks` |
| Judge verdicts | mechanical for `project`, `nets`, `board`, `outputs`; `check` carries its own level | `test_agent_eval.py -k judge` |
| Call log | mechanical | `test_agent_eval.py -k shim` |
| Reference solutions | KICAD-VERIFIED through `fenolite check` | `test_eval_solutions.py` on 10.0.6 |
| A run with a real agent | a recorded author run; no release claim | `docs/evidence/agent-eval.md` |

## Budget (6.75 days)

| work | days |
|---|---|
| entry check, register | 0.25 |
| task format, loader, five tasks with their solutions | 2.0 |
| judge | 1.0 |
| shim | 0.5 |
| runner, environment, `prepare`, `replay` | 1.5 |
| the first real row and one run with the maintainer | 0.5 |
| the record and its test | 0.5 |
| closing | 0.5 |
| **total** | **6.75** |

Cut order: (1) `two-sided`; (2) `--repeat`; (3) `custom-footprint` (it waits for the page `footprints` of c0080 to be judged fairly). Not optional: `led-indicator` and `fix-short`, the judge, the call log, `replay` with both tests, the refusal in CI, the record.

## Risks / Trade-offs

- [A run costs money] → started by a person, one task by default, a time budget per task, the agent's own cap passed when it has one, and the first run decides the batch.
- [One run is one sample] → the record says so; `--repeat` and the count of runs are in every claim made from it.
- [The agent is not really fresh] → the row's `isolation` flags, a work folder outside the repository, and a mark on records without isolation.
- [The agent reads the reference solution] → solutions are not copied into the temporary folder, which is outside the checkout; the prompt gives no path to it.
- [Tasks become the target] → five small tasks are a smoke test of usability; the record makes no wider claim, and a task is replaced when every run passes it.
- [The shim changes behaviour] → it passes the three streams and the exit code through untouched; a test compares a command's bytes with and without it.
- [The change waits for a person] → tasks 4.2 and 4.3 are the maintainer's runs. Everything else closes without them, and task 4.2 says what to write when he decides not to run.
- [The judge trusts `check`] → that is the point: `check` is Fenolite's judge, and the oracle test proves each solution on KiCad.

## Migration Plan

- Additive: a folder under `tools/`, one evidence page, two test files, one make target.
- Rollback: remove them; nothing in the package depends on the harness.

## Open Questions

- **A release gate from these tasks** ("four of five pass in one batch"). Default: none yet. After two batches the maintainer can put a number in a release change.
- **A second real runner.** Default: when someone needs it; a row and its source are all it takes.
- **Tasks that need Freerouting.** Default: none in the first five; a sixth task can ask for it once c0078 is archived, and then measures `fetch`.
- **Windows.** Default: not supported by the runner (process groups and the shim are POSIX); the judge and the tasks are portable.
