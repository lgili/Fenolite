# geometry-kernel Specification

## Purpose
Give every package one exact, deterministic, platform-independent integer geometry (predicates, arcs, circles, polygons and their normal form, mixed contours, microdegree transforms, a spatial index) in the KiCad file frame, and record KiCad's frame and arc conventions with kicad-cli evidence.
## Requirements
### Requirement: Stdlib-only integer geometry package
`fenolite.geometry` SHALL be importable with no optional extra installed, SHALL import from `fenolite` only `fenolite.core` and its own modules, SHALL contain no static import of a third-party package and SHALL load optional packages only through `fenolite.geometry.boolean._extra`. It SHALL re-export `Point` and `Size` from `fenolite.core.coords` (the same classes, not copies). Every public function that returns a `Point` SHALL return integer nanometres, exact rational results SHALL be `Fraction`, and no public function SHALL return a `float`. Public functions that take a `Point` or a microdegree angle SHALL raise `TypeError` naming the argument when a coordinate or the angle is not an `int`.

#### Scenario: Same point class
- **WHEN** `fenolite.geometry.Point is fenolite.core.coords.Point` is evaluated
- **THEN** it is `True`

#### Scenario: Import without extras
- **GIVEN** an environment where `shapely` and `pyclipper` cannot be imported
- **WHEN** `python -c "import fenolite.geometry"` runs
- **THEN** the exit code is 0

### Requirement: Coordinate frame and orientation sign
The kernel SHALL use the file frame of the first backend (X to the right, Y down) and SHALL define `orient2d(a, b, c) = (b.x−a.x)·(c.y−a.y) − (b.y−a.y)·(c.x−a.x)` computed exactly with integers; a positive value SHALL be called *positive orientation* (a left turn in a Y-up frame, clockwise as displayed in the Y-down frame). Documentation and docstrings MUST NOT describe an orientation as clockwise or counter-clockwise without naming the frame.

#### Scenario: Positive orientation
- **WHEN** `orient2d(Point(0, 0), Point(10, 0), Point(0, 10))` is called
- **THEN** it returns `100`

#### Scenario: Exact at the 32-bit limit
- **GIVEN** `a = Point(-(2**31 - 1), -(2**31 - 1))`, `b = Point(2**31 - 1, 2**31 - 1)` and `c = Point(2**31 - 2, 2**31 - 2)`
- **WHEN** `orient2d(a, b, c)` is called
- **THEN** it returns `0`

#### Scenario: Antisymmetry
- **WHEN** `orient2d(a, b, c)` and `orient2d(b, a, c)` are compared for generated integer points
- **THEN** one is the negation of the other

### Requirement: Exact segment classification and intersection
`classify_segments(a, b, c, d)` SHALL return exactly one of `DISJOINT`, `PROPER`, `TOUCHING`, `COLLINEAR_OVERLAP`, `COLLINEAR_TOUCH` using only integer arithmetic, SHALL treat a degenerate segment (`a == b`) as a point, and `intersection_point(a, b, c, d)` SHALL return the exact intersection as a pair of `Fraction` for `PROPER`, `TOUCHING` and `COLLINEAR_TOUCH`, and `None` otherwise. `round_point(x, y)` SHALL round each coordinate half to even with `fenolite.core.units.round_half_even_div`.

#### Scenario: Proper crossing
- **WHEN** `classify_segments(Point(0, 0), Point(10, 10), Point(0, 10), Point(10, 0))` is called
- **THEN** it returns `PROPER` and `intersection_point` of the same segments returns `(Fraction(5), Fraction(5))`

#### Scenario: Rational intersection rounded half to even
- **GIVEN** segments `(0, 0)–(3, 1)` and `(0, 1)–(3, 0)`
- **WHEN** `intersection_point` is called and its result is passed to `round_point`
- **THEN** the exact point is `(Fraction(3, 2), Fraction(1, 2))` and the rounded point is `Point(2, 0)`

#### Scenario: Endpoint on the other segment
- **WHEN** `classify_segments(Point(0, 0), Point(10, 0), Point(5, 0), Point(5, 10))` is called
- **THEN** it returns `TOUCHING`

#### Scenario: Collinear cases
- **WHEN** `(0, 0)–(10, 0)` is classified against `(5, 0)–(15, 0)` and against `(10, 0)–(20, 0)`
- **THEN** the results are `COLLINEAR_OVERLAP` and `COLLINEAR_TOUCH`, and `intersection_point` returns `None` for the first and `(Fraction(10), Fraction(0))` for the second

#### Scenario: Disjoint
- **WHEN** `(0, 0)–(10, 0)` is classified against `(0, 5)–(10, 5)`
- **THEN** it returns `DISJOINT` and `intersection_point` returns `None`

### Requirement: Three-valued point location
`point_in_ring(p, ring, rule)` and `Polygon.locate(p, rule)` SHALL return `INSIDE`, `OUTSIDE` or `BOUNDARY` exactly, SHALL report `BOUNDARY` for any point on an edge or vertex, SHALL use the non-zero winding rule by default and the even-odd rule when `rule=FillRule.EVENODD`, and `Polygon.locate` SHALL report points inside a hole as `OUTSIDE` and points on a hole's edge as `BOUNDARY`.

#### Scenario: Square
- **GIVEN** the ring `(0, 0), (10, 0), (10, 10), (0, 10)`
- **WHEN** `(5, 5)`, `(10, 5)`, `(0, 0)` and `(11, 5)` are located
- **THEN** the results are `INSIDE`, `BOUNDARY`, `BOUNDARY` and `OUTSIDE`

#### Scenario: Fill rules differ on a doubly wound ring
- **GIVEN** the ring `(0, -100), (59, 81), (-95, -31), (95, -31), (-59, 81)` whose winding number around `(0, 0)` is 2
- **WHEN** `(0, 0)` is located with each rule
- **THEN** the non-zero rule returns `INSIDE` and the even-odd rule returns `OUTSIDE`

#### Scenario: Point in a hole
- **GIVEN** a polygon with outer square `0..30` and a hole `10..20`
- **WHEN** `(15, 15)` and `(10, 15)` are located
- **THEN** the results are `OUTSIDE` and `BOUNDARY`

### Requirement: Exact distances and integer clearance tests
`dist2_point_segment` and `dist2_segment_segment` SHALL return the exact squared Euclidean distance as a `Fraction` (zero when the segments intersect in any way), `segments_closer_than(a, b, c, d, limit)` SHALL decide `distance < limit` with integer arithmetic only, and `floor_sqrt`/`ceil_sqrt` SHALL return the exact floor and ceiling of the square root of a non-negative `int` or `Fraction`, raising `ValueError` for a negative argument.

#### Scenario: Rational distance
- **WHEN** `dist2_point_segment(Point(1, 1), Point(0, 0), Point(2, 1))` is called
- **THEN** it returns `Fraction(1, 5)`

#### Scenario: Endpoint is nearest
- **WHEN** `dist2_point_segment(Point(15, 0), Point(0, 0), Point(10, 0))` is called
- **THEN** it returns `Fraction(25)`

#### Scenario: Strict clearance comparison
- **GIVEN** parallel segments `(0, 0)–(10, 0)` and `(0, 3)–(10, 3)`
- **WHEN** `segments_closer_than(…, limit=3)` and `segments_closer_than(…, limit=4)` are called
- **THEN** they return `False` and `True`

#### Scenario: Square roots
- **WHEN** `floor_sqrt(Fraction(1, 5))`, `ceil_sqrt(Fraction(1, 5))`, `floor_sqrt(25)` and `ceil_sqrt(26)` are called
- **THEN** they return `0`, `1`, `5` and `6`

#### Scenario: Negative argument
- **WHEN** `floor_sqrt(-1)` is called
- **THEN** a `ValueError` is raised

### Requirement: Closed integer bounding boxes
`BBox(x0, y0, x1, y1)` SHALL be an immutable closed box with integer bounds, SHALL reject `x0 > x1` or `y0 > y1` with `ValueError`, and SHALL provide `of_points`, `union`, `intersects` (touching boxes intersect), `contains_point`, `contains_bbox` and `inflate(d)`; `of_points` of an empty iterable and an `inflate` with a negative `d` that would invert the box SHALL raise `ValueError`.

#### Scenario: Touching boxes intersect
- **WHEN** `BBox(0, 0, 10, 10).intersects(BBox(10, 0, 20, 10))` is called
- **THEN** it returns `True`

#### Scenario: Inverted box rejected
- **WHEN** `BBox(10, 0, 0, 10)` is constructed
- **THEN** a `ValueError` is raised

#### Scenario: Over-deflation rejected
- **WHEN** `BBox(0, 0, 10, 10).inflate(-6)` is called
- **THEN** a `ValueError` is raised

### Requirement: Three-point arcs
`Arc(start, mid, end)` SHALL be defined by its three integer points, which SHALL be kept unchanged; it SHALL expose the exact circumcentre `centre` as a pair of `Fraction` (or `None` when the points are collinear), the exact `radius2`, the orientation sign of `orient2d(start, mid, end)`, and `bbox()` that contains every point of the true arc and is the smallest such integer box. Construction SHALL raise `GeometryError` with code `geometry.degenerate` when `start == end`, when `mid` equals an endpoint, or when the points are collinear and `mid` does not lie strictly between `start` and `end`; collinear points with `mid` strictly between SHALL give an arc with `is_straight == True` that behaves as the segment `start–end`.

#### Scenario: Exact centre of a stored arc
- **GIVEN** `Arc(Point(0, 26500000), Point(-707107, 26207107), Point(-1000000, 25500000))`
- **WHEN** `centre` is read
- **THEN** it equals `(Fraction(-309449, 414214), Fraction(10562457309449, 414214))`

#### Scenario: Outward-rounded bounding box
- **GIVEN** the same arc
- **WHEN** `bbox()` is called
- **THEN** it returns `BBox(-1000001, 25500000, 0, 26500001)`

#### Scenario: Half circle
- **GIVEN** `Arc(Point(1000, 0), Point(0, 1000), Point(-1000, 0))`
- **WHEN** `centre`, `radius2`, the orientation sign and `bbox()` are read
- **THEN** they are `(0, 0)`, `1000000`, positive and `BBox(-1000, 0, 1000, 1000)`

#### Scenario: Closed arc rejected
- **WHEN** `Arc(Point(0, 0), Point(5, 5), Point(0, 0))` is constructed
- **THEN** a `GeometryError` with code `geometry.degenerate` is raised with a message pointing to `Circle`

#### Scenario: Collinear arcs
- **WHEN** `Arc(Point(0, 0), Point(5, 0), Point(10, 0))` and `Arc(Point(0, 0), Point(15, 0), Point(10, 0))` are constructed
- **THEN** the first has `is_straight == True` and `centre is None`, and the second raises `GeometryError`

### Requirement: Circles from centre and a point on the circle
`Circle(centre, radius2)` SHALL store the exact squared radius; `Circle.from_kicad(center, end)` SHALL build it from a centre and a point on the circle without any square root, and `bbox()` SHALL be the smallest integer box containing the circle.

#### Scenario: Irrational radius stays exact
- **WHEN** `Circle.from_kicad(Point(0, 0), Point(1, 1))` is built and `bbox()` is called
- **THEN** `radius2 == 2` and the box is `BBox(-2, -2, 2, 2)`

#### Scenario: Negative radius rejected
- **WHEN** `Circle.from_radius(Point(0, 0), -1)` is called
- **THEN** a `ValueError` is raised

### Requirement: Deterministic polygonisation with a chord-error bound
`Arc.polygonize(tol)`, `Circle.polygonize(tol)` (with `outer=False`, the default) and `Path.polygonize(tol)` SHALL return integer vertices computed without floating-point trigonometry, identical on every platform. An arc SHALL be split at `mid` and a circle into four quarter arcs starting at the rounded point `(cx + r, cy)` in positive orientation; each part SHALL be bisected uniformly until the exact sagitta of every chord, measured from the true circle, is at most `tol`, or until `MAX_BISECTION_DEPTH = 32` levels. Every vertex SHALL lie within 1 nm of the circle, consecutive duplicate vertices SHALL be removed, an arc's output SHALL start at `start`, end at `end` and contain `mid`, and every point of the true curve SHALL lie within `tol + 1` nm of the polyline. The default `tol` SHALL be 5000 nm. `tol` below 1 SHALL raise `ValueError`.

#### Scenario: Bound holds
- **GIVEN** generated arcs with radii from 0.1 mm to 50 mm and `tol` from 1 µm to 50 µm
- **WHEN** they are polygonised
- **THEN** every vertex is within 1 nm of the circle, every chord's sagitta is at most `tol`, and each arc's output starts at `start`, ends at `end` and contains `mid`

#### Scenario: Platform independence
- **GIVEN** `Circle(Point(0, 0), 10**12)` polygonised with the default `tol`
- **WHEN** the vertex list is encoded as UTF-8 text with one line `x,y\n` per vertex (decimal integers, output order, no closing duplicate) and hashed with SHA-256
- **THEN** the list has 32 vertices and the hash equals the golden value committed in the test, on ubuntu and on macOS

#### Scenario: Tiny radius terminates
- **WHEN** `Circle.from_radius(Point(0, 0), 3).polygonize(1)` is called
- **THEN** it returns at least four vertices, none equal to its successor, each within 1 nm of the circle

#### Scenario: Invalid tolerance
- **WHEN** `polygonize(0)` is called
- **THEN** a `ValueError` is raised

### Requirement: Outer polygon of a circle
`Circle.polygonize(tol, outer=True)` SHALL return a polygon whose vertices lie within 1 nm of the radius `R = r + tol + 1` nm, with every chord's exact sagitta measured at `R` at most `tol`, so that the polygon contains the closed disc of the circle. `Arc.polygonize` and `Path.polygonize` SHALL NOT accept `outer`.

#### Scenario: Outer polygon contains the circle
- **WHEN** `Circle.from_radius(Point(0, 0), 1000000).polygonize(5000, outer=True)` is built
- **THEN** every vertex `v` satisfies `1005000² ≤ v.x² + v.y² ≤ 1005002²` (within 1 nm of `R = 1005001`), and every generated integer point `p` with `p.x² + p.y² ≤ 10**12` is located `INSIDE` or `BOUNDARY` of the result

#### Scenario: Outer is circle-only
- **WHEN** `Arc(Point(1000, 0), Point(0, 1000), Point(-1000, 0)).polygonize(5000, outer=True)` is called
- **THEN** a `TypeError` is raised

### Requirement: Polygons with holes and a normal form
`Polygon(outer, holes)` SHALL reject at construction, with `GeometryError` code `geometry.degenerate`, any ring with fewer than three vertices, a closing duplicate vertex, consecutive duplicate vertices or zero doubled area; a ring that passes through the same vertex twice SHALL be accepted. It SHALL expose `area2` (exact shoelace sum, twice the signed area), `is_simple()`, `is_convex()` and `normalize()`, whose result has an outer ring of positive `area2`, holes of negative `area2`, every ring starting at its lexicographically smallest vertex, collinear vertices removed and holes sorted ascending by their normalised vertex tuple. `convex_hull` SHALL return the hull vertices in normal form without collinear points. `clip_convex(subject, clip)` SHALL intersect two convex hole-free polygons, SHALL round the result with `round_point`, remove consecutive duplicate and collinear vertices and return `None` when the result has zero area, and SHALL raise `ValueError` if either operand is not convex. `polygons_intersect(a, b)` SHALL decide whether the closed regions share a point.

#### Scenario: Doubled area
- **WHEN** `Polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10))).area2` is read
- **THEN** it is `200`

#### Scenario: Normal form
- **GIVEN** a polygon with outer ring `(0, 10), (10, 10), (10, 0), (0, 0)`
- **WHEN** `normalize()` is called
- **THEN** the outer ring is `(0, 0), (10, 0), (10, 10), (0, 10)`

#### Scenario: Degenerate rings rejected
- **WHEN** polygons with outer rings `(0, 0), (10, 0)` and `(0, 0), (5, 0), (10, 0)` and `(0, 0), (10, 0), (10, 10), (0, 0)` are constructed
- **THEN** each raises `GeometryError` with code `geometry.degenerate`

#### Scenario: Self-intersecting ring detected
- **WHEN** `is_simple()` is called on the polygon `(0, 0), (10, 10), (10, 0), (0, 20)`
- **THEN** it returns `False`

#### Scenario: Convex hull
- **WHEN** `convex_hull` is called on the four corners of the square `0..10`, `(5, 5)` and `(5, 0)`
- **THEN** it returns `(0, 0), (10, 0), (10, 10), (0, 10)`

#### Scenario: Convex clip
- **WHEN** `clip_convex` intersects squares `0..10` and `5..15`
- **THEN** it returns the polygon `(5, 5), (10, 5), (10, 10), (5, 10)`

#### Scenario: Touching clip is empty
- **WHEN** `clip_convex` intersects squares `0..10` and `10..20`
- **THEN** it returns `None`

#### Scenario: Holes sorted
- **GIVEN** a polygon with outer square `0..30` and the holes `(20, 20), (20, 25), (25, 25), (25, 20)` and `(5, 5), (5, 10), (10, 10), (10, 5)` in that order
- **WHEN** `normalize()` is called
- **THEN** the holes are `((5, 5), (5, 10), (10, 10), (10, 5))` then `((20, 20), (20, 25), (25, 25), (25, 20))`

#### Scenario: Concave clip operand rejected
- **WHEN** `clip_convex` is called with an L-shaped subject
- **THEN** a `ValueError` is raised

#### Scenario: Closed-set intersection
- **WHEN** `polygons_intersect` is called on squares `0..10` and `10..20`, on squares `0..10` and `11..20`, and on squares `0..30` and `10..20`
- **THEN** the results are `True`, `False` and `True`

### Requirement: Canonical form of polygon sets
`normalize_polygons(polys)` SHALL return the canonical form of a polygon set in which every ring is simple: it SHALL split each ring at repeated vertices, keep a sub-loop with the orientation of its ring as a separate ring of the same kind (regions that touch at a vertex become separate polygons), turn a sub-loop of opposite orientation inside an outer ring into a hole of that polygon (a hole that touches its shell stays a hole), apply `Polygon.normalize()` to every polygon, and sort the polygons ascending by `(bbox as (x0, y0, x1, y1), outer ring, holes)`.

#### Scenario: Corner-touching squares
- **GIVEN** the single ring `(0, 0), (10, 0), (10, 10), (20, 10), (20, 20), (10, 20), (10, 10), (0, 10)`
- **WHEN** `normalize_polygons` is called on that polygon
- **THEN** it returns `(Polygon(((0, 0), (10, 0), (10, 10), (0, 10))), Polygon(((10, 10), (20, 10), (20, 20), (10, 20))))`

#### Scenario: Hole touching the shell
- **GIVEN** the single ring `(0, 0), (30, 0), (30, 30), (0, 30), (0, 15), (10, 20), (10, 10), (0, 15)`
- **WHEN** `normalize_polygons` is called on that polygon
- **THEN** it returns one polygon with outer ring `(0, 0), (30, 0), (30, 30), (0, 30)` and the hole `(0, 15), (10, 20), (10, 10)`

#### Scenario: Order independence
- **WHEN** `normalize_polygons` is called on generated polygon lists and on their permutations
- **THEN** the results are equal

### Requirement: Mixed line and arc contours
`Path(pieces, closed)` SHALL hold an ordered chain of `Segment` and `Arc` pieces whose consecutive endpoints are equal, and `assemble_rings(pieces)` SHALL chain unordered pieces into closed paths by exact endpoint equality, reversing pieces as needed. Each ring SHALL start at its lexicographically smallest endpoint and SHALL be traversed so that its polygonisation at `DEFAULT_TOL` has positive `area2` (if that is 0, towards the lexicographically smaller neighbouring endpoint, then the smaller `mid`), so that the result is identical for every input order. A zero-length `Segment` SHALL raise `GeometryError` with code `geometry.degenerate` naming its point, a dangling endpoint SHALL raise `GeometryError` with code `geometry.open-contour` and a point shared by more than two pieces SHALL raise `GeometryError` with code `geometry.branching-contour`, each naming the offending points.

#### Scenario: Shuffled outline assembled
- **GIVEN** the four sides of the square `0..10` in random order, two of them reversed
- **WHEN** `assemble_rings` is called
- **THEN** one closed `Path` is returned, it starts at `(0, 0)`, its polygonisation has positive `area2`, and it is identical for every permutation of the input

#### Scenario: Line and arc outline
- **GIVEN** the segment `(-1000, 0)–(1000, 0)` and the arc `(1000, 0), (0, 1000), (-1000, 0)`
- **WHEN** they are assembled and polygonised with `tol=5`
- **THEN** one closed ring is produced whose vertices include `(1000, 0)`, `(0, 1000)` and `(-1000, 0)`

#### Scenario: Gap rejected
- **GIVEN** the four sides of a square with one side ending 1 nm short of the next
- **WHEN** `assemble_rings` is called
- **THEN** a `GeometryError` with code `geometry.open-contour` is raised naming both loose endpoints

#### Scenario: Zero-length piece rejected
- **GIVEN** the four sides of the square `0..10` and the segment `(10, 0)–(10, 0)`
- **WHEN** `assemble_rings` is called
- **THEN** a `GeometryError` with code `geometry.degenerate` is raised naming `(10, 0)`

#### Scenario: Branch rejected
- **GIVEN** three segments sharing the endpoint `(0, 0)`
- **WHEN** `assemble_rings` is called
- **THEN** a `GeometryError` with code `geometry.branching-contour` is raised naming `(0, 0)`

### Requirement: Deterministic microdegree rotation
`cos_sin_fixed(udeg)` SHALL return `(round(cos θ·2^128), round(sin θ·2^128))` computed inside `decimal.localcontext(decimal.Context(prec=70, rounding=decimal.ROUND_HALF_EVEN))`, so that the caller's decimal context cannot change the result, exact for multiples of 90° and for the angles whose sine or cosine is ±1/2, and `rotate_point(p, udeg)` SHALL compute `x' = x·cosθ + y·sinθ`, `y' = −x·sinθ + y·cosθ` (positive angles display counter-clockwise in the Y-down frame) from that table with `round_half_even_div`, so that each coordinate is within 0.5 nm of the exact rotation and exact ties round half to even. The module MUST NOT call floating-point trigonometric functions.

#### Scenario: Quarter turn
- **WHEN** `rotate_point(Point(1000, 0), 90_000_000)` is called
- **THEN** it returns `Point(0, -1000)`

#### Scenario: Ties round half to even
- **WHEN** `rotate_point(Point(0, 3), 30_000_000)` and `rotate_point(Point(1, 0), 60_000_000)` are called
- **THEN** they return `Point(2, 3)` and `Point(0, -1)`

#### Scenario: Exact table entries
- **WHEN** `cos_sin_fixed(60_000_000)[0]`, `cos_sin_fixed(30_000_000)[1]` and `cos_sin_fixed(90_000_000)` are read
- **THEN** they are `2**127`, `2**127` and `(0, 2**128)`

#### Scenario: Caller's decimal context has no effect
- **GIVEN** the thread's global decimal context set to `prec=5` and `rounding=ROUND_FLOOR` and an empty table cache
- **WHEN** `cos_sin_fixed` is evaluated for the 12 golden angles of the test
- **THEN** every `(C, S)` equals its golden value

#### Scenario: Float argument rejected
- **WHEN** `rotate_point(Point(1, 0), 90.0)` is called
- **THEN** a `TypeError` is raised naming `udeg`

#### Scenario: Agreement with a high-precision reference
- **GIVEN** generated points within ±2^31 nm and generated microdegree angles
- **WHEN** `rotate_point` is compared with an 80-digit `decimal` reference rounded half to even
- **THEN** they are equal

#### Scenario: Four quarter turns are the identity
- **WHEN** a generated point is rotated four times by `90_000_000`
- **THEN** the result equals the original point

### Requirement: Placement transforms
`Transform` SHALL represent `p ↦ R(θ)·M^m·p + t`, where `M` mirrors about the local X axis (`y ↦ −y`) and is applied first, with `θ` normalised to `[0, 360 000 000)`; its properties `dx` and `dy` SHALL return the exact translation as `Fraction`. It SHALL provide `apply`, `apply_angle` (`u ↦ (−u if mirror else u) + θ` modulo a full turn), `apply_segment`, `apply_arc`, `apply_polygon`, `apply_bbox` (outward), `compose(inner)` that applies `inner` first and rounds once (each coordinate within 0.5 nm of the exact composed map), `inverse()`, and `Transform.placement(at, rot_udeg, mirror=False)`. Two successive `apply` calls round twice: for all transforms `a` and `b` and every integer point `p`, each coordinate of `a.apply(b.apply(p))` SHALL be within `(1 + |cos θa| + |sin θa|) / 2` nm of `A(B(p))`, where `A` and `B` are the unrounded maps of `a` and `b` and `cos θa`, `sin θa` are the fixed-point values `a` uses; this is at most `(1 + √2) / 2` nm (about 1.2072 nm) and SHALL NOT be stated as 1 nm. `inverse()` SHALL be exact for multiples of 90° with integer translation; for every other transform `t` and every integer point `p`, `t.inverse().apply(t.apply(p))` SHALL be within 1 nm of `p` per axis. `apply_arc` and `apply_polygon` SHALL raise `GeometryError` with code `geometry.degenerate` when the rounded points no longer form a valid `Arc` or `Polygon`.

#### Scenario: Footprint placement
- **WHEN** `Transform.placement(Point(1000, 2000), 90_000_000).apply(Point(0, 100))` is called
- **THEN** it returns `Point(1100, 2000)`

#### Scenario: Mirror first
- **WHEN** `Transform.placement(Point(0, 0), 0, mirror=True).apply(Point(5, 7))` is called
- **THEN** it returns `Point(5, -7)`

#### Scenario: Relative to absolute angle
- **WHEN** `Transform.placement(Point(0, 0), 90_000_000, mirror=True).apply_angle(30_000_000)` is called
- **THEN** it returns `60_000_000`

#### Scenario: Angle normalisation
- **WHEN** `Transform.rotation(-90_000_000).rot_udeg` is read
- **THEN** it is `270_000_000`

#### Scenario: Composition adds angles
- **WHEN** `Transform.rotation(30_000_000).compose(Transform.rotation(60_000_000))` is compared with `Transform.rotation(90_000_000)`
- **THEN** they are equal

#### Scenario: Exact inverse for quarter turns
- **WHEN** `Transform.placement(Point(1000, 2000), 90_000_000).inverse().apply(Point(1100, 2000))` is called
- **THEN** it returns `Point(0, 100)`

#### Scenario: Inverse round trip at other angles
- **GIVEN** generated transforms whose angle is not a multiple of 90°, with translations and points within ±2^30 nm
- **WHEN** `t.inverse().apply(t.apply(p))` is computed
- **THEN** each coordinate differs from `p` by at most 1 nm

#### Scenario: Mirror reverses orientation
- **GIVEN** the polygon `(0, 0), (10, 0), (10, 10), (0, 10)` with `area2 == 200`
- **WHEN** `Transform.placement(Point(0, 0), 0, mirror=True).apply_polygon` is applied to it
- **THEN** the returned polygon, before normalisation, has `area2 == -200`, and its `normalize()` equals `Polygon((Point(0, -10), Point(10, -10), Point(10, 0), Point(0, 0)))`

#### Scenario: Degenerate after rounding
- **WHEN** `Transform.rotation(30_000_000)` is applied with `apply_arc` to `Arc(Point(0, 0), Point(1, 0), Point(1, 1))` and with `apply_polygon` to the polygon `(0, 0), (0, 1), (-1, 1)`
- **THEN** each call raises `GeometryError` with code `geometry.degenerate` (the rounded `mid` equals the rounded `end`; two rounded vertices coincide)

#### Scenario: Two applies stay within the two-rounding bound
- **GIVEN** generated transforms `a` and `b` and generated integer points `p`
- **WHEN** `a.apply(b.apply(p))` is compared with the exact rational `A(B(p))`
- **THEN** each coordinate differs by at most `(1 + |cos θa| + |sin θa|) / 2` nm, and `(|cos θa| + |sin θa|)² ≤ 2` for the fixed-point values of every generated angle

#### Scenario: Two-rounding bound is tight
- **GIVEN** `b = Transform(0, False, 2**127, 2**127)` (a translation by half a nanometre on each axis), `p = Point(1, 1)`, and `a` a rotation by `45_000_000` whose X translation makes the X coordinate of `A(Point(2, 2))` a half-integer that rounds up
- **WHEN** `a.apply(b.apply(p))` is compared with the exact rational `A(B(p))`
- **THEN** the X coordinates differ by exactly `(1 + cos θa + sin θa) / 2` nm, which is more than 1.2071067811865475 nm

#### Scenario: Two applies exceed 1 nm with integer translations
- **WHEN** `Transform.rotation(315_000_000).apply(Transform.rotation(30_000_000).apply(Point(0, 1_386_483)))` is compared with the exact rational composed map
- **THEN** one coordinate differs by more than 1.206 nm and by no more than `(1 + √2) / 2` nm

### Requirement: Immutable spatial index
`SpatialIndex.build(items)` SHALL pack `(BBox, payload)` items into an immutable Sort-Tile-Recursive tree; `query(bbox)` SHALL return the payloads whose closed boxes intersect `bbox` in insertion order, `pairs()` SHALL return every pair of intersecting item indices `(i, j)` with `i < j` sorted ascending, and both results SHALL equal a brute-force computation. An index built from no items SHALL answer every query with an empty list.

#### Scenario: Agreement with brute force
- **GIVEN** 2000 generated boxes
- **WHEN** 200 generated queries and `pairs()` are compared with brute force
- **THEN** the results are identical, including order

#### Scenario: Insertion order
- **GIVEN** items `[(BBox(0, 0, 10, 10), "b"), (BBox(5, 5, 6, 6), "a")]`
- **WHEN** `query(BBox(5, 5, 5, 5))` is called
- **THEN** it returns `["b", "a"]`

#### Scenario: Empty index
- **WHEN** `SpatialIndex.build([]).query(BBox(0, 0, 1, 1))` is called
- **THEN** it returns `[]`

### Requirement: KiCad frame conventions are documented with evidence
`docs/formats/kicad/geometry.md` SHALL state, each with its source id and evidence label, the file frame (Y down, millimetres, 1 nm resolution, 32-bit range), the rotation direction, the placement and storage of bottom-side footprint children, absolute pad angles, the three-point arc and centre-plus-point circle encodings, the arc direction written by KiCad, arcs inside `pts` (`fp_poly`, custom-pad `gr_poly`, zone polygons), the default arc approximation error, and the frame and unit of the IPC-D-356 export used as evidence (Y up, 0.0001 in). The rotation direction (`H-G-ROT-DIR`), bottom-side placement (`H-G-BOTTOM-PLACE`), arcs kept on re-save (`H-G-ARC-ROUND`), arc direction (`H-G-ARC-DIR`) and arcs inside `pts` (`H-G-PTS-ARC`) SHALL be checked by `needs_kicad` tests under `tests/kicad/` that run `kicad-cli` on authored files, and each test SHALL run `kicad-cli version`, fail unless the major is 9 or 10, and report the exact version.

#### Scenario: Rotation and bottom side against kicad-cli
- **GIVEN** `kicad-cli` 10.0.x is available and an authored board with front footprints at 90° and 30° and a back footprint at 30°
- **WHEN** `pytest tests/kicad/test_geometry_frame.py` runs `kicad-cli pcb export ipcd356`
- **THEN** the export header declares `UNITS CUST 0`, and every pad difference, converted to the file frame with `Δx = ΔX·2540` nm and `Δy = −ΔY·2540` nm, equals the difference given by `Transform.placement` applied to the stored local pad positions exactly for the 90° footprint and within 2 export units per axis for the 30° footprints

#### Scenario: Arcs survive a KiCad re-save
- **GIVEN** `kicad-cli` 10.0.x is available and an authored footprint with shallow `fp_arc`s in both orientations and an `fp_poly` and a keepout zone polygon whose `pts` contain an `arc`
- **WHEN** `pytest tests/kicad/test_geometry_arcs.py` runs `kicad-cli fp upgrade --force`
- **THEN** every `fp_arc` keeps its `mid` and its set `{start, end}` and is written with positive orientation, and every `pts` arc is present with the same three points in the same order

#### Scenario: Unsupported kicad-cli major
- **GIVEN** the `kicad-cli` found reports a major other than 9 or 10
- **WHEN** either test runs
- **THEN** it fails naming the reported version and the supported majors

#### Scenario: No kicad-cli
- **GIVEN** no `kicad-cli` is found
- **WHEN** the two tests are collected
- **THEN** they are skipped with the `needs_kicad` reason and the hypotheses keep their current level

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

