# c0413 design: rotated and custom teardrop parents

## Measurements (2026-11-05, base `origin/dev` `3675515a`)

Public row `kicad-demo-9-0-9-1-pcb-01` (`custom_pads_test`), strict `tests/_fidelity.roundtrip`, KiCad
10.0.6 (macOS `kicad-cli`):

| step | result |
|---|---|
| base | `7:opaque-count=1` (teardrop), `8:render-pixels=1`; no `derived_cache` summary: `_parents` raises "unqualified non-quarter parent pose" (footprint and custom pad at 20°) |
| scratch: pose let through | `_custom_anchor` raises "unknown custom clearance option" (`(clearance convexhull)` on a custom pad at 90°) |
| scratch: both let through | proof runs; status `native-cache-unqualified`. KiCad 10 regenerates 6 caches per side with identical exact geometry, but one cache touches only the primitive copper of a custom pad at 270° (its `gr_line` end, 4.7 mm from the anchor) |
| this change | status `equal`: 6 raw caches against 0, 6 regenerated on each side, same exact-geometry SHA-256 (`63e9eae9…`); the teardrop `opaque-count` is gone, `8:render-pixels=1` remains (c0414) |

## Decisions

### Non-quarter poses: fixed-point turn, bounded error, refusal in the band

`core.trig.cos_sin_fixed(udeg)` returns cos and sin rounded at 2**-128 (a 70-digit `decimal` series). A
pose angle must be whole microdegrees; a finer angle refuses. A quarter turn stays exact. Otherwise the
pad centre (footprint offset turned by the footprint angle) and every point mapped into the pad frame
are within 2**-113 mm of their exact values when all coordinates lie within 4096 mm (KiCad's 32-bit
nanometre coordinates stay within ±2148 mm). The parent carries `MARGIN = 2**-100`:

- a test holds when it holds for every body shrunk by the margin;
- it fails when it fails for every body grown by the margin;
- otherwise it raises, and `qualifies` refuses the board.

Shrinking and growing are exact supersets/subsets: a rectangle grows by a square (a superset of the
disc dilation) and shrinks by the margin on each side; circles, ovals, rounded rectangles and capsules
change their radius; a disc uses rational bounds of its square root 2**-64 apart. A coordinate beyond
4096 mm refuses a non-quarter parent. A margin-free parent at a non-quarter angle cannot be constructed.

### Custom pads

- `(options (clearance outline|convexhull) (anchor rect|circle))`. The clearance mode shapes the
  clearance outline only; the anchor remains copper in both (native control `hull-anchor`).
- The body is the anchor plus primitives Fenolite bounds from inside, in the pad frame: a `gr_line` of
  positive width is the capsule of half its width (round caps, native controls `line-*-cap`); a filled
  `gr_circle` is its disc (the stroke beyond is left out); a filled `gr_poly` of plain `xy` vertices or a
  filled `gr_rect` is its interior. Arcs, unfilled shapes, curved polygons and unknown primitives add
  nothing. Fill counts only as `(fill yes)` or `(fill solid)`.
- Polygon bodies are used only by exact (quarter-turn) parents: shrinking a polygon is not needed then.
- Bottom-side footprints keep the anchor only; the primitive frame on the bottom side is not measured.
- A drill offset on a non-quarter pad keeps refusing that parent, as before.

### Native proof scope

The contact controls run on KiCad 9.0.9 and 10.0.6: DRC `shorting_items` between a target pad and a
probe track of another net that starts at a far pad of that net (a track touching only the target is
re-netted on load, like `H-K-VIA-RENET`). Each case asserts both the native report and Fenolite's
prediction for the same point. The regeneration proof itself stays KiCad 10 only
(`H-K-DERIVED-TD-PROOF`: native 9 does not regenerate these caches); the 9.0.9 job covers the contact
controls and the unit predicates.

## Not changed

Pure equivalence, the import's regenerated-teardrop accounting, the proof's configuration and geometry
comparison, `regions` and `without_regions`.
