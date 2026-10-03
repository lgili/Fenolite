## ADDED Requirements

### Requirement: Board-frame protocol
`fenolite.backends.base` SHALL define the plain-data records through which `checks`, `placement` and `lens` read the board-frame geometry of a design without importing a backend, and the protocol `BoardFrame` that computes them:
- `PadCopper(layer: str, core: tuple[Point, ...], width: Nm, filled: bool = False, exact: bool = True)`: the copper of a pad on one copper layer, the set of points within `width / 2` of the core, boundary included. The core MUST be one point (a disc of diameter `width`), two or more points with `filled` false (an open polyline of closed segments; a closed outline repeats its first point at its end), or three or more points with `filled` true (the region that a ring accepted by `Polygon` encloses under the non-zero rule, the ring in the normal form of `geometry-kernel`, "Polygons with holes and a normal form"). `exact` is false when the entry is a conservative superset of the pad's copper.
- `BoardPad(footprint_id: str, ref: str, path: str, pad_id: str, number: str, kind: PadKind, position: Point, rotation: Udeg, side: Side, layers: tuple[str, ...], net_id: str | None, net: str | None, copper: tuple[PadCopper, ...] = (), hole: tuple[Point, ...] = (), drill: Nm | None = None)`.
- `PlacedExtent(footprint_id: str, side: Side, front: tuple[tuple[Point, ...], ...] = (), back: tuple[tuple[Point, ...], ...] = (), source: Literal["courtyard", "definition", "pads", "none"] = "none", exact: bool = True)`, whose property `own` MUST return `front` on the `top` side and `back` on the `bottom` side. Each ring is a ring that `Polygon` accepts, in the normal form.
- `BoardFrame`, a `@runtime_checkable` `typing.Protocol` with `board_pads(design: Design, *, issues: list[Issue] | None = None) -> tuple[BoardPad, ...]` and `placed_extents(design: Design, *, issues: list[Issue] | None = None) -> tuple[PlacedExtent, ...]`.

The records MUST be frozen dataclasses with slots whose field types are builtins, `typing` constructs, `fenolite.core` types and `fenolite.model` types only. `PadCopper` MUST raise `ValueError` for an empty core, a negative width, a core of one point with width 0, and a filled core of fewer than three points: the cores that c0029's `Thick` refuses and that `backends.base` can check without `geometry`. `backends.base` MUST still import only `core` and `model`.

`KicadBackend` MUST satisfy `BoardFrame` through `board-frame` ("Board-frame module"), and `backends/kicad/backend.py` MUST hold the statement `_FRAME: BoardFrame = KicadBackend()`, which pyright checks. `board_pads` and `placed_extents` are not operations: `CapabilityReport.operations` stays the closed list of "Capability reports", and the pinned capability tests pass unchanged.

#### Scenario: KiCad backend is a board frame
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k board_frame` checks `isinstance(KicadBackend(), BoardFrame)` and `KicadBackend().capabilities().operations`
- **THEN** the first is true, and the operations name neither `board_pads` nor `placed_extents`

#### Scenario: Base module stays neutral
- **WHEN** `uv run pytest tests/unit/backends/test_registry.py -k base_imports` runs
- **THEN** it passes, `backends/base.py` importing only `core` and `model`

#### Scenario: Records are plain data
- **WHEN** `uv run pytest tests/unit/backends/test_base_types.py -k frame_records` reads `typing.get_type_hints` of `PadCopper`, `BoardPad` and `PlacedExtent`, and builds `PadCopper("F.Cu", (), 0)`, `PadCopper("F.Cu", (Point(0, 0),), -1)`, `PadCopper("F.Cu", (Point(0, 0),), 0)` and `PadCopper("F.Cu", (Point(0, 0), Point(1, 0)), 0, filled=True)`
- **THEN** every annotation names only builtins, `typing` constructs, `fenolite.core` or `fenolite.model` types, and the four constructions raise `ValueError`

#### Scenario: Own face by side
- **GIVEN** `PlacedExtent("fp_x", "bottom", front=(), back=((Point(0, 0), Point(10, 0), Point(10, 10)),))`
- **WHEN** `own` is read
- **THEN** it equals `back`
