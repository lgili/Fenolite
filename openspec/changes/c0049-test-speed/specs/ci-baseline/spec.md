## MODIFIED Requirements

### Requirement: Quality gates
The `unit` job MUST run, in order, `uv sync --extra dev`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright src`, `uv run pytest -q -n auto --dist loadfile`, and MUST fail if any step fails. The pytest step runs the same tests as the serial command `uv run pytest -q` ("Parallel test runs").

#### Scenario: Lint error fails the job
- **GIVEN** a source file with an unused import
- **WHEN** the workflow runs
- **THEN** the `ruff check` step fails and the job is marked failed

#### Scenario: Type error fails the job
- **GIVEN** a function in `src/` that returns `str` where `int` is declared
- **WHEN** the workflow runs
- **THEN** the `pyright src` step fails

#### Scenario: Unit tests run in parallel
- **GIVEN** the committed `ci.yml`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** it passes only if the pytest step of the `unit` job is `uv run pytest -q -n auto --dist loadfile`

### Requirement: Local parity
The quality gates SHALL be runnable locally through the `Makefile` target `make check`, so that contributors reproduce CI before pushing. `make check` MUST run, in order, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright src`, `uv run python tools/residue/scan.py` and the whole test suite, and its exit code MUST be non-zero if any step fails.
- The test step SHALL be `uv run pytest -q $(PYTEST_PARALLEL)`, where `PYTEST_PARALLEL` is `-n $(PYTEST_WORKERS) --maxprocesses $(PYTEST_MAX_WORKERS) --dist loadfile`.
- `PYTEST_WORKERS` SHALL default to `auto` and `PYTEST_MAX_WORKERS` to the cap recorded in `tests/README.md`. Both MUST be overridable on the command line, for example `make check PYTEST_MAX_WORKERS=4`.
- `make check` SHALL stay the gate before a merge: it selects every test that the serial `uv run pytest -q` selects.

#### Scenario: Local check
- **WHEN** a contributor runs `make check` on a clean checkout
- **THEN** the five steps run, the tests run on several workers, and the exit code is non-zero if any step fails

#### Scenario: Makefile shape checked
- **GIVEN** the committed `Makefile`
- **WHEN** `uv run pytest tests/unit/test_parallel_runs.py` runs
- **THEN** it passes only if `check` depends on `lint format types residue test`, the `test` recipe is `uv run pytest -q $(PYTEST_PARALLEL)`, and `PYTEST_PARALLEL` holds `-n $(PYTEST_WORKERS)`, `--maxprocesses $(PYTEST_MAX_WORKERS)` and `--dist loadfile`

### Requirement: kicad-10 oracle job
`.github/workflows/ci.yml` SHALL contain a job `kicad-10` that runs on every push and pull request on `ubuntu-latest`. The job runs inside the official image `kicad/kicad:10.0.6`, pinned by its index digest (`@sha256:` followed by 64 hex digits), with container `options: --user 0`. It MUST run the following steps in this order:
1. `actions/checkout@v4`
2. `astral-sh/setup-uv`
3. `kicad-cli version`
4. `uv sync --locked --extra dev`
5. `actions/cache` of the corpus cache, keyed on `hashFiles('tests/corpus/manifest.toml')`
6. `uv run python tools/corpus_fetch.py --uses rt0 --uses libs --exclude-uses heavy`
7. `uv run pytest tests/kicad tests/corpus -q -n auto --dist loadfile` with `FENOLITE_REQUIRE=kicad,corpus`

The job MUST fail if any step fails. `tests/unit/test_ci_workflow.py` SHALL check the job textually, because the dev extra has no YAML parser: the digest pin, the container options, the order of the steps above, the cache key, `--uses libs`, `--exclude-uses heavy`, the environment variable and the parallel options of the pytest step.

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

#### Scenario: Library rows not fetched
- **GIVEN** a `kicad-10` job whose fetch step lacks `--uses libs`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** the test fails naming the job `kicad-10` and `--uses libs`

#### Scenario: Serial pytest step rejected
- **GIVEN** a `kicad-10` job whose pytest step is `uv run pytest tests/kicad tests/corpus -q`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** the test fails naming the job `kicad-10` and `-n auto --dist loadfile`

### Requirement: KiCad 9.0 oracle job
`.github/workflows/ci.yml` SHALL contain a job `kicad-9` that runs on every push and pull request inside the official image `kicad/kicad:9.0.9`, pinned by index digest (`@sha256:` followed by 64 hex digits), with the same container mechanism as the `kicad-10` job. It MUST run the following steps in order:
1. `kicad-cli version`
2. `uv sync --locked --extra dev`
3. `actions/cache` of the corpus cache named by `FENOLITE_CORPUS_CACHE`, keyed on `corpus-rt2-9-${{ hashFiles('tests/corpus/manifest.toml') }}`
4. `uv run python tools/corpus_fetch.py --uses rt2-9`
5. `uv run pytest tests/kicad -q -rA -n auto --dist loadfile` (every outcome listed in the log) with `FENOLITE_REQUIRE=kicad`

The job SHALL fetch only the corpus rows tagged `rt2-9` (corpus-policy, "RT2 rows for KiCad 9.0"), which are the five readable non-heavy demo boards at tag 9.0.9.1, and no other row. Its `needs_corpus` tests therefore run on those rows and skip every other row, and tests marked `kicad_min_major(10)` skip without failing. Tests marked `needs_kicad` fail instead of skipping when `kicad-cli` is missing. The job MUST fail if any step fails, and it SHALL be a required check for merging. `tests/unit/test_ci_workflow.py` SHALL check the job textually: the digest pin, the container options, the order of the steps above, the cache key, the single fetch with `--uses rt2-9`, the environment variable and the parallel options of the pytest step.

#### Scenario: Job runs the 9.0 binary
- **GIVEN** a pull request that touches `src/`
- **WHEN** the `kicad-9` job runs
- **THEN** its log shows `kicad-cli version` reporting `9.0.9`, and `tests/kicad/test_environment.py` passes

#### Scenario: Workflow shape checked
- **GIVEN** the committed `ci.yml`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** it passes only if the job `kicad-9` exists, its image is `kicad/kicad:9.0.9@sha256:<64 hex>`, its steps follow the order above, its cache key is `corpus-rt2-9-${{ hashFiles('tests/corpus/manifest.toml') }}`, its only corpus fetch is `uv run python tools/corpus_fetch.py --uses rt2-9`, and its test step runs `uv run pytest tests/kicad -q -rA -n auto --dist loadfile` with `FENOLITE_REQUIRE=kicad`

#### Scenario: Unpinned image rejected
- **GIVEN** a workflow edit that references `kicad/kicad:9.0` without a digest
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** the test fails naming the job

#### Scenario: Wider fetch rejected
- **GIVEN** a workflow edit whose `kicad-9` fetch step runs `uv run python tools/corpus_fetch.py --uses rt0`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** the test fails naming the job `kicad-9` and the use `rt2-9`

#### Scenario: RT2 on the 9.0 rows
- **GIVEN** the `kicad-9` job with the `rt2-9` rows cached
- **WHEN** its test step runs
- **THEN** the log lists `tests/kicad/check/test_corpus_rt.py` as passed for the five `rt2-9` boards, and every other corpus test as passed or skipped

## ADDED Requirements

### Requirement: Parallel test runs
The test suite SHALL give the same outcome for every test id whether it runs serially or on several `pytest-xdist` workers with `--dist loadfile`.
- A test MUST write only below its own `tmp_path` (or a folder that pytest or `tempfile` made for it), MUST NOT use a fixed port or a fixed path outside the repository, and MUST NOT depend on a test of another file having run before it. A test MAY read what earlier tests of its own file collected, because `--dist loadfile` runs a file on one worker in file order; such a suite is not safe with `--dist load`.
- A test that gives a subprocess a time limit MUST leave at least 10 seconds for every call that is expected to finish, so that a loaded machine does not change its outcome. A shorter limit is allowed only for a call that is expected to time out.
- `pyproject.toml` MUST NOT put `-n` or `--dist` into `addopts`: a plain `uv run pytest` SHALL stay serial.
- The write modes `FENOLITE_PROBES_WRITE=1`, `FENOLITE_GOLDEN_WRITE=1`, `FENOLITE_CENSUS_OUT=<file>` and `FENOLITE_CHECK_EVIDENCE=<file>` write tracked or shared files. `tests/conftest.py` MUST stop a parallel run in which one of them is on, before any test runs, with pytest's usage-error exit code 4 and a message that names the variable and says to drop `-n`.
- `tools/test_outcomes.py A.xml B.xml` SHALL compare the JUnit files of two runs. It prints the totals of each run and every test id whose outcome differs, and exits 0 when there is no difference, 1 when there is one, and 2 when a file cannot be read.
- `tests/README.md` SHALL record the measured times before and after, the worker counts, what else ran on the machine, and the result of the comparison.

#### Scenario: Serial and parallel runs agree
- **GIVEN** `serial.xml` from `uv run pytest -q --junitxml serial.xml` and `parallel.xml` from `uv run pytest -q -n auto --dist loadfile --junitxml parallel.xml` on the same checkout
- **WHEN** `uv run python tools/test_outcomes.py serial.xml parallel.xml` runs
- **THEN** it prints equal totals and `differences: 0`, and exits 0

#### Scenario: A differing test is named
- **GIVEN** two JUnit files in which `test_a` passed in the first and failed in the second
- **WHEN** the tool runs
- **THEN** it prints `test_a: passed -> failure` and exits 1

#### Scenario: Write mode refused in a parallel run
- **GIVEN** `FENOLITE_CENSUS_OUT=census.json`
- **WHEN** `uv run pytest tests/corpus -n 2` runs
- **THEN** no test runs, the exit code is 4, and the message names `FENOLITE_CENSUS_OUT` and says to drop `-n`

#### Scenario: Write mode allowed in a serial run
- **GIVEN** `FENOLITE_PROBES_WRITE=1`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py -q` runs without `-n`
- **THEN** the run starts as before this change

#### Scenario: Plain pytest stays serial
- **WHEN** `uv run pytest tests/unit/test_parallel_runs.py -k plain` runs
- **THEN** it passes only if `addopts` of `pyproject.toml` holds neither `-n` nor `--dist`

### Requirement: Fast local check
The `Makefile` SHALL have a target `make check-fast` for use while iterating. It MUST run, in order, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright src`, `uv run python tools/residue/scan.py` and `uv run pytest tests/unit tests/residue tests/consistency -q $(PYTEST_PARALLEL) -m "not needs_kicad and not needs_corpus and not needs_libs"`.
- The target MUST NOT start `kicad-cli` and MUST NOT read the corpus or the official KiCad libraries, so it gives the same result on a machine without them.
- The tests it leaves out are run by `make check`; `check-fast` SHALL NOT replace `make check` as the gate before a merge.

#### Scenario: Fast check on a machine without KiCad
- **GIVEN** a machine without `kicad-cli`, corpus cache or KiCad libraries
- **WHEN** `make check-fast` runs on a clean checkout
- **THEN** the five steps run, no test marked `needs_kicad`, `needs_corpus` or `needs_libs` is selected, and the exit code is 0

#### Scenario: Makefile shape checked
- **GIVEN** the committed `Makefile`
- **WHEN** `uv run pytest tests/unit/test_parallel_runs.py -k fast` runs
- **THEN** it passes only if `check-fast` depends on `lint format types residue test-fast` and the `test-fast` recipe is the pytest command above

### Requirement: Working rule for parallel worktrees
`CONTRIBUTING.md` SHALL have a section "Parallel worktrees", and `AGENTS.md` SHALL state the same rule in short form:
- while working on a task, run `make check-fast` and the tests of the files the task touched;
- run `make check` once, on the rebased branch, right before the merge;
- never start several full suites at the same time on one machine.

#### Scenario: Rule present in both documents
- **WHEN** `uv run pytest tests/unit/test_parallel_runs.py -k working_rule` runs
- **THEN** it passes only if both documents name `make check-fast` and `make check` and forbid several full suites at once, and `CONTRIBUTING.md` has the section "Parallel worktrees"
