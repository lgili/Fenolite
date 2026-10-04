# Geometry kernel (`fenolite.geometry`)

`fenolite.geometry` is the exact integer geometry used by the backends, checks and placement code.
It imports only `fenolite.core` and the standard library. It works with no optional extra installed,
and every answer is the same on every platform.

```python
>>> from fenolite.geometry import Point, orient2d
>>> orient2d(Point(0, 0), Point(10, 0), Point(0, 10))
100

```

## Frame and sign convention

- Coordinates are integer nanometres in the KiCad file frame: X points right and **Y points down**
  ([KiCad frame facts](formats/kicad/geometry.md)). Angles are integer microdegrees.
- `orient2d(a, b, c) = (b.x−a.x)·(c.y−a.y) − (b.y−a.y)·(c.x−a.x)` is computed exactly with Python
  integers.
  - A positive value is called **positive orientation**. It is a left turn in a Y-up frame, so it
    displays **clockwise** in the Y-down frame.
  - This page never says "clockwise" or "counter-clockwise" without naming the frame.
- External outputs in another frame are converted where they are compared, never inside the kernel.
  For example, the IPC-D-356 export is Y up.

## Exactness and rounding

- Functions that return a `Point` return integer nanometres.
- Exact rational results are `Fraction`: intersection points, arc centres, squared distances and
  transform translations. No public function returns a `float`.
- Passing a non-`int` coordinate or angle raises `TypeError` naming the argument.

```python
>>> from fractions import Fraction
>>> from fenolite.geometry import intersection_point, round_point
>>> exact = intersection_point(Point(0, 0), Point(3, 1), Point(0, 1), Point(3, 0))
>>> exact
(Fraction(3, 2), Fraction(1, 2))
>>> round_point(*exact)  # half to even on each axis
Point(x=2, y=0)

```

- `round_point` is the only path from a rational to nanometres. It applies
  `core.units.round_half_even_div` to each axis.
  - The error is at most 0.5 nm per axis and at most √2/2 nm in distance.
- In general a rounded intersection point lies on neither input segment. The kernel therefore never
  re-evaluates a predicate on a rounded point.
- A constructor fed with rounded points can meet a degenerate result: `Transform.apply_arc`,
  `apply_polygon` and the convex clip. When that happens it raises `GeometryError` with code
  `geometry.degenerate`, or returns an empty result, as each function documents.
- Clearance decisions never form a fraction. `segments_closer_than(a, b, c, d, limit)` compares
  `cross² < limit²·|d|²` in integers.

## Predicates

- `classify_segments` returns `DISJOINT`, `PROPER`, `TOUCHING`, `COLLINEAR_OVERLAP` or
  `COLLINEAR_TOUCH`. A segment with `a == b` is treated as a point.
- `point_in_ring` and `Polygon.locate` return `INSIDE`, `OUTSIDE` or `BOUNDARY`.
  - They test for the boundary first.
  - They then compute the winding number with the half-open crossing rule.
  - The fill rule is non-zero by default; `FillRule.EVENODD` is available.
- `dist2_point_segment` and `dist2_segment_segment` return exact squared distances.
- `floor_sqrt` and `ceil_sqrt` return exact integer bounds of a square root.

```python
>>> from fenolite.geometry import FillRule, point_in_ring
>>> star = (Point(0, -100), Point(59, 81), Point(-95, -31), Point(95, -31), Point(-59, 81))
>>> point_in_ring(Point(0, 0), star), point_in_ring(Point(0, 0), star, FillRule.EVENODD)
(<Location.INSIDE: 'inside'>, <Location.OUTSIDE: 'outside'>)

```

## Arcs and circles

`Arc(start, mid, end)` keeps its three points exactly as given.

- `centre` and `radius2` are derived exactly from the circumcircle, with `D = 2·orient2d`.
  - No rule decision should depend on them: the stored points condition the centre badly for
    shallow arcs. Moving `mid` by 1 nm moves the centre of an r = 10 mm, 0.1° arc by more than 0.1 mm.
- `orientation` is the sign of `orient2d(start, mid, end)`.
  - **KiCad does not preserve it.** A re-save swaps `start` and `end` of negatively oriented
    graphic arcs (`H-G-ARC-DIR`).
  - What survives a re-save is `mid` and the set `{start, end}` (`H-G-ARC-ROUND`).
- Construction rejects these cases with `geometry.degenerate`:
  - `start == end` (a full circle is a `Circle`);
  - `mid` equal to an endpoint;
  - collinear points with `mid` outside `start–end`.
- Collinear points with `mid` strictly between `start` and `end` make a straight arc.
- `bbox()` is the smallest integer box containing the true arc. It is decided with exact comparisons
  of squares.

```python
>>> from fenolite.geometry import Arc, Circle
>>> arc = Arc(Point(0, 26500000), Point(-707107, 26207107), Point(-1000000, 25500000))
>>> arc.bbox()
BBox(x0=-1000001, y0=25500000, x1=0, y1=26500001)
>>> Circle.from_kicad(Point(0, 0), Point(1, 1)).bbox()  # radius √2 stays exact
BBox(x0=-2, y0=-2, x1=2, y1=2)

```

### Polygonisation

`Arc.polygonize(tol)`, `Circle.polygonize(tol)` and `Path.polygonize(tol)` never call
floating-point trigonometry.

- **How the curve is split:**
  - An arc is split at `mid`.
  - A circle is split into four quarters. They start at the rounded point `(cx + r, cy)` and run in
    positive orientation.
- **How each part is refined:**
  - Each part is bisected uniformly, so every chord of a part sits at the same depth.
  - Each new vertex is the projection of the chord midpoint on the circle. It is computed with
    `math.isqrt` on numbers scaled by 2**64, then rounded with `round_point`.
  - Bisection stops when the exact sagitta of every chord, measured from the true circle, is at most
    `tol`, or after `MAX_BISECTION_DEPTH = 32` levels.
- **Guarantees:**
  - Every vertex is within 1 nm of the circle.
  - Consecutive duplicates are removed.
  - Every point of the true curve is within `tol + 1` nm of the polyline.
  - An arc's output starts at `start`, contains `mid` and ends at `end`.
- `DEFAULT_TOL = 5000` nm is KiCad's default maximum approximation error (S-0010).
- `Circle.polygonize(tol, outer=True)` puts the vertices on the radius `R = r + tol + 1` nm, with the
  sagitta measured at `R`. Every chord then stays farther than `r` from the centre, so the polygon
  contains the disc. Only `Circle` accepts `outer`.

```python
>>> len(Circle(Point(0, 0), 10**12).polygonize())  # r = 1 mm at the default tolerance
32

```

## Polygons and the canonical form

- `Polygon(outer, holes)` validates every ring when it is built. Each ring needs at least 3
  vertices, no closing duplicate, no consecutive duplicates and a non-zero `area2`.
  - A ring that passes through a vertex twice (a pinch) is accepted.
- `area2` is the exact shoelace sum, which is twice the signed area.
- `is_simple()` is an O(n log n + k) test that uses the spatial index of edge boxes.
- `is_convex()` requires a polygon with no holes, turns of one sign and a single winding.
- `normalize()` gives the normal form of one polygon:
  - the outer ring has positive `area2` and the holes have negative `area2`;
  - every ring starts at its lexicographically smallest vertex;
  - collinear vertices are removed;
  - holes are sorted by their vertex tuples.
- `normalize_polygons(polys)` is the canonical form of a polygon set. It works in three steps:
  1. Every ring is split at repeated vertices, so that each ring becomes simple:
     - a sub-loop with its ring's orientation becomes a separate ring of the same kind, so regions
       that touch at a vertex become separate polygons;
     - a sub-loop of opposite orientation inside an outer ring becomes a hole of that polygon, so a
       hole that touches its shell stays a hole.
  2. Each polygon is normalised.
  3. The set is sorted by `(bbox, outer ring, holes)`.

  Every boolean backend returns this form, so results compare with `==`.

```python
>>> from fenolite.geometry import Polygon, normalize_polygons
>>> pinched = Polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(20, 10), Point(20, 20),
...                    Point(10, 20), Point(10, 10), Point(0, 10)))
>>> [p.outer[0] for p in normalize_polygons([pinched])]
[Point(x=0, y=0), Point(x=10, y=10)]

```

- `convex_hull` uses the monotone chain and returns the hull in normal form.
- `clip_convex` (Sutherland–Hodgman) intersects two convex polygons without holes:
  - it rounds the result and removes duplicate and collinear vertices;
  - it returns `None` when no area is left.
- `polygons_intersect(a, b)` treats both polygons as closed sets, so touching polygons intersect.

## Mixed contours

- `Path(pieces, closed)` chains `Segment` and `Arc` pieces whose consecutive endpoints are equal. It
  models outlines and `pts` lists that contain arcs (`H-G-PTS-ARC`).
- `assemble_rings(pieces)` chains unordered pieces by **exact** endpoint equality, reversing pieces
  as needed.
  - Each ring starts at its smallest endpoint.
  - Each ring runs so that its polygonisation at `DEFAULT_TOL` has positive `area2`.
  - The result is the same for every input order.
- `assemble_rings` raises `GeometryError` naming the points, with these codes:

  | problem | code |
  |---|---|
  | a zero-length segment | `geometry.degenerate` |
  | a dangling endpoint | `geometry.open-contour` |
  | a point shared by more than two pieces | `geometry.branching-contour` |

```python
>>> from fenolite.geometry import Segment, assemble_rings
>>> sides = [Segment(Point(10, 10), Point(0, 10)), Segment(Point(10, 0), Point(0, 0)),
...          Segment(Point(10, 0), Point(10, 10)), Segment(Point(0, 0), Point(0, 10))]
>>> ring, = assemble_rings(sides)
>>> ring.polygonize()
(Point(x=0, y=0), Point(x=10, y=0), Point(x=10, y=10), Point(x=0, y=10))

```

## Transforms

### Rotation

- `cos_sin_fixed(udeg)` returns `(round(cos θ·2**128), round(sin θ·2**128))`.
  - It is computed with `decimal` series in a private context (precision 70, round half to even),
    so the caller's decimal context cannot change it.
  - It is exact at multiples of 90° and where the sine or cosine is ±1/2.
  - Results are memoised.
- Rotation is `x' = x·cosθ + y·sinθ`, `y' = −x·sinθ + y·cosθ`. Positive angles display
  counter-clockwise in the Y-down frame, as KiCad's do (`H-G-ROT-DIR`).
- `rotate_point` rounds each coordinate half to even. The result is within 0.5 nm per axis of the
  exact rotation.
  - That it equals the correctly rounded exact rotation, ties included, is an observed property. It
    is checked against an 80-digit reference; it is not a proven theorem.

```python
>>> from fenolite.geometry import rotate_point
>>> rotate_point(Point(1000, 0), 90_000_000), rotate_point(Point(0, 3), 30_000_000)
(Point(x=0, y=-1000), Point(x=2, y=3))

```

### Transform

- `Transform` is `p ↦ R(θ)·M^m·p + t`.
  - `M` mirrors about the local X axis (`y ↦ −y`) and is applied first.
  - `θ` is normalised to `[0, 360°)`.
  - The translation is kept in units of 2**-128 nm; `dx` and `dy` return it as `Fraction`.
- `compose(inner)` applies `inner` first. Angles add, and `M·R(θ) = R(−θ)·M`.
  - `compose(a, b).apply(p)` rounds once: within 0.5 nm per axis.
  - `a.apply(b.apply(p))` rounds twice: within 1 nm per axis.
- `inverse()` is exact for multiples of 90° with an integer translation. Otherwise a round trip of an
  integer point is within 1 nm per axis.
- `apply_angle(u) = (−u if mirror else u) + θ`, modulo a full turn.
- `Transform.placement(at, rot, mirror=False)` maps local coordinates to board coordinates.
  - A bottom-side footprint's children are already mirrored in the file. Its absolute positions are
    `at + R(θ)·stored`, with no further mirror (`H-G-BOTTOM-PLACE`).

```python
>>> from fenolite.geometry import Transform
>>> Transform.placement(Point(1000, 2000), 90_000_000).apply(Point(0, 100))
Point(x=1100, y=2000)
>>> Transform.placement(Point(0, 0), 90_000_000, mirror=True).apply_angle(30_000_000)
60000000

```

## Spatial index

- `SpatialIndex.build(items)` packs `(BBox, payload)` pairs with Sort-Tile-Recursive, with a node
  capacity of 16.
  - The index is immutable: rebuild it when the items change.
- `query(bbox)` returns the payloads whose closed boxes intersect `bbox`, in insertion order.
- `pairs()` returns every intersecting index pair `(i, j)` with `i < j`, sorted.

## Thick shapes

A `Thick(core, width, filled=False)` is the set of points within `width / 2` of its core, boundary
included. It describes copper without approximating a curve by a polygon.

| core | `filled` | shape |
|---|---|---|
| one point | false | a disc of diameter `width` (a via, a round pad) |
| two or more points | false | an open polyline swept by a disc (a track, an oval pad, a polygonised arc) |
| three or more points | true | the closed region of the ring under the non-zero rule, grown by `width / 2` (a zone fill, a rectangular or rounded pad) |

- A negative width raises `ValueError`. An empty core, a single point with width 0, and a filled core
  that `Polygon` refuses raise `GeometryError` with code `geometry.degenerate`.
- A ring that walks out to a hole and back (a fractured ring) encloses nothing inside the hole,
  because the winding number there is 0.
- The gap of two shapes is `dist(core_a, core_b) − (width_a + width_b) / 2`. The distance is 0 when
  the cores meet, and a filled core meets every point inside its region.

| function | result |
|---|---|
| `thick_bbox(t)` | the box of the core grown by `⌈width / 2⌉`; it contains the shape |
| `thick_touch(a, b)` | the gap is at most 0: the shapes share a point |
| `thick_closer_than(a, b, limit)` | the gap is strictly below `limit` |
| `thick_gap_floor(a, b)` | `⌊gap⌋` in nanometres for a positive gap, else 0 |
| `thick_witness(a, b)` | the rounded midpoint of the first closest pair of core points; a common point when the cores meet |

- Every answer is exact. With doubled lengths the half-widths are integers, so each test compares
  `4·dist²`, an exact rational, with the square of an integer. No function forms a float.
- Every function gives the same answer for `(a, b)` and `(b, a)`.
- A core with 16 pieces or more gets a spatial index of its pieces on first use, so a track is tested
  only against the edges of a large fill that lie near it.

```python
>>> from fenolite.geometry import Thick, thick_closer_than, thick_gap_floor, thick_touch
>>> via = Thick((Point(0, 0),), 600_000)
>>> track = Thick((Point(-5_000_000, 425_000), Point(5_000_000, 425_000)), 250_000)
>>> thick_touch(via, track)
True
>>> clear = Thick((Point(-5_000_000, 625_000), Point(5_000_000, 625_000)), 250_000)
>>> thick_touch(via, clear), thick_gap_floor(via, clear)
(False, 200000)
>>> thick_closer_than(via, clear, 200_000), thick_closer_than(via, clear, 200_001)
(False, True)

```

## Boolean backends

- `BooleanBackend` is the protocol every backend implements: `name`, `operations`, `union`,
  `intersection`, `difference`, `xor` and `offset`.
  - Inputs are read with the non-zero rule.
  - Results are in canonical form and contain only polygons with non-zero area. A result that only
    touches along an edge or at a point is `()`.
- The coordinate domain is |v| ≤ `COORD_LIMIT = 2**31 − 1` nm. Values outside it raise
  `geometry.out-of-range` before any backend code runs.
- This version ships only the stdlib **fallback** (`BACKEND_ORDER = ("fallback",)`).
  - It intersects two convex polygons without holes.
  - Every other operation or operand raises `BackendUnavailable` with issue code
    `geometry.backend-unavailable` and hint `pip install 'fenolite[geo]'`.
- The pyclipper and shapely backends come with the first change that needs general booleans or
  offsets (zone fill), together with their cross-checks and a licence review. Shapely bundles
  LGPL-licensed GEOS (S-0015).
- `fenolite.geometry.boolean._extra.load_extra` is the only code in the stdlib-only packages that may
  load the `geo` extra.

```python
>>> from fenolite.geometry import select_backend
>>> square = Polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)))
>>> other = Polygon((Point(5, 5), Point(15, 5), Point(15, 15), Point(5, 15)))
>>> select_backend().intersection(square, other)[0].outer
(Point(x=5, y=5), Point(x=10, y=5), Point(x=10, y=10), Point(x=5, y=10))

```

## Algorithm references

These are algorithms only; no code was copied from any of them.

- Exact orientation predicates: Shewchuk, https://www.cs.cmu.edu/~quake/robust.html
- Point in polygon (winding number): https://en.wikipedia.org/wiki/Point_in_polygon
- Circumcircle: https://en.wikipedia.org/wiki/Circumcircle
- Sagitta: https://en.wikipedia.org/wiki/Sagitta_(geometry)
- Shoelace formula: https://en.wikipedia.org/wiki/Shoelace_formula
- Monotone-chain convex hull:
  https://en.wikibooks.org/wiki/Algorithm_Implementation/Geometry/Convex_hull/Monotone_chain
- Sutherland–Hodgman clipping: https://en.wikipedia.org/wiki/Sutherland%E2%80%93Hodgman_algorithm
- STR packing: Leutenegger, Edgington, Lopez (1997),
  https://ia600900.us.archive.org/27/items/nasa_techdoc_19970016975/19970016975.pdf
- Machin's formula for π and the power series of sine and cosine (standard analysis).
