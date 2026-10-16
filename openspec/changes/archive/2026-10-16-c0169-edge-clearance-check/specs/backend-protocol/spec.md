## ADDED Requirements

### Requirement: Board edges of a frame
`BoardFrame` SHALL give `board_edges(design, *, issues=None) -> tuple[EdgeRing, ...] | None`, a pure query: the board ring first, then each cut-out or slot ring, as `EdgeRing(name, points, mids)` with exact arcs, overlapping inner rings merged; `None` when no ring closes. `DesignRules` SHALL carry `min_edge_clearance: Nm | None` and `edge_floor_over_rules: bool`. The KiCad and Altium backends MUST implement both.

#### Scenario: Edges of a read KiCad board
- **GIVEN** the shared fixture built for target 10 and read back
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_frame_edges.py` calls `board_edges`
- **THEN** it gives the board ring and three cut-out rings, the merged L among them, named `board` and `edge ring 1` to `edge ring 3`
