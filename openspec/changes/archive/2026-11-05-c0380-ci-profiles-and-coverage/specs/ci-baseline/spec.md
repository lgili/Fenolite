## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: kicad-10 oracle job

Full CI SHALL retain pinned KiCad 10.0.6, all current corpus uses, geo, FENOLITE_HEAVY=1 and FENOLITE_REQUIRE=kicad,corpus,libs. All tests/kicad and tests/corpus node ids plus whole resource-bearing unit files SHALL execute in four audited whole-file partitions with loadfile scheduling and container-local temporary files. Fast MAY omit these jobs only without satisfying the full gate.

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
