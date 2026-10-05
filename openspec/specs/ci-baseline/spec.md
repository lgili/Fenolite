# ci-baseline Specification

## Purpose
Run the same quality gates on every push and pull request as `make check` runs locally (lint, format, strict types, tests, residue scan) on ubuntu and macOS with a locked environment.
## Requirements
### Requirement: Unit CI job on two operating systems
The repository SHALL contain a GitHub Actions workflow `.github/workflows/ci.yml` with a job `unit` that runs on every push and pull request, using `uv`, on these five combinations: `ubuntu-latest` with Python 3.11, 3.12 and 3.13, `macos-latest` with Python 3.12, and `windows-latest` with Python 3.12.
- The steps MUST be the same on every combination.
- No combination MAY carry `continue-on-error`: Windows is a merge gate like the others (the maintainer's decision of 2026-10-05, after a first run with 35 failures).
- `tests/unit/test_ci_workflow.py` SHALL check the five combinations textually.
- A test that needs a POSIX executable MUST be skipped on Windows only through `tests/_resources.py::posix_tools`, with the reason `posix-only fake tool`, and the skipped tests MUST be fewer than 5 % of the collected tests (`H-G-REL-WINDOWS`).

#### Scenario: Every combination executes the job
- **WHEN** a pull request is opened
- **THEN** five `unit` runs appear, and the pull request cannot merge while any is failing

#### Scenario: Matrix checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k unit_matrix` runs
- **THEN** it passes only if `ci.yml` names the three operating systems and Python 3.11, 3.12 and 3.13, and no run carries `continue-on-error`

#### Scenario: Fake tool runs on Windows
- **WHEN** `uv run pytest tests/unit/backends/kicad -k fake` runs on `windows-latest`
- **THEN** the fake `kicad-cli` built by `tests/_fakecli.py` answers `version` through its `.cmd` wrapper

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

### Requirement: Locked, reproducible environment
`uv.lock` SHALL be committed and the CI job SHALL use `uv sync --locked` semantics so that a drifted lockfile fails the build.

#### Scenario: Drifted lockfile
- **GIVEN** `pyproject.toml` adds a dev dependency without updating `uv.lock`
- **WHEN** the workflow runs
- **THEN** the sync step fails with a lockfile mismatch

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
6. `uv run python tools/corpus_fetch.py --uses rt0 --uses libs --uses project --uses cfb --uses altium-text --exclude-uses heavy`
7. `uv run pytest tests/kicad tests/corpus -q -n auto --dist loadfile` with `FENOLITE_REQUIRE=kicad,corpus`

The job MUST fail if any step fails. `tests/unit/test_ci_workflow.py` SHALL check the job textually, because the dev extra has no YAML parser: the digest pin, the container options, the order of the steps above, the cache key, `--uses libs`, `--uses project`, `--uses cfb` and `--uses altium-text` (the rows that c0039 and c0042 added to the workflow), `--exclude-uses heavy`, the environment variable and the parallel options of the pytest step.

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

#### Scenario: Project rows not fetched
- **GIVEN** a `kicad-10` job whose fetch step lacks `--uses project`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** the test fails naming the job `kicad-10` and `--uses project`

#### Scenario: Demo projects are checked
- **WHEN** the `kicad-10` job runs
- **THEN** `tests/kicad/check/test_check_demos.py::test_demo_projects` runs on the fetched demo projects and is not skipped for a missing corpus

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

### Requirement: Routing smoke job
`.github/workflows/ci.yml` SHALL contain a job `routing` that runs on every push to `main` and on pull requests, inside the pinned `kicad/kicad:10.0.6` image of the `kicad-10` job, and that is NOT a required check for merging, because it downloads third-party code. It MUST run these steps in this order:
1. `actions/checkout@v4`
2. `astral-sh/setup-uv`
3. `kicad-cli version`
4. `uv sync --locked --extra dev`
5. a clone of `https://github.com/drandyhaas/KiCadRoutingTools` at the tag `routingtools.PINNED_TAG`, whose commit hash the step prints
6. the tool's build step (`python build_router.py`) and its dependencies installed in a virtual environment of its own, never in Fenolite's
7. `uv run pytest tests/routing -q -rA` with `FENOLITE_REQUIRE=kicad,router`, `FENOLITE_KRT` set to the clone and `FENOLITE_KRT_PYTHON` to that environment's interpreter

`tests/unit/test_ci_workflow.py` SHALL check the job textually: the image digest equal to `kicad-10`'s, the tag equal to `PINNED_TAG`, and the order of the steps. `docs/routing.md` SHALL say that the job is not a merge gate, because branch protection is not stored in the repository.

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k routing` runs
- **THEN** it passes only if the `routing` job exists with the pinned image, clones the tool at `PINNED_TAG`, and runs `tests/routing` with `FENOLITE_REQUIRE=kicad,router`

#### Scenario: Tag drift caught
- **GIVEN** `PINNED_TAG` changed in `routingtools.py` and not in `ci.yml`
- **WHEN** the same test runs
- **THEN** it fails naming both values

### Requirement: Router resource
The marker `needs_router` SHALL skip a test when `FENOLITE_KRT` does not name a KiCadRoutingTools checkout holding `py_router/route.py`, with a reason naming `FENOLITE_KRT`, and SHALL fail it instead, with the same message, when `FENOLITE_REQUIRE` lists `router`. This adds the resource `router` beside `kicad`, `corpus` and `libs` of "Required-resource mode", whose rules stay as they are.

#### Scenario: Missing tool fails in the routing job
- **GIVEN** `FENOLITE_REQUIRE=router` and no `FENOLITE_KRT`
- **WHEN** `uv run pytest tests/unit/test_conftest_require.py -k router` runs a `needs_router` test through `pytester`
- **THEN** it fails with a message naming `FENOLITE_KRT`

#### Scenario: Default is skip
- **GIVEN** neither variable set
- **WHEN** `uv run pytest tests/routing -q` runs
- **THEN** every test is skipped and the exit code is 0

### Requirement: Freerouting in the routing job
The `routing` job of `.github/workflows/ci.yml` (c0016) SHALL also install Java 25 and download the Freerouting jar of `freerouting.PINNED_VERSION` from its release page, MUST verify the jar against a SHA-256 written in `ci.yml`, and MUST run `uv run pytest tests/routing -q -rA` with `FENOLITE_FREEROUTING_JAR` set and `freerouting` added to `FENOLITE_REQUIRE`. The job stays outside the merge gate. The marker `needs_freerouting` SHALL skip without the variable and fail, with the same message, when `FENOLITE_REQUIRE` lists `freerouting`. `tests/unit/test_ci_workflow.py` SHALL check the version, the checksum step and the environment textually.

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k freerouting` runs
- **THEN** it passes only if the job downloads the pinned version, verifies a 64-hex SHA-256 and sets `FENOLITE_FREEROUTING_JAR`

#### Scenario: Version drift caught
- **GIVEN** `PINNED_VERSION` changed in the plugin and not in `ci.yml`
- **WHEN** the same test runs
- **THEN** it fails naming both values

### Requirement: Wheel job
`.github/workflows/ci.yml` SHALL contain a job `wheel` that runs on every push and pull request on `ubuntu-latest` with Python 3.12 and proves that the built package installs alone. It MUST run these steps in this order:
1. `actions/checkout@v4`
2. `astral-sh/setup-uv`
3. `uv build --out-dir dist` and `uv build packaging/phenolite --out-dir dist`
4. `uv run --no-project python tools/residue/scan.py`
5. a fresh virtual environment and `pip install --no-index --find-links dist fenolite`
6. in that environment: `fenolite capabilities --json` exits 0, and `importlib.metadata.requires("fenolite")` holds no requirement without an extra marker
7. a check that the wheel holds no path starting with `tests/`, `private/` or `examples/`

`tests/unit/test_ci_workflow.py` SHALL check the job textually: `--no-index`, the residue step before the install, and the order of the steps. The residue step runs with the public patterns only: no private list is given to CI (release-gate, "Release record").

#### Scenario: Wheel installs with no dependency
- **WHEN** the `wheel` job runs
- **THEN** the install succeeds with no index and `fenolite capabilities --json` prints a valid envelope

#### Scenario: A runtime dependency fails the job
- **GIVEN** `pyproject.toml` with one entry in `dependencies`
- **WHEN** the `wheel` job runs
- **THEN** step 5 fails, because the dependency cannot be found without an index

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k wheel` runs
- **THEN** it passes only if the job exists with the steps in the order above

### Requirement: DCO job
`.github/workflows/ci.yml` SHALL contain a job `dco` that runs on every push and pull request on `ubuntu-latest` and fails when a commit lacks the sign-off that `CONTRIBUTING.md` requires. It MUST run these steps in this order:
1. `actions/checkout@v4` with `fetch-depth: 0`
2. `python3 tools/dco_check.py`

`tools/dco_check.py [<revision range>]` SHALL use only the standard library and `git` as a subprocess.
- Without an argument it MUST read every commit reachable from `HEAD`; with one, the commits of that range.
- It MUST skip commits with more than one parent, and commits whose full hash is listed in `tools/dco_exceptions.txt` with a reason: a commit already on the main branch cannot gain a trailer. A malformed line of that file MUST make the tool exit 2.
- A commit passes when its message holds a trailer line `Signed-off-by: <name> <<address>>`. The tool MUST NOT compare the trailer with the author.
- It MUST print one line `<short hash> <subject>` per failing commit and exit 1, exit 0 when none fails, and exit 2 when `git` fails.

`tests/unit/test_ci_workflow.py` SHALL check the job textually: `fetch-depth: 0` and the command.

#### Scenario: History passes
- **WHEN** `python3 tools/dco_check.py` runs on the repository
- **THEN** it prints nothing and exits 0

#### Scenario: Unsigned commit is named
- **GIVEN** a temporary repository with one signed commit and one commit without the trailer
- **WHEN** `uv run pytest tests/unit/test_dco_check.py` runs the tool there
- **THEN** the tool exits 1 and prints only the unsigned commit's hash and subject

#### Scenario: Merge commit skipped
- **GIVEN** a temporary repository whose only unsigned commit has two parents
- **WHEN** the same test runs the tool
- **THEN** it exits 0

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k dco` runs
- **THEN** it passes only if the job `dco` exists, its checkout has `fetch-depth: 0` and its second step is `python3 tools/dco_check.py`

