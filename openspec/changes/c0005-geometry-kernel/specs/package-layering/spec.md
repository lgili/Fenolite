## MODIFIED Requirements

### Requirement: Third-party imports only in extras-guarded modules
Modules outside `core`, `model`, `geometry` and `dsl` MUST import third-party packages only inside a function or under `try/except ImportError` guarded by the extra name, and `import fenolite` SHALL succeed with no extras installed. Modules inside `core`, `model`, `geometry` and `dsl` MUST NOT import third-party packages, statically or through `importlib.import_module` or `__import__`, with one exception: `fenolite.geometry.boolean._extra.load_extra(name)` MAY load, at call time, a package whose import name is in its closed tuple `GEO_MODULES`, and SHALL be the only place in those four packages that calls `importlib.import_module` or `__import__`. `GEO_MODULES` MUST equal the import names of the packages listed in the `geo` extra of `pyproject.toml`, and `import fenolite.geometry` SHALL succeed with no extra installed.

#### Scenario: Bare import succeeds without extras
- **GIVEN** an environment with only `fenolite` installed
- **WHEN** `python -c "import fenolite, fenolite.cli.main"` runs
- **THEN** the exit code is 0

#### Scenario: Import inside a function in geometry fails
- **GIVEN** `src/fenolite/geometry/boolean/fallback.py` contains `import shapely` inside a function
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** the test fails naming the file and `shapely`

#### Scenario: Dynamic import outside the loader fails
- **GIVEN** `src/fenolite/geometry/polygon.py` calls `importlib.import_module("pyclipper")`
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** the test fails naming the file and stating that only `geometry/boolean/_extra.py` may load extras

#### Scenario: Loader list drifts from the extra
- **GIVEN** `pyproject.toml` adds a package to the `geo` extra and `GEO_MODULES` is not updated
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** the test fails naming the missing module

#### Scenario: Geometry imports without extras
- **GIVEN** an environment with only `fenolite` installed
- **WHEN** `python -c "import fenolite.geometry, fenolite.geometry.boolean"` runs
- **THEN** the exit code is 0
