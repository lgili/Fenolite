# tools

Developer scripts (stdlib-only, run as `uv run python tools/<script>.py`). They are not part of the
installed package. Later changes add the schema generator, the residue scan, the corpus fetcher and
the oracle setup scripts here.

| script | what it does |
|---|---|
| `test_outcomes.py` | Compares the JUnit XML files of two pytest runs (`--junitxml`): the totals of each run and every test id whose outcome differs; exit 0 when equal, 1 when not. It proves that a parallel run gives the results of a serial run (`tests/README.md`, "Parallel runs"). |
| `kicad_libs_fetch.py` | Fetches the official KiCad footprint and symbol libraries at the pinned commits of tags 10.0.6 and 9.0.9 into a verified cache outside the repository (`--cache`, else `FENOLITE_LIBS_CACHE`, else `~/.cache/fenolite/libs`); `--verify` re-hashes it. The libraries are CC-BY-SA 4.0 and are never committed (`docs/formats/kicad/libraries.md`, "Library cache"). |
| `altium_census.py` | `--uses altium-sch` or `--uses altium-schlib` [`--json`]: reads the cached Altium schematic or library corpus rows with `fenolite.backends.altium.read` and prints the merged census (record ids, unknown ids and keys, key case, `WEIGHT`, owners, fractions, pin strings, side streams, stream sizes, issue codes). Key names, ids and counts only, never a value of a file (change c0040). |
| `gen_evidence_matrix.py` | Renders `docs/evidence/matrix.md` from the evidence declarations of the backend modules (`fenolite.backends.matrix`) and the level text of `docs/hypotheses.md`: the matrix of backend, file kind and operation, the register level of each id it names, and each module's declaration. `--check` writes nothing and exits 1 when the committed page is stale (`tests/unit/test_evidence_matrix_page.py` runs it). |
| `yardstick.py` | Takes `examples/yardstick` through the loop of its stage and judges the run (change c0119; "The yardstick" below). |
| `yardstick_budgets.toml` | The seconds and MiB each step of the yardstick may take, per stage, and the findings a stage accepts. |

## The yardstick

`uv run python tools/yardstick.py run --out build/yardstick --record build/yardstick/record.json` (or
`make yardstick`) reads `STAGE` from `examples/yardstick/design.py` without running it, and runs the steps
of that stage, each as one child process `python -m fenolite <args> --json` in the output folder, which
becomes the project folder and must be empty. It needs `kicad-cli` 10 and `FENOLITE_LIBS_CACHE` naming the
verified library cache of tag 10.0.6 (`kicad_libs_fetch.py --tag 10.0.6`).

- **Steps of stage 1**, in order: `capabilities`, `build-dry`, `build`, `fill`, `check` (concise; it exits
  5 before stage 4, because nothing is routed), `export`, `render`, `bom`, `pnp`, `manifest`, `rebuild-dry`,
  `rebuild`, `inspect`, `build-install` (a dry-run build without `FENOLITE_LIBS_CACHE`, so the libraries
  come from the KiCad install), then `heavy-read` and `heavy-rt1` once for each of the two corpus boards
  tagged `heavy` (`corpus_fetch.py --uses heavy --only <id> <id>`; `--skip-heavy` leaves them out).
  `--only STEP,…` runs single steps on an existing project.
- **Per step** the record keeps the arguments, the exit code, the wall seconds, the peak resident memory
  of the step's largest process, the bytes of the reply and the issue counts by code. The replies are
  kept under `yardstick-run/replies/` of the output folder.
- **Rules.** Every step exits as its stage expects; every `check` stage that ran is `ok`, except
  `drc.kicad`, whose only error type before stage 4 is `unconnected_items`; `copper.clearance` has no
  finding and the net comparison no difference; the manifest lists every file that `export`, `render`,
  `bom` and `pnp` wrote; the dry rebuild plans no change to a file outside `.fenolite/`, and the rebuild
  leaves the board's bytes unchanged. A failed `build` or `fill` skips the steps that need the board.
- **Budgets.** `yardstick_budgets.toml` holds a table per stage: `source`, then `seconds` and `mib` per
  step under `[stage<n>.steps.<step>]`. A step over its budget fails the run; a step without a budget is
  recorded and fails nothing; a stage without a table is exit 2. `rebase RECORD RECORD RECORD` prints the
  budgets that three runs give (median seconds times 1.5, rounded up to 10 s; largest MiB times 1.25,
  rounded up to 50 MiB), and `rebase --provisional RECORD` those of one local run (times 4 and times 2).
- **Accepted findings.** A finding that only a repair in Fenolite can remove is accepted for a stage by
  an entry `[stage<n>.accepted.<key>]` with `stage` (the `check` stage), `type`, `reason` and `owner` (the
  change or issue that owns the repair). It is counted in every record and fails nothing; any other type
  still fails the run. Stage 1 has none.
- **The record** (`fenolite.yardstick-record.v0`) holds the date, the commit, the stage, the runner, the
  tool versions, the board's measures, the steps, the rules, the accepted findings, the budgets and the
  verdict, with no absolute path. `row RECORD --url URL` prints its row of the `Runs` table of
  `docs/evidence/yardstick.md`.
- **Exit codes:** 0 passed; 1 a step, a rule or a budget failed; 2 usage, or a missing `kicad-cli`,
  library cache, corpus row or budget table. The summary is printed, and appended to `--summary FILE`.
- Seconds and MiB are measures of one runner: no evidence label moves on a budget.
