## Context

- **Today.** `backends/altium/adapter/copper.zones` builds `ZoneFill(layer, region_points(region.outline))` for each region of a poured polygon. `RegionRecord.holes` (c0041; `docs/formats/altium/pcb-read.md`) is parsed and then only counted in the census as `region-holes`. The living requirement "Zones from polygons" says so: "region holes are not in the model and are counted".
- **What it costs.** `docs/evidence/equivalence-triangle.md`, "Level 5": on the public row `altium-third-party-pcbdoc-03` the main pour has 268 holes and five other regions start inside holes, so Fenolite's read joins them to the pour and KiCad's does not (one `route-stub` notice, pinned by count in `tests/kicad/equivalence/test_triangle_level5.py`). `checks/copper.py` reads a fill as a filled ring, so every item of another net inside a hole is a short.
- **What the model holds.** `model.board.ZoneFill.polygon` is one ring. A KiCad board stores a filled polygon with holes as one ring too: each hole is reached by a bridge of zero width, walked there and back. Fenolite's KiCad reader keeps such rings as they are, and `geometry.point_in_ring`, `geometry.thick` and `checks/copper.py` already answer correctly on them.
- **Constraints.** Integer nanometres, no float, deterministic output, no runtime dependency, no change of the model.

## Goals / Non-Goals

**Goals:**
- Copper that lies in a hole of an imported pour is not joined to the pour, in the copper check and at level 5.
- A fill of a region without holes is the same polygon as before, so boards without holes keep their content.
- A hole that cannot be merged is said, with a count.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **One ring with bridges, not a new field.** A `holes` field on `ZoneFill` would change the model, the canonical JSON, both writers and every reader of a fill. The keyhole ring needs none of that and is the form KiCad's own files use. Checked on an authored case before any code (2026-10-06): for the square `0..100` with the hole `30..70 × 40..60` merged by a bridge on `y = 40`, a point in the hole is `OUTSIDE` under both fill rules, a track and a filled square inside the hole do not touch the fill (`thick_touch`), a track across the bridge touches (the bridge runs through copper), and the doubled area is the outline's minus the hole's.
2. **Where the helper lives.** `geometry/polygon.py`, beside `Polygon` and `area2`: it is pure ring arithmetic and the Altium adapter may import `geometry`. Name `keyhole_ring`, result `Keyhole(ring, merged, outside)`.
3. **The outline is kept as given.** The helper neither reverses nor rotates `outer`; holes are turned to run against it. A region without holes therefore gives the tuple it gave before this change, and the non-zero rule gives winding 0 inside a hole whichever way the document wound its rings.
4. **Order and anchor.** Holes are merged by ascending leftmost vertex (ties by the point tuple). The anchor of a hole is the nearest crossing of a ray towards −x from that vertex with the ring built so far. A hole merged earlier has no point to the right of a later hole's leftmost vertex except on the same vertical line, so the bridge of a later hole crosses no earlier hole and no later one: it runs through copper. The winding number of the result is the sum of the windings of the outline and of the holes, whatever the anchors are, because each bridge is walked once in each direction.
5. **Rounding.** An anchor inside an edge gets `x` rounded half to even (`core.units.round_half_even_div`, as `round_point` does), so it may lie up to half a nanometre off the edge; the edge then bends by that much. An anchor at a vertex is the vertex. The area identity is exact when no anchor was rounded, which the property test states.
6. **Holes that are dropped.** Fewer than three distinct points or no area: dropped, counted only in the census (`region-holes`). Leftmost vertex outside the outline: dropped, counted in `Keyhole.outside`, reported by `altium.import.zone-hole-outside` (warning) once per document. A hole on the outline's boundary is merged with a bridge of zero length.
7. **Census.** `region-holes` keeps its meaning, "holes that are not in the model": for a region that is a fill it now counts the dropped holes only; for free and footprint regions it counts all, as before.
8. **Cut order.** First the 300-hole bound, then the copper-check measurement, never the property test and the triangle.

## Files and public API

- `src/fenolite/geometry/polygon.py`: `Keyhole(ring: Ring, merged: int, outside: int)`, `keyhole_ring(outer: Sequence[Point], holes: Iterable[Sequence[Point]]) -> Keyhole`; re-exported by `fenolite.geometry`.
- `src/fenolite/backends/altium/adapter/copper.py`: `zones` builds the fill polygon with `keyhole_ring` and reports the dropped holes; `shapes` no longer counts the holes of a region that is a fill.
- `src/fenolite/backends/altium/adapter/codes.py`: `altium.import.zone-hole-outside` (warning); `src/fenolite/cli/data/explain.toml` and the table of `docs/cli-contract.md`, "Altium import".
- Tests: `tests/unit/geometry/test_keyhole.py`, `tests/unit/backends/altium/adapter/test_copper.py` and `test_codes.py` (extended), `tests/kicad/equivalence/test_triangle_level5.py` (the pinned notice).
- Pages: `docs/geometry.md`, `docs/formats/altium/import.md`, `docs/evidence/equivalence-triangle.md`.

## Other places that read a region

| place | what it makes | holes | this change |
|---|---|---|---|
| `adapter/copper.zones` | the fills of a zone | dropped | fixed |
| `adapter/copper.shapes`, free regions | a filled `polygon` graphic, on copper with its net in the bag (`altium.import.copper-shape`) | dropped, counted as `region-holes` | not changed: a graphic is not copper with a net in the model, the copper check and level 5 do not read it |
| `adapter/copper.definition_graphics`, footprint regions of a library | a filled `polygon` graphic | dropped, counted | not changed, for the same reason |
| regions of a component in a PCB document | nothing (`footprint-graphics`) | counted | not changed |
| regions of a split plane or of an unmapped polygon | nothing (`polygons`, `pour-primitives`) | counted | not changed |
| `read/bodies.py`, component bodies | `ComponentBody` outline | parsed, not used | not changed: a body is no copper |
| `shape_regions` (`ShapeBasedRegions6`) | nothing (`shape-based-regions`) | not read as holes | not changed |

## The writer side (not changed)

`backends/altium/pcbdoc.py` writes a zone as a polygon record without poured copper ("Polygons stay unpoured", c0085), and `lens/altium_copper.py` lowers a zone by its outline. No `ZoneFill` reaches a document, so a keyhole ring is never written and nothing has to follow from this change. A later change that writes fills as regions would have to split a keyhole ring back into an outline and holes (at the points the ring visits twice) or write the ring as an outline with zero-width slits; that is a decision of that change.

## Measured (2026-10-06, `kicad-cli` 10.0.6, macOS, local)

Counts only; the document is the public row `altium-third-party-pcbdoc-03` (S-0172), read from the corpus cache.

**Level 5, Fenolite's read against KiCad's import** (`tests/kicad/equivalence/test_triangle_level5.py`):

| | before | after |
|---|---|---|
| pieces of copper (Fenolite, KiCad) | 54, 59 | 59, 59 |
| pieces that reach no pad (Fenolite, KiCad) | 0, 5 | 5, 5 |
| differences at levels 1 to 5 | 0 | 0 |
| `route-stub` notices | 1 | 0 |
| points of the six fills (Fenolite, KiCad) | 180, 7 582 | 7 515, 7 582 |

**The copper check on Fenolite's read** (`checks.copper.check_copper(design, pads=None)`; items: 6 fills, 604 tracks, 47 vias; 383 pads left out because the Altium backend has no board frame):

| finding | before | after |
|---|---|---|
| `copper.short` | 267 | 0 |
| `copper.clearance` | 6 | 266 (221 fill against track, 45 fill against via) |
| pairs judged | 1 339 | 1 936 |

- The 267 shorts were tracks and vias of other nets that lie in holes of the pour.
- The clearance findings that replace them are all against 0.5 mm with the source `zone`: the clearance the model gives a zone that names none. The import reads no clearance for a polygon. The gaps found are 0.127 mm to 0.493 mm, which is what the document's pour keeps. They are true gaps measured against a default the document never had; reading a polygon's clearance from its rules is outside this change (an open point for c0088, which runs the copper check on Altium input).
- `fenolite check` on the document runs no copper stage for an Altium input today (its stages are `model.validate`, `erc.lite`, `netlist.assignment_compare` and `roundtrip.rta0` to `rta2`), so the command's findings are the same before and after: exit 5 for 12 errors of `model.validate` that have nothing to do with copper; `roundtrip.rta0` and `rta1` are `ok`.

**Holes over the seven rows of the triangle list**: the poured regions hold 607 holes (136, 58, 271, 27, 45, 30, 40); all are merged, none is outside its outline, none is without area. The anchor searches test 994 703 edges on the third row and under 100 000 on each other row; the import of the third row takes under 0.1 s more.

**Round trips**: `tests/unit/lens`, `tests/unit/backends/altium` and `tests/corpus/test_altium_roundtrip.py` pass unchanged (2 658 passed). No round-trip level compares the zone fills of an import: RT-A0 to RT-A2 compare the readers' records.

## Sources registered by this change

- None. The hole layout of a region is already a row of `docs/formats/altium/pcb-read.md` (S-0160 and the census). What a hole means for a pour is read from `kicad-cli pcb import` (S-0020) on the public document of S-0172 and from the page on polygons and regions (S-0285); all three are registered.

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-IMP-ZONE-HOLES | The holes of a poured region are free of the pour's copper: copper of the same polygon that lies inside a hole is a piece of its own, as in KiCad's import of the document | `tests/kicad/equivalence/test_triangle_level5.py` on `altium-third-party-pcbdoc-03` | the same number of pieces per net on both sides and no `route-stub` notice on that row |
| H-G-KEYHOLE | The keyhole ring of an outline and its holes has the outline's area minus the holes' exactly when no anchor is rounded, and locates every point off the bridges as the polygon with holes does, under the non-zero and the even-odd rule | `tests/unit/geometry/test_keyhole.py` (property test) | every generated case holds; 300 holes within the stated bound of edge tests |

Both start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Size (design-days)

| group | dd |
|---|---|
| entry and registers | 0.25 |
| keyhole ring | 0.5 |
| adapter, code and pages | 0.25 |
| triangle, copper check, round trips | 0.25 |
| closing | 0.25 |

Total: 1.5. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-import`, "Zones from polygons": the bullet on `fills` loses "region holes are not in the model and are counted" and gains what `polygon` is and which holes are counted; two scenarios are added. "Import issue codes": the warnings gain `altium.import.zone-hole-outside`. Both are written as MODIFIED from the living text.
- `geometry-kernel`: ADDED "Keyhole ring of a polygon with holes".
- Archive order: after c0089, whose triangle test and evidence page this change edits. No other active change holds a delta for the two modified requirements (checked 2026-10-06).

## Risks / Trade-offs

- [Holes that overlap each other or cross the outline] → the winding inside the overlap is −1, which both rules read as inside. The documents measured hold none; the helper does not repair them, and the property test generates disjoint holes only.
- [A track that ends exactly on a bridge touches the fill] → correct: a bridge lies in copper.
- [The bridge of a hole bends an edge by up to half a nanometre] → below the 2 nm of the import's rounding; stated in the requirement.
- [Fills grow: a ring with 268 holes holds every hole's points plus two per bridge] → the copper check indexes the edges of a large ring; the triangle and the copper check are timed on the row with the largest pour.
- [Content of imported boards with holes changes] → the changelog says so; boards without holes are unchanged.

## Migration Plan

- None for callers: no signature changes. An imported Altium board whose pours have holes holds other fill polygons than before.
- Rollback: `zones` builds the fill from the outline alone.

## Open Questions

- **Should a free region on copper with holes become a keyhole graphic?** Default: no; it is a graphic and nothing reads it as copper. It becomes a question when the model gains a copper shape with a net.
