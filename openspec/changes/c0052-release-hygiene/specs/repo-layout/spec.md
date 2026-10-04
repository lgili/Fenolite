## MODIFIED Requirements

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

## ADDED Requirements

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
