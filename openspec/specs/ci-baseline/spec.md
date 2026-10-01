# ci-baseline Specification

## Purpose
Run the same quality gates on every push and pull request as `make check` runs locally (lint, format, strict types, tests, residue scan) on ubuntu and macOS with a locked environment.
## Requirements
### Requirement: Unit CI job on two operating systems
The repository SHALL contain a GitHub Actions workflow `.github/workflows/ci.yml` with a job `unit` that runs on every push and pull request, on `ubuntu-latest` and `macos-latest`, with Python 3.12, using `uv`.

#### Scenario: Both runners execute the job
- **WHEN** a pull request is opened
- **THEN** two `unit` runs appear, one per operating system, and the pull request cannot merge while either is failing

### Requirement: Quality gates
The `unit` job MUST run, in order, `uv sync --extra dev`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright src`, `uv run pytest -q`, and MUST fail if any step fails.

#### Scenario: Lint error fails the job
- **GIVEN** a source file with an unused import
- **WHEN** the workflow runs
- **THEN** the `ruff check` step fails and the job is marked failed

#### Scenario: Type error fails the job
- **GIVEN** a function in `src/` that returns `str` where `int` is declared
- **WHEN** the workflow runs
- **THEN** the `pyright src` step fails

### Requirement: Locked, reproducible environment
`uv.lock` SHALL be committed and the CI job SHALL use `uv sync --locked` semantics so that a drifted lockfile fails the build.

#### Scenario: Drifted lockfile
- **GIVEN** `pyproject.toml` adds a dev dependency without updating `uv.lock`
- **WHEN** the workflow runs
- **THEN** the sync step fails with a lockfile mismatch

### Requirement: Local parity
The same four commands SHALL be runnable locally through a `Makefile` target `make check` (or `uv run task check`) so that contributors reproduce CI before pushing.

#### Scenario: Local check
- **WHEN** a contributor runs `make check` on a clean checkout
- **THEN** the same four steps run and the exit code is non-zero if any fails

### Requirement: kicad-10 oracle job
`.github/workflows/ci.yml` SHALL contain a job `kicad-10` that runs on every push and pull request on `ubuntu-latest`. The job runs inside the official image `kicad/kicad:10.0.6`, pinned by its index digest (`@sha256:` followed by 64 hex digits), with container `options: --user 0`. It MUST run the following steps in this order:
1. `actions/checkout@v4`
2. `astral-sh/setup-uv`
3. `kicad-cli version`
4. `uv sync --locked --extra dev`
5. `actions/cache` of the corpus cache, keyed on `hashFiles('tests/corpus/manifest.toml')`
6. `uv run python tools/corpus_fetch.py --uses rt0 --exclude-uses heavy`
7. `uv run pytest tests/kicad tests/corpus -q` with `FENOLITE_REQUIRE=kicad,corpus`

The job MUST fail if any step fails. `tests/unit/test_ci_workflow.py` SHALL check the job textually, because the dev extra has no YAML parser: the digest pin, the container options, the order of the steps above, the cache key, `--exclude-uses heavy` and the environment variable.

#### Scenario: Oracle job runs on a pull request
- **WHEN** a pull request is opened
- **THEN** a `kicad-10` run appears next to the `unit` runs and its log shows `kicad-cli version` reporting 10.0.6

#### Scenario: Unpinned image rejected
- **GIVEN** `ci.yml` refers to `kicad/kicad:10.0` without a digest
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** the test fails naming the job `kicad-10`

#### Scenario: Steps out of order
- **GIVEN** a `kicad-10` job that runs `uv sync` before `kicad-cli version`
- **WHEN** the same test runs
- **THEN** it fails naming the two steps

### Requirement: Required-resource mode
When the environment variable `FENOLITE_REQUIRE` lists a resource (`kicad`, `corpus`, `libs`; comma-separated), tests marked with the matching `needs_*` marker MUST fail, not skip, if the resource is missing. The failure message MUST be the one the skip would have shown. With `corpus` listed, a corpus test MUST also fail when any non-heavy `rt0` manifest item is missing from the cache, naming the item. Without the variable, the skip rules of `corpus-policy` apply unchanged.

#### Scenario: Missing kicad-cli fails in the oracle job
- **GIVEN** `FENOLITE_REQUIRE=kicad` and `FENOLITE_KICAD_CLI` pointing to a missing file on a machine without `kicad-cli`
- **WHEN** `uv run pytest tests/kicad -q` runs
- **THEN** the `needs_kicad` tests fail with `kicad-cli not found` and the exit code is non-zero

#### Scenario: Partial corpus cache fails
- **GIVEN** `FENOLITE_REQUIRE=corpus` and a cache that holds only the `origin:kicad-demos` items
- **WHEN** `uv run pytest tests/corpus/test_rt0.py -q` runs
- **THEN** it fails naming a missing `origin:third-party` item

#### Scenario: Default remains skip
- **GIVEN** `FENOLITE_REQUIRE` unset and no `kicad-cli`
- **WHEN** `uv run pytest tests/kicad -q` runs
- **THEN** the tests are skipped and the exit code is 0

### Requirement: KiCad 9.0 oracle job
`.github/workflows/ci.yml` SHALL contain a job `kicad-9` that runs on every push and pull request inside the official image `kicad/kicad:9.0.9`, pinned by index digest (`@sha256:` followed by 64 hex digits), with the same container mechanism as the `kicad-10` job. It MUST run the following steps in order:
1. `kicad-cli version`
2. `uv sync --locked --extra dev`
3. `uv run pytest tests/kicad -q -rA` (every outcome listed in the log) with `FENOLITE_REQUIRE=kicad`

The job SHALL NOT fetch the corpus, so its `needs_corpus` tests skip, and tests marked `kicad_min_major(10)` skip without failing. Tests marked `needs_kicad` fail instead of skipping when `kicad-cli` is missing. The job MUST fail if any step fails, and it SHALL be a required check for merging.

#### Scenario: Job runs the 9.0 binary
- **GIVEN** a pull request that touches `src/`
- **WHEN** the `kicad-9` job runs
- **THEN** its log shows `kicad-cli version` reporting `9.0.9`, and `tests/kicad/test_environment.py` passes

#### Scenario: Workflow shape checked
- **GIVEN** the committed `ci.yml`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** it passes only if the job `kicad-9` exists, its image is `kicad/kicad:9.0.9@sha256:<64 hex>`, its test step runs `uv run pytest tests/kicad -q` with `FENOLITE_REQUIRE=kicad`, and it has no corpus fetch step

#### Scenario: Unpinned image rejected
- **GIVEN** a workflow edit that references `kicad/kicad:9.0` without a digest
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** the test fails naming the job

### Requirement: Token fuzz check in both KiCad jobs
The token fuzz check SHALL run as the test `tests/kicad/test_token_fuzz.py::test_committed_results` (markers `needs_kicad`, `slow`), which runs `tools/kicad_token_fuzz.py --check docs/evidence/kicad/token-fuzz` against the running `kicad-cli`. Both KiCad jobs SHALL run it through their `uv run pytest tests/kicad` step, so no step is added to the `kicad-10` job. The test MUST fail when the results file for the running `kicad-cli` version is missing or when any outcome differs.

#### Scenario: Image bump without results
- **GIVEN** `FENOLITE_KICAD_CLI` pointing to a fake `kicad-cli` whose `version` prints `10.0.7`, and no `10.0.7.json` under `docs/evidence/kicad/token-fuzz/`
- **WHEN** `uv run pytest tests/kicad/test_token_fuzz.py -k committed` runs
- **THEN** the test fails stating that the results file for `10.0.7` is missing

#### Scenario: Both jobs run the KiCad tests
- **GIVEN** the committed `ci.yml`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** it passes only if the pytest steps of both `kicad-9` and `kicad-10` include `tests/kicad`

