# tests

| Folder | What lives there | Needs |
|---|---|---|
| `unit/` | fast, hermetic tests of `fenolite` and of repository invariants | nothing |
| `consistency/` | CLI contract checks run against every registered command (change c0002) | nothing |
| `residue/` | IP residue scan over the tree and the built wheel (change c0003) | nothing; private token list optional |
| `corpus/` | tests over the fetched public corpus (`tools/corpus_fetch.py`) | `needs_corpus` |
| `kicad/` | tests that call `kicad-cli` 9.0/10.0 | `needs_kicad` |
| `libs/` | census of the official KiCad libraries (read, resolve, count; nothing committed) | `needs_libs`, `slow` |
| `data/` | small fixtures authored for Fenolite, declared in `data/MANIFEST.toml` | nothing |

Run everything that needs no external tool with `uv run pytest -q`. `make check-fast` runs the
checks and the tests of `unit/`, `residue/` and `consistency/` that need no external resource;
`make check` runs every test. Both use parallel workers (see "Parallel runs" below).

## Markers and modes

| Marker or variable | Effect |
|---|---|
| `needs_kicad`, `needs_corpus`, `needs_libs` | skip when the resource is absent |
| `FENOLITE_REQUIRE=kicad,corpus,libs` | required-resource mode: those skips become failures (CI oracle jobs) |
| `kicad_min_major(10)` | skip when the running `kicad-cli` is older (for example `pcb upgrade`, 10.0 only); never a failure, even in required-resource mode |
| `FENOLITE_HEAVY=1` | include corpus files over 20 MB |
| `FENOLITE_KICAD_CLI=/path` | use this `kicad-cli` (a missing file counts as no `kicad-cli`) |
| `KICAD10_FOOTPRINT_DIR`, `KICAD10_SYMBOL_DIR` (or `KICAD9_*`) | official library folders for `needs_libs`; they take precedence over the install |
| `FENOLITE_KICAD_INSTALL_DIR=/path` | the KiCad share folder to use instead of the default install (a missing path counts as no install) |
| `FENOLITE_CENSUS_OUT=/path/census.json` | where `tests/libs/` writes its counts (never a tracked file) |

## Parallel runs

`make check`, `make check-fast` and the CI jobs run the tests on `pytest-xdist` workers
(capability ci-baseline, "Parallel test runs"). A plain `uv run pytest ...` stays serial.

| Where | Options |
|---|---|
| `make check`, `make check-fast` | `-n auto --maxprocesses 8 --dist loadfile` (`PYTEST_WORKERS`, `PYTEST_MAX_WORKERS`, `PYTEST_PARALLEL`) |
| CI `unit`, `kicad-10`, `kicad-9` | `-n auto --dist loadfile` (4 workers on the Linux runners, 3 on macOS) |
| by hand | `uv run pytest tests/kicad -q -n 8 --dist loadfile` |

Rules for tests:

- Write only below `tmp_path`. Use no fixed port and no fixed path outside the repository.
- Do not depend on a test of another file. A summary test may read what the earlier tests of its
  own file collected: `--dist loadfile` runs a file on one worker, in file order. `--dist load`
  breaks such files, so do not use it.
- Give every subprocess call that must finish a limit of 10 s or more. A short limit is only for
  a call that must time out.
- The write modes are serial. With `FENOLITE_PROBES_WRITE=1`, `FENOLITE_GOLDEN_WRITE=1`,
  `FENOLITE_CENSUS_OUT` or `FENOLITE_CHECK_EVIDENCE` set, a run with `-n` stops with a usage error
  (exit code 4): several workers would write the same file.
- Prove a change of the options with `uv run python tools/test_outcomes.py serial.xml parallel.xml`
  on the `--junitxml` files of a serial and a parallel run.

### Measurements (2026-10-04, change c0049)

Machine: 10 cores (4 performance, 6 efficiency), macOS, KiCad 10.0.6, corpus and library caches
present. The machine was never quiet: other agents ran test suites and a Docker container during
every run below (2 to 12 other pytest processes, load average 5 to 38). The times are therefore
upper bounds, and comparisons between rows are rough.

| Run | Options | Wall time | Outcomes |
|---|---|---|---|
| whole suite, before | serial | 3357 s (56 min) | 4827 passed, 24 skipped |
| `tests/kicad` | serial (part of the run above) | 1783 s | 584 passed, 10 skipped |
| `tests/kicad` | `-n 6 --dist loadfile` | 605 s | 584 passed, 10 skipped |
| `tests/kicad` | `-n 8 --dist loadfile` | 546 s | 584 passed, 10 skipped |
| `tests/kicad` | `-n 10 --dist loadfile` | 617 s | 584 passed, 10 skipped |
| `tests/kicad` | `-n 8 --dist load` | 838 s | 583 passed, 11 skipped: `test_upgraded_summary` lost the results of its file |
| `make check-fast` | `-n auto --maxprocesses 8 --dist loadfile` | 122 s (tests 101 s) | 3832 passed, 6 skipped |
| `make check`, after (rebased: 736 more tests) | `-n auto --maxprocesses 8 --dist loadfile` | 1226 s (20 min; tests 1205 s) | 5563 passed, 24 skipped |

- The cap is 8: the fastest of 6, 8 and 10, and it leaves two cores to the `kicad-cli` threads.
- With `loadfile` the longest file bounds the run. In the `tests/kicad` runs with 8 and 10 workers,
  `tests/kicad/check/test_corpus_rt.py` alone took 509 s and 611 s on its worker (412 s serial). The
  next ones are `tests/libs/test_official_resolve.py` (468 s serial), `tests/libs/test_official_read.py`
  (411 s) and `tests/kicad/check/test_check_demos.py` (364 s). Splitting them is later work.
- Equality. `tools/test_outcomes.py` on the serial and the final parallel JUnit files: the 4849
  test ids present in both runs have the same outcome (0 differences). The parallel run has 738
  more ids (723 from changes merged between the two runs, 15 from this change) and lacks 2 that
  were renamed. On one commit, the 594 ids of `tests/kicad` (`-n 8 --dist loadfile`) equal the
  serial run id by id.
- Before and after are not the same suite: the final run holds 15 % more tests and used 4538 s of
  CPU against 3064 s. Per test, the wall time went from 0.69 s to 0.22 s (3.2 times faster) while
  other agents kept the machine at a load average of 18 to 31.
- The maintainer's earlier figure for a serial `make check` on a quiet machine was 11 minutes.
