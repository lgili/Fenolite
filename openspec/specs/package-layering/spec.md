# package-layering Specification

## Purpose
Keep the dependency graph between `fenolite` sub-packages acyclic and intentional, and keep the core importable with no third-party packages installed.
## Requirements
### Requirement: Allowed import edges
Sub-packages of `fenolite` MUST only import from their own package, from `core` (which every package MAY import), and from the packages listed for them: `core` → standard library only; `model` → nothing else; `geometry` → nothing else; `dsl` → `model`; `catalog` → `model`; `lens` → `model`, `backends`; `backends` (its top-level modules such as `base` and `registry`) → `model`, `geometry`, any `backends.<x>`; `backends.<x>` → `model`, `geometry`, `backends.base`; `libs` → `model`, `geometry`; `checks`, `analysis`, `placement` → `model`, `geometry`, `backends.base`; `routing` (its `protocol` and other top-level modules) → `model`, `geometry`; `routing.plugins.<x>` → `routing`, `model`, `geometry`, `backends.<x>`; `templates` → `model`; `render`, `exports`, `convert`, `verify` → `model`, `geometry`, `backends`; `view` → `model`, `geometry`, `backends`, any `backends.<x>`; `api` → `model`, `geometry`, `backends`, any `backends.<x>`, `checks`, `analysis`, `convert`, `lens`; `panel` → `model`, `geometry`, `backends`, any `backends.<x>`, `checks`, `convert`, `dsl` (the panel of change c0173: it lays out a board read by a backend, judges it with `checks`, reads it as a conversion reads it, and builds c0118's generated footprints with `dsl`; `dsl` does not import `panel`); `cli` and the root modules `fenolite/__init__.py`, `fenolite/__main__.py` → any `fenolite` package; `roles` → `model`, `geometry`, `backends.base`, `analysis`; `agent` → `cli`. No package but `cli`, `agent` and the root modules MAY import `api`. No package but `cli` and the root modules MAY import `roles`. A sub-package that is not in this table MUST be added to it before it is created.

A router plugin returns model entities and transforms pads, so it imports `model` and `geometry` as its backend does; it still MUST NOT import another backend or `backends.base` consumers such as `checks`.

#### Scenario: Forbidden edge fails
- **GIVEN** `src/fenolite/model/board.py` imports `fenolite.backends.kicad`
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** the test fails naming `model → backends.kicad`

#### Scenario: Public API stays on top
- **GIVEN** `src/fenolite/checks/equivalence/levels.py` imports `fenolite.api`
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** the test fails naming `checks → api`, and `src/fenolite/api/sides.py` importing `fenolite.backends.registry` and `fenolite.checks.equivalence` passes

#### Scenario: Core stays stdlib-only
- **GIVEN** `src/fenolite/core/io.py` imports `shapely`
- **WHEN** the test runs
- **THEN** the test fails naming the third-party import

#### Scenario: Plugin imports its backend and the model
- **GIVEN** `src/fenolite/routing/plugins/kicad/routingtools.py` importing `fenolite.backends.kicad.pcb`, `fenolite.model.board` and `fenolite.routing.protocol`
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes; the same module importing `fenolite.backends.specctra` or `fenolite.checks` makes it fail naming the edge

#### Scenario: The viewer imports the readers, not the checks
- **GIVEN** `src/fenolite/view/scene.py` importing `fenolite.backends.base` and `fenolite.model.board`
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes; the same module importing `fenolite.checks` makes it fail naming `view → checks`

#### Scenario: Panels on top of the backends
- **GIVEN** `src/fenolite/panel/kicad.py` importing `fenolite.backends.kicad.embed` and `fenolite.dsl.assembly`, and `src/fenolite/dsl/panel.py` importing only `fenolite.model` and `fenolite.core`
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes; `src/fenolite/dsl/panel.py` importing `fenolite.panel` makes it fail naming `dsl → panel`

#### Scenario: Roles read the analyses, checks do not
- **GIVEN** `src/fenolite/roles/measure.py` importing `fenolite.analysis.shapes` and `src/fenolite/checks/roles.py` importing only `fenolite.checks.stages`, `fenolite.model.design` and `fenolite.backends.base`
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes; `src/fenolite/checks/roles.py` importing `fenolite.roles` or `fenolite.analysis` makes it fail naming the edge, and so does `src/fenolite/roles/measure.py` importing `fenolite.backends.kicad`

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

### Requirement: Public API runs the commands lazily
`fenolite.api` MAY import `cli` inside a function body only, for `fenolite.api.run`; the layering test SHALL list such edges in its `LAZY` table and SHALL fail a top-level one, naming it. `import fenolite.api` MUST NOT import any module of `fenolite.cli`.

#### Scenario: Lazy edge only
- **GIVEN** `src/fenolite/api/commands.py` importing `fenolite.cli.main` inside a function, then at the top of the module
- **WHEN** `uv run pytest tests/unit/test_import_graph.py -k "lazily or loads_no_command"` runs
- **THEN** the first passes, the second fails naming `api → cli`, and a fresh `import fenolite.api` loads no `fenolite.cli` module

### Requirement: Shipped block library layering
The starter block modules of `fenolite.blocks` (`divider`, `rc`, `led`, `i2c`, `protect`) SHALL import only `fenolite.dsl` (with c0254's generators), `fenolite.core` and the standard library, a narrower set than the row that c0268 gives the package. The import-graph test MUST hold this row.

#### Scenario: Blocks stay above the DSL
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** no starter block module imports `fenolite.model`, `fenolite.backends`, `fenolite.cli` or `fenolite.testing`

### Requirement: Shipped self tests remain tool free
The shipped `fenolite.blocks.tests` modules MAY import `fenolite.testing` and the standard library to run plain zero-argument test functions. They MUST NOT import a test framework or add a runtime dependency. This exception MUST NOT widen the permitted imports of starter block bodies.

#### Scenario: Installed self tests run without pytest
- **WHEN** `fenolite blocks test --json` runs with external tool calls refused
- **THEN** every shipped plain test runs through `fenolite.testing` without importing pytest

### Requirement: Generated footprints are imported lazily
`Footprint.from_package` SHALL import `fenolite.catalog.footprints` inside its method body. The package edge `dsl` → `catalog` is already allowed by "Allowed import edges" for c0248 device lookup; this method-local implementation MUST NOT narrow that package-wide permission or require a second `LAZY` entry. `catalog` MUST NOT import `dsl`.

#### Scenario: Lazy edge of the DSL
- **GIVEN** `src/fenolite/dsl/footprint.py` importing `fenolite.catalog.footprints` inside `Footprint.from_package`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes under the existing `dsl` → `catalog` permission; the existing reverse-edge control still fails naming `catalog → dsl`, and `Footprint.from_package` keeps its generator import inside the method body

### Requirement: Lazy source BOM preservation at the API boundary
The API MAY import exactly `fenolite.importer.bom_only` inside function bodies of `api/_drawn.py` and `api/sides.py` to preserve source purchasing instances using the importer's shared hierarchy and identity traversal. This grants no other API-to-importer edge. Top-level imports, imports guarded only by ImportError, and other importer modules MUST remain forbidden. Fresh `import fenolite.api` MUST load no importer module.

#### Scenario: Exact lazy boundary only
- **WHEN** the import-graph controls exercise permitted imports, top-level imports,
  guarded imports, other API modules and other importer targets
- **THEN** only the exact function-body edges pass and a fresh API import loads no importer

#### Scenario: Repeated source identity survives
- **WHEN** the API reads purchasing instances in repeated sheet modules
- **THEN** the shared complete traversal retains source identities and electrical partitions

### Requirement: Draftsman drawing preparation imports
`lens.altium_draftsman` MAY import only `exports.drawing_spec`, `drawing_layout` and `drawing_tables` for pure preparation; `lens.altium` MAY import `drawing_spec` for its value/default. The general lens import row MUST stay unchanged. Altium backends MUST NOT import exports, and no lens exception MAY admit plotting or export runners.

#### Scenario: Preparation stays pure and bounded
- **WHEN** the import guard and candidate packing tests run
- **THEN** only those exact module edges are accepted, `exports.drawings` remains forbidden, and packing starts no subprocess

### Requirement: Supplier package boundary
`suppliers` SHALL import only its own package, `core`, `pick`, `catalog` and `model`, with third-party keyring imported lazily. No other source package SHALL import `suppliers` directly; callers MUST use the `fenolite.suppliers` entry points. Static discovery and code metadata MUST stay outside the provider runtime. All existing package import edges MUST remain unchanged.

#### Scenario: Suppliers stay behind the entry points
- **GIVEN** a supplier imports pick and catalog, and CLI discovers it through metadata
- **WHEN** the import-graph proof runs
- **THEN** it passes; a direct CLI, DSL or pick import of suppliers fails, as does a supplier import of DSL

