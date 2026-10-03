## MODIFIED Requirements

### Requirement: Unit CI job on two operating systems
The repository SHALL contain a GitHub Actions workflow `.github/workflows/ci.yml` with a job `unit` that runs on every push and pull request, using `uv`, on these five combinations: `ubuntu-latest` with Python 3.11, 3.12 and 3.13, `macos-latest` with Python 3.12, and `windows-latest` with Python 3.12.
- The steps MUST be the same on every combination.
- `tests/unit/test_ci_workflow.py` SHALL check the five combinations textually.
- A test that needs a POSIX executable MUST be skipped on Windows only through `tests/_resources.py::posix_tools`, with the reason `posix-only fake tool`, and the skipped tests MUST be fewer than 5 % of the collected tests (`H-G-REL-WINDOWS`).

#### Scenario: Every combination executes the job
- **WHEN** a pull request is opened
- **THEN** five `unit` runs appear, and the pull request cannot merge while any is failing

#### Scenario: Matrix checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k unit_matrix` runs
- **THEN** it passes only if `ci.yml` names the three operating systems and Python 3.11, 3.12 and 3.13

#### Scenario: Fake tool runs on Windows
- **WHEN** `uv run pytest tests/unit/backends/kicad -k fake` runs on `windows-latest`
- **THEN** the fake `kicad-cli` built by `tests/_fakecli.py` answers `version` through its `.cmd` wrapper

### Requirement: kicad-10 oracle job
`.github/workflows/ci.yml` SHALL contain a job `kicad-10` that runs on every push and pull request on `ubuntu-latest`. The job runs inside the official image `kicad/kicad:10.0.6`, pinned by its index digest (`@sha256:` followed by 64 hex digits), with container `options: --user 0`. It MUST run the following steps in this order:
1. `actions/checkout@v4`
2. `astral-sh/setup-uv`
3. `kicad-cli version`
4. `uv sync --locked --extra dev`
5. `actions/cache` of the corpus cache, keyed on `hashFiles('tests/corpus/manifest.toml')`
6. `uv run python tools/corpus_fetch.py --uses rt0 --uses project --exclude-uses heavy`
7. `uv run pytest tests/kicad tests/corpus -q` with `FENOLITE_REQUIRE=kicad,corpus`

The job MUST fail if any step fails. `tests/unit/test_ci_workflow.py` SHALL check the job textually, because the dev extra has no YAML parser: the digest pin, the container options, the order of the steps above, the cache key, `--uses rt0 --uses project`, `--exclude-uses heavy` and the environment variable.

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

#### Scenario: Demo projects are fetched
- **WHEN** the `kicad-10` job runs
- **THEN** the read-only test of `check` on demo projects runs and is not skipped for a missing corpus

## ADDED Requirements

### Requirement: Wheel job
`.github/workflows/ci.yml` SHALL contain a job `wheel` that runs on every push and pull request on `ubuntu-latest` with Python 3.12 and proves that the built package installs alone. It MUST run these steps in this order:
1. `actions/checkout@v4`
2. `astral-sh/setup-uv`
3. `uv build --out-dir dist` and `uv build packaging/phenolite --out-dir dist`
4. `uv run --no-project python tools/residue/scan.py`
5. a fresh virtual environment and `pip install --no-index --find-links dist fenolite`
6. in that environment: `fenolite capabilities --json` exits 0, and `importlib.metadata.requires("fenolite")` holds no requirement without an extra marker
7. a check that the wheel holds no path starting with `tests/`, `private/` or `examples/`

`tests/unit/test_ci_workflow.py` SHALL check the job textually: `--no-index`, the residue step before the install, and the order of the steps.

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
