## ADDED Requirements

### Requirement: Allowed import edges
Sub-packages of `fenolite` MUST only import from their own package, from `core` (which every package MAY import), and from the packages listed for them: `core` → standard library only; `model` → nothing else; `geometry` → nothing else; `dsl` → `model`; `lens` → `model`, `backends`; `backends` (its top-level modules such as `base` and `registry`) → `model`, `geometry`, any `backends.<x>`; `backends.<x>` → `model`, `geometry`, `backends.base`; `libs` → `model`, `geometry`; `checks`, `analysis`, `placement` → `model`, `geometry`, `backends.base`; `routing` (its `protocol` and other top-level modules) → `model`, `geometry`; `routing.plugins.<x>` → `routing`, `backends.<x>`; `templates` → `model`; `render`, `exports`, `convert`, `verify` → `model`, `geometry`, `backends`; `cli` and the root modules `fenolite/__init__.py`, `fenolite/__main__.py` → any `fenolite` package; `agent` → `cli`. A sub-package that is not in this table MUST be added to it before it is created.

#### Scenario: Forbidden edge fails
- **GIVEN** `src/fenolite/model/board.py` imports `fenolite.backends.kicad`
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** the test fails naming `model → backends.kicad`

#### Scenario: Core stays stdlib-only
- **GIVEN** `src/fenolite/core/io.py` imports `shapely`
- **WHEN** the test runs
- **THEN** the test fails naming the third-party import

### Requirement: Third-party imports only in extras-guarded modules
Modules outside `core`, `model`, `geometry` and `dsl` MUST import third-party packages only inside a function or under `try/except ImportError` guarded by the extra name, and `import fenolite` SHALL succeed with no extras installed.

#### Scenario: Bare import succeeds without extras
- **GIVEN** an environment with only `fenolite` installed
- **WHEN** `python -c "import fenolite, fenolite.cli.main"` runs
- **THEN** the exit code is 0
