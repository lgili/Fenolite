## ADDED Requirements

### Requirement: Generated footprints are imported lazily
`fenolite.dsl` MAY import `fenolite.catalog.footprints` inside the body of `Footprint.from_package` only; the layering test SHALL list the edge `dsl` → `catalog` in its `LAZY` table and SHALL fail a top-level one. `catalog` MUST NOT import `dsl`. (When change c0248 adds `dsl` → `catalog` to the allowed edges, this lazy edge stays valid.)

#### Scenario: Lazy edge of the DSL
- **GIVEN** `src/fenolite/dsl/footprint.py` importing `fenolite.catalog.footprints` inside `Footprint.from_package`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes, and the same import at the top of the module fails naming `dsl → catalog`
