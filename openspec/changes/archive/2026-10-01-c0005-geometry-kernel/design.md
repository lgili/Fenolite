## Context

The model (c0004) stores lengths as integer nanometres (`Nm = int`) and angles as integer microdegrees (`Udeg = int`); `fenolite.core.coords.Point`/`Size` are frozen, ordered dataclasses without arithmetic, and `fenolite.core.units.round_half_even_div(n, d)` is the one integer rounding primitive. The package-layering table already reserves `geometry` (imports `core` only) and lets `backends.*`, `checks`, `placement`, `libs`, `routing`, `render`, `exports`, `convert` and `verify` import it; `lens` may not (a later change must add that edge if the layout lens needs geometry). `pyproject.toml` already declares the extra `geo = ["shapely>=2.1", "pyclipper>=1.3"]`; this change leaves it untouched. `tests/unit/test_import_graph.py` treats `geometry` as stdlib-only.

Facts this design relies on (ids in `docs/evidence/sources.md`, registered by task 1.1):

| fact | source |
|---|---|
| Board files are in millimetres with 1 nm internal resolution; `gr_arc`/`fp_arc` store `start`, `mid` (point on the arc) and `end`; `gr_circle`/`fp_circle` store `center` and `end` (a point on the circle); `pts` is documented as a list of `xy` points; board angles are degrees | S-0001 |
| Coordinates are stored as 32-bit integers (about 4 m × 4 m); items rotate counter-clockwise on screen with the R hotkey; the default maximum error when arcs/circles are approximated by segments is 0.005 mm; "Flip board items L/R" chooses the flip axis | S-0010 |
| `math.isqrt` is exact; the `math` module is a thin wrapper around the platform C library (last-ulp differences between platforms) | S-0011 |
| `decimal` is a software implementation of decimal arithmetic, identical on every platform; the context (precision, rounding) is per-thread state that callers can change; the documentation gives series recipes for `pi`, `cos`, `sin` | S-0012 |
| shapely: `set_precision(grid_size=…)`, set operations with `grid_size`, `buffer`, `orient_polygons`, `STRtree` | S-0013 |
| shapely 2.1.2 is BSD-3-Clause, requires numpy ≥ 1.21, ships wheels that bundle GEOS | S-0014 |
| GEOS is LGPL-licensed | S-0015 |
| pyclipper 1.4.0 is MIT (embedded Clipper 6.4.2 under the Boost licence), has no runtime dependency; API names `Pyclipper.Execute`/`Execute2`, `PyclipperOffset`, `JT_*`, `ET_*`, `PFT_*` | S-0016 |
| Clipper 1: integer coordinates; `ArcTolerance`; join types with `MiterLimit`; `PolyTree`; fill rules; `StrictlySimple` off by default; superseded by Clipper2 | S-0017 |
| The KiCad 10.0.6 footprint library has `(arc (start)(mid)(end))` inside `pts` in three contexts: `fp_poly` (folder `Sensor_Pressure.pretty`), custom-pad `gr_poly` primitives (`Transistor_Power.pretty`) and keepout `zone` `polygon` outlines (`Module.pretty`); read for a fact, nothing copied, no file named | S-0018 |
| Observed with `kicad-cli` 10.0.6 `pcb export ipcd356` on the pic_programmer demo board (format 20241229): the header says `UNITS CUST 0` (unit 0.0001 in = 2540 nm); X = x_file − x₀ and **Y = y₀ − y_file** (Y up, constant origin per file); a footprint at 90° with pad 2 at local `(0, 2.54)` exports pad 2 at X + 1000 units relative to pad 1, i.e. in the file frame `x' = x·cosθ + y·sinθ`, `y' = −x·sinθ + y·cosθ`; pad angles in the board file equal the footprint angle (`(at 0 2.54 90)` under a 90° footprint), and the export writes that pad rotation as `R270`; the one bottom footprint stores its children with `y` negated compared with the library footprint of the same name | S-0019 |

Algorithms are cited here, not in the source register, because they are not format facts: exact orientation predicates (Shewchuk, https://www.cs.cmu.edu/~quake/robust.html), point in polygon (https://en.wikipedia.org/wiki/Point_in_polygon), circumcircle (https://en.wikipedia.org/wiki/Circumcircle), sagitta (https://en.wikipedia.org/wiki/Sagitta_(geometry)), shoelace formula (https://en.wikipedia.org/wiki/Shoelace_formula), monotone-chain convex hull (https://en.wikibooks.org/wiki/Algorithm_Implementation/Geometry/Convex_hull/Monotone_chain, algorithm only, no code copied), Sutherland–Hodgman clipping (https://en.wikipedia.org/wiki/Sutherland%E2%80%93Hodgman_algorithm), STR packing (Leutenegger, Edgington, Lopez 1997, https://ia600900.us.archive.org/27/items/nasa_techdoc_19970016975/19970016975.pdf).

Exploratory measurements on the maintainer's machine (CPython 3.13, not normative): `orient2d` on 2^31-range ints ≈ 0.3 µs; winding-number point-in-polygon on 200 vertices ≈ 8 µs; STR index over 50 000 boxes builds in 0.04 s and answers a 2 × 2 mm query in ≈ 10 µs; 100 000 fixed-point rotations take ≈ 0.05 s (float: 0.024 s). Float rotation rounds the ties `(0, 3 nm)` at 30° and `(1 nm, 0)` at 60° wrongly. `kicad-cli` 10.0.6 `fp upgrade --force` on an authored footprint rewrote every `fp_arc` whose `orient2d(start, mid, end)` was negative with `start` and `end` swapped and `mid` kept, and kept a positively oriented `arc` inside `fp_poly` `pts` unchanged (`H-G-ARC-DIR`). An authored board loaded in `pcb export ipcd356`; a footprint at 30° exported pad differences of 500 and 866 units, i.e. quantised to 2.54 µm.

## Goals / Non-Goals

**Goals:**
- Exact, deterministic, platform-independent answers for every predicate; every rounding documented with its bound.
- One coordinate/sign convention stated once and used everywhere.
- The small API later changes need: arcs and mixed contours (outlines, courtyards, `pts` with arcs), placement transforms, polygon containment and intersection tests, a spatial index, a normal form for polygon sets, and a stable `BooleanBackend` protocol with a stdlib fallback.
- No runtime dependency; `import fenolite.geometry` works with no extra installed.

**Non-Goals:**
- Everything listed under "Non-goals" in the proposal (the pyclipper and shapely backends, fallback operations beyond convex intersection, zone fill, widened-shape clearance, pad shape expansion, file I/O, model mapping, Clipper2, numpy, floats in results, capabilities reporting).
- Interior-overlap tests with exact collinear-edge handling (`polygons_intersect` is closed-set).
- Performance work beyond the STR index (no C extension, no vectorisation).

## Decisions

1. **Package shape and reuse of `Point`.** `fenolite.geometry` re-exports `Point` and `Size` from `fenolite.core.coords` and adds free functions instead of operators, so `core` is untouched and the model keeps its dataclasses. Hot loops may use plain `tuple[int, int]` internally; the public API takes and returns `Point`. `Vec` is a type alias of `Point` used for displacements. Functions that return a `Point` return integer nanometres; exact rational results (intersection points, centres, squared distances, fixed-point translations) are `Fraction`; no public function returns a `float`. *Rejected:* a separate `Vec` class with operators; adding `__add__` to `core.coords.Point` (changes `core-primitives` for convenience only).

2. **One frame, sign stated once.** Coordinates are in the KiCad file frame: X to the right, **Y down** (S-0001/S-0010). `orient2d(a, b, c) = (b.x−a.x)(c.y−a.y) − (b.y−a.y)(c.x−a.x)`; its sign is called *positive* or *negative* orientation. A positive value is a left turn in a Y-up mathematical frame and therefore appears **clockwise on screen**. Specs and docs never say "CCW" without naming the frame. External outputs in another frame (the IPC-D-356 export is Y up, S-0019) are converted at the comparison, never in the kernel. *Rejected:* flipping Y on import.

3. **Exact predicates with Python integers and `Fraction`.** With 32-bit coordinates (S-0010) differences fit in 33 bits and `orient2d` products in about 66 bits: exact, no filter needed. Comparisons that decide a clearance never form a fraction: `dist < c ⇔ cross² < c²·|d|²` in integers. *Rejected:* floats with adaptive-precision predicates (far more code than exact ints); ints-only without `Fraction` (intersection points need rationals).

4. **Rounding policy.** Every exact rational becomes nanometres only through `round_point(x, y)`, which applies `core.units.round_half_even_div` per axis (error ≤ 0.5 nm per axis, ≤ √2/2 nm Euclidean). A rounded intersection lies in general on neither input segment, so no predicate is ever re-evaluated on a rounded point; documented in `docs/geometry.md`. Any constructor fed with rounded points (`apply_arc`, `apply_polygon`, clipping) can therefore meet a degenerate result and raises `geometry.degenerate` or returns an empty result as specified per function.

5. **Arcs are their three stored points.** `Arc(start, mid, end)` is authoritative; `centre` (exact `Fraction` pair, circumcircle formula with `D = 2·orient2d`) and `radius2` (exact `Fraction`) are derived and never used for a rule decision, because for shallow arcs the stored points condition the centre badly (exploratory: 0.88 mm centre error for r = 10 mm, 0.1° sweep). Construction rejects `start == end` (a full circle is a `Circle`) and `mid` equal to an endpoint (`GeometryError`, code `geometry.degenerate`). Collinear points are accepted when `mid` lies strictly between `start` and `end` (`is_straight`, `centre is None`); collinear with `mid` outside is rejected. `orientation` is the sign of `orient2d(start, mid, end)`. **KiCad does not preserve it**: a re-save swaps `start` and `end` of negatively oriented graphic arcs (`H-G-ARC-DIR`), so consumers must not base any rule on `Arc.orientation` read from a file; the point set `{start, end}` and `mid` are what survive (`H-G-ARC-ROUND`). A point on the circle is on the arc iff `orient2d(start, end, p)` has the sign of `orient2d(start, end, mid)` or `p` is an endpoint. `bbox()` is exact and outward-rounded: start/end plus each axis extreme `centre ± r` that lies on the arc, with `floor`/`ceil` of `cx ± r` decided by exact comparison of squares.

6. **Deterministic polygonisation.** `Arc.polygonize(tol)`, `Circle.polygonize(tol, *, outer=False)` and `Path.polygonize(tol)` never call `math.cos`/`sin`. An arc is split at `mid`; a circle is split into four quarter arcs at its axis extremes, starting at the rounded point `(cx + r, cy)` and in positive orientation. Each part is bisected uniformly (every chord of a part at the same depth): the new vertex is `centre + r·u`, `u` the unit direction of the chord midpoint from the centre, computed with `isqrt` on integers scaled by 2^64 and rounded with `round_point`, until the exact sagitta of every chord (measured from the true circle) is ≤ `tol`, or 32 levels are reached. Consecutive duplicate vertices produced by rounding are removed. Default (`outer=False`): vertices within 1 nm of the circle, arc output starts at `start`, ends at `end` and contains `mid`; every point of the true curve is within `tol + 1 nm` of the polyline; the 32-level cap binds only when `r` is of the order of `tol` (tiny radii) and then the documented bound is `tol + 1 nm` as well. `outer=True` exists **only for `Circle`**: vertices at radius `R = r + tol + 1 nm` (within 1 nm after rounding) with the sagitta bound measured at `R`, so every chord stays at distance > `r` from the centre and the polygon contains the disc. Outer variants for arcs and paths wait for the change that needs them. Default `tol = 5000` nm, KiCad's default maximum approximation error (S-0010). *Rejected:* float trigonometry (platform-dependent, S-0011); fixed angular steps (not bounded by chord error).

7. **Rotation through a fixed-point table.** `cos_sin_fixed(udeg) -> (C, S)` returns `round(cos θ·2^128)`, `round(sin θ·2^128)` computed with series recipes (S-0012) inside `decimal.localcontext(decimal.Context(prec=70, rounding=decimal.ROUND_HALF_EVEN))`, so the caller's decimal context (precision, rounding, traps) cannot change the table; memoised with `functools.lru_cache`; multiples of 90° and the exact half values (`S(30°) = C(60°) = 2^127` and their symmetric angles) are hard-coded. Rotation of `(x, y)` is `(rhe(x·C + y·S, 2^128), rhe(−x·S + y·C, 2^128))`. Pre-rounding error ≤ (|x|+|y|)·2^−129 (≈ 1e-29 nm for 32-bit inputs). That the result equals the correctly rounded exact rotation, ties included, is an **observed property** checked against an 80-digit `decimal` reference on generated points and angles, not a proven theorem. Documented bound: ≤ 0.5 nm per axis. *Rejected:* `math.sin/cos` (platform-dependent; observed wrong tie rounding); rational rotations; a per-call `decimal` evaluation (0.1 ms per call).

8. **Transforms compose symbolically and round once.** `Transform` is `p ↦ R(θ)·M^m·p + t`, `M` = mirror about the local X axis (`y ↦ −y`), applied first. The rotation convention in the Y-down frame is `x' = x·cosθ + y·sinθ`, `y' = −x·sinθ + y·cosθ` (positive angles appear counter-clockwise on screen, matching KiCad: S-0010, S-0019, `H-G-ROT-DIR`). Angles are normalised to `[0, 360 000 000)`. `compose(a, b)` (apply `b` then `a`) adds angles and XORs mirrors (`M·R(θ) = R(−θ)·M`) and keeps the translation in 2^128 fixed point, so `compose(a, b).apply(p)` rounds once (≤ 0.5 nm per axis from the exact map) while `a.apply(b.apply(p))` rounds twice (≤ 1 nm). The properties `dx`, `dy` return that translation exactly as `Fraction` (integer-valued for placements and quarter-turn compositions); `apply(Point(0, 0))` gives the rounded translation. `inverse()` is exact for multiples of 90° with integer translation; otherwise, for every integer point `p`, `t.inverse().apply(t.apply(p))` is within 1 nm of `p` per axis. `apply_angle(u) = (−u if mirror else u) + θ (mod 360°)`. `Transform.placement(at, rot_udeg, mirror=False)`; a mirror about the Y axis is `mirror=True` composed with 180°. Observed storage of a bottom-side footprint: its children are already mirrored in the file, and absolute = `at + R(θ)·stored` with no further mirror (`H-G-BOTTOM-PLACE`, checked by the ipcd356 test). That the stored children equal the library footprint mirrored about local X (`H-G-BOTTOM-STORE`) and how the library angle maps to the stored one (`H-G-FLIP`) compare board files with library files, which `kicad-cli` does not export; the kernel offers the mirror but encodes no flip rule. Pad angles stored absolute (`H-G-PAD-ANGLE-ABS`) are handled by `apply_angle` and its inverse.

9. **Polygons: non-zero rule, integral doubled area, one normal form.** `Polygon(outer, holes=())` validates at construction: ≥ 3 vertices per ring, no closing duplicate, no consecutive duplicates, `area2 ≠ 0`; a ring that passes through a vertex twice (a pinch) is accepted. `area2` (shoelace, exact int, twice the area) gives orientation. Simplicity is a separate O(n log n + k) test (`is_simple`). Default fill rule is non-zero; even-odd is available. `Polygon.normalize()` applies the ring rules: outer `area2 > 0`, holes `area2 < 0`, each ring starts at its lexicographically smallest vertex, collinear vertices removed, holes sorted by their normalised vertex tuple. `normalize_polygons(polys)` is the canonical form of a polygon set (the OGC model): it first splits every ring at repeated vertices so that each ring is simple — a sub-loop with the ring's own orientation becomes a separate ring of the same kind (regions touching at a vertex become separate polygons), a sub-loop of opposite orientation inside an outer ring becomes a hole of that polygon (a hole touching its shell stays a hole) — then normalises each polygon and sorts the set by `(bbox as (x0, y0, x1, y1), outer ring tuple, holes tuple)`. Every boolean backend returns this form, so results compare with `==`. *Rejected:* even-odd default (non-zero is the natural choice for unions of pads and zones, S-0017); leaving pinches unnormalised (Clipper without `StrictlySimple` and GEOS represent the same region differently, S-0017).

10. **Mixed contours.** `Path(pieces: tuple[Segment | Arc, ...], closed: bool)` models `pts` lists with arcs (S-0018, `H-G-PTS-ARC`: `fp_poly`, custom-pad `gr_poly` and zone polygons) and outlines drawn with lines and arcs (S-0001). `assemble_rings(pieces)` chains unordered pieces into closed `Path`s by **exact** endpoint equality, reversing pieces as needed. It is deterministic for every input order: each ring starts at its lexicographically smallest endpoint and is traversed so that its polygonisation at `DEFAULT_TOL` has positive `area2` (if that is 0, towards the lexicographically smaller neighbouring endpoint, then the smaller `mid`). A zero-length `Segment` (`a == b`) raises `geometry.degenerate` naming the point; callers that meet such pieces in files filter and report them first. A dangling endpoint or a vertex shared by more than two pieces raises `geometry.open-contour` / `geometry.branching-contour` naming the points. *Rejected:* tolerance snapping by default (hides authoring errors; additive keyword later).

11. **Spatial index: STR-packed and immutable.** `SpatialIndex.build(items)` packs `(BBox, payload)` pairs with Sort-Tile-Recursive (node capacity 16); `query(bbox)` returns payloads whose closed boxes intersect, in insertion order; `pairs()` returns every intersecting index pair `(i, j)`, `i < j`, sorted. The index is rebuilt, never updated. *Rejected:* a uniform grid (degrades with uneven item sizes); a dynamic R-tree (update code the immutable model never needs).

12. **Boolean backend protocol.** `BooleanBackend` exposes `name`, `operations: frozenset[str]` and `union`, `intersection`, `difference`, `xor`, `offset(polys, delta, *, join, tol, miter_limit)`. Inputs are sequences of `Polygon` read with the non-zero rule; outputs are `normalize_polygons` results containing only polygons. The coordinate domain is |v| ≤ 2^31 − 1 nm (S-0010); values outside raise `geometry.out-of-range` before any backend code runs.

13. **Scope of backends in this change: protocol, loader and fallback only.** `select_backend(prefer=None)` walks `BACKEND_ORDER`; in this change it is `("fallback",)`. `prefer` names one; an unknown name raises `ValueError` listing the known names. `available_backends()` lists the usable ones. The pyclipper and shapely backends (`clipper_backend.py`, `shapely_backend.py`, the paths fixed by the cross-change interface) are added by the first change that needs booleans or offsets (zone fill), which prepends `"clipper", "shapely"` to `BACKEND_ORDER`; no v0.1 path needs them, and deferring them keeps this change within about a week and imports no LGPL code (see "Hand-over"). *Rejected:* shipping both backends now (two backends, cross-checks, a CI job and a licence decision for about a week of work no caller needs yet).

14. **Stdlib fallback: convex intersection only.** `FallbackBackend.intersection(a, b)` clips with Sutherland–Hodgman (through `clip_convex`) when every operand is a single hole-free convex polygon. After rounding (decision 4) it removes consecutive duplicate and collinear vertices and returns `()` when fewer than three vertices remain or `area2 == 0` (touching operands, slivers that collapse); otherwise one polygon that is simple and convex within 1 nm (per-axis rounding can bend a vertex slightly inward). Any other operation or input raises `BackendUnavailable` with issue code `geometry.backend-unavailable` and hint `pip install 'fenolite[geo]'`. *Rejected:* a pure-Python general polygon clipper (weeks of work and a long bug tail); Sutherland–Hodgman with concave subjects (produces overlapping bridge edges).

15. **Errors.** `fenolite.geometry.errors`: `GeometryError(FenoliteError)` with `code` (`geometry.degenerate`, `geometry.out-of-range`, `geometry.open-contour`, `geometry.branching-contour`) and `BackendUnavailable(FenoliteError)` carrying an `Issue` (`geometry.backend-unavailable`, severity `error`). Codes follow `core.errors.ISSUE_CODE`. The CLI mapping to an exit code belongs to the first command that uses geometry.

16. **Loading the `geo` extra without breaking layering.** No module of `geometry` contains a static third-party import. `fenolite/geometry/boolean/_extra.py::load_extra(name)` is the single place in the stdlib-only packages that calls `importlib.import_module`, for names in the closed tuple `GEO_MODULES = ("pyclipper", "shapely")` (the import names of the declared `geo` extra); other names raise `ValueError`, and `ImportError` becomes `BackendUnavailable`. It is created in task 2.1 so that the import-graph rule of task 2.2 has its target; in this change no backend calls it. The `package-layering` requirement "Third-party imports only in extras-guarded modules" is MODIFIED (full text copied) to state this one exception, because the current text implies that `geometry` never loads a third-party package. *Rejected:* `import shapely` inside functions (pyright strict errors without the extra); moving the backends to a new top-level package (the interface fixes `fenolite.geometry.boolean`).

17. **KiCad frame and arc evidence.** Two `needs_kicad` tests live in `tests/kicad/` (the folder of tests that call `kicad-cli`), so the `kicad-10` job of c0006 and the `kicad-9` job of c0007 run them in required-resource mode. Authored CC0 files use format version 20241229, which both majors load. Each test first runs `kicad-cli version`, fails unless the major is 9 or 10, and prints the exact version, which is written into the hypothesis result; a row is labelled `KICAD-VERIFIED (<major>.0.x)` only for the majors that ran.
    - `tests/kicad/test_geometry_frame.py` writes a minimal board (front footprints at 90° and 30°, a back footprint at 30° with children stored mirrored, two through-hole pads each on named nets), runs `kicad-cli pcb export ipcd356`, reads the unit from the header (expects `UNITS CUST 0`, 0.0001 in = 2540 nm) and each pad's `X…Y…` pair, and converts the export frame back to the file frame: Δx_file = ΔX·2540 nm, Δy_file = −ΔY·2540 nm. Pad differences are compared with `Transform.placement(at, θ).apply(stored)` differences divided by 2540: exactly for the 90° footprint (local offsets are multiples of 2540 nm), within ±2 units per axis for the 30° footprints (each exported value is quantised to one unit with an unobserved rounding mode, and a difference subtracts two). It also records the exported pad rotation field (observation only, `H-G-PAD-ANGLE-ABS`).
    - `tests/kicad/test_geometry_arcs.py` writes a footprint into a temporary `.pretty` folder with `fp_arc`s of r = 0.1 mm/10°, 1 mm/1°, 10 mm/0.1° and 50 mm/0.05° **in both orientations**, an `fp_poly` and a keepout `zone` polygon whose `pts` each contain an `arc` (one of each orientation), runs `kicad-cli fp upgrade --force`, and checks: for every `fp_arc`, `mid` and the set `{start, end}` are unchanged (`H-G-ARC-ROUND`) and the written orientation is positive (`H-G-ARC-DIR`); every `pts` arc is still present with the same three points in the same order (`H-G-PTS-ARC`).
    Minimal files are written from S-0001 and the observed demo layout; they are authored, CC0 and never copied from KiCad data.

18. **CI.** No new job. The `unit` job runs `tests/unit/geometry` (the fallback tests included) on ubuntu and macOS; the KiCad jobs of c0006/c0007 run `tests/kicad`, which now includes the two tests above.

## Hypotheses (registered by task 1.2, backend column in brackets)

The brief allocates the `H-G-*` prefix to this change, so KiCad-frame rows use it with backend `kicad`; the register gains a note saying so.

| id | statement | test | criterion |
|---|---|---|---|
| H-G-ROT-DIR [kicad] | A board-file footprint angle θ maps local `(x, y)` to `(x·cosθ + y·sinθ, −x·sinθ + y·cosθ)` in the Y-down frame (S-0010, S-0019) | `tests/kicad/test_geometry_frame.py` | front pad differences match at 90° (exact) and 30° (±2 units) |
| H-G-BOTTOM-PLACE [kicad] | For a bottom footprint, absolute = `at + R(θ)·stored`, no further mirror (S-0019) | same | back pad differences match at 30° (±2 units) |
| H-G-BOTTOM-STORE [kicad] | Stored children of a bottom footprint = library footprint mirrored about local X (S-0019, one footprint of one origin) | board backend change: corpus boards from ≥ 2 origins vs their library footprints | one rule explains every pad; target CORPUS-VERIFIED |
| H-G-FLIP [kicad] | How a library footprint's angle maps to a stored bottom angle (S-0010, S-0019) | same as H-G-BOTTOM-STORE | one rule explains every footprint |
| H-G-PAD-ANGLE-ABS [kicad] | Pad angles in board files are absolute (footprint angle included) (S-0019) | same as H-G-BOTTOM-STORE; the frame test records the export's `R` field | stored pad angle − footprint angle equals the library pad angle for every pad |
| H-G-ARC-ROUND [kicad] | KiCad keeps an `fp_arc`'s `mid` and the set `{start, end}` on re-save (S-0001) | `tests/kicad/test_geometry_arcs.py` | unchanged after `kicad-cli fp upgrade --force`, all four radius/sweep pairs, both orientations |
| H-G-ARC-DIR [kicad] | KiCad re-saves graphic arcs with positive `orient2d(start, mid, end)`, swapping `start`/`end` otherwise (observed 10.0.6) | same | every re-saved `fp_arc` has positive orientation |
| H-G-PTS-ARC [kicad] | `pts` may contain `(arc (start)(mid)(end))` in `fp_poly`, custom-pad `gr_poly` and zone polygons; undocumented in S-0001 (S-0018) | same, plus the library scan of the KiCad libraries change | each `pts` arc survives with the same points in the same order |

That a centre derived from a shallow arc is ill-conditioned is mathematics, shown by a unit test in `test_arc.py`, not a KiCad hypothesis.

## Files and public API

```
src/fenolite/geometry/__init__.py      re-exports the names below; select_backend, available_backends
src/fenolite/geometry/errors.py        GeometryError(message, *, code="geometry.degenerate"), BackendUnavailable(issue: Issue)
src/fenolite/geometry/vector.py        Point, Size, Vec = Point
    add(p: Point, v: Vec) -> Point; sub(a: Point, b: Point) -> Vec; neg(v: Vec) -> Vec
    dot(a: Vec, b: Vec) -> int; cross(a: Vec, b: Vec) -> int; norm2(v: Vec) -> int
src/fenolite/geometry/predicates.py
    orient2d(a: Point, b: Point, c: Point) -> int
    class SegmentRelation(StrEnum): DISJOINT, PROPER, TOUCHING, COLLINEAR_OVERLAP, COLLINEAR_TOUCH
    classify_segments(a: Point, b: Point, c: Point, d: Point) -> SegmentRelation
    intersection_point(a, b, c, d) -> tuple[Fraction, Fraction] | None
    round_point(x: Fraction | int, y: Fraction | int) -> Point
    class Location(StrEnum): INSIDE, OUTSIDE, BOUNDARY
    class FillRule(StrEnum): NONZERO, EVENODD
    point_in_ring(p: Point, ring: Sequence[Point], rule: FillRule = FillRule.NONZERO) -> Location
    dist2_point_segment(p, a, b) -> Fraction; dist2_segment_segment(a, b, c, d) -> Fraction
    segments_closer_than(a, b, c, d, limit: int) -> bool          # integer-only comparison
    floor_sqrt(q: Fraction | int) -> int; ceil_sqrt(q: Fraction | int) -> int
src/fenolite/geometry/shapes.py
    BBox(x0: int, y0: int, x1: int, y1: int)  # closed; of_points(), union(), intersects(), contains_point(),
                                               # contains_bbox(), inflate(d), width, height
    Segment(a: Point, b: Point)                # bbox(), length2, is_degenerate
    Arc(start: Point, mid: Point, end: Point)  # centre, radius2, is_straight, orientation (+1/-1/0),
                                               # contains_point_on_circle(p), bbox(), polygonize(tol=5000), reversed()
    Circle(centre: Point, radius2: int)        # from_kicad(center, end), from_radius(centre, r), bbox(),
                                               # polygonize(tol=5000, *, outer=False)
    DEFAULT_TOL: int = 5000; MAX_BISECTION_DEPTH: int = 32
src/fenolite/geometry/polygon.py
    Polygon(outer: tuple[Point, ...], holes: tuple[tuple[Point, ...], ...] = ())
        area2 -> int; bbox() -> BBox; locate(p, rule=FillRule.NONZERO) -> Location; is_simple() -> bool
        is_convex() -> bool; normalize() -> Polygon
    area2(ring) -> int; normalize_polygons(polys: Iterable[Polygon]) -> tuple[Polygon, ...]
    convex_hull(points: Iterable[Point]) -> tuple[Point, ...]
    clip_convex(subject: Polygon, clip: Polygon) -> Polygon | None        # both convex, hole-free; None if empty
    polygons_intersect(a: Polygon, b: Polygon) -> bool                     # closed sets
    Path(pieces: tuple[Segment | Arc, ...], closed: bool)                  # bbox(), polygonize(tol) -> tuple[Point, ...]
    assemble_rings(pieces: Iterable[Segment | Arc]) -> tuple[Path, ...]
src/fenolite/geometry/transform.py
    TRIG_BITS = 128; FULL_TURN = 360_000_000
    cos_sin_fixed(udeg: int) -> tuple[int, int]
    rotate_point(p: Point, udeg: int) -> Point                             # TypeError on non-int arguments
    Transform: identity(), translation(dx, dy), rotation(udeg), mirror_x_axis(), placement(at, rot_udeg, mirror=False)
        rot_udeg: int, mirror: bool, dx: Fraction, dy: Fraction (properties); apply(p) -> Point; apply_angle(udeg) -> int
        apply_segment / apply_arc / apply_polygon (may raise geometry.degenerate) / apply_bbox (outward)
        compose(inner: Transform) -> Transform; inverse() -> Transform
src/fenolite/geometry/index.py
    SpatialIndex[T]: build(items: Iterable[tuple[BBox, T]], *, capacity=16) -> SpatialIndex[T]
        query(bbox) -> list[T]; query_indices(bbox) -> list[int]; pairs() -> list[tuple[int, int]]; __len__
src/fenolite/geometry/boolean/__init__.py   BACKEND_ORDER = ("fallback",); select_backend(prefer: str | None = None) -> BooleanBackend;
                                            available_backends() -> tuple[str, ...]
src/fenolite/geometry/boolean/base.py       BooleanBackend (runtime-checkable Protocol), Join = Literal["round", "miter", "square"],
                                            COORD_LIMIT = 2**31 - 1, check_domain(polys) -> None
src/fenolite/geometry/boolean/_extra.py     GEO_MODULES = ("pyclipper", "shapely"); load_extra(name: str) -> ModuleType
src/fenolite/geometry/boolean/fallback.py   FallbackBackend (name "fallback", operations {"intersection"})
tests/unit/geometry/  test_vector.py, test_predicates.py, test_shapes.py, test_arc.py, test_polygon.py, test_normal_form.py,
                      test_paths.py, test_transform.py, test_index.py, test_boolean_fallback.py, test_extra_loader.py
tests/kicad/          test_geometry_frame.py, test_geometry_arcs.py (needs_kicad)
tests/strategies.py   + small_points, rings (simple, from convex hulls), arcs, transforms
docs/geometry.md, docs/formats/kicad/geometry.md
```

## Evidence level per behaviour (before merge)

| behaviour | level | how |
|---|---|---|
| predicates, shapes, polygons, normal form, index, transform algebra, fallback | mechanical (no format label) | unit + hypothesis property tests in the `unit` job on ubuntu and macOS |
| fixed-point table identical on every platform and independent of the caller's decimal context | mechanical | golden `(C, S)` values for 12 angles, also under an altered global context |
| `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE` | KICAD-VERIFIED (10.0.x) | `tests/kicad/test_geometry_frame.py` passing with local `kicad-cli` 10.0.x before merge (version and date in the row); 9.0.x once the `kicad-9` job runs it |
| `H-G-ARC-ROUND`, `H-G-ARC-DIR`, `H-G-PTS-ARC` | KICAD-VERIFIED (10.0.x) | `tests/kicad/test_geometry_arcs.py`, same rule |
| `H-G-BOTTOM-STORE`, `H-G-FLIP`, `H-G-PAD-ANGLE-ABS` | INFERRED | settled by the board backend change on corpus boards from ≥ 2 origins |

The two KiCad tests are merge-blocking: they must pass locally with `kicad-cli` 10.0.x. If a criterion fails, the row is recorded as `refuted` with the observed behaviour, and the design, spec and `docs/formats/kicad/geometry.md` are corrected in this change before merge (task 10.2).

## Hand-over to the change that adds the pyclipper and shapely backends

Facts found while designing them, to be carried over (not normative here):
- Declaring a shapely backend loads LGPL GEOS in-process (S-0015). ADR-0004 rejects copyleft behind an optional extra, and `tests/unit/test_no_copyleft_deps.py` bans LGPL Python packages. That change must first add an ADR (or an ADR-0004 amendment) stating whether a permissive Python package that dynamically links an LGPL native library inside its own wheel may be an optional extra, citing S-0015, or else ship pyclipper only.
- Clipper: set `StrictlySimple = True`; `ArcTolerance` is clamped to `|delta|·0.25`, so offsets of the two backends are compared by bbox and area only (S-0017).
- shapely 2.1.2 / GEOS 3.13.1: `intersection(triangle (0,0),(3,0),(0,3), box(0,1,3,2), grid_size=1)` returns a collection with a `LINESTRING (3 1, 2 1)`; the band `-10..10 × 1..2` does not; touching squares `0..10` and `10..20` return `LINESTRING (10 0, 10 10)`, which must become `()` (`H-G-SHAPELY-GC`, to register there).
- Exact cross-backend agreement is limited to inputs whose pairwise edge intersections are all integer points; results compare through `normalize_polygons`.
- The `geo` CI job, the `ci-baseline` delta for it and the `pyclipper>=1.4` bound (S-0016) belong to that change.

## Risks / Trade-offs

- [Fixed-point rotation is ≈ 2× slower than float] → cache per angle; 100 000 rotations ≈ 0.05 s.
- [`Fraction` arithmetic is slow in hot loops] → predicates and clearance tests are integer-only.
- [Rounded intersection points break later predicates] → documented rule (decision 4); general booleans are delegated to backends that snap consistently.
- [A minimal authored board or footprint does not load in `kicad-cli`] → exploratory probes already loaded both with 10.0.6; tasks 8.1/8.2 each have a day, and the tests stay merge-blocking.
- [IPC-D-356 record layout is known only from observed output] → the test extracts only the unit and coordinate pairs by pattern and compares differences between pads, never absolute placement.
- [A `kicad-cli` of an untested major "verifies" a row] → the tests assert the major and record the exact version.
- [Exact endpoint chaining rejects real-world outlines with sub-nanometre gaps or zero-length segments] → corpus runs in the board backend change will tell; a `tolerance=` keyword is additive, and callers filter zero-length pieces.

## Migration Plan

- New package only; nothing persisted changes. Rollback = remove `src/fenolite/geometry/` and the two `tests/kicad/test_geometry_*.py` files.

## Open Questions

- The dev-docs board page (sexpr-pcb) is registered as S-0021 by c0006; this change cites S-0001 only for arc and circle encodings to avoid a duplicate row.
- Should `lens` be allowed to import `geometry` (moved-footprint detection)? Deferred to the change that writes the layout lens.
- Should `assemble_rings` accept a snapping tolerance for outlines KiCad itself accepts? Decided on corpus data by the board backend change.
