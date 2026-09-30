## ADDED Requirements

### Requirement: Installable package with a console entry point
The repository SHALL contain a `src`-layout Python package named `fenolite` that installs with `pip`/`uv` on Python 3.11+ and exposes a console script `fenolite`.

#### Scenario: Version is printed
- **GIVEN** a clean virtual environment with Python ≥ 3.11
- **WHEN** the user runs `uv pip install -e .` and then `fenolite --version`
- **THEN** the command exits with code 0 and prints `fenolite <version>` where `<version>` equals `fenolite.__version__`

#### Scenario: Module execution works
- **WHEN** the user runs `python -m fenolite --version`
- **THEN** the output and exit code are identical to `fenolite --version`

### Requirement: Zero runtime dependencies in the core
`pyproject.toml` SHALL declare `dependencies = []`. All third-party packages SHALL live in optional extras, and the only extras allowed at bootstrap are `geo`, `kicad-ipc`, `route`, `mcp`, `dev` and `oracles`.

#### Scenario: Invariant test rejects a runtime dependency
- **GIVEN** a contributor adds `"shapely"` to `[project].dependencies`
- **WHEN** `pytest tests/unit/test_pyproject_invariants.py` runs
- **THEN** the test fails naming the offending dependency

#### Scenario: Invariant test rejects an unknown extra
- **GIVEN** a contributor adds an extra named `fast`
- **WHEN** `pytest tests/unit/test_pyproject_invariants.py` runs
- **THEN** the test fails naming the unknown extra

#### Scenario: Clean install pulls nothing else
- **WHEN** `uv pip install --dry-run .` runs in an empty environment
- **THEN** no package other than `fenolite` is scheduled for installation

### Requirement: Version is single-sourced
The package version MUST be defined once in `src/fenolite/__init__.py` as `__version__` and MUST be the value used by the build backend and by `fenolite --version`.

#### Scenario: Build metadata matches the module
- **WHEN** `uv build` produces a wheel
- **THEN** the wheel's `Version` metadata equals `fenolite.__version__`

### Requirement: Standard directory layout
The repository SHALL contain the directories `src/fenolite/`, `tests/unit/`, `docs/adr/`, `docs/evidence/`, `docs/formats/`, `tools/`, `schemas/`, `examples/`, `openspec/` and `verify_results/`. Each non-package directory SHALL contain a `README.md` or `.gitkeep` explaining its purpose; a Python package directory satisfies the rule with its `__init__.py`.

#### Scenario: Layout check
- **WHEN** `pytest tests/unit/test_repo_layout.py` runs
- **THEN** every listed directory exists and contains a `README.md`, a `.gitkeep` or, for `src/fenolite/`, an `__init__.py`

### Requirement: Ignored paths
`.gitignore` SHALL ignore `private/`, `.fenolite/`, `.venv/`, `dist/`, `build/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `*.bak` and `.claude/*`.

#### Scenario: Private planning material never reaches the index
- **GIVEN** a file `private/notes.md` exists
- **WHEN** the user runs `git status --porcelain`
- **THEN** the file is not listed and `git check-ignore private/notes.md` succeeds
