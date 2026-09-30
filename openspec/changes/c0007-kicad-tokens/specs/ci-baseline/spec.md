## ADDED Requirements

### Requirement: KiCad 9.0 oracle job
`.github/workflows/ci.yml` SHALL contain a job `kicad-9` that runs on every push and pull request inside the official image `kicad/kicad:9.0.9`, pinned by index digest (`@sha256:` followed by 64 hex digits), with the same container mechanism as the `kicad-10` job. It MUST run the following steps in order:
1. `kicad-cli version`
2. `uv sync --locked --extra dev`
3. `uv run pytest tests/kicad -q` with `FENOLITE_REQUIRE=kicad`

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
