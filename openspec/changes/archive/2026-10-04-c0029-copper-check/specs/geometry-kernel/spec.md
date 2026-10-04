## ADDED Requirements

### Requirement: Thick shapes
`fenolite.geometry.thick` SHALL define the frozen dataclass `Thick(core: tuple[Point, ...], width: int, filled: bool = False)`: the set of points within `width / 2` of its core, boundary included. The core MUST be one point (a disc of diameter `width`), two or more points with `filled=False` (an open polyline of closed segments) or three or more points with `filled=True` (the closed region of the ring under the non-zero rule, holes of a fractured ring included).
- `width` MUST be an `int` of at least 0, else `ValueError`. A core of one point with `width == 0`, an empty core, and a filled core that `Polygon` refuses MUST raise `GeometryError` with code `geometry.degenerate`.
- `thick_bbox(t) -> BBox` MUST return the box of the core grown by `⌈width / 2⌉` on every side, so it contains the shape.
- The module MUST import only the standard library, `core` and `geometry`, and its public names MUST be re-exported by `fenolite.geometry`.

#### Scenario: Shapes built
- **WHEN** `Thick((Point(0, 0),), 600_000)`, `Thick((Point(0, 0), Point(10, 0)), 250_000)` and `Thick((Point(0, 0), Point(100, 0), Point(100, 100)), 0, filled=True)` are built
- **THEN** they are a disc, a stadium and a filled triangle, and `thick_bbox` of the disc is `BBox(-300_000, -300_000, 300_000, 300_000)`

#### Scenario: Degenerate shapes refused
- **WHEN** `Thick((Point(0, 0),), 0)`, `Thick((), 5)`, `Thick((Point(0, 0), Point(1, 1), Point(2, 2)), 0, filled=True)` and `Thick((Point(0, 0),), -1)` are built
- **THEN** the first three raise `GeometryError` with code `geometry.degenerate`, and the last raises `ValueError`

### Requirement: Exact gaps between thick shapes
For two `Thick` shapes `a` and `b`, the gap SHALL be `dist(core_a, core_b) − (a.width + b.width) / 2`, where `dist` is the Euclidean distance between the two closed cores and is 0 when they meet, a filled core meeting every point inside its region. The functions below SHALL decide with integers and `Fraction` only, never a `float`, and SHALL give the same answer for `(a, b)` and `(b, a)`:
- `thick_touch(a, b) -> bool`: the gap is at most 0, so the two shapes share a point.
- `thick_closer_than(a, b, limit) -> bool`: the gap is strictly below `limit`, an `int` of at least 0 (`ValueError` otherwise).
- `thick_gap_floor(a, b) -> int`: `⌊gap⌋` in nm when the gap is positive, and 0 otherwise.
- `thick_witness(a, b) -> Point`: the rounded midpoint (`round_point`) of the first closest pair of core points, the pieces taken in core order; for meeting cores, a rounded common point. The same inputs MUST give the same point.

#### Scenario: Parallel tracks
- **GIVEN** `a = Thick((Point(0, 0), Point(10, 0)), 2)` and `b = Thick((Point(0, 5), Point(10, 5)), 2)`
- **WHEN** the four functions are called
- **THEN** `thick_touch` is false, `thick_closer_than(a, b, 3)` is false, `thick_closer_than(a, b, 4)` is true, `thick_gap_floor` is 3, and `thick_witness` lies on the line `y = 2` or `y = 3`

#### Scenario: Half-nanometre radii touch exactly
- **GIVEN** `a = Thick((Point(0, 0),), 5)` and `b = Thick((Point(0, 5),), 5)`
- **WHEN** `thick_touch(a, b)` is called, and again with `b` moved to `Point(0, 6)`
- **THEN** it returns true, then false with `thick_gap_floor == 1`

#### Scenario: Point inside a filled ring
- **GIVEN** the filled square `Thick((Point(0, 0), Point(100, 0), Point(100, 100), Point(0, 100)), 0, filled=True)`, a disc of width 2 at `(50, 50)` and a disc of width 20 at `(150, 50)`
- **WHEN** the gaps are tested
- **THEN** the first disc touches the square, and for the second `thick_closer_than(…, 40)` is false and `thick_closer_than(…, 41)` is true

#### Scenario: Agreement with exact brute force
- **GIVEN** generated pairs of discs, stadiums, polylines and filled rings with coordinates within ±10⁹ nm and widths up to 10⁷ nm
- **WHEN** `uv run pytest tests/unit/geometry/test_thick.py -k brute_force` compares `thick_touch`, `thick_closer_than` and `thick_gap_floor` with a computation over every pair of core pieces using `dist2_point_segment`, `dist2_segment_segment` and `point_in_ring`
- **THEN** every answer agrees, every returned value is a `bool`, an `int` or a `Point` of `int`s, and the module source names neither `float` nor `math.sqrt`, as an AST scan in the same test checks
