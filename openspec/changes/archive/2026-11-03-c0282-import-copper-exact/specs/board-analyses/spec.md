## MODIFIED Requirements

### Requirement: Copper of a net as thick shapes
`fenolite.analysis.copper.net_copper` SHALL group copper `Thick` shapes by net and layer. Tracks, vias, pads and fills use the copper check's shapes. Arcs remain polylines at `arc_tol`, with band `arc_tol + 1`; their underlying arc and width MUST match the check's exact arc. Keep kind, locator and entity id, count unsupported items by kind and omit netless copper. `fenolite.analysis` MUST NOT import `fenolite.checks`.

#### Scenario: Shapes equal the copper check's
- **GIVEN** generated boards with tracks, arcs, vias, fills and authored pad records
- **WHEN** `uv run pytest tests/unit/analysis/test_copper.py -k same_shapes` compares both builders
- **THEN** non-arc shapes match exactly and analysis arcs match polygonisations of the check's exact arcs, retaining their widths and declared bands

#### Scenario: Layering holds
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** analysis imports no checks module
