## MODIFIED Requirements

### Requirement: Freerouting in the routing job
The `routing` job of `.github/workflows/ci.yml` (c0016) SHALL also install Java 25 and install the Freerouting jar of `freerouting.PINNED_VERSION` with `uv run fenolite fetch freerouting --dir /tmp/freerouting --confirm --json` (`cli-contract`, "Fetch command"), which downloads it from its release page and writes it only when its size and its SHA-256 are those of the table row; the job MUST NOT download the jar in any other way. It MUST run `uv run pytest tests/routing -q -rA` with `FENOLITE_FREEROUTING_JAR` set to the fetched file and `freerouting` added to `FENOLITE_REQUIRE`. The job stays outside the merge gate. The marker `needs_freerouting` SHALL skip without the variable and fail, with the same message, when `FENOLITE_REQUIRE` lists `freerouting`. `tests/unit/test_ci_workflow.py` SHALL check the install step, the version and the environment textually.

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k freerouting` runs
- **THEN** it passes only if the job installs the jar with `fenolite fetch freerouting --confirm` after Fenolite is installed and before the tests, downloads it in no other way, and sets `FENOLITE_FREEROUTING_JAR` to the file of the pinned version in the folder of `--dir`

#### Scenario: Version drift caught
- **GIVEN** `PINNED_VERSION` changed in the plugin and not in `ci.yml`
- **WHEN** the same test runs
- **THEN** it fails naming both values
