## ADDED Requirements

### Requirement: Board cut-outs and free holes of a document
The import SHALL give a region whose keys make a board cut-out as `Edge.Cuts` graphics of width 0 (a polygon, or lines and arcs from shape-based vertices), so `board_outline` takes it as a cut-out. A free pad on Multi-Layer without name, net or copper ring SHALL become a board `Hole` with its drill, plating, slot length and rotation; every other free pad stays a board-only footprint.

#### Scenario: Written fixture read back
- **GIVEN** the shared fixture built for Altium with `pcbdoc.CUTOUT_REGIONS` true in the test
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_free_holes.py` imports the document
- **THEN** `Board.holes` holds the round hole `H1`, `edge_outline` gives the three cut-out rings within 1 µm, and no board-only footprint is made for them
