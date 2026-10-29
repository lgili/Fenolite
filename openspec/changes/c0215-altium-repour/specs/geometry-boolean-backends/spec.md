## REMOVED Requirements

### Requirement: Clipper union backend
**Reason**: change c0215 needs the intersection, the difference, the xor and offsets of integer polygons for the pour engine; the backend gives them all ("Clipper backend").
**Migration**: nothing changes for the union; a caller that relied on `BackendUnavailable` from the other operations of `ClipperBackend` now gets their result.

## ADDED Requirements

### Requirement: Clipper backend
`fenolite.geometry.boolean.clipper.ClipperBackend` SHALL satisfy `BooleanBackend` with `name == "clipper"` and `operations == frozenset({"union", "intersection", "difference", "xor", "offset"})`, load `pyclipper` only through `load_extra`, and compute every operation on integer rings with the non-zero rule. Every result MUST be in normal form with integer vertices; the union MUST keep every input vertex that lies on its boundary.
- `offset(polys, delta, *, join, tol, miter_limit)` MUST grow (shrink, for a negative `delta`) every ring with Clipper's offset of closed polygons; with round joins the vertices of each arc lie on the arc and its chords at most `tol` inside it.
- `stroke(paths, delta, *, tol)` MUST give the points within `delta` of the open polylines `paths` with round ends and joins, a path of one point being a disc, under the same `tol`; a `delta` below 1 or a `tol` below 1 MUST raise `ValueError`.
- A coordinate that, grown by the offset, would leave the domain MUST raise `GeometryError` with code `geometry.out-of-range` before Clipper is called.

#### Scenario: Two slots in an L
- **GIVEN** the two stadiums 2 mm wide between (110, 110)–(120, 110) mm and (120, 110)–(120, 120) mm, polygonised at 1 µm
- **WHEN** `uv run pytest tests/unit/geometry/test_clipper.py -k slots` unites them
- **THEN** the result is one polygon without holes whose only vertex absent from the inputs is (119 mm, 111 mm)

#### Scenario: Intersection, difference and xor
- **GIVEN** the squares 0..10 and 5..15
- **WHEN** `uv run pytest tests/unit/geometry/test_clipper.py -k other_operations` runs the three operations
- **THEN** the intersection is the square 5..10, the difference the L of six vertices, the xor two polygons, and an operand with a vertex at x = 2**31 raises `geometry.out-of-range`

#### Scenario: Offsets and strokes
- **WHEN** `uv run pytest tests/unit/geometry/test_clipper.py -k tolerance` strokes the point (0, 0) by 100 µm with `tol=50`
- **THEN** every vertex lies within 1 nm of the circle of 100 µm, and the sag of each chord is at most 51 nm
