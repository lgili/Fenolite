## MODIFIED Requirements

### Requirement: Zero runtime dependencies in the core
`pyproject.toml` SHALL declare `dependencies = []`. All third-party packages SHALL live in optional extras, and the only extras allowed are `geo`, `kicad-ipc`, `mcp`, `dev`, `oracles` and `devices`. The former `route` extra is removed: it named a package that no code imports, and routers run as subprocesses and register through entry points. The `devices` extra MUST name only the data-only distribution `fenolite-devices` with an exact version, and no module of it SHALL be imported.

#### Scenario: Invariant test rejects a runtime dependency
- **GIVEN** a contributor adds `"shapely"` to `[project].dependencies`
- **WHEN** `pytest tests/unit/test_pyproject_invariants.py` runs
- **THEN** the test fails naming the offending dependency

#### Scenario: Invariant test rejects an unknown extra
- **GIVEN** a contributor adds an extra named `fast`, or adds `route` back
- **WHEN** `pytest tests/unit/test_pyproject_invariants.py` runs
- **THEN** the test fails naming the unknown extra

#### Scenario: Clean install pulls nothing else
- **WHEN** `uv pip install --dry-run .` runs in an empty environment
- **THEN** no package other than `fenolite` is scheduled for installation

#### Scenario: The devices extra is pinned data
- **GIVEN** a contributor writes `devices = ["fenolite-devices>=1.0"]`
- **WHEN** `pytest tests/unit/test_pyproject_invariants.py` runs
- **THEN** the test fails asking for an exact `==` version
