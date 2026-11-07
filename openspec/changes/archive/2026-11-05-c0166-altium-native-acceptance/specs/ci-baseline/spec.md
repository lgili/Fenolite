## MODIFIED Requirements

### Requirement: kicad-10 oracle job
`.github/workflows/ci.yml` SHALL contain a job `kicad-10` that runs on every push and pull request on `ubuntu-latest`. The job runs inside the official image `kicad/kicad:10.0.6`, pinned by its index digest (`@sha256:` followed by 64 hex digits), with container `options: --user 0`. It MUST run the following steps in this order:
1. `actions/checkout@v4`
2. `astral-sh/setup-uv`
3. `kicad-cli version`
4. `uv sync --locked --extra dev`
5. `actions/cache` of the corpus cache, keyed on `hashFiles('tests/corpus/manifest.toml')`
6. `uv run python tools/corpus_fetch.py --uses rt0 --uses libs --uses project --uses cfb --uses altium-text`
7. `uv run pytest tests/kicad tests/corpus -q -n auto --dist loadfile` with `FENOLITE_REQUIRE=kicad,corpus` and `FENOLITE_HEAVY=1`

The job MUST fail if any step fails. `tests/unit/test_ci_workflow.py` SHALL check the job textually, because the dev extra has no YAML parser: the digest pin, the container options, the order of the steps above, the cache key, `--uses libs`, `--uses project`, `--uses cfb` and `--uses altium-text` (the rows that c0039 and c0042 added to the workflow), `FENOLITE_HEAVY=1`, the environment variable and the parallel options of the pytest step.

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

#### Scenario: Heavy DIFAT input required
- **GIVEN** the three existing manifest rows tagged heavy
- **WHEN** the kicad-10 job runs
- **THEN** their input hashes are checked by corpus_fetch, heavy inputs are enabled, and convert-difat executes instead of reporting inconclusive because heavy inputs are off

#### Scenario: Heavy inputs disabled rejected
- **GIVEN** a workflow edit that excludes heavy rows or disables FENOLITE_HEAVY
- **WHEN** the workflow guard tests run
- **THEN** they fail naming kicad-10 and the missing heavy prerequisite

### Requirement: KiCad 9.0 oracle job
`.github/workflows/ci.yml` SHALL contain a job `kicad-9` that runs on every push and pull request inside the official image `kicad/kicad:9.0.9`, pinned by index digest (`@sha256:` followed by 64 hex digits), with the same container mechanism as the `kicad-10` job. It MUST run the following steps in order:
1. `kicad-cli version`
2. `uv sync --locked --extra dev`
3. `actions/cache` of the corpus cache named by `FENOLITE_CORPUS_CACHE`, keyed on `corpus-rt2-9-sch-9-downgrade-demo-${{ hashFiles('tests/corpus/manifest.toml') }}`
4. `uv run python tools/corpus_fetch.py --uses rt2-9 --uses sch-9 --uses downgrade-demo`
5. `uv run pytest tests/kicad -q -rA -n auto --dist loadfile` (every outcome listed in the log) with `FENOLITE_REQUIRE=kicad`

The job SHALL fetch only the corpus rows tagged `rt2-9` (corpus-policy, "RT2 rows for KiCad 9.0"), which are the five readable non-heavy demo boards at tag 9.0.9.1, and the rows tagged `sch-9` (corpus-policy, "Schematic corpus rows"), which are the demo schematics of the tree of tag 9.0.9.1, and the narrow `downgrade-demo` selection: only existing manifest entries inside the cm5_minima and pic_programmer demo folders at tag 10.0.6. Those newer inputs are converted to format 9 before native loading, as required by c0162. No other row is fetched. Its `needs_corpus` tests therefore run on those rows and skip every other row, and tests marked `kicad_min_major(10)` skip without failing. Tests marked `needs_kicad` fail instead of skipping when `kicad-cli` is missing. The job MUST fail if any step fails, and it SHALL be a required check for merging. `tests/unit/test_ci_workflow.py` SHALL check the job textually: the digest pin, the container options, the order of the steps above, the cache key, the single fetch with `--uses rt2-9 --uses sch-9 --uses downgrade-demo`, the environment variable and the parallel options of the pytest step.

#### Scenario: Job runs the 9.0 binary
- **GIVEN** a pull request that touches `src/`
- **WHEN** the `kicad-9` job runs
- **THEN** its log shows `kicad-cli version` reporting `9.0.9`, and `tests/kicad/test_environment.py` passes

#### Scenario: Workflow shape checked
- **GIVEN** the committed `ci.yml`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** it passes only if the job `kicad-9` exists, its image is `kicad/kicad:9.0.9@sha256:<64 hex>`, its steps follow the order above, its cache key is `corpus-rt2-9-sch-9-downgrade-demo-${{ hashFiles('tests/corpus/manifest.toml') }}`, its only corpus fetch is `uv run python tools/corpus_fetch.py --uses rt2-9 --uses sch-9 --uses downgrade-demo`, and its test step runs `uv run pytest tests/kicad -q -rA -n auto --dist loadfile` with `FENOLITE_REQUIRE=kicad`

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

#### Scenario: Downgrade inputs required
- **GIVEN** the KiCad-9 job with the two existing KiCad-10 downgrade source projects
- **WHEN** its downgrade demo probes run
- **THEN** both source projects are available, converted to format 9 before native loading, and compared against their unchanged frozen expected outcomes

#### Scenario: Downgrade selection remains narrow
- **GIVEN** a manifest edit that assigns downgrade-demo to an unrelated folder or omits a declared file of the two selected folders
- **WHEN** the workflow selection guard runs
- **THEN** it fails without fetching unrelated KiCad-10 projects
