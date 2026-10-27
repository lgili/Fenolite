## ADDED Requirements

### Requirement: Inferred evidence names a hypothesis
Every `Evidence` that the package builds with level `INFERRED` SHALL name at least one registered hypothesis.
- A test MUST read every module under `src/fenolite/` and fail on `Evidence(Level.INFERRED, ...)` without hypotheses.
- A call that is an argument of `Evidence.combine` is allowed, as it only caps the level.
- Any other exception MUST be named in the test with its reason, and the test MUST fail when that call is gone.

#### Scenario: A bare inferred evidence fails
- **GIVEN** a module that builds `Evidence(Level.INFERRED)` outside `Evidence.combine` and outside the named exceptions
- **WHEN** `uv run pytest tests/unit/test_inferred_hypotheses.py` runs
- **THEN** it fails and names the module, the line and the function

#### Scenario: The cited rows are registered
- **WHEN** `uv run pytest tests/unit/test_inferred_hypotheses.py -k registered` runs
- **THEN** the eight rows of change c0200 are rows of `docs/hypotheses.md` and each is cited in the package
