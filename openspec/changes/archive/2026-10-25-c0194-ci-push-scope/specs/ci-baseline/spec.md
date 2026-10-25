## ADDED Requirements

### Requirement: Pushes that run CI
`.github/workflows/ci.yml` SHALL run on a push of any branch except a branch under `backup/`, and on every pull request; a push of a tag SHALL run no job of it (change c0194).
- The `push` trigger MUST hold exactly the branch filters `"**"` and `"!backup/**"`, and no `tags` filter.
- `tests/unit/test_ci_workflow.py` MUST check the trigger textually.

#### Scenario: Trigger checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k push_trigger` runs
- **THEN** it passes only if the `on` block of `ci.yml` is the branch filter above and `pull_request:`

#### Scenario: Tags run nothing
- **GIVEN** a copy of `ci.yml` whose push trigger has no filter
- **WHEN** the trigger check runs on it
- **THEN** it fails and says that a tag push would run CI
