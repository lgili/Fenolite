## MODIFIED Requirements

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

## ADDED Requirements

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
