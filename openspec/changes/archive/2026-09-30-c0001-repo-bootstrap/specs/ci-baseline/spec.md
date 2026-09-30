## ADDED Requirements

### Requirement: Unit CI job on two operating systems
The repository SHALL contain a GitHub Actions workflow `.github/workflows/ci.yml` with a job `unit` that runs on every push and pull request, on `ubuntu-latest` and `macos-latest`, with Python 3.12, using `uv`.

#### Scenario: Both runners execute the job
- **WHEN** a pull request is opened
- **THEN** two `unit` runs appear, one per operating system, and the pull request cannot merge while either is failing

### Requirement: Quality gates
The `unit` job MUST run, in order, `uv sync --extra dev`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright src`, `uv run pytest -q`, and MUST fail if any step fails.

#### Scenario: Lint error fails the job
- **GIVEN** a source file with an unused import
- **WHEN** the workflow runs
- **THEN** the `ruff check` step fails and the job is marked failed

#### Scenario: Type error fails the job
- **GIVEN** a function in `src/` that returns `str` where `int` is declared
- **WHEN** the workflow runs
- **THEN** the `pyright src` step fails

### Requirement: Locked, reproducible environment
`uv.lock` SHALL be committed and the CI job SHALL use `uv sync --locked` semantics so that a drifted lockfile fails the build.

#### Scenario: Drifted lockfile
- **GIVEN** `pyproject.toml` adds a dev dependency without updating `uv.lock`
- **WHEN** the workflow runs
- **THEN** the sync step fails with a lockfile mismatch

### Requirement: Local parity
The same four commands SHALL be runnable locally through a `Makefile` target `make check` (or `uv run task check`) so that contributors reproduce CI before pushing.

#### Scenario: Local check
- **WHEN** a contributor runs `make check` on a clean checkout
- **THEN** the same four steps run and the exit code is non-zero if any fails
