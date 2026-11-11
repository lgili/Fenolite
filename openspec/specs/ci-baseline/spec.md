# ci-baseline Specification

## Purpose
Run the same quality gates on every push and pull request as `make check` runs locally (lint, format, strict types, tests, residue scan) on ubuntu and macOS with a locked environment.
## Requirements
### Requirement: Unit CI job on two operating systems

Full-profile CI SHALL run the existing five unit environments: ubuntu-latest with Python 3.11/3.12/3.13 and macos-latest/windows-latest with Python 3.12. No unit environment MAY use continue-on-error, except the existing explicitly diagnostic Mac preprobe. Working-branch fast CI MAY omit this matrix only when its distinct fast result cannot satisfy the full gate. All full environments retain the same baseline test collection as before.

#### Scenario: Every pull request executes the matrix
- **WHEN** a pull request is opened or updated
- **THEN** all five unit environments are required by the full aggregate

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

Every CI profile SHALL require locked sync, lint, format, strict types and current-tree residue checks. Platform-independent quality steps MAY run once in a separate required job. Native macOS and Windows type checks MUST remain. Full unit execution SHALL retain its original full baseline collection and loadfile scheduler, with additional receipt/timing/JUnit instrumentation.

#### Scenario: Quality check fails
- **WHEN** lint, format, types or residue checking fails
- **THEN** neither the fast nor full aggregate can succeed

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
- **THEN** it passes only if the unit wrapper retains the full baseline collection and `-n auto --dist loadfile` execution

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

Full CI SHALL retain pinned KiCad 10.0.6, all current corpus uses, geo, FENOLITE_HEAVY=1 and FENOLITE_REQUIRE=kicad,corpus,libs. All tests/kicad and tests/corpus node ids plus whole resource-bearing unit files SHALL execute in five audited whole-file partitions with container-local temporary files. Four partitions SHALL retain hash-based loadfile scheduling for the ordinary native collection. The routing completion scale file SHALL run serially in the fifth partition with its original fixtures, assertions, and budgets. Fast MAY omit these jobs only without satisfying the full gate.

#### Scenario: Heavy corpus test assigned
- **WHEN** full CI partitions the KiCad 10 collection
- **THEN** every selected heavy test is assigned once and remains subject to its original assertions

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

#### Scenario: Routing scale isolated
- **WHEN** full CI partitions the KiCad 10 collection
- **THEN** the routing completion scale file is scheduled exactly once on a dedicated serial runner

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

Full-profile CI SHALL retain the pinned official KiCad 9.0.9 image, existing corpus fetch uses and complete tests/kicad execution with FENOLITE_REQUIRE=kicad and loadfile scheduling. Fast working-branch CI MAY omit this job only without satisfying the full aggregate.

#### Scenario: Full KiCad compatibility
- **WHEN** any PR runs
- **THEN** KiCad 9 execution remains required even when KiCad 10 passes

#### Scenario: Job runs the 9.0 binary
- **GIVEN** a pull request that touches `src/`
- **WHEN** the `kicad-9` job runs
- **THEN** its log shows `kicad-cli version` reporting `9.0.9`, and `tests/kicad/test_environment.py` passes

#### Scenario: Workflow shape checked
- **GIVEN** the committed `ci.yml`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** it passes only if the job `kicad-9` exists, its image is `kicad/kicad:9.0.9@sha256:<64 hex>`, its steps follow the order above, its cache key is `corpus-rt2-9-sch-9-${{ hashFiles('tests/corpus/manifest.toml') }}`, its only corpus fetch is `uv run python tools/corpus_fetch.py --uses rt2-9 --uses sch-9`, and its audited wrapper runs the complete tests/kicad collection with loadfile scheduling with `FENOLITE_REQUIRE=kicad`

#### Scenario: Unpinned image rejected
- **GIVEN** a workflow edit that references `kicad/kicad:9.0` without a digest
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** the test fails naming the job

#### Scenario: Wider fetch rejected
- **GIVEN** a workflow edit whose `kicad-9` fetch step runs `uv run python tools/corpus_fetch.py --uses rt0`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** the test fails naming the job `kicad-9` and the use `rt2-9`

#### Scenario: Fetch without the schematic rows rejected
- **GIVEN** a workflow edit whose `kicad-9` fetch step lacks `--uses sch-9`, or names `--uses sch` in its place
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** the test fails naming the job `kicad-9` and `--uses sch-9`

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
The `routing` job of `.github/workflows/ci.yml` (c0016) SHALL also install Java 25 and install the Freerouting jar of `freerouting.PINNED_VERSION` with `uv run fenolite fetch freerouting --dir /tmp/freerouting --confirm --json` (`cli-contract`, "Fetch command"), which downloads it from its release page and writes it only when its size and its SHA-256 are those of the table row; the job MUST NOT download the jar in any other way. It MUST run `uv run pytest tests/routing -q -rA` with `FENOLITE_FREEROUTING_JAR` set to the fetched file and `freerouting` added to `FENOLITE_REQUIRE`. The job stays outside the merge gate. The marker `needs_freerouting` SHALL skip without the variable and fail, with the same message, when `FENOLITE_REQUIRE` lists `freerouting`. `tests/unit/test_ci_workflow.py` SHALL check the install step, the version and the environment textually.

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k freerouting` runs
- **THEN** it passes only if the job installs the jar with `fenolite fetch freerouting --confirm` after Fenolite is installed and before the tests, downloads it in no other way, and sets `FENOLITE_FREEROUTING_JAR` to the file of the pinned version in the folder of `--dir`

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

### Requirement: macOS application nightly job
`.github/workflows/nightly.yml` SHALL contain a job `macos-app` that runs on a schedule, once a day, and on `workflow_dispatch`, on a GitHub-hosted macOS runner, and that runs the oracle tests against the `kicad-cli` of the official KiCad 10.0.6 macOS disk image. It repeats in CI what the hypothesis register records as "confirmed with local `kicad-cli` 10.0.6 (macOS)". It is NOT a check of pull requests and NOT a merge gate.
- The disk image MUST be the release asset `kicad-unified-universal-10.0.6.dmg` of the tag `10.0.6` of `https://github.com/KiCad/kicad-source-mirror`, pinned by its SHA-256 written in the workflow as 64 hex digits. The job MUST fail before anything of the image runs when the digest of the downloaded file differs.
- The job MUST run these steps in this order:
  1. `actions/checkout@v4`
  2. `astral-sh/setup-uv`
  3. `actions/cache` of the downloaded image, keyed on the pinned SHA-256
  4. the download of the image, skipped when the cache holds it
  5. the check of its SHA-256 with `shasum -a 256 --check`
  6. `hdiutil attach` of the image, read-only and without opening a window
  7. `"$FENOLITE_KICAD_CLI" version`, with `FENOLITE_KICAD_CLI` set to the `kicad-cli` inside the mounted `KiCad.app`
  8. `uv sync --locked --extra dev`
  9. `uv run pytest tests/kicad -q -n auto --dist loadfile` with `FENOLITE_REQUIRE=kicad`
- The job MUST NOT fetch the corpus and MUST NOT run `tests/corpus`: the `kicad-10` job covers them. It MUST set `timeout-minutes`, and MUST fail if any step fails.
- KiCad is run as a subprocess from the mounted image and is never installed into, copied into or committed to the repository.
- `tests/unit/test_ci_workflow.py` SHALL check the job textually: the schedule and `workflow_dispatch` triggers, the absence of `push` and `pull_request` triggers, the asset URL, a 64-digit digest that the `shasum` step uses, the order of the steps above, `FENOLITE_REQUIRE=kicad` and the parallel options of the pytest step ("Parallel test runs").
- `H-K-CI-MACOSAPP` MUST be settled by the first runs: the image mounts, `kicad-cli` runs from the mounted volume without a display and reports `10.0.6`, and the suite passes. When the binary cannot run from the mounted volume, the fallback MUST be applied and recorded in the register row: step 6 copies the `KiCad` folder of the image to the runner's temporary folder and clears its quarantine attribute, and step 7 uses that copy. When neither runs, the job MUST be removed, and the roadmap MUST say that the macOS application stays a local oracle.
- `docs/roadmap.md` MUST name the job among the CI jobs and say that it is not a merge gate.

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k macos_app` runs
- **THEN** it passes only if `nightly.yml` holds the job `macos-app` with a `schedule` trigger and `workflow_dispatch`, no `push` and no `pull_request` trigger, the asset URL of tag `10.0.6`, a 64-digit SHA-256 used by the `shasum` step, and the nine steps in order

#### Scenario: Unpinned image rejected
- **GIVEN** a `nightly.yml` whose `shasum` step is removed
- **WHEN** the same test runs
- **THEN** it fails naming the job `macos-app` and the digest check

#### Scenario: Corpus tests rejected
- **GIVEN** a `macos-app` job whose pytest step also names `tests/corpus`
- **WHEN** the same test runs
- **THEN** it fails naming the job and `tests/corpus`

#### Scenario: First nightly run
- **WHEN** the job runs on `workflow_dispatch` after the change merges
- **THEN** its log shows `kicad-cli version` reporting `10.0.6` and the `tests/kicad` suite passing, and the row of `H-K-CI-MACOSAPP` records the run's URL, or the fallback that was applied

### Requirement: Yardstick nightly job
`.github/workflows/nightly.yml` SHALL contain a job `yardstick` that runs `tools/yardstick.py run` on `examples/yardstick` (release-gate, "Yardstick runner") on the workflow's `schedule` and on `workflow_dispatch`. It is NOT a check of pull requests and NOT a merge gate (change c0119).
- It MUST run on `ubuntu-latest` inside the image `kicad/kicad:10.0.6` pinned by the same SHA-256 as the `kicad-10` job of `ci.yml`, with the container option `--user 0`, and MUST set `timeout-minutes`.
- It MUST run these steps in this order:
  1. `actions/checkout@v4`
  2. `astral-sh/setup-uv` with Python 3.12
  3. `uv sync --locked --extra dev`
  4. `kicad-cli version`, failing unless it prints `10.0.6`
  5. `actions/cache` of the official library cache, keyed on the pin of tag 10.0.6, then `uv run python tools/kicad_libs_fetch.py --tag 10.0.6 --cache <folder>`
  6. `actions/cache` of the corpus rows of the two heavy demo boards, keyed on the hash of `tests/corpus/manifest.toml`, then `uv run python tools/corpus_fetch.py --uses heavy --only` with the two board ids
  7. from stage 4 of the example on, Java 25, the Freerouting jar of `freerouting.PINNED_VERSION` and KiCadRoutingTools at `routingtools.PINNED_TAG`, installed and checked by SHA-256 as the `routing` job of `ci.yml` installs them
  8. `uv run python tools/yardstick.py run` with `--out` and `--record` under `$RUNNER_TEMP`, `--summary "$GITHUB_STEP_SUMMARY"`, and `FENOLITE_LIBS_CACHE` set to the folder of step 5
  9. `actions/upload-artifact@v4` of the record and the replies, with `if: always()` and `retention-days: 90`
- The job MUST fail when the runner exits non-zero. It MUST NOT run `pytest`, and MUST NOT write to the repository.
- `tests/unit/test_ci_workflow.py` SHALL check the job textually: the job exists in `nightly.yml` and in no other workflow; the image digest equals that of `kicad-10`; the order of the steps; `--tag 10.0.6`; the `--only` filters of the heavy fetch; the upload step with `if: always()`; and, once the example reaches stage 4, the router steps with their digests.
- `docs/roadmap.md` MUST name the job among the CI jobs and say that it is not a merge gate.

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k yardstick` runs
- **THEN** it passes only if `nightly.yml` holds the job `yardstick` in the pinned 10.0.6 image with the nine steps in order, and no workflow triggered by `push` or `pull_request` holds it

#### Scenario: Unpinned image rejected
- **GIVEN** a `nightly.yml` whose `yardstick` job names `kicad/kicad:10.0.6` without a digest
- **WHEN** the same test runs
- **THEN** it fails naming the job `yardstick` and the image

#### Scenario: Upload only on success rejected
- **GIVEN** a `yardstick` job whose upload step has no `if: always()`
- **WHEN** the same test runs
- **THEN** it fails naming the upload step

#### Scenario: First run by hand
- **WHEN** the job runs on `workflow_dispatch` after the change merges
- **THEN** its log shows `kicad-cli version` printing `10.0.6` and the runner's verdict, the run's artefact holds the record, and a row of `docs/evidence/yardstick.md` names the run

### Requirement: Pushes that run CI
`.github/workflows/ci.yml` SHALL run on a push of any branch except a branch under `backup/`, and on every pull request; a push of a tag SHALL run no job of it (change c0194).
- The `push` trigger MUST hold exactly the branch filters `"**"` and `"!backup/**"`, and no `tags` filter.
- `tests/unit/test_ci_workflow.py` MUST check the trigger textually.

#### Scenario: Trigger checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k push_trigger` runs
- **THEN** it passes only if the `on` block of `ci.yml` is the branch filter above and `pull_request:`

#### Scenario: Tags run nothing
- **GIVEN** a copy of `ci.yml` whose push trigger has no filter
- **WHEN** the trigger check runs on it
- **THEN** it fails and says that a tag push would run CI

### Requirement: Portable byte-fidelity proofs

Portability tests SHALL compare canonical UTF-8 bytes using binary output, interpret native paths as paths and parse shell-quoted commands as argument sequences. They MUST retain exact payload equality assertions.

#### Scenario: A Windows path needs quoting
- **WHEN** a conflict hint quotes an output path
- **THEN** the test verifies its parsed output argument against the expected path

### Requirement: Container-local corpus temporary files

The KiCad 10 CI job SHALL place pytest temporary files in a directory available inside its container and collect import-census artifacts from the same directory.

#### Scenario: Host temporary paths differ from container paths
- **WHEN** the oracle and corpus test step starts
- **THEN** pytest can create its base directory and the artifact step searches that directory

### Requirement: Import census covers selected corpus rows

The recorded import census SHALL include every licence-eligible KiCad 10.0.6 demo-board row selected by the corpus test, including heavy rows. A unit preflight MUST check coverage without fetching or importing boards. Measurements MUST identify their source pins and CI commit/version; the corpus test MUST still require exit 0, exact equivalence and matching omitted-kind counts.

#### Scenario: Heavy imports pass before the missing record fails
- **GIVEN** CI emits exit 0 and equivalent=true for rows 06 and 18 but their census rows are absent
- **WHEN** the aggregate measurements are recorded
- **THEN** the preflight finds all selected rows, and the existing heavy import assertions remain active

### Requirement: Declared CAC closure geometry deferral
The working-branch CI SHALL restore the maintainer-approved geometry exclusion only for pushes
whose ref is `refs/heads/codex/cac-next`. Its source-bound manifest MUST name the 27 known native
c0332 failures and their unchanged test-file digests. They SHALL be explicitly deselected and
reported as deferred, never passed. Every other selected test remains required. Main, dev and
pull-request selection MUST remain unchanged. c0332 remains open and this scoped result MUST NOT
be reported as its complete geometry validation. No runtime acceptance, assertion or budget changes.

#### Scenario: Scoped closure push
- **WHEN** codex/cac-next runs the native10 closure job with the reviewed unchanged test sources
- **THEN** only the 27 declared geometry nodeids are deselected and the summary names their deferral

#### Scenario: Full release or pull-request selection
- **WHEN** the workflow runs on main, dev or a pull request
- **THEN** the closure-only step does not set selection arguments

#### Scenario: Stale exclusion source
- **WHEN** a declared test file differs from its bound digest
- **THEN** scope preparation fails before executing the native suite

### Requirement: Conservative CI profiles

Every pull request and merge group, integration-ref execution, unknown event/ref and CI-control change SHALL select full validation. Only recognized working-branch pushes or explicit manual fast requests on a working branch MAY select fast. Missing or invalid policy inputs MUST NOT downgrade full coverage. Fast SHALL run light tool-free tests on Linux (c0381); full retains all existing tool-free tests and SHALL NOT publish a passing full aggregate.

#### Scenario: Manual downgrade refused
- **WHEN** a manual fast request targets dev, main or another integration ref
- **THEN** full validation is selected

#### Scenario: CAC batch integration
- **WHEN** a push or manual fast request targets cac/lote-12 or another cac/lote-* batch branch
- **THEN** full integration validation is selected

#### Scenario: CI policy changed on a working branch
- **WHEN** a push changes CI workflows, test-control files or CI tools
- **THEN** full validation is selected regardless of the branch prefix

#### Scenario: Owner census proof changed
- **WHEN** a working push or manual fast request changes owner discovery, census measurement, reuse or its native driver
- **THEN** full validation is selected to exercise the changed native proof

#### Scenario: CI policy guidance changed
- **WHEN** docs/ci.md changes on a working branch or an explicit manual fast request
- **THEN** full validation is selected, as for agent/contributor workflow guidance

### Requirement: Audited file-preserving partition

Full validation SHALL retain all current environments, required resources and assertions. KiCad 10 MAY use multiple runners only with whole-file assignment, original within-file order and an exhaustive disjoint union of the baseline node ids. New tests MUST be assigned automatically, and every selected test MUST have a recorded terminal outcome.

#### Scenario: New test file
- **WHEN** a new test file enters the collected baseline
- **THEN** exactly one shard selects each of its node ids

#### Scenario: Shard or outcome omitted
- **WHEN** a shard receipt or a selected test outcome is missing, duplicated or inconsistent
- **THEN** coverage auditing and the full aggregate fail

### Requirement: Native coverage of resource-dependent units

KiCad 10 SHALL also run entire unit files containing needs_kicad, needs_corpus or needs_libs cases.
The Linux/Python 3.12 unit inventory SHALL independently require these files in the native baseline
and require their resource-marked cases to pass.

#### Scenario: Resource unit test skipped in portable jobs
- **WHEN** a unit case needs KiCad, corpus or libraries and cannot run in the portable matrix
- **THEN** its whole file executes in KiCad 10 and the marked case cannot be waived by a native skip

### Requirement: Distinct complete merge gate

A full aggregate SHALL require successful static checks, every full test environment, every specialized check and coverage auditing on the tested commit. Skipped, cancelled, missing or failed dependencies MUST NOT satisfy it. Fast and full aggregates SHALL have different names. Documentation MUST state which full aggregate integration branches require; nightly-only results MUST NOT substitute for it.

#### Scenario: Fast succeeds
- **WHEN** a working-branch fast run succeeds
- **THEN** it cannot report the full merge check as successful

#### Scenario: Full dependency skipped
- **WHEN** a required full job is skipped or absent
- **THEN** the full aggregate fails

### Requirement: Measured whole-file priority

CI SHALL use the locked loadfile scheduler when prioritizing measured expensive whole files. Every planned
id and original within-file order SHALL remain unchanged. Serial job order SHALL remain unchanged.
An actual worker regression MUST prove the scheduling option works across dependency updates.

#### Scenario: Expensive file has few cases
- **WHEN** a measured expensive file has fewer cases than another file
- **THEN** it is scheduled early without splitting its cases or omitting any planned id

### Requirement: Hash-bound owner census reuse

The drawn corpus SHALL restrict reuse of a complete owner measurement to one module and matching owner/root,
manifest, full input inventory and declared/actual hashes, tool instance, major, version and commit
match. Inputs MUST be checked before lookup and after execution. Internal errors or changed/missing
inputs MUST NOT seed reuse. The store SHALL retain metadata only, never CAD bytes.

#### Scenario: Two sheets share one complete owner
- **WHEN** two sheet cases measure exactly the same validated owner project in the same environment
- **THEN** the complete pipeline executes once, both cases retain their own ids and contexts, and the second report discloses reuse

#### Scenario: Input or execution identity changed
- **WHEN** any project/library/sheet is missing, changed, differently declared, or the owner/tool/version/commit/manifest differs
- **THEN** no previous successful measurement can satisfy that case

#### Scenario: Owner measurement fails
- **WHEN** the complete owner pipeline refuses or finds a connectivity difference
- **THEN** every target sheet retains that strict failure, including when the same measurement is reused

### Requirement: Independent sheet census proof

Owner measurement reuse SHALL retain every sheet case, complete owner/instance checks, strict result
assertion and independent report copy. Reports MUST disclose reuse and identify the owner measurement
without source names, values or absolute paths. Original timings SHALL describe the original pipeline,
not a new execution.

#### Scenario: Shared result metadata is edited
- **WHEN** one sheet report is changed after lookup
- **THEN** other sheet reports and future lookups retain their original independent contents

### Requirement: Light working-push feedback
Recognized working pushes MAY exclude measured whole-file long_flow tests from fast and use Linux/Python 3.13. Full validation SHALL retain every test and environment, and SHALL remain required on every PR and integration ref. Test/classification changes MUST force full. The target is 5–10 minutes and MUST be measured.

#### Scenario: Long board flow
- **WHEN** a test file is classified long_flow
- **THEN** fast excludes the entire file and full still collects every original case

#### Scenario: Classification changed
- **WHEN** tests or marker configuration change
- **THEN** the working push selects full

### Requirement: Audited parallel light execution
CI SHALL run the light selection in three whole-file partitions and SHALL require an exact-commit, complete, disjoint receipt audit before ci-fast succeeds.

#### Scenario: Missing light partition
- **WHEN** any light partition is missing or unsuccessful
- **THEN** the light audit and ci-fast SHALL fail

