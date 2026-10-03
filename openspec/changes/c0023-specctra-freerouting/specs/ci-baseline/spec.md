## ADDED Requirements

### Requirement: Freerouting in the routing job
The `routing` job of `.github/workflows/ci.yml` (c0016) SHALL also install Java 25 and download the Freerouting jar of `freerouting.PINNED_VERSION` from its release page, MUST verify the jar against a SHA-256 written in `ci.yml`, and MUST run `uv run pytest tests/routing -q -rA` with `FENOLITE_FREEROUTING_JAR` set and `freerouting` added to `FENOLITE_REQUIRE`. The job stays outside the merge gate. The marker `needs_freerouting` SHALL skip without the variable and fail, with the same message, when `FENOLITE_REQUIRE` lists `freerouting`. `tests/unit/test_ci_workflow.py` SHALL check the version, the checksum step and the environment textually.

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k freerouting` runs
- **THEN** it passes only if the job downloads the pinned version, verifies a 64-hex SHA-256 and sets `FENOLITE_FREEROUTING_JAR`

#### Scenario: Version drift caught
- **GIVEN** `PINNED_VERSION` changed in the plugin and not in `ci.yml`
- **WHEN** the same test runs
- **THEN** it fails naming both values
