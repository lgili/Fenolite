## MODIFIED Requirements

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
