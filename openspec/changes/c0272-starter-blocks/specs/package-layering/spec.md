## ADDED Requirements

### Requirement: Shipped block library layering
The starter block modules of `fenolite.blocks` (`divider`, `rc`, `led`, `i2c`, `protect`) SHALL import only `fenolite.dsl` (with c0254's generators), `fenolite.core` and the standard library, a narrower set than the row that c0268 gives the package. The import-graph test MUST hold this row.

#### Scenario: Blocks stay above the DSL
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** no starter block module imports `fenolite.model`, `fenolite.backends`, `fenolite.cli` or `fenolite.testing`
