## ADDED Requirements

### Requirement: Keyhole ring of a polygon with holes
`fenolite.geometry.polygon.keyhole_ring(outer, holes)` SHALL return `Keyhole(ring, merged, outside)`: one ring of integer points that bounds the region of `outer` without its holes, the number of holes the ring holds and the number of holes dropped because they lie outside `outer`. `fenolite.geometry` SHALL re-export `Keyhole` and `keyhole_ring`.
- `ring` MUST start at `outer[0]` and hold the points of `outer` in the order given, with the anchors and the holes between them: `outer` is neither reversed nor rotated, and without a hole to merge `ring == tuple(outer)`.
- A hole with fewer than three distinct points or with zero doubled area MUST be dropped without a count. A hole whose leftmost vertex (the smallest `(x, y)`) is `OUTSIDE` of `outer` MUST be dropped and counted in `outside`. When `outer` has fewer than three points or zero doubled area, `ring` MUST be `tuple(outer)` and every hole that is not dropped for its own shape MUST be counted in `outside`.
- The holes that remain MUST be merged in ascending order of their leftmost vertex, ties by their point tuples. For each, a horizontal ray is cast from its leftmost vertex towards smaller `x`; the crossing with the ring built so far that is nearest to the vertex is the anchor (the first edge in ring order among equals). An anchor that is a vertex of the ring MUST be that vertex; an anchor inside an edge MUST be inserted into the edge with its `x` rounded half to even to a nanometre and the `y` of the ray. The hole MUST then be spliced in at the anchor: anchor, the hole from its leftmost vertex once around and back to that vertex, anchor. The bridge between the anchor and the hole is therefore walked once in each direction.
- A merged hole MUST run opposite to `outer` (its doubled area has the other sign), so that a point strictly inside a hole is `OUTSIDE` of `ring` under the non-zero rule and under the even-odd rule, and a point on a bridge is `BOUNDARY`.
- When `outer` and the holes hold no two equal consecutive points, `ring` MUST hold none and no closing copy of its first point; it MAY pass through one point several times.
- When no anchor was rounded, `area2(ring)` MUST equal `area2(outer)` plus the doubled areas of the merged holes as they run in `ring`: the absolute area is the outline's minus the holes'.
- The result MUST depend only on `outer` and on the set of holes with their point order, not on the order in which the holes are given. The function MUST use integers and `Fraction` only, MUST NOT return a `float`, and the number of edges its anchor searches test MUST be at most the number of merged holes times the number of points of `ring`.

#### Scenario: One hole
- **GIVEN** the outer ring `(0, 0), (100, 0), (100, 100), (0, 100)` and the hole `(30, 40), (70, 40), (70, 60), (30, 60)`
- **WHEN** `keyhole_ring` is called
- **THEN** `ring` is `(0, 0), (100, 0), (100, 100), (0, 100), (0, 40), (30, 40), (30, 60), (70, 60), (70, 40), (30, 40), (0, 40)`, `merged == 1`, `outside == 0`, `area2(ring) == 18400`, the point `(50, 50)` is `OUTSIDE` under both fill rules, `(10, 10)` is `INSIDE` and `(15, 40)` is `BOUNDARY`

#### Scenario: Without a hole
- **WHEN** `keyhole_ring` is called with a ring and no hole, and with the same ring and a hole of three equal points
- **THEN** both results hold the ring as it was given, `merged == 0` and `outside == 0`

#### Scenario: Hole outside the outline
- **GIVEN** the square `0..100` and a hole that is the square `200..220`
- **WHEN** `keyhole_ring` is called
- **THEN** `ring` is the square as given, `merged == 0` and `outside == 1`

#### Scenario: Area and location over generated polygons
- **WHEN** `uv run pytest tests/unit/geometry/test_keyhole.py` builds outlines with disjoint holes from a seeded generator, in every order of the holes and in both directions of every ring
- **THEN** each result is the same ring for every order, its doubled area is the outline's minus the holes' exactly whenever no anchor was rounded, every sampled point is located by `ring` as `Polygon(outer, holes).locate` locates it under both fill rules except on a bridge, and a case of 300 holes tests no more edges than the bound of the requirement
