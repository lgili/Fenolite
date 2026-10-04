## Context

- Every test run is serial: `make test` is `uv run pytest -q`, and the three CI jobs call pytest
  without `-n`. `pytest-xdist>=3.6` is in the `dev` extra and locked, but unused.
- Measured on 2026-10-04: CI `unit` about 2 minutes (3620 tests), `kicad-9` about 4 minutes (278
  tests), `kicad-10` 32 minutes (720 tests). Local `make check`: 11 minutes alone, 30 to 70 minutes
  when several agents run it at once.
- The development machine has 10 cores (4 performance, 6 efficiency). GitHub's Linux runners have
  4, and the macOS runners 3.
- The suite has 4851 tests at the start of this change. Most of the time is spent in `kicad-cli`
  subprocesses (`tests/kicad`, `tests/corpus`) and in the library census (`tests/libs`).
- Facts about `pytest-xdist` used here
  (<https://pytest-xdist.readthedocs.io/en/stable/distribution.html>,
  <https://pytest-xdist.readthedocs.io/en/stable/how-to.html>):
  - `-n auto` starts one worker per CPU; `--maxprocesses N` caps that number; the environment
    variable `PYTEST_XDIST_AUTO_NUM_WORKERS` replaces the detected count.
  - `--dist load` (the default) sends tests to any free worker. `--dist loadfile` keeps the tests
    of one file on one worker. `--dist loadgroup` keeps tests with the same `xdist_group` mark on
    one worker.
  - Each worker is a separate Python process: module globals and `functools.cache` values are per
    worker.

### Audit: what is unsafe in parallel

| Area | Finding | Handling |
|---|---|---|
| Probe results (`docs/evidence/kicad/probes/<version>.json`) | Written only with `FENOLITE_PROBES_WRITE=1`, by one test. Read-only otherwise. | Write mode refused in a parallel run (Decision 4). |
| Golden files (`tests/data/altium/**`) | Written only with `FENOLITE_GOLDEN_WRITE=1`. Read-only otherwise. | Same. |
| Census output (`FENOLITE_CENSUS_OUT`) | Several tests read, merge and rewrite one JSON file (`tests/_boards.py`, `tests/_libcensus.py`, `tests/unit/backends/kicad/test_pro.py`). Two workers lose each other's rows. | Same. |
| Check evidence (`FENOLITE_CHECK_EVIDENCE`) | Several tests append lines to one file. | Same. |
| `kicad-cli` runs | `KicadCli.run` makes a fresh `tempfile.mkdtemp` folder per run and sets `KICAD_CONFIG_HOME` inside it. The test helpers do the same. No shared configuration, no lock file in the repository. | Safe. |
| Corpus and library caches | Read only by the tests. The fetch tools write them, and no test calls a fetch tool on the real cache. | Safe. |
| Fixed paths | `/tmp/...` appears only inside strings that tests feed to sanitisers. Every written file is under `tmp_path` or a `pytester` folder. | Safe. |
| Ports and Docker | No test opens a socket or starts Docker. (Docker appears only in task proofs.) | Nothing to do. |
| Session and module state | Two module-scoped fixtures, both read-only. About 40 helper modules memoise `kicad-cli` results with `functools.cache`: a worker that lacks a value computes it again, so the outcome does not depend on order. | Safe, but it costs time: Decision 2. |
| Execution order inside a file | Six test files collect results in a module-level list or dict and end with a summary test that reads it: `tests/kicad/board/test_board_upgraded.py` (`PASSED`), `tests/kicad/test_rt0_oracle.py`, and four files under `tests/unit/backends/kicad/`. Measured during implementation: with `--dist load`, `test_upgraded_summary` ran on a worker that held no result and changed from passed to skipped. No test depends on a test of another file. | `--dist loadfile` keeps a file on one worker, in file order (Decision 2). |
| Time limits | `tests/unit/backends/kicad/test_oracle.py` (three tests, 3 s) and `tests/unit/cli/test_check_cmd.py::test_oracle_timeout` (2 s) give the fake `kicad-cli` a limit that its quick `version` call must also meet. Under load that call is late and the tests fail, each run a different one. | The quick call gets a generous limit (Decision 5). |
| Time limits that are safe | `test_cli_runner.py` (1 s), `test_cli_export.py` and `test_plan.py` (0.5 s): the only call is the one that must time out. Real `kicad-cli` runs have limits of 120 to 900 s. | Nothing to do; the worker cap keeps real runs far from their limits. |
| `pytester` tests | They run inner pytest sessions in their own folders. | Safe. The new guard test uses a subprocess. |

## Goals / Non-Goals

**Goals**

- `make check` and the three CI jobs run the tests on several workers, with the same outcomes.
- `make check-fast` gives feedback in about 2 minutes without KiCad, corpus or libraries.
- The numbers, the worker counts and the equality proof are written down.
- A rule that keeps several agents from running full suites at once.

**Non-Goals**

- Removing, weakening or re-marking tests; nightly jobs; job sharding; faster single tests.
- Any change under `src/`, to the corpus, to the images or to the names of the required checks.

## Decisions

1. **Parallel options on the command line, not in `addopts`.** `make` and CI pass `-n`. A plain
   `uv run pytest ...` stays serial: task proofs, single files, `--pdb` and the write modes keep
   working as they do today.
   - Rejected: `addopts = "-n auto"`. It would make every proof command parallel, slow down
     one-file runs by the worker start-up, and break the write modes by default.
2. **`--dist loadfile`.** It is needed for equal outcomes, not only for speed.
   - Summary tests read what the earlier tests of their file collected (see the audit). `loadfile`
     runs a file on one worker in file order, as a serial run does.
   - The oracle tests memoise `kicad-cli` results per helper module. With `load`, the tests of one
     file are spread over all workers and each worker repeats the memoised runs.
   - Task 2.1 runs `load` once on `tests/kicad` and records its time and its outcome difference.
   - Rejected: `load` or `worksteal`. Both move single tests between workers: one outcome changes
     (measured) and the memoised values are lost.
   - Rejected: `loadgroup` with one `xdist_group` mark per summary file. It gives the same
     grouping for six files at the cost of marks that a new summary test can forget.
   - Cost: the longest file bounds the wall time. Splitting the long files is later work.
3. **Worker counts.**
   - Local: `-n auto --maxprocesses $(PYTEST_MAX_WORKERS)`. `kicad-cli` starts threads of its own
     for DRC and zone work, so one worker per core oversubscribes the machine. Task 2.1 measures
     6, 8 and 10 workers on `tests/kicad` and sets the default cap to the fastest. Both
     variables can be set per call: `make check PYTEST_MAX_WORKERS=4`.
   - CI: `-n auto` without a cap. The runners have 3 or 4 cores, below any cap worth setting.
   - Rejected: a `pytest_xdist_auto_num_workers` hook in `tests/conftest.py`. `--maxprocesses`
     does the same with no code.
4. **Write modes are serial.** `tests/conftest.py` gets `WRITE_MODES` and a `pytest_sessionstart`
   hook. On the controller of a parallel run (`config.option.numprocesses` set, no
   `workerinput`), an active write mode raises `pytest.UsageError`: exit code 4, no test runs.
   - Rejected: a file lock around the census merge. It needs platform code (`fcntl`, `msvcrt`) for
     a mode that only maintainers use.
   - Rejected: `xdist_group` for the census tests. They live in several folders, and `loadfile`
     ignores groups.
5. **Timeout tests are made robust, not pinned.** A pin (`xdist_group`) puts tests on one worker,
   but the other workers still load the machine, so the quick calls stay late. Instead, the quick
   `version` call runs under a 60 s limit and only the sleeping calls keep a short one:
   - `test_oracle.py`: `_oracle` builds the `KicadCli` with 60 s, calls `version()` (its result is
     cached on the object) and then sets `timeout = 1.0`.
   - `test_check_cmd.py::test_oracle_timeout`: the test wraps `KicadCli.version` so that it runs
     with 60 s, and keeps `--timeout 2` for the sleeping calls.
   The assertions do not change, and the tests take no longer than before.
   - Rejected: a 10 s limit for every call. Tried first: `test_oracle_timeout` went from 6 s to
     31 s, because each timed-out call waits for the whole limit.
   - Rejected: a second, serial pytest call for these tests. It changes the CI commands and the
     counts per step, and a loaded machine fails a serial run as well.
6. **`make check` gains the residue scan.** CI already runs `tools/residue/scan.py` in the `unit`
   job; `make check` did not. `check` is now `lint format types residue test`, so `check-fast` is
   a strict subset of `check`.
7. **`check-fast` selects by folder and marker.** `tests/unit tests/residue tests/consistency`
   with `-m "not needs_kicad and not needs_corpus and not needs_libs"`. The marker expression
   deselects the few tests of those folders that use a real resource (eight files today), so the
   target behaves the same on every machine.
   - Rejected: hiding `kicad-cli` with `FENOLITE_KICAD_CLI=/nonexistent`. The tests would still
     be collected and reported as skips.
8. **Equality is proved per test id.** `tools/test_outcomes.py` reads two JUnit files and
   compares the outcome of every `classname::name`. Equal totals alone could hide one test that
   changed in each direction.
9. **Numbers live in `tests/README.md`.** A section "Parallel runs" holds the table of times, the
   worker counts, the conditions and the comparison output. `docs/evidence/` is for format and
   product evidence.

## Files and public API

| File | Change |
|---|---|
| `Makefile` | `PYTEST_WORKERS`, `PYTEST_MAX_WORKERS`, `PYTEST_PARALLEL`; targets `check` (adds `residue`), `check-fast`, `test`, `test-fast` |
| `.github/workflows/ci.yml` | the three pytest steps end with `-n auto --dist loadfile` |
| `tests/conftest.py` | `WRITE_MODES`, `active_write_modes()`, `pytest_sessionstart` |
| `tests/unit/test_ci_workflow.py` | pins the three parallel pytest steps; `test_unit_job_untouched` becomes `test_unit_job_runs_in_parallel` |
| `tests/unit/test_parallel_runs.py` | new: Makefile shape, `addopts`, the documents, the guard (pytester subprocess), the comparison tool |
| `tests/unit/backends/kicad/test_oracle.py`, `tests/unit/cli/test_check_cmd.py` | the quick `version` call runs under a 60 s limit |
| `tools/test_outcomes.py` | new: `outcomes(path) -> dict[str, str]`, `differences(a, b) -> list[str]`, `main(argv) -> int` |
| `tools/README.md`, `tests/README.md`, `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `CHANGELOG.md` | text |

No file under `src/` changes. No public API of the package changes.

## Sources registered by this change

None. The two `pytest-xdist` pages are cited by URL; they describe a development tool, not a format.

## Hypotheses registered by this change

None.

## Evidence level per behaviour (before merge)

| Behaviour | Level |
|---|---|
| Product behaviours and format facts | unchanged; no label moves |
| Serial and parallel outcomes equal, local, KiCad 10.0.6 | proved by `tools/test_outcomes.py` on the two JUnit files; recorded in `tests/README.md` |
| Serial and parallel totals equal in CI | checked after the push against the last serial run on `main`; recorded when the change is archived |
| Timings | measurements with their conditions; no label |

## Size (design-days)

| Part | Days |
|---|---|
| Audit, guard, timeout tests | 0.25 |
| Measurements (serial, worker counts, distribution mode) | 0.5 |
| Makefile, workflow, workflow test | 0.25 |
| Comparison tool and tests | 0.25 |
| Documents and closing | 0.25 |
| **Total** | **1.5** |

## Overlaps with other active changes

Archive order: **this change first**. It is implemented now; the others are proposals.

| Change | Its `ci-baseline` delta | Effect |
|---|---|---|
| c0025-release-v0-1 | MODIFIES "kicad-10 oracle job" (fetch step: `--uses rt0 --uses project`) | Same requirement. c0025 rebases onto this text: its step 7 becomes `uv run pytest tests/kicad tests/corpus -q -n auto --dist loadfile`, and it keeps the scenario "Serial pytest step rejected". |
| c0025-release-v0-1 | MODIFIES "Unit CI job on two operating systems" (five combinations, Windows) | Not modified here. The parallel step then also runs on `windows-latest`; `pytest-xdist` supports it, and c0025 checks it. |
| c0025-release-v0-1 | ADDS "Wheel job" | No overlap: it runs no pytest. |
| c0016-routing-plugins | ADDS "Routing smoke job" and "Router resource" (`uv run pytest tests/routing -q -rA`) | No shared requirement. Its job may stay serial or take `-n auto --dist loadfile`; its tests must meet "Parallel test runs" if `make check` selects them. |
| c0023-specctra-freerouting | ADDS "Freerouting in the routing job" | Same as c0016. |

c0021 is archived; its `kicad-10` text (`--uses libs`) is the living text copied here. No other
active change has a `ci-baseline` delta. Changes that add write modes later must add them to
`WRITE_MODES`.

## Risks / Trade-offs

- **A hidden order dependency shows up later.** `loadfile` keeps the order inside a file, so the
  risk is between files only. The equality proof covers today's suite; "Parallel test runs" makes
  the rule explicit for new tests.
- **Load-dependent failures.** More workers mean slower `kicad-cli` runs. The limits of real runs
  are 120 s and more, against run times of a few seconds; the cap keeps the margin.
- **`loadfile` balance.** One very long file bounds the wall time. Task 2.1 records the longest
  files; splitting a file is later work, not part of this change.
- **CI gain is bounded by 4 cores.** `kicad-10` should drop from 32 minutes to roughly a third.
  The real number is read after the push.
- **Several agents still share one machine.** Parallel suites multiply the load, so the working
  rule matters more than before: one full suite at a time.
- **macOS runner memory.** Three workers on the `unit` job; the unit tests are light.

## Migration Plan

1. Land the change. No user-facing behaviour changes.
2. After the push, compare the totals of the three CI jobs with the last serial run on `main` and
   record the job times in `tests/README.md` when archiving.
3. Rollback: remove `-n auto --dist loadfile` from the three steps and set `PYTEST_WORKERS=0`.

## Open Questions

- **Cap value.** Default: the fastest of 6, 8 and 10 on `tests/kicad` (task 2.1). Measured: 8.
- **Should the CI `unit` job on macOS use `-n auto`?** Default: yes; three cores still help.
- **Should `check-fast` include `tests/consistency`?** Default: yes, it needs no external tool.
