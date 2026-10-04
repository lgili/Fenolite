# repo-layout Specification

## Purpose
Keep Fenolite installable, importable and dependency-free at its core: package layout, single-sourced version, console entry point, the closed list of optional extras, the documented directory layout and the paths that are never committed.
## Requirements
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
`pyproject.toml` SHALL declare `dependencies = []`. All third-party packages SHALL live in optional extras, and the only extras allowed are `geo`, `kicad-ipc`, `mcp`, `dev` and `oracles`. The former `route` extra is removed: it named a package that no code imports, and routers run as subprocesses and register through entry points.

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

### Requirement: Package metadata
`pyproject.toml` SHALL declare `[project.urls]` with exactly the keys `Homepage`, `Source`, `Issues` and `Changelog`. `Homepage` and `Source` MUST be `https://github.com/lgili/Fenolite`, `Issues` that address followed by `/issues`, and `Changelog` that address followed by `/blob/main/CHANGELOG.md`. The classifiers MUST hold exactly one `Development Status ::` entry, and it MUST be `Development Status :: 3 - Alpha` until a later change raises it.

#### Scenario: Metadata checked
- **WHEN** `uv run pytest tests/unit/test_pyproject_invariants.py -k "urls or classifier"` runs
- **THEN** it passes, and the checks it calls report a problem for a missing key of `[project.urls]`, for an address outside the repository and for the status `2 - Pre-Alpha`

### Requirement: Source distribution contents
The `sdist` target of `pyproject.toml` SHALL use an allowlist (`[tool.hatch.build.targets.sdist] include`) and no `exclude` list, so that a file left in the repository root never ships. The allowlist MUST be exactly `/src`, `/tests`, `/docs`, `/examples`, `/schemas`, `/tools`, `/README.md`, `/CHANGELOG.md`, `/CONTRIBUTING.md`, `/LEGAL.md`, `/LEGAL-ANNEX.md`, `/LICENSE` and `/NOTICE`.
- The built archive MUST NOT hold `openspec/`, `AGENTS.md`, `CLAUDE.md`, `packaging/`, `private/`, `dogfood/`, `uv.lock`, `Makefile` or any file whose name contains `.bak`.
- A wheel built from that archive MUST list the same files as the wheel built before this change.

#### Scenario: Allowlist checked
- **WHEN** `uv run pytest tests/unit/test_pyproject_invariants.py -k sdist` runs
- **THEN** it passes, and the check it calls reports a problem for a table with an `exclude` key and for an `include` list that holds `/openspec`

#### Scenario: Built archive
- **GIVEN** a working tree that holds an untracked file `AGENTS.md.bak-1` in the root
- **WHEN** `uv build --out-dir <scratch>` runs and the archive is listed with `tar tzf`
- **THEN** the top-level names are `src`, `tests`, `docs`, `examples`, `schemas`, `tools`, the seven documents of the allowlist, and the files the build backend adds itself (`pyproject.toml`, `PKG-INFO`, `.gitignore`); the wheel is built from the archive

