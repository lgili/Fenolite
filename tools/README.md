# tools

Developer scripts (stdlib-only, run as `uv run python tools/<script>.py`). They are not part of the
installed package. Later changes add the schema generator, the residue scan, the corpus fetcher and
the oracle setup scripts here.

| script | what it does |
|---|---|
| `test_outcomes.py` | Compares the JUnit XML files of two pytest runs (`--junitxml`): the totals of each run and every test id whose outcome differs; exit 0 when equal, 1 when not. It proves that a parallel run gives the results of a serial run (`tests/README.md`, "Parallel runs"). |
| `kicad_libs_fetch.py` | Fetches the official KiCad footprint and symbol libraries at the pinned commits of tags 10.0.6 and 9.0.9 into a verified cache outside the repository (`--cache`, else `FENOLITE_LIBS_CACHE`, else `~/.cache/fenolite/libs`); `--verify` re-hashes it. The libraries are CC-BY-SA 4.0 and are never committed (`docs/formats/kicad/libraries.md`, "Library cache"). |
| `altium_census.py` | `--uses altium-sch` or `--uses altium-schlib` [`--json`]: reads the cached Altium schematic or library corpus rows with `fenolite.backends.altium.read` and prints the merged census (record ids, unknown ids and keys, key case, `WEIGHT`, owners, fractions, pin strings, side streams, stream sizes, issue codes). Key names, ids and counts only, never a value of a file (change c0040). |
| `gen_agent_guide.py` | Writes the generated parts of the agent guide under `src/fenolite/agent/skill/`: `references/commands.md` from `fenolite.cli.describe`, `references/dsl-reference.md` from the signatures of `fenolite.dsl`, and the index of pages between the two marker lines of `SKILL.md`. `--check` writes nothing and exits 1 naming each stale file; `make check-fast` runs it. |
| `gen_evidence_matrix.py` | Renders `docs/evidence/matrix.md` from the evidence declarations of the backend modules (`fenolite.backends.matrix`) and the level text of `docs/hypotheses.md`: the matrix of backend, file kind and operation, the register level of each id it names, and each module's declaration. `--check` writes nothing and exits 1 when the committed page is stale (`tests/unit/test_evidence_matrix_page.py` runs it). |
| `yardstick.py` | Takes `examples/yardstick` through the loop of its stage and judges the run (change c0119; "The yardstick" below). |
| `yardstick_budgets.toml` | The seconds and MiB each step of the yardstick may take, per stage, and the findings a stage accepts. |

## The yardstick

`uv run python tools/yardstick.py run --out build/yardstick --record build/yardstick/record.json` (or
`make yardstick`) reads `STAGE` from `examples/yardstick/design.py` without running it, and runs the steps
of that stage, each as one child process `python -m fenolite <args> --json` in the output folder, which
becomes the project folder and must be empty. It needs `kicad-cli` 10 and `FENOLITE_LIBS_CACHE` naming the
verified library cache of tag 10.0.6 (`kicad_libs_fetch.py --tag 10.0.6`); from stage 4 also
`FENOLITE_FREEROUTING_JAR` (`fenolite fetch freerouting --confirm`, and Java 25) and `FENOLITE_KRT` with
`FENOLITE_KRT_PYTHON` (the pinned KiCadRoutingTools checkout), as the nightly job sets them.

- **Steps of stage 1**, in order: `capabilities`, `build-dry`, `build`, `fill`, `check` (concise; it exits
  5 before stage 4, because nothing is routed), `export`, `render`, `bom`, `pnp`, `manifest`, `rebuild-dry`,
  `rebuild`, `inspect`, `build-install` (a dry-run build without `FENOLITE_LIBS_CACHE`, so the libraries
  come from the KiCad install), then `heavy-read` and `heavy-rt1` once for each of the two corpus boards
  tagged `heavy` (`corpus_fetch.py --uses heavy --only <id> <id>`; `--skip-heavy` leaves them out).
  `--only STEP,…` runs single steps on an existing project.
- **Steps added by the later stages:** stage 3 `impedance`; stage 4 `route` (Freerouting, `--timeout 3600`,
  two tiers; it leaves the pair open), `route-pairs` (KiCadRoutingTools on the pair, with the escape of
  the controller; after `route` until the pair is routed as a coupled pair, c0157), `fill-routed`, `check-routed` (exit 0, or 5 with counts within the ratchets), `net` and `analyze`;
  stage 5 `export-package` (the document kinds and drawings, with `--manifest`) and `testpoints`.
- **Per step** the record keeps the arguments, the exit code, the wall seconds, the peak resident memory
  of the step's largest process, the bytes of the reply and the issue counts by code. The replies are
  kept under `yardstick-run/replies/` of the output folder.
- **Rules.** Every step exits as its stage expects; every `check` stage that ran is `ok`, except
  `drc.kicad`, whose only error type before stage 4 is `unconnected_items`; `copper.clearance` has no
  finding and the net comparison no difference; the manifest lists every file that `export`, `render`,
  `bom` and `pnp` wrote; the dry rebuild plans no change to a file outside `.fenolite/`, and the rebuild
  leaves the board's bytes unchanged. A failed `build` or `fill` skips the steps that need the board.
  From stage 4, `check-routed` holds KiCad's open connections and DRC errors of the routed board to the
  stage's ratchets; an error of `length.rules` there counts through KiCad's `length_out_of_range` or
  `skew_out_of_range` when KiCad reports that type as often, and fails the stage otherwise; at stage 5 every file that `export-package` and `testpoints` wrote is listed in
  `fab/fenolite-artifacts.json`.
- **Budgets.** `yardstick_budgets.toml` holds a table per stage: `source`, then `seconds` and `mib` per
  step under `[stage<n>.steps.<step>]`, and from stage 4 `[stage<n>.ratchets]` with `open_connections` and
  `drc_errors`. A step over its budget, or a count over its ratchet, fails the run; a step without a
  budget is recorded and fails nothing; a stage without a table, or from stage 4 without its ratchets, is
  exit 2. `rebase RECORD RECORD RECORD` prints the budgets that three runs give (median seconds times 1.5,
  rounded up to 10 s; largest MiB times 1.25, rounded up to 50 MiB; a ratchet is the largest count), and
  `rebase --provisional RECORD` those of one local run (times 4 and times 2).
- **Accepted findings.** A finding that only a repair in Fenolite can remove is accepted for a stage by
  an entry `[stage<n>.accepted.<key>]` with `stage` (the `check` stage), `type`, `reason` and `owner` (the
  change or issue that owns the repair). It is counted in every record and fails nothing; any other type
  still fails the run. Stage 1 has none.
- **The record** (`fenolite.yardstick-record.v0`) holds the date, the commit, the stage, the runner, the
  tool versions, the board's measures, the steps, the rules, the accepted findings, the budgets and the
  verdict, with no absolute path. `row RECORD --url URL` prints its row of the `Runs` table of
  `docs/evidence/yardstick.md`.
- **Exit codes:** 0 passed; 1 a step, a rule or a budget failed; 2 usage, or a missing `kicad-cli`,
  library cache, corpus row, router, budget table or ratchet table. The summary is printed, and appended to `--summary FILE`.
- Seconds and MiB are measures of one runner: no evidence label moves on a budget.

## Agent evaluation (`tools/agent_eval/`)

Measures whether a fresh AI agent can use Fenolite (change c0081). `run.py` gives one task of
`tools/agent_eval/tasks/` to one runner of `runners.toml` in a clean place, and Fenolite itself decides
the result.

```
make agent-eval TASK=led-indicator RUNNER=replay
uv run python tools/agent_eval/run.py --task led-indicator --runner replay [--repeat N] [--keep] [--record] [--yes]
```

| file | what it does |
|---|---|
| `run.py` | Builds the wheel of the checkout, installs it with no extra and no index in a new environment under a new temporary folder outside the repository (`uv` does both), makes an empty work folder, copies the task's `files/`, runs its `prepare` lines, installs the guide as the runner's row says, prints the budget, starts the runner with the call log first on `PATH`, stops it when the task's minutes are over, judges, writes `result.json` beside the work folder and prints one verdict line. Exit 0 when every verdict is `passed`, 5 otherwise, 1 when the place could not be prepared, 2 for a refused run. The temporary folder is removed unless `--keep` is given. |
| `judge.py` | The verdict, from the files of the work folder: the project exists, `fenolite check` exits 0, the nets of the built model are the expected groups of `REF-PIN`, the board fits, the output files exist. `passed` needs `kicad-cli`; without it the verdict is `unjudged`. |
| `shim.py` | The call log: a stand-in named `fenolite` that passes a call through unchanged and appends one JSON line per call (`n`, `argv`, `exit`, `elapsed_ms`, `error_code`). It logs no environment value; an absolute path is logged relative to the current folder, or as `<outside>/NAME`. |
| `tasks.py`, `tasks/` | The task format and the five tasks with their reference solutions (`tasks/README.md`). |
| `runners.toml` | The runners. `replay` plays the reference solution of a task and starts no agent: it is what the test suites run. Every other row starts a real agent and names the public page it was written from. |

**A run with a real agent costs money and is started by a person, never by an agent and never in CI.**
`run.py` refuses a runner other than `replay` while the variable `CI` is set; without `--yes` it prints
the task, the runner, the time budget and the cost cap and starts nothing; a row marked `unconfigured`
does not start at all. One run is one agent session of at most the task's minutes (20, and 30 for
`custom-footprint`), so the five tasks are at most 110 minutes of agent time. What a session costs is
not known before the first one: run `led-indicator` once, read the cost the runner reports, then decide
on the rest. The tool reads no key and calls no service itself; the agent it starts inherits the
environment of the person who started it, and is not sandboxed beyond an empty work folder and a new
environment.

To record a run, add `--record`: one row is appended to `docs/evidence/agent-eval.md` (date, commit,
runner, model, task, verdict, calls, failed calls, minutes, first failure), with no path, prompt or
transcript. Add a row to `Findings` by hand for each distinct first failure. `--keep` leaves the
temporary folder, which holds the transcript, on your machine; it is never committed.
