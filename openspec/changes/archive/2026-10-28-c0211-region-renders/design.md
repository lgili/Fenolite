## Context

`fenolite render` runs `kicad-cli` on a copy of the project and writes whole-side plots. c0175's requirement
"Region renders" asks for a close view of one rectangle, with net names, open connections and a coordinate
grid, drawn by Fenolite so it needs no tool. The analyses already hold what such a view needs:
- `analysis.pour` has the copper of every zone in its state;
- `analysis.connectivity` has the open connections with their two ends;
- `analysis.crossings` has the ways of a cut with their ends on the board;
- the backend's board frame has the pads with their holes.

## Decisions

1. **Fenolite's own SVG, not a cropped plot.** The region is drawn from the model by
   `analysis.region.draw_region`, as text built with the standard library. No tool runs, the same board gives
   the same bytes, and a test reads the elements and their coordinates instead of pixels. A cropped
   `kicad-cli` plot would need the tool, and it cannot carry the open connections or data attributes. The
   viewer's scene (`fenolite.view`) is built for the browser, and `analysis` may not import `view`, so the
   drawing has its own small palette.
2. **The module sits in `analysis`.** The drawing needs `analysis.pour`, `connectivity` and `crossings`.
   `exports` and `render` may not import `analysis` (`tests/unit/test_import_graph.py`), and `analysis` may
   import `model`, `geometry` and `backends.base`, which is all it uses. The command lives in
   `cli/_region.py` and `cmd_render.py` hands `--region` to it.
3. **Board millimetres, exact.** Coordinates and lengths are written in millimetres with every digit of
   their nanometres (`1.5`, `11.839999`), so a value in the SVG is the board's value. The `viewBox` is the
   region plus a margin for the grid labels, the SVG `y` axis points down as the board's does, and `width`
   is `--width` pixels (default 1600) with the height in proportion.
4. **What is drawn.** Every copper shape of `analysis.pour` whose box meets the region is drawn, bottom
   layer first, and the `clipPath` of the region clips it:
   - a disc is a `circle`, a filled ring a `path` with `Z`, and a polyline a stroked `path`;
   - the vias are drawn once, then the holes and slots in black, then the edge and cut-outs;
   - a pad label is drawn only for a pad with a net whose position lies in the region;
   - an open connection or a cut is drawn when its segment's box meets the region.

   The grid step is the smallest of 0.1, 0.2, 0.5, 1, 2, 5 … 500 mm that draws at most ten intervals on the
   longer side. `--grid` sets it, and a step that would draw more than 200 lines on one axis is refused.
5. **Zones in their state.** Each zone layer is taken in its state of `analysis.pour`, as the practice
   checks take it (c0204):
   - a saved fill is drawn as its polygons;
   - a simulated pour as one rectangle per run of cells along a row, cut to the region;
   - an outline-state zone as its outline.

   Every zone outline is also drawn dashed. `result.region.copper` lists the states used, `zones` lists
   each zone layer, and `render.copper-simulated` (info) names a zone that is not a saved fill.
6. **Open connections on that copper.** `connectivity()` takes `pour=`. Its copper is then
   `pour.copper`, and the items that one island of a simulated pour covers are joined, the rule of
   `H-G-PRACTICE-GROUPS`. Without simulated or outline zones the result is that of the saved copper, at
   `KICAD-VERIFIED`; otherwise it is `INFERRED` with `H-G-PRACTICE-POUR`. An unfilled board, which
   Fenolite's `build` gives, then shows the connections that remain once the pours are made, not every pad
   of the ground net.
7. **The cut overlay on the region.** `--cut` runs `analyze_crossings` with the board boundary and
   `--cut-width` / `--cut-clearance` (the classes' values by default). It draws the cut in orange and each
   way as a segment in its layer's colour, with `data-tracks` and `data-length`.
   `analysis.input-missing` keeps its code, and its hint names the render options. This settles c0199's
   left-out `--render`.
8. **Codes and evidence.** `render.region-empty` (warning) is given when nothing but the grid and the edge
   falls in the region: a rectangle in the wrong units is the likely cause. The file is still written, since
   a render is never a gate. The reply's evidence combines `H-G-REGION-RENDER` (`INFERRED`) with that of the
   connections and the cuts. `--manifest` lists `region.svg` with the kind `render` and the tool `fenolite`.

## Risks / Trade-offs

- A large region with a large simulated pour draws many cell rectangles; runs along a row keep the size
  to one rectangle per run, and the region bounds what is written.
- `--width` means pixels for `--png` and for the region, as before; the cut's track width is therefore
  `--cut-width`.

## Open Questions

None.
