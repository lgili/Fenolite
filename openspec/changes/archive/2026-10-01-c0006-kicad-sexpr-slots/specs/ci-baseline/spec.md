## ADDED Requirements

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
