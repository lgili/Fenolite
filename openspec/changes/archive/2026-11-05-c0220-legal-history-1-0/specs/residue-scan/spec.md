## MODIFIED Requirements

### Requirement: Integration points
The residue scan SHALL run as a step of the CI `unit` job, SHALL be runnable as `pytest tests/residue`, and SHALL be installable as a git pre-commit hook via `make hooks`. Its `--history` mode, which reads every blob reachable from any ref, MUST run in `.github/workflows/release.yml` before the distribution is built and in `.github/workflows/nightly.yml`, and a hit MUST fail that job. `make residue-history` MUST run `--history` with the private lists that the `Makefile` exports, so that the maintainer can run the private gate over the whole history; the summary line it prints holds counts only.

#### Scenario: Hook blocks a commit
- **GIVEN** the hook is installed and a staged file contains a structural hit
- **WHEN** `git commit` runs
- **THEN** the commit is refused and the hook output names the file

#### Scenario: The release scans the history
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k history` reads `release.yml` and `nightly.yml`
- **THEN** each runs `tools/residue/scan.py --history`, the release before its build step

#### Scenario: The private run prints counts
- **GIVEN** private lists configured in `private/`
- **WHEN** `make residue-history` runs
- **THEN** its last line is the summary with the counts of hits, files and waivers and `private gate: on`, and it names no private token
