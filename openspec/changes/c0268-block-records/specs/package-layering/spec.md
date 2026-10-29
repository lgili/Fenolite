## MODIFIED Requirements

### Requirement: Allowed import edges
Sub-packages of `fenolite` MUST only import from their own package, from `core` (which every package MAY import), and from the packages listed for them: `core` → standard library only; `model` → nothing else; `geometry` → nothing else; `dsl` → `model`; `catalog` → `model`; `lens` → `model`, `backends`; `backends` (its top-level modules such as `base` and `registry`) → `model`, `geometry`, any `backends.<x>`; `backends.<x>` → `model`, `geometry`, `backends.base`; `libs` → `model`, `geometry`; `checks`, `analysis`, `placement` → `model`, `geometry`, `backends.base`; `roles` → `model`, `geometry`, `backends.base`, `analysis`; `routing` (its `protocol` and other top-level modules) → `model`, `geometry`; `routing.plugins.<x>` → `routing`, `model`, `geometry`, `backends.<x>`; `templates` → `model`; `blocks` → `dsl`, `model`; `render`, `exports`, `convert`, `verify` → `model`, `geometry`, `backends`; `view` → `model`, `geometry`, `backends`, any `backends.<x>`; `api` → `model`, `geometry`, `backends`, any `backends.<x>`, `checks`, `analysis`, `convert`, `lens`; `cli` and the root modules `fenolite/__init__.py`, `fenolite/__main__.py` → any `fenolite` package; `agent` → `cli`. No package but `cli`, `agent` and the root modules MAY import `api`. No package but `cli` and the root modules MAY import `roles`. No package but `cli` and the root modules MAY import `blocks`; a design script or a block package imports it as any user code does. A sub-package that is not in this table MUST be added to it before it is created.

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

#### Scenario: Shipped blocks build on the DSL only
- **GIVEN** `src/fenolite/blocks/divider.py` importing `fenolite.dsl` and `fenolite.core.units`
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes; the same module importing `fenolite.catalog` or `fenolite.backends` makes it fail naming the edge, and `src/fenolite/dsl/block.py` importing `fenolite.blocks` makes it fail naming `dsl → blocks`

#### Scenario: Roles read the analyses, checks do not
- **GIVEN** `src/fenolite/roles/measure.py` importing `fenolite.analysis.shapes` and `src/fenolite/checks/roles.py` importing only `fenolite.checks.stages`, `fenolite.model.design` and `fenolite.backends.base`
- **WHEN** `pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes; `src/fenolite/checks/roles.py` importing `fenolite.roles` or `fenolite.analysis` makes it fail naming the edge, and so does `src/fenolite/roles/measure.py` importing `fenolite.backends.kicad`
