## Why

Every later board feature — reading arcs and outlines, placing footprints, courtyard and outline checks, comparing layouts, a light design-rule check for the second backend — needs geometry that gives the same answer on every platform. KiCad stores coordinates as 32-bit integer nanometres (S-0010), and the model already uses integer nanometres and microdegrees. Floating-point geometry would bring back rounding ties, wrong orientation signs near degeneracy and platform-dependent trigonometry (S-0011). This change adds an exact integer kernel before the KiCad backend (c0006–c0009) starts to use it.

## What Changes

- New stdlib-only package `fenolite.geometry` (layering: imports `core` only):
  - `vector.py`: re-exports `Point`/`Size` from `fenolite.core.coords` and adds integer vector helpers.
  - `shapes.py`: `Segment`, three-point `Arc` (exact circumcentre, exact outward-rounded bbox, deterministic polygonisation with a chord-error bound), `Circle`, `BBox`.
  - `polygon.py`: `Polygon` with holes, exact doubled area, simplicity test, a canonical normal form for polygon sets, convex hull, a convex-only clip, and `Path`/`assemble_rings` for mixed line/arc contours.
  - `transform.py`: `Transform` (µdeg rotation from a fixed-point cosine/sine table computed with `decimal`, mirror, translation, composition with a single rounding, inverse).
  - `predicates.py`: exact `orient2d`, segment classification and intersection, three-valued point-in-polygon, exact squared distances.
  - `index.py`: an immutable STR-packed `SpatialIndex`.
  - `boolean/`: the `BooleanBackend` protocol, the single loader for the existing `geo` extra, a stdlib fallback limited to convex intersection, and `select_backend()`.
- `docs/geometry.md` and `docs/formats/kicad/geometry.md` (KiCad frame, rotation direction, bottom-side placement, arc encoding and direction, arcs inside `pts`).
- Two `needs_kicad` tests under `tests/kicad/` that check the frame and arc conventions with `kicad-cli`; the KiCad CI jobs of c0006/c0007 run them.
- Size: about one week. The pyclipper and shapely backends, their cross-checks, their licence review and a `geo` CI job move to the first change that needs booleans (zone fill); no v0.1 path needs them.

## Capabilities

### New Capabilities
- `geometry-kernel`: exact integer primitives, predicates, shapes, polygons, transforms and spatial index.
- `geometry-boolean-backends`: the boolean protocol, backend selection, the fallback, and result normal form.

### Modified Capabilities
- `package-layering`: the stdlib-only rule gains one exception, the `geo` extra loader in `geometry` (MODIFIED, full text copied).

## Non-goals

- The pyclipper and shapely backends, offsets, and fallback operations beyond convex intersection; zone filling (KiCad fills zones through `kicad-cli`).
- Clearance between widened shapes, annular-ring and design-rule logic (the check changes).
- Reading or writing KiCad files; mapping model entities to geometry (the KiCad backend changes).
- Pad shape expansion and text geometry.
- Clipper2, numpy anywhere, and any float-based public result.

## Evidence level required

- Kernel mathematics: mechanical unit and property tests; no format behaviour, so no KiCad label.
- KiCad conventions in `docs/formats/kicad/geometry.md`: rotation direction (`H-G-ROT-DIR`), bottom-side placement (`H-G-BOTTOM-PLACE`), three-point arcs kept on re-save (`H-G-ARC-ROUND`), the arc direction KiCad writes (`H-G-ARC-DIR`) and arcs inside `pts` (`H-G-PTS-ARC`) reach **KICAD-VERIFIED** with a local `kicad-cli` 10.0.x run before merge; the tests are merge-blocking, and a refuted criterion is recorded as refuted and corrected in this change. Bottom-side storage relative to the library (`H-G-BOTTOM-STORE`), the flip rule (`H-G-FLIP`) and absolute pad angles (`H-G-PAD-ANGLE-ABS`) stay **INFERRED** until the board backend change compares corpus boards from ≥ 2 origins. Sources: S-0001, S-0010 … S-0019 in `docs/evidence/sources.md`.

## Impact

- New package `src/fenolite/geometry/`; tests under `tests/unit/geometry/` and `tests/kicad/`; `tests/strategies.py`; `tests/unit/test_import_graph.py`.
- Documentation and registers: `docs/geometry.md`, `docs/formats/kicad/geometry.md`, `docs/evidence/sources.md`, `docs/hypotheses.md`, `LEGAL-ANNEX.md`, `CHANGELOG.md`, and `src/fenolite/backends/kicad/PROVENANCE.md` if it exists at merge.
- No runtime dependency; `pyproject.toml`, the CI workflow, `fenolite.model`, its schemas and the CLI are unchanged.
