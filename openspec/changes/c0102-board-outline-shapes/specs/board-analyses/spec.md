## MODIFIED Requirements

### Requirement: Board boundary
`fenolite.analysis.boundary.board_boundary(board, *, arc_tol=DEFAULT_TOL, thickness=None) -> BoardBoundary` SHALL return the frozen record `BoardBoundary(outer, cutouts, thickness, band, source)`: the outer ring, the cut-out rings, the board thickness, the bound in nanometres of the approximation of curved edges, and `source`, one of `model`, `edge` and `none`.
- With `Board.outline`, `outer` MUST be its board ring and `cutouts` its cut-outs, each with the arcs of `Outline.arcs` (`design-model`, "Board outline arcs") replaced by their polygonisation at `arc_tol`, and `source` MUST be `model`. `band` MUST then be `arc_tol + 1` when the outline holds an arc, and 0 otherwise.
- Otherwise the graphics on the layer of kind `edge` MUST be chained with `geometry.assemble_rings` by exact endpoint equality. Arcs and circles MUST be replaced by their polygonisation at `arc_tol`, and `band` MUST then be `arc_tol + 1`. The ring of largest area is `outer`; a ring inside it is a cut-out. `source` is `edge`.
- When no ring closes, or a `GeometryError` is raised, `source` MUST be `none` and `outer` empty; the function MUST NOT raise.
- `thickness` MUST be the argument when given, else the sum of the `thickness` of `Board.stackup.layers`, else `None`. Fenolite MUST NOT assume a board thickness.

#### Scenario: Outline from the model
- **GIVEN** a board whose `outline` is a 20 mm × 10 mm rectangle with one rectangular cut-out
- **WHEN** `uv run pytest tests/unit/analysis/test_boundary.py -k model` calls `board_boundary(board, thickness=1_600_000)`
- **THEN** `source == "model"`, `band == 0`, `len(cutouts) == 1` and `thickness == 1_600_000`

#### Scenario: Outline from edge graphics
- **GIVEN** a board without `outline` whose `edge` layer holds four lines closing a rectangle and four lines closing a slot inside it
- **WHEN** `board_boundary(board)` runs
- **THEN** `source == "edge"`, `outer` has four points, `cutouts` holds one ring and `thickness is None`

#### Scenario: Open contour
- **GIVEN** a board whose `edge` layer holds three lines that do not close
- **WHEN** `board_boundary(board)` runs
- **THEN** `source == "none"` and nothing raised

#### Scenario: Model outline with a round cut-out
- **GIVEN** a board whose `outline` is a 20 mm × 10 mm rectangle with a cut-out of the two vertices (11 mm, 5 mm) and (9 mm, 5 mm) joined by the arcs through (10 mm, 4 mm) and (10 mm, 6 mm)
- **WHEN** `uv run pytest tests/unit/analysis/test_boundary.py -k model_arcs` calls `board_boundary(board)`
- **THEN** `source == "model"`, `band == DEFAULT_TOL + 1`, and the one cut-out has more than two vertices, each within 1 nm of the circle of radius 1 mm centred at (10 mm, 5 mm)
