## MODIFIED Requirements

### Requirement: kicad-10 oracle job
`.github/workflows/ci.yml` SHALL contain a job `kicad-10` that runs on every push and pull request on `ubuntu-latest`. The job runs inside the official image `kicad/kicad:10.0.6`, pinned by its index digest (`@sha256:` followed by 64 hex digits), with container `options: --user 0`. It MUST run the following steps in this order:
1. `actions/checkout@v4`
2. `astral-sh/setup-uv`
3. `kicad-cli version`
4. `uv sync --locked --extra dev`
5. `actions/cache` of the corpus cache, keyed on `hashFiles('tests/corpus/manifest.toml')`
6. `uv run python tools/corpus_fetch.py --uses rt0 --uses libs --exclude-uses heavy`
7. `uv run pytest tests/kicad tests/corpus -q` with `FENOLITE_REQUIRE=kicad,corpus`

The job MUST fail if any step fails. `tests/unit/test_ci_workflow.py` SHALL check the job textually, because the dev extra has no YAML parser: the digest pin, the container options, the order of the steps above, the cache key, `--uses libs`, `--exclude-uses heavy` and the environment variable.

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
