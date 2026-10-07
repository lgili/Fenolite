## ADDED Requirements

### Requirement: Path lengths
`fenolite.geometry` SHALL export `segment_length(a, b) -> int`, `arc_length(start, mid, end) -> int` and `arc_length_to(start, mid, end, at) -> int` from the module `geometry/lengths.py`, computed with integers and `Fraction` only.
- `segment_length` MUST be the distance between the two points rounded to the nearest integer nanometre; a square root of an integer is never a half, so no tie rule is needed.
- `arc_length` MUST be `r·θ` of the arc of "Three-point arcs" that runs from `start` through `mid` to `end`, computed in fixed-point integer arithmetic with at least 128 fractional bits and rounded half to even. For three distinct points on a line with `mid` between the ends it MUST be `segment_length(start, mid) + segment_length(mid, end)`. For every input that the arc shape of "Three-point arcs" refuses (two equal points, or collinear points with `mid` outside the ends) it MUST be `segment_length(start, end)`. Both are what `analysis.views.arc_length` and `checks.equivalence.routing.arc_length` return on `dev` before this change.
- `arc_length_to(start, mid, end, at)` MUST be the length, computed as `arc_length` computes it, of the part of the arc from `start` to the point of the arc nearest to `at`; with `at == end` it MUST equal `arc_length(start, mid, end)`.
- No function MUST use a `float`. `analysis.views.arc_length(arc)` MUST equal `arc_length(arc.start, arc.mid, arc.end)` for every arc, and the track lengths of `views` MUST equal `segment_length`.
- One implementation. `analysis.views` and `checks.equivalence.routing` (the routed lengths of equivalence level 5, change c0089) MUST call these functions and MUST hold no fixed-point arc arithmetic of their own. `checks.equivalence.routing.arc_length(start, mid, end)` MUST equal `arc_length(start, mid, end)` for every three points, so that no level-5 result changes.

#### Scenario: Segment
- **WHEN** `uv run pytest tests/unit/geometry/test_lengths.py -k segment` calls `segment_length(Point(0, 0), Point(3_000_000, 4_000_000))` and `segment_length(Point(0, 0), Point(1, 1))`
- **THEN** the results are `5_000_000` and `1`

#### Scenario: Half circle and its quarter
- **GIVEN** the arc from (15 mm, 30 mm) through (18 mm, 33 mm) to (21 mm, 30 mm), a half circle of radius 3 mm
- **WHEN** `arc_length` and `arc_length_to` with `at` = (18 mm, 33 mm) are computed
- **THEN** the results are `9_424_778` and `4_712_389`

#### Scenario: Points on a line
- **WHEN** `arc_length(Point(0, 0), Point(1_000_000, 0), Point(3_000_000, 0))` and `arc_length(Point(0, 0), Point(0, 0), Point(3_000_000, 0))` are computed
- **THEN** both results are `3_000_000`

#### Scenario: Agreement with an independent computation
- **GIVEN** generated arcs with radii from 0.1 mm to 50 mm and sweeps from 1° to 359°, and the points of those arcs nearest to generated points
- **WHEN** `uv run pytest tests/unit/geometry/test_lengths.py -k independent` compares `arc_length` and `arc_length_to` with the same lengths computed in the test with `math.atan2` and `math.hypot`, and `views.arc_length` with `arc_length`
- **THEN** every pair differs by at most 1 nm, and the views agree exactly

#### Scenario: Equivalence level 5 measures with the kernel
- **GIVEN** the generated arcs of "Agreement with an independent computation" and the arcs of the level-5 fixtures of `tests/unit/checks/equivalence`
- **WHEN** `uv run pytest tests/unit/geometry/test_lengths.py -k routing tests/unit/checks/equivalence/test_level5.py` compares `checks.equivalence.routing.arc_length` with `arc_length`, and runs the level-5 tests
- **THEN** the two are equal to the nanometre on every arc, on collinear points with `mid` between and outside the ends and on points of which two are equal, `arc_length(P, M, P)` is 0 for a point `P` and another point `M`, and every level-5 test passes with its recorded lengths
