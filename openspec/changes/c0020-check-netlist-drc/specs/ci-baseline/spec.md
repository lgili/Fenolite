## MODIFIED Requirements

### Requirement: KiCad 9.0 oracle job
`.github/workflows/ci.yml` SHALL contain a job `kicad-9` that runs on every push and pull request inside the official image `kicad/kicad:9.0.9`, pinned by index digest (`@sha256:` followed by 64 hex digits), with the same container mechanism as the `kicad-10` job. It MUST run the following steps in order:
1. `kicad-cli version`
2. `uv sync --locked --extra dev`
3. `actions/cache` of the corpus cache named by `FENOLITE_CORPUS_CACHE`, keyed on `corpus-rt2-9-${{ hashFiles('tests/corpus/manifest.toml') }}`
4. `uv run python tools/corpus_fetch.py --uses rt2-9`
5. `uv run pytest tests/kicad -q -rA` (every outcome listed in the log) with `FENOLITE_REQUIRE=kicad`

The job SHALL fetch only the corpus rows tagged `rt2-9` (corpus-policy, "RT2 rows for KiCad 9.0"), which are the five readable non-heavy demo boards at tag 9.0.9.1, and no other row. Its `needs_corpus` tests therefore run on those rows and skip every other row, and tests marked `kicad_min_major(10)` skip without failing. Tests marked `needs_kicad` fail instead of skipping when `kicad-cli` is missing. The job MUST fail if any step fails, and it SHALL be a required check for merging. `tests/unit/test_ci_workflow.py` SHALL check the job textually: the digest pin, the container options, the order of the steps above, the cache key, the single fetch with `--uses rt2-9` and the environment variable.

#### Scenario: Job runs the 9.0 binary
- **GIVEN** a pull request that touches `src/`
- **WHEN** the `kicad-9` job runs
- **THEN** its log shows `kicad-cli version` reporting `9.0.9`, and `tests/kicad/test_environment.py` passes

#### Scenario: Workflow shape checked
- **GIVEN** the committed `ci.yml`
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py` runs
- **THEN** it passes only if the job `kicad-9` exists, its image is `kicad/kicad:9.0.9@sha256:<64 hex>`, its steps follow the order above, its cache key is `corpus-rt2-9-${{ hashFiles('tests/corpus/manifest.toml') }}`, its only corpus fetch is `uv run python tools/corpus_fetch.py --uses rt2-9`, and its test step runs `uv run pytest tests/kicad -q` with `FENOLITE_REQUIRE=kicad`

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
