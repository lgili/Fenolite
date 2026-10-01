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
`select_backend(prefer=None)` SHALL return the first available backend in the order of `BACKEND_ORDER`, which in this version is `("fallback",)`; `available_backends()` SHALL list the names of the available ones in that order; `prefer` SHALL select a named backend and SHALL raise `ValueError` listing the known names for an unknown name. `fenolite.geometry.boolean._extra.load_extra(name)` SHALL raise `ValueError` for a name outside `GEO_MODULES` and SHALL convert an `ImportError` into `BackendUnavailable` with issue code `geometry.backend-unavailable` and a hint naming the `geo` extra. No third-party package SHALL be imported when `fenolite.geometry` or `fenolite.geometry.boolean` is imported.

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

