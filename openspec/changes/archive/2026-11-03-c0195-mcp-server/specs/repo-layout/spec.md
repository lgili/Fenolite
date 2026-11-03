## MODIFIED Requirements

### Requirement: Zero runtime dependencies in the core
`pyproject.toml` SHALL declare `dependencies = []`. All third-party packages SHALL live in optional extras, and the only extras allowed are `geo`, `kicad-ipc`, `dev` and `oracles`. The former `route` extra is removed: it named a package that no code imports, and routers run as subprocesses and register through entry points. The former `mcp` extra is removed (change c0195): the MCP server uses the standard library, and the official SDK is a test oracle in `oracles`.

#### Scenario: Invariant test rejects a runtime dependency
- **GIVEN** a contributor adds `"shapely"` to `[project].dependencies`
- **WHEN** `pytest tests/unit/test_pyproject_invariants.py` runs
- **THEN** the test fails naming the offending dependency

#### Scenario: Invariant test rejects an unknown extra
- **GIVEN** a contributor adds an extra named `fast`, or adds `route` or `mcp` back
- **WHEN** `pytest tests/unit/test_pyproject_invariants.py` runs
- **THEN** the test fails naming the unknown extra

#### Scenario: Clean install pulls nothing else
- **WHEN** `uv pip install --dry-run .` runs in an empty environment
- **THEN** no package other than `fenolite` is scheduled for installation

