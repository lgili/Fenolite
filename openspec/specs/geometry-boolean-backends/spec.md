# geometry-boolean-backends Specification

## Purpose
Define the protocol, coordinate domain, selection order and result normal form shared by boolean backends, with a stdlib fallback limited to convex intersection so that no caller depends on an optional extra by accident.

## Requirements

### Requirement: Boolean backend protocol
`fenolite.geometry.boolean.base.BooleanBackend` SHALL be a runtime-checkable protocol with `name: str`, `operations: frozenset[str]` (a subset of `union`, `intersection`, `difference`, `xor`, `offset`) and the methods `union(polys)`, `intersection(a, b)`, `difference(a, b)`, `xor(a, b)` and `offset(polys, delta, *, join="round", tol=5000, miter_limit=2)`. Inputs SHALL be sequences of `Polygon` read with the non-zero fill rule. Every result SHALL be a `tuple[Polygon, ...]` equal to its own `normalize_polygons` form, containing only polygons of non-zero area (no lines or points), with integer vertices within √2/2 nm of the exact result; an empty result, including a result that touches only along an edge or at a point, SHALL be the empty tuple.

#### Scenario: Fallback satisfies the protocol
- **WHEN** `isinstance(FallbackBackend(), BooleanBackend)` is evaluated
- **THEN** it is `True`, and the backend's `name` is `"fallback"` and its `operations` is `frozenset({"intersection"})`

#### Scenario: Result in normal form
- **GIVEN** the squares `0..10` and `5..15`, the first given with the ring `(0, 10), (10, 10), (10, 0), (0, 0)`
- **WHEN** `intersection` is called on the fallback backend
- **THEN** it returns exactly `(Polygon((Point(5, 5), Point(10, 5), Point(10, 10), Point(5, 10))),)`

#### Scenario: Touching intersection is empty
- **WHEN** `intersection` is called on the squares `0..10` and `10..20` (sharing the edge `x = 10`)
- **THEN** it returns `()`

#### Scenario: Disjoint intersection is empty
- **WHEN** `intersection` is called on the squares `0..10` and `20..30`
- **THEN** it returns `()`

### Requirement: Coordinate domain of backends
Every backend SHALL reject input coordinates whose absolute value exceeds `COORD_LIMIT = 2**31 − 1` nm, and offsets whose result could exceed it, with `GeometryError` code `geometry.out-of-range`, before calling any backend-specific or third-party code.

#### Scenario: Out-of-range coordinate
- **WHEN** `intersection` is called on the fallback with a polygon that has a vertex at `x = 2**31`
- **THEN** a `GeometryError` with code `geometry.out-of-range` is raised

### Requirement: Backend selection
`select_backend(prefer=None, *, operation=None)` SHALL return the first available backend in the order of `BACKEND_ORDER`, which in this version is `("fallback", "clipper")`; with `operation`, it SHALL return the first available backend whose `operations` holds that operation, and SHALL raise `BackendUnavailable` with issue code `geometry.backend-unavailable` and a hint naming the `geo` extra when none does. `available_backends()` SHALL list the names of the available ones in that order; `prefer` SHALL select a named backend and SHALL raise `ValueError` listing the known names for an unknown name. `fenolite.geometry.boolean._extra.load_extra(name)` SHALL raise `ValueError` for a name outside `GEO_MODULES` and SHALL convert an `ImportError` into `BackendUnavailable` with issue code `geometry.backend-unavailable` and a hint naming the `geo` extra. No third-party package SHALL be imported when `fenolite.geometry` or `fenolite.geometry.boolean` is imported.

#### Scenario: Default without extras
- **GIVEN** `pyclipper` and `shapely` cannot be imported
- **WHEN** `select_backend()` is called
- **THEN** the `fallback` backend is returned and `available_backends()` is `("fallback",)`

#### Scenario: Unknown backend name
- **WHEN** `select_backend("cgal")` is called
- **THEN** a `ValueError` is raised listing the known names

#### Scenario: Extra missing
- **GIVEN** `shapely` cannot be imported
- **WHEN** `load_extra("shapely")` is called
- **THEN** `BackendUnavailable` is raised whose issue has code `geometry.backend-unavailable` and a hint containing `fenolite[geo]`

#### Scenario: Name outside the extra
- **WHEN** `load_extra("numpy")` is called
- **THEN** a `ValueError` is raised naming `GEO_MODULES`

#### Scenario: Selection by operation
- **GIVEN** the `geo` extra installed
- **WHEN** `select_backend()` and `select_backend(operation="union")` are called
- **THEN** the first returns `fallback` and the second `clipper`; without `pyclipper` the second raises `BackendUnavailable` naming `fenolite[geo]`

### Requirement: Stdlib fallback limited to convex intersection
The `fallback` backend SHALL report `operations == frozenset({"intersection"})` and SHALL compute `intersection` when every operand is a single hole-free convex polygon. After rounding each vertex with `round_point` it SHALL remove consecutive duplicate and collinear vertices and SHALL return `()` when fewer than three vertices remain or the doubled area is 0; otherwise it SHALL return one simple polygon that is convex within 1 nm. It SHALL raise `BackendUnavailable` with issue code `geometry.backend-unavailable` for every other operation and for concave or holed operands, without returning an approximate result.

#### Scenario: Convex intersection without extras
- **WHEN** the fallback intersects the squares `0..10` and `5..15`
- **THEN** it returns `(Polygon((Point(5, 5), Point(10, 5), Point(10, 10), Point(5, 10))),)`

#### Scenario: Sliver collapses on rounding
- **GIVEN** the square `0..10` and the triangle `(0, 10), (30, 9), (30, 20)`, whose exact intersection is the triangle `(0, 10), (10, 10), (10, 29/3)`
- **WHEN** the fallback intersects them
- **THEN** it returns `()`

#### Scenario: Union unavailable
- **WHEN** the fallback's `union` is called
- **THEN** `BackendUnavailable` is raised with issue code `geometry.backend-unavailable`

#### Scenario: Concave operand refused
- **WHEN** the fallback's `intersection` is called with an L-shaped operand
- **THEN** `BackendUnavailable` is raised naming the non-convex operand

### Requirement: Clipper union backend
`fenolite.geometry.boolean.clipper.ClipperBackend` SHALL satisfy `BooleanBackend` with `name == "clipper"` and `operations == frozenset({"union"})`, load `pyclipper` only through `load_extra`, and compute `union` on integer rings with the non-zero rule. Its result MUST be in normal form with integer vertices and MUST keep every input vertex that lies on the union's boundary. Every other operation MUST raise `BackendUnavailable`.

#### Scenario: Two slots in an L
- **GIVEN** the two stadiums 2 mm wide between (110, 110)–(120, 110) mm and (120, 110)–(120, 120) mm, polygonised at 1 µm
- **WHEN** `uv run pytest tests/unit/geometry/test_clipper.py -k slots` unites them
- **THEN** the result is one polygon without holes whose only vertex absent from the inputs is (119 mm, 111 mm)

### Requirement: Union of curved rings
`geometry.rings.merge_rings(rings, *, tol=MERGE_TOL)` SHALL return the union of rings of lines and arcs, `MERGE_TOL == 1_000` nm. A ring that overlaps no other MUST be returned unchanged. A group MUST be united by `select_backend(operation="union")` after polygonisation at `tol`, and each run of result vertices from arcs of one circle MUST become one arc of that circle. The result MUST be deterministic and within `tol` of the exact union.

#### Scenario: L of two slots keeps its arcs
- **WHEN** `uv run pytest tests/unit/geometry/test_merge_rings.py -k ell` merges the two stadiums of "Two slots in an L" given with their exact arcs
- **THEN** it returns one ring of seven vertices with three arcs, among them the quarter arc from (120, 109) mm to (121, 110) mm about (120, 110) mm, and the same call twice gives equal results

#### Scenario: A union with a hole is refused
- **WHEN** four slots that enclose a square of board are merged
- **THEN** a `GeometryError` names the four rings

#### Scenario: Separate rings untouched
- **WHEN** two stadiums 5 mm apart are merged
- **THEN** both are returned with their vertices and mids unchanged
