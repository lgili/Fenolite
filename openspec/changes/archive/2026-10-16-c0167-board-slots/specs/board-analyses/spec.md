## MODIFIED Requirements

### Requirement: Board boundary
`fenolite.analysis.boundary.board_boundary(board, *, arc_tol=DEFAULT_TOL, thickness=None) -> BoardBoundary` SHALL return the frozen record `BoardBoundary(outer, cutouts, thickness, band, source, problem)`: the outer ring, the cut-out rings, the board thickness, the bound in nanometres of the approximation of curved edges, `source`, one of `model`, `edge` and `none`, and `problem`, `None` or a short reason.
- With `Board.outline`, `outer` MUST be its board ring and `cutouts` its cut-outs and the stadiums of its slots (`design-model`, "Board slots"), overlapping ones merged by `geometry.rings.merge_rings`, each with its arcs replaced by their polygonisation at `arc_tol`, and `source` MUST be `model`. `band` MUST then be `arc_tol + 1` when the outline holds an arc or a slot, and 0 otherwise. When cut-outs or slots overlap and no backend gives `union`, `source` MUST be `none` and `problem` `overlap-needs-geo`.
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

#### Scenario: Slots in the boundary
- **GIVEN** the shared fixture `tests/data/slots/design.py` converted with `to_model`
- **WHEN** `uv run pytest tests/unit/analysis/test_boundary.py -k slots` calls `board_boundary`, with the `geo` extra and with `pyclipper` hidden
- **THEN** the first gives three cut-outs (the lone slot, the merged L, the rounded cut-out) and `band == DEFAULT_TOL + 1`; the second gives `source == "none"` and `problem == "overlap-needs-geo"`
