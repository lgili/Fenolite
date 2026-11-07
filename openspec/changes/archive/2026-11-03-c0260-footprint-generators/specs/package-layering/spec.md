## ADDED Requirements

### Requirement: Generated footprints are imported lazily
`Footprint.from_package` SHALL import `fenolite.catalog.footprints` inside its method body. The package edge `dsl` → `catalog` is already allowed by "Allowed import edges" for c0248 device lookup; this method-local implementation MUST NOT narrow that package-wide permission or require a second `LAZY` entry. `catalog` MUST NOT import `dsl`.

#### Scenario: Lazy edge of the DSL
- **GIVEN** `src/fenolite/dsl/footprint.py` importing `fenolite.catalog.footprints` inside `Footprint.from_package`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes under the existing `dsl` → `catalog` permission; the existing reverse-edge control still fails naming `catalog → dsl`, and `Footprint.from_package` keeps its generator import inside the method body
