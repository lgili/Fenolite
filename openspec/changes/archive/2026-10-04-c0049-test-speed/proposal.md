## Why

The tests are too slow, and every run is serial. Measured on 2026-10-04:

- CI `unit` jobs: about 2 minutes (3620 tests).
- CI `kicad-9`: about 4 minutes (278 tests).
- CI `kicad-10` (oracle and corpus): 32 minutes (720 tests, about 2.7 s each).
- Local `make check`: 11 minutes alone, and 30 to 70 minutes when several agents run it at once on
  one machine.

`pytest-xdist` is already in the `dev` extra and in `uv.lock`, but nothing uses it
(<https://pytest-xdist.readthedocs.io/en/stable/distribution.html>). The development machine has 10
cores and GitHub's Linux runners have 4.

## What Changes

- **Parallel test runs.** `make test`, `make check` and the pytest steps of the CI jobs `unit`,
  `kicad-10` and `kicad-9` run with `-n auto --dist loadfile`. The Makefile adds a cap
  (`--maxprocesses`), because `kicad-cli` uses threads of its own. A plain `uv run pytest` stays
  serial, so task proofs and single files behave as before.
- **Parallel safety.** The audit (design.md) finds two unsafe things:
  - The opt-in write modes (`FENOLITE_PROBES_WRITE`, `FENOLITE_GOLDEN_WRITE`,
    `FENOLITE_CENSUS_OUT`, `FENOLITE_CHECK_EVIDENCE`) write tracked or shared files.
    `tests/conftest.py` refuses them in a parallel run with a usage error.
  - Four tests give a fake `kicad-cli` a 2 or 3 second limit that its quick calls must also meet.
    Under load they fail. The quick calls now run under a generous limit.
- **Proof of equality.** A serial and a parallel run of the whole suite give the same outcome for
  every test id. The comparison tool is `tools/test_outcomes.py` (JUnit XML in, differences out).
- **Two make targets.** `make check-fast` runs lint, format check, types, the residue scan and the
  tests of `tests/unit`, `tests/residue` and `tests/consistency` that need no external resource.
  `make check` runs everything as today, in parallel, plus the residue scan that CI already runs.
  It stays the gate before a merge.
- **Working rule.** `CONTRIBUTING.md` and `AGENTS.md` say: iterate with `check-fast` plus the tests
  of the touched files; run `make check` once on the rebased branch before the merge; never start
  several full suites at once on one machine.
- **Numbers.** `tests/README.md` records the timings, worker counts, conditions and comparison.

## Capabilities

### Modified Capabilities (no new capability)

- `ci-baseline`:
  - MODIFIED "Quality gates", "Local parity", "kicad-10 oracle job" and "KiCad 9.0 oracle job"
    (the pytest command of each).
  - ADDED "Parallel test runs", "Fast local check" and "Working rule for parallel worktrees".

## Non-goals

- No test is removed, weakened, re-marked or moved to a nightly job.
- No change to what CI checks: the same jobs, steps, images, corpus fetches and environment
  variables. The required checks keep their names, "kicad-9 (kicad-cli 9.0 oracle)" and
  "kicad-10 (kicad-cli oracle and corpus)".
- No new dependency and no change under `src/`.
- No job sharding, no test-result cache, no speed-up of single tests.
- No fix of `tests/unit/geometry/test_transform.py::test_composition_rounds_once`, a latent
  Hypothesis failure that is tracked separately.

## Evidence level required

- This change touches no format fact and no evidence label of the product.
- The timings are measurements of one machine on one day, recorded with their conditions.
- Equality is proved by `tools/test_outcomes.py` on the JUnit files of the local runs (KiCad
  10.0.6). For CI it is checked after the push against the last serial run on `main`.

## Impact

- Files: `Makefile`, `ci.yml`, `tests/conftest.py`, three unit test files and a new one,
  `tools/test_outcomes.py`, and documents. Nothing under `src/`.
- Order: implemented now and archived before c0016, c0023 and c0025, which also change
  `ci-baseline`. c0025 MODIFIES "kicad-10 oracle job" and rebases its text onto this change's.
- Size: small, 1.5 design-days.
