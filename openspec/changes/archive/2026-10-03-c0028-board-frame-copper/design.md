## Context

- **The gap (dogfood buck board).** Items A5 and the `placed_extent` half of A2 of the dogfood report:
  - 29 power-track segments were drawn from a hand-made pad table, with `Transform.placement` applied by hand to every pad;
  - a placement change silently invalidated every coordinate;
  - a hand-written extent check got the 270° case wrong;
  - courtyard overlaps were found only by KiCad's DRC after writing.
- **Pads today.** `Pad.position` is footprint-local; absolute = `instance.position + R(instance.rotation)·pad.position`, with no further mirror (`docs/design-model.md`, "Pad frame"; `H-G-BOTTOM-PLACE`, `KICAD-VERIFIED (9.0.x, 10.0.x)`). `Pad.rotation` is relative, and `pcb.pad_angle_to_board(relative, footprint)` gives the stored absolute angle (`H-G-PAD-ANGLE-ABS`). It is the only helper.
- **Pad tokens are opaque.** The board and library readers keep `roundrect_rratio`, `chamfer_ratio`, `chamfer`, `rect_delta`, `options` and `primitives` opaque, and project an offset drill to its diameter and an oval drill to `None` (`docs/formats/kicad/libraries.md`, "Pads"). The exact copper of most pads therefore needs the KiCad slots.
- **Courtyards.** `embed.footprint_extent(defn)` (c0017) works in the definition's frame. `FootprintInstance` has no graphics. Its `fp_*` children are opaque slots in `FootprintInstance.ext["kicad"]`, for read boards and for built ones alike, because `place_footprint` returns `read_board` of the node it emitted. A `FootprintDef` holds them as modelled `Graphic`s (`graphics_on("F.CrtYd")`). c0018's `mod.board_footprints` already reads placed footprints as definitions in the stored frame.
- **Layering** (`package-layering`, unchanged):
  - `lens` may import `model` and `backends`, never `geometry`;
  - `checks` and `placement` may import `model`, `geometry` and `backends.base`, never `backends.kicad`;
  - `backends.kicad` may import `geometry`;
  - `backend-protocol` "Backend protocol" requires that `backends.base` import only `core` and `model` (test `base_imports`).
- **Scripts and the lens.** A `design.py` runs once and binds `design` (c0011). c0019 decides each part's placement after the script ran: a locked `place()`, then the existing board, then `place()`, then staging. A script therefore cannot know the board-frame position of a pad that the user moved in KiCad.
- **Copper in c0019.** "Copper items follow their nets" keeps every existing track, arc, via and zone whose net name the built design still has, with its uuid and slots. The built design has no copper today.
- **Writer uuids.** `pcb.kicad_uuid(entity)` is `native_ids["kicad"]`, else `uuid5(FENOLITE_NS, "kicad-out:<id>")`. c0017's placed copies set the native ids first, so a design read back has the same ids.
- **Siblings.**
  - c0029 (copper check, after this change) expects `BoardFrame.board_pads(design)` in `backend-protocol`, satisfied by `KicadBackend`. It wants pad records whose per-layer copper entries hold core points and a width. It defines `geometry/thick.py` (`Thick(core, width, filled)`) and builds its own copper items.
  - c0027 MODIFIES c0011's "Built project files", "Build command", "Build issue codes", "Build evidence", "Placement of built parts" and "DSL to model".
  - c0030 will place references outside courtyards with `placed_extent`.
  - c0022 (roadmap) will check courtyard overlap, parts outside the outline and edge clearance with it.

## Goals / Non-Goals

**Goals**
- Board-frame records for every pad: position, rotation, layers, net, hole, and exact integer copper entries per copper layer, with all pads sharing a number.
- The courtyard of a placed, rotated or flipped footprint in the board frame, front and back, with a defined fallback.
- Manual copper declared by pad references: tracks with waypoints and layer-changing vias, single vias, stitching along a polyline or in a region. Nets are inferred and checked, and ids come from caller keys.
- Script copper that follows footprints moved in KiCad and stays byte-identical across rebuilds, and copper that disappears with its intent.
- Records that c0029, c0022 and c0030 can consume without a layering change.

**Non-Goals**
- Placement legality (c0022), the copper check and its guard (c0029), field placement (c0030), routing (c0016, c0023), zone fill (c0015), zone settings (c0031).
- Arcs, blind, buried and micro vias, and zones created by the copper API (v0.2a).
- Avoiding zones and the board edge while stitching; a CLI pad query (v0.2a).
- A geometry type for thick shapes (c0029 owns `geometry/thick.py`), a `package-layering` change, a model or schema change.

## Decisions

1. **Copper is declared as intents and resolved by the build.**
   - The DSL records frozen dataclasses: tracks, vias and stitches that refer to pads by part and number and to points in the board frame of `place()`.
   - `lens.build.build_design` resolves them after placing the parts at their effective placements (c0019). Copper therefore follows a footprint that the user moved in KiCad.
   - A script on a model design (a board read from a file) passes the same dataclasses to `resolve_copper`.
   - Rejected: a public helper that the script calls with coordinates. The script runs before the effective placements exist, so the dogfood failure would come back.
   - Rejected: a CLI step after `build_design`. The build already returns hashed files and `.fenolite/` texts.
   - Rejected: a model layer for intents. That is a schema change, and the board already holds the result.

2. **Homes.**

   | piece | home | why |
   |---|---|---|
   | records `PadCopper`, `BoardPad`, `PlacedExtent`; protocol `BoardFrame` | `backends/base.py` | `checks` and `placement` may import only `backends.base`; plain `core` and `model` types keep "Backend protocol" true |
   | pad entries, holes, extents, polygons | `backends/kicad/frame.py` | needs the opaque KiCad slots and `geometry` |
   | resolution, uuids, merge | `backends/kicad/copper.py` | needs the frame, `geometry` and KiCad uuids |
   | intent dataclasses and the script API | `dsl/intents.py`, `dsl/design.py`, `dsl/part.py` | `dsl` imports only `model` |
   | build step | `lens/build.py` | `lens` may import `backends.kicad`; it never imports `geometry` itself |
   | merge with an existing board | `lens/preserve.py` | calls `copper.merge_copper`, which compares integers and texts |

   - `KicadBackend` satisfies `BoardFrame` (`_FRAME: BoardFrame = KicadBackend()`), as c0029's `DesignRulesSource` is satisfied. `board_pads` is not an operation, so `CapabilityReport` is unchanged.
   - `copper` reads intents through structural protocols (`PadEndLike`, …), as c0011's `lens.build.PlacementRequest` reads `dsl.Placement`; it never imports `dsl`.
   - Rejected: records holding `geometry` types (`Polygon`). `backends.base` must import only `core` and `model`.
   - Rejected: records only in `backends.kicad`. `checks` (c0029) and `placement` (c0022) could not import them.
   - Rejected: a new package. It needs a MODIFIED `package-layering`, which only c0029 may propose.
   - Rejected: `placement` or `checks` as home. `lens` cannot import them, so the build could not resolve intents.
   - Rejected: model fields for corner ratios and primitives. That is a schema change, and custom pads would stay opaque.
   - Rejected: a geometry `RoundedShape` type here. c0029 adds `Thick` for the same concept, and two kernels would diverge.

3. **Copper entries: integer core points and a width.**
   - Each `PadCopper` is the set of points within `width / 2` of its core: one point (a disc), an open polyline (`filled` false), or a simple ring (`filled` true). These are exactly the conventions of c0029's `Thick`, so c0029 builds one `Thick` per entry with no conversion.
   - Exactness. Cores and widths are integers. A circle is a point with width `w`; a roundrect is its inner box with width `2r`; an oval is a segment. None of them is approximated, while a polygon of a circle could never be exact. Using the width (a diameter) instead of a radius keeps odd sizes and odd track widths integral.
   - Rounding. Each coordinate is computed exactly (corners at half sizes are rationals) and rounded half to even once, after the placement transform: within 0.5 nm per axis, exact at multiples of 90° with even sizes. For a roundrect, `r` is rounded first and the inner box is `w − 2r` by `h − 2r`, so the entry's outer box is exactly the pad's box. An inner box with a side of 0 becomes its segment or point, unfilled, a core that c0029's `Thick` accepts.
   - `PadCopper` refuses the cores that `Thick` refuses and that `backends.base` can see without `geometry`: an empty core, a negative width, one point of width 0, and a filled core of fewer than three points. A filled ring that only `Polygon` would refuse is left to c0029, which counts its pad as unsupported.
   - Token rules come from S-0001 and are `INFERRED` until `H-G-FRAME-SHAPE`:
     - a circle's diameter is the X size;
     - `roundrect_rratio` scales the shorter side, clamped to [0, 0.5], 0.25 when absent;
     - the custom anchor is `rect` unless `options` say `circle`.
   - Supersets, each flagged with `exact=False` and one `kicad.frame.shape-approximated` info, so c0029 can treat it conservatively:
     - a trapezoid grows its box by `|dx| + |dy|` on every side, which contains it whether its delta lengthens an edge by `d` in total or at each end (S-0001 does not settle which);
     - a chamfered pad keeps its unchamfered shape;
     - arcs and unfilled circles of custom primitives become polylines (`DEFAULT_TOL`) whose width grows by `2·DEFAULT_TOL + 2`, the bound within which the polyline follows the curve; a `gr_poly` with arcs in `pts` becomes its polygonised ring, filled when the primitive is;
     - a `gr_curve` becomes the convex hull of its control points, which contains a Bézier curve;
     - a padstack layer with an unknown corner ratio becomes its box.
   - A `gr_poly` without `fill` counts as filled, as custom pad polygons are filled (INFERRED).
   - Padstacks: `F.Cu` takes the pad's own shape, `B.Cu` and inner layers their named entry, else `Inner`, else the pad's shape (`libraries.md`, "Padstacks").
   - Rejected: polygons only. They are inexact for every rounded pad.
   - Rejected: a radius. Halving breaks integrality.

4. **Holes.**
   - `hole` and `drill` give the drill in the board frame: a point for a round drill, a slot segment for `(drill oval W H)`, with the opaque `(offset X Y)` applied.
   - The stitching helper needs them: an `np_thru_hole` pad has no copper but must not receive a via.
   - Rejected: the model's `Pad.drill` alone. It is `None` for oval drills and ignores offsets, so a slot or an offset hole would be missed.

5. **Positions reuse verified rows.**
   - `position` and `rotation` are the formulas of `H-G-BOTTOM-PLACE` and `H-G-PAD-ANGLE-ABS`, already `KICAD-VERIFIED (9.0.x, 10.0.x)` through IPC-D-356 and DRC library parity.
   - `test_pad_positions` re-checks `board_pads` against `pcb export ipcd356`, adding 180° and 270° on both sides. The 270° case is the one the dogfood script got wrong. Its data joins those rows; no new hypothesis is registered.
   - Rejected: a new row for board-frame positions. It would restate verified formulas, and two rows for one fact can drift apart.

6. **Placed extents read the footprint's own node.**
   - The pieces on `F.CrtYd` and `B.CrtYd` are read with c0018's footprint reader in the stored frame, then moved by `Transform.placement(position, rotation)` with no mirror, as pads are. `fp_poly` children whose `pts` hold arcs are read as mixed contours (`H-G-PTS-ARC`).
   - This works for read and built boards, needs no library, and follows courtyard edits made in KiCad.
   - An instance without KiCad slots, built in memory by a test or a script, uses a given definition, mirrored for the bottom side, with `source="definition"`.
   - Both faces are returned, because KiCad checks front courtyards against front ones and back against back, and a footprint may have both. `own` gives the face of the footprint's side.
   - Rings: a rect gives its corners and a polygon its points. A circle gives `Circle.polygonize(tol, outer=True)` around its moved centre, which contains the disc. Lines and arcs are chained exactly with `assemble_rings`.
   - A face that does not close gives the convex hull of its pieces and a warning. KiCad's DRC has its own malformed-courtyard check (S-0038, `INFERRED`); Fenolite does not claim to match it.
   - Without a courtyard, the extent is the convex hull of the boxes of the pad entries (`source="pads"`), in the spirit of c0017's pad-box fallback but in the board frame; without pads it is empty (`source="none"`).
   - Rejected: the definition only. It needs a library and misses KiCad edits.
   - Rejected: an axis-aligned box. It is wrong at 30°, and the dogfood bug lived in box arithmetic.
   - Rejected: the own face only. c0022 needs both faces.

7. **Polygons on request.**
   - `copper_polygon` gives `Polygon(core)` for a filled ring of width 0. For a disc, a segment or a convex ring with a width, it gives an outer polygon (vertices within `width / 2 + tol + 2` nm, the disc rule of `Circle.polygonize(outer=True)`).
   - It answers the brief's "integer polygon" for every entry that has one, for consumers that need polygons (rendering, booleans) without approximating the record itself.
   - Rejected: an inner approximation. It would let a short pass.

8. **Copper uuids: RFC 9562 version 8 with a Fenolite marker.**
   - `copper_uuid(key, locator)` puts the 48-bit marker `0x66656E6F6C69` in `custom_a`, version 8, variant `0b10`, and the first 74 bits of SHA-256 of `kicad-copper:<key>:<locator>` in the other bits (S-0110). The text starts with `66656e6f-6c69-8`.
   - Python 3.11 refuses `version=8` (S-0111), so the bits are set on the integer.
   - The Fenolite id is `derived_id("trk"|"via", "kicad", uuid)`, so a design read back has the same ids. This is the fifth case of the MODIFIED "Identifier derivation" (Decision 16).
   - The marker is what lets a rebuild tell script copper from copper drawn in KiCad, which gets version-4 uuids. Stale script copper, whose key the script no longer has, can therefore be removed without any registry.
   - Locators number items inside one intent (`seg[i]`, `via[i]`, `via`, `via[k]`, `via[i,j]`), so other intents never shift.
   - Region stitch vias use global grid indices, so a growing region keeps the ids of the vias it already had.
   - Rejected: `uuid5` as for placed copies. After a key is removed, its copper cannot be told from user copper.
   - Rejected: a KiCad `group` per key. It needs writer work for created boards and more evidence, and breaks when a user ungroups.
   - Rejected: a registry in `.fenolite/`. c0019 requires a deleted cache to rebuild the same bytes.
   - Rejected: a key in `.kicad_pro`. KiCad's handling of unknown keys is unverified.
   - Rejected: content-based locators. Every move of a footprint would change ids.

9. **Tracks from paths.**
   - A path is pad ends, points and via steps. Segments join consecutive points on the current layer.
   - A via step places a through via (first to last copper layer) and switches layer. A zero-length segment is skipped, keeping its locator reserved.
   - Pad ends may stand anywhere in a path, so a power track can chain several pads. Pad ends are chosen in path order: the first takes the candidate nearest to the second element (or the nearest pair with a second pad end), and each later one the candidate nearest to the element before it, among the pads with copper on the layers of its segments (exact squared distances, ties to the earlier pad). `index=` overrides.
   - Widths and via sizes fall back to the net class (`NetClass.track_width`, `via_diameter`, `via_drill`), else an error. A pad with no copper on the segment's layer is an error.
   - Rejected: an error on shared numbers. Exposed pads are the common case.
   - Rejected: pad ends only at the two ends of a path. Daisy-chained supply pads would need one intent per hop.
   - Rejected: the first pad in file order. It is arbitrary.
   - Rejected: blind and buried vias in v0.1. They need span rules and evidence.

10. **Nets are inferred and checked.**
    - A track's net is the net of its pad ends. Ends on two nets, an end without a net, or a named net that differs give `kicad.copper.net-conflict`. Joining an unconnected pad would create a connection that the circuit lacks.
    - Vias, stitches and pad-less tracks must name their net.
    - An intent ending at a part that the build staged creates nothing (`kicad.copper.end-unplaced`, warning). Copper drawn to the staging row would be wrong, and the part's `place()` fixes it.
    - Shorts with other copper are c0029's check.
    - Rejected: taking the net from an explicit `net=` alone. A wrong pad or a typo would then join two nets without a word, the dogfood board's re-net failure in another form.
    - Rejected: drawing intents that end at a staged part. The copper would run off the board to the staging row and be regenerated on every build until the part is placed.

11. **Stitching.**
    - **Along a polyline**, each segment is cut into the fewest equal parts no longer than `pitch`, decided with integers (`n²·pitch² ≥ length²`).
    - **In a region**, candidates are `origin + (i·pitch, j·pitch)` inside the region at least `diameter / 2 + margin` from every edge. The global grid keeps positions and ids when the region changes. The DSL's origin is the board corner.
    - **Clearance.** A candidate is dropped when its disc comes closer than `clearance` to a pad entry or hole, or to a track, arc or via of another net or of no net, or touches a via of its own net. Vias already kept count.
    - The test is a private exact function in `copper`: a squared distance to a point, polyline or ring, compared with `(2·gap + w₁ + w₂)²/4`. It uses c0005's `dist2_point_segment` and `point_in_ring`, with a `SpatialIndex` over obstacle boxes.
    - Arcs count as polylines with a grown width. Zones, rule areas and the board edge do not count.
    - Rejected: a grid anchored at the region's corner. It shifts every via when the region grows.
    - Rejected: no avoidance. The helper would write shorts that only c0029's guard or KiCad would catch.
    - Rejected: using c0029's `thick_closer_than`. c0029 comes later; Open Question 1 allows the swap.

12. **The script owns its copper.**
    - `merge_copper(existing, built)` drops every existing item whose uuid is a copper uuid:
      - when `built` has an item with that uuid, it is regenerated (`kicad.copper.regenerated` info when a field differs: a KiCad edit was replaced, or the pads it joins moved);
      - otherwise it is stale (`kicad.copper.stale` warning).
    - An existing item without a copper uuid that equals a script item is a duplicate (`kicad.copper.duplicate` info). This happens when a KiCad operation gave script copper new uuids.
    - Everything else stays.
    - `resolve_copper` applies the same rule to its input, so resolving twice is idempotent.
    - Rejected: the board wins for script copper. Coordinates go stale again, the dogfood failure. Footprints, fields and zones keep the other model (Decision 20).
    - Rejected: keeping stale copper. It can short a net.
    - Rejected: matching by content alone. Every regenerated track would look new.

13. **Build integration is additive.**
    - `build_design(…, copper_intents=())` resolves intents after placing, staging, setting layers and assigning pad nets, and before the build checks and `Design.validate()`, with `unplaced` the staged paths.
    - `BuildOutput.design` therefore holds the script copper, and c0019's "Without an existing board, the board text MUST be … write_triad of the built model" stays literally true.
    - A copper error returns no files (exit 5).
    - The envelope combines `copper.EVIDENCE` and `frame.EVIDENCE` when intents exist, and `result.copper` gives counts. `cmd_build` passes `dsl.copper(design)`.
    - This extends, without modifying, these lists of c0011 and c0019:
      - the step list and signature of "Built project files" (keyword-only argument with a default);
      - the flow of "Build command";
      - the combined evidence of "Build evidence";
      - the pass-through codes of "Build issue codes" (`kicad.copper.*`, `kicad.frame.*`);
      - the modules and re-exports of "DSL package".

      The new requirements say "in addition". The coordinator may fold them into c0027's MODIFIED texts, which are archived after c0019's.
    - Rejected: MODIFIED c0011 requirements. c0019 and c0027 already modify them, and a third copy multiplies rebases.
    - Rejected: resolving only on the merged layout. `BuildOutput.design` would differ by case.

14. **Lens merge.**
    - ADDED `layout-lens` "Script copper in a merge" makes `merge_layout` pass the existing board and the built design to `merge_copper`, keep only the existing items it keeps, apply c0019's net rule to those, and append the built script copper.
    - This narrows c0019's "Copper items follow their nets" ("keep every track …") to the items that `merge_copper` keeps. Archive order: c0019 first.
    - c0019's normal form (`merge_layout` of the built model with its own written board) regenerates every script item identically, so a second rebuild writes the same bytes.
    - Rejected: a MODIFIED "Copper items follow their nets". It would copy c0019's text while c0019 is still under review; the narrowing is stated once, in the ADDED requirement.
    - Rejected: resolving copper again after the merge. The merged layout would hold two copies of every script item until a second pass removed them.

15. **Issue codes are backend codes.**
    - `kicad.frame.*` and `kicad.copper.*` (closed tables `FRAME_ISSUE_CODES`, `COPPER_ISSUE_CODES`) pass through c0011's and c0019's closed sets as `kicad.*` codes: c0019's MODIFIED `design-dsl` "Build issue codes" and its `layout-lens` "Layout issue codes" let every `kicad.*` code through, and "Board-frame issue codes" and "Copper issue codes" name both.
    - Rejected: rows in `BUILD_ISSUE_CODES` or `PRESERVE_ISSUE_CODES`. Those are MODIFIED requirements of c0011 and c0019, already modified by c0019 and c0027.

16. **"Identifier derivation" gets a fifth case (MODIFIED).**
    - Script copper has no native id in a source file, like c0017's placed copies and unlike c0012's sheets. The created-object rule (`uuid4` from the seed) would otherwise apply, and c0011's fourth case ("each object they create … from `KEYS`") would contradict it.
    - The full text is c0011's MODIFIED version, plus one bullet, the fifth-case paragraph and one scenario. Archive order: c0011 first; a change of c0011's text needs a rebase.
    - c0031 (zone settings) also MODIFIES this requirement, adding a `zone` row to c0011's table, and plans to re-copy this change's text once it is archived; c0031 archives after this change.
    - Rejected: an ADDED requirement that overrides c0011's fourth case. Two MUSTs would conflict.

17. **Oracle: probes first, canaries with negative controls.**
    - The uuid probes run before any resolution code (task group 2), on boards whose items get copper uuids in the test. A `reject` or `different` outcome stops the change (Risks).
    - **Pad entries.** The bench's rules file fixes every clearance at 0.2 mm, so the verdict does not rest on KiCad's defaults. Probe vias of another net are placed by exact bisection at 0.2 mm ±20 µm along an edge normal and a corner diagonal of each pad. The margin is four times KiCad's default arc approximation error (0.005 mm, S-0010), so KiCad's verdict is unambiguous, while a wrong corner radius or size shows.
    - **Extents.** Pairs of footprints overlapping by 20 µm must give one `courtyards_overlap` each, and pairs 20 µm apart none (key name from S-0058; c0020's `H-K-DRC-TYPES` covers the type field).
    - **Routing.** The routed blink must show no `unconnected_items`, a cut control exactly one, and a footprint moved by token edit and re-saved on 10.0.6 still none after a rebuild.
    - Rejected: comparing Gerber or SVG exports. That needs a parser for a new format.
    - Rejected: GUI-only checks. They cannot be automated.

18. **A runnable example.**
    - `examples/blink_routed/design.py` (CC0, authored for Fenolite) is the blink with four copper intents, in the board frame of `place()`:
      - `led_drv`: `U1` pad `1`, (8, 12.2), (8, 7), (31.2, 7), `R1` pad `1`, on `F.Cu`, width 0.3 mm: 4 tracks;
      - `led_a`: `R1` pad `2`, (36, 9), a via step at (36, 14) to `B.Cu` (0.6 mm, drill 0.3 mm), `D1` pad `2`, width 0.3 mm: 3 tracks and 1 via;
      - `gnd`: `U1` pad `10`, (12, 26), a via step at (14, 26) to `B.Cu` (0.6 mm, drill 0.3 mm), (38, 26), `D1` pad `1`, with the width of class `PWR`: 4 tracks and 1 via;
      - `gnd_fence`: a stitch on `GND` along (16, 26)–(36, 26) with pitch 5 mm, diameter 0.6 mm and drill 0.3 mm, so its 5 vias sit on the `B.Cu` part of `gnd` and are connected through it.
    - Every via size is explicit, because the blink's class `PWR` sets a clearance and a track width but no via sizes: without them resolution gives `kicad.copper.size-missing` ("Tracks from intents", "Stitching vias"). The stitch's clearance comes from `PWR` (0.2 mm).
    - Totals: 11 tracks and 7 vias. Every waypoint keeps at least 0.275 mm from copper of another net at the blink placements (checked by hand against the Mini footprints); the clearance canary of the oracle confirms it.
    - It is the oracle's fixture and the documentation's example.
    - Rejected: free-standing stitch vias in the fixture. KiCad's connectivity may report them as dangling or unconnected, which would blur the route probe.
    - Rejected: a test-only fixture. The docs need a runnable script.

19. **Coordination.**
    - c0029 consumes `BoardFrame.board_pads` and builds `Thick(entry.core, entry.width, entry.filled)` per entry; its copper items and gap functions stay its own.
    - c0022 consumes `BoardFrame.placed_extents`, from `placement` or through the CLI.
    - c0030 uses `placed_extent` from `backends.kicad`.
    - Rejected: taking c0029's `Thick` into this change. c0029 already ADDs it to `geometry-kernel`, and the same requirement added by two changes cannot both archive.

20. **Two precedence models for script-owned board items, on purpose.**
    - **Script copper is derived output.** Its source is the intents; the build regenerates it on every build from the effective placements (Decision 12). A KiCad edit of script copper is replaced (`kicad.copper.regenerated`), and copper whose intent is gone is removed (`kicad.copper.stale`). Its marker is the version-8 copper uuid (Decision 8). To keep a hand edit, the user redraws the copper in KiCad, where it is board copper (Open Question 3).
    - **Footprints, fields and zones are edited in place.** c0019 (footprints), c0030 (fields) and c0031 (zones) keep GUI edits; the script wins only where it locks the item (a locked `place()`, a locked field request, a locked `zone()`). c0019 also gives the values of user properties to the script (its Decision 22). A removed script footprint or zone is an orphan (`layout.orphan`, `kicad.zone.orphan`). Footprints are marked by `fenolite.path`, zones by the uuid derived from their name.
    - Why two: a track's geometry is a function of the pads it joins, which the board owns. A kept GUI edit of a track goes stale when a pad moves, the dogfood failure. A footprint placement, a field or a zone setting is the thing the user edits, and nothing derives it.
    - The codes follow the models: derived copper without an intent is `stale`; an edited item without its declaration is an `orphan`. No marker is shared between the models (c0031 Open Question "Marker of script zones").
    - `docs/lens.md` holds one precedence table per item kind: rows for footprints (c0019) and script copper here; c0030 and c0031 add the rows of fields and zones.
    - Rejected: one model where the board wins unless locked, for copper too. Every track would need a lock to follow its pads, and an unlocked track would point at old pad positions after a move.
    - Rejected: one model where the script always wins, for footprints, fields and zones too. Every GUI edit of a placement, a label or a zone setting would be lost on the next build, which c0019, c0030 and c0031 reject.
    - Rejected: one shared uuid marker for every script item. Copper needs a marker that survives a removed key (Decision 8); zones are matched by the uuid of their own name and need no marker bits; a shared scheme would change c0031's matching for no gain.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/base.py` (extended) | `@dataclass(frozen=True, slots=True) class PadCopper(layer: str, core: tuple[Point, ...], width: Nm, filled: bool = False, exact: bool = True)`; `class BoardPad(footprint_id: str, ref: str, path: str, pad_id: str, number: str, kind: PadKind, position: Point, rotation: Udeg, side: Side, layers: tuple[str, ...], net_id: str \| None, net: str \| None, copper: tuple[PadCopper, ...] = (), hole: tuple[Point, ...] = (), drill: Nm \| None = None)`; `class PlacedExtent(footprint_id: str, side: Side, front: tuple[tuple[Point, ...], ...] = (), back: tuple[tuple[Point, ...], ...] = (), source: Literal["courtyard", "definition", "pads", "none"] = "none", exact: bool = True)` with property `own`; `@runtime_checkable class BoardFrame(Protocol)`: `board_pads(design: Design, *, issues: list[Issue] \| None = None) -> tuple[BoardPad, ...]`, `placed_extents(design: Design, *, issues: list[Issue] \| None = None) -> tuple[PlacedExtent, ...]` |
| `src/fenolite/backends/kicad/frame.py` (new) | `board_pads(design, *, issues=None) -> tuple[BoardPad, ...]`; `find_pads(design: Design, component: str, number: str \| int) -> tuple[BoardPad, ...]`; `placed_extent(footprint: FootprintInstance, *, definition: FootprintDef \| None = None, tol: int = DEFAULT_TOL, issues: list[Issue] \| None = None) -> PlacedExtent`; `placed_extents(design, *, definitions: Mapping[str, FootprintDef] \| None = None, tol: int = DEFAULT_TOL, issues=None) -> tuple[PlacedExtent, ...]`; `copper_polygon(entry: PadCopper, *, tol: int = DEFAULT_TOL) -> Polygon`; `COURTYARD_LAYERS = ("F.CrtYd", "B.CrtYd")`; `FRAME_ISSUE_CODES: Mapping[str, Severity]`; `EVIDENCE: Evidence` |
| `src/fenolite/backends/kicad/copper.py` (new) | `COPPER_MARKER = 0x66656E6F6C69`; `copper_uuid(key: str, locator: str) -> str`; `is_copper_uuid(text: str) -> bool`; protocols with read-only properties `PadEndLike(component: str, number: str, index: int \| None)`, `ViaStepLike(at: Point, layer: str, diameter: Nm \| None, drill: Nm \| None)`, `TrackIntentLike(key, path: Sequence[PadEndLike \| Point \| ViaStepLike], layer, width, net)`, `ViaIntentLike(key, at, net, diameter, drill)`, `StitchIntentLike(key, net, pitch, along, region, origin, diameter, drill, clearance, margin)`, `CopperIntentLike`; `resolve_copper(design: Design, intents: Sequence[CopperIntentLike], *, unplaced: Collection[str] = (), issues: list[Issue] \| None = None) -> Design`; `merge_copper(existing: Design, built: Design) -> CopperMerge`; `@dataclass(frozen=True, slots=True) class CopperMerge(kept: frozenset[str], issues: tuple[Issue, ...] = (), regenerated: int = 0, stale: int = 0, duplicates: int = 0)`; `COPPER_ISSUE_CODES`; `EVIDENCE` |
| `src/fenolite/backends/kicad/backend.py` (extended) | `KicadBackend.board_pads(design, *, issues=None)`, `KicadBackend.placed_extents(design, *, issues=None)`; `_FRAME: BoardFrame = KicadBackend()` |
| `src/fenolite/backends/kicad/__init__.py` (extended) | re-exports `board_pads`, `find_pads`, `placed_extent`, `placed_extents`, `resolve_copper` |
| `src/fenolite/dsl/intents.py` (new) | `PadRef`; `via_step(x, y, *, to: str, diameter=None, drill=None) -> ViaStep`; `copper(design: Design) -> tuple[CopperIntent, ...]`; frozen dataclasses `PadEnd(component: str, number: str, index: int \| None = None)`, `ViaStep(at: Point, layer: str, diameter: Nm \| None = None, drill: Nm \| None = None)`, `TrackIntent(key: str, path: tuple[PadEnd \| Point \| ViaStep, ...], layer: str = "F.Cu", width: Nm \| None = None, net: str \| None = None)`, `ViaIntent(key: str, at: Point, net: str, diameter: Nm \| None = None, drill: Nm \| None = None)`, `StitchIntent(key: str, net: str, pitch: Nm, along: tuple[Point, ...] = (), region: tuple[Point, ...] = (), origin: Point = Point(0, 0), diameter: Nm \| None = None, drill: Nm \| None = None, clearance: Nm \| None = None, margin: Nm = 0)`; `CopperIntent = TrackIntent \| ViaIntent \| StitchIntent` |
| `src/fenolite/dsl/design.py`, `part.py`, `__init__.py` (extended) | `Design.track(key, *path, layer="F.Cu", width=None, net=None)`, `Design.via(key, x, y, *, net, diameter=None, drill=None)`, `Design.stitch(key, *, net, pitch, along=(), region=(), origin=None, diameter=None, drill=None, clearance=None, margin=None)`; `Part.pad(number, *, index=None) -> PadRef`; re-exports |
| `src/fenolite/lens/build.py` (c0011, c0019; extended) | `build_design(…, copper_intents: Sequence[CopperIntentLike] = ())`; `BuildOutput.summary["copper"]` |
| `src/fenolite/lens/preserve.py` (c0019; extended) | `merge_layout` calls `copper.merge_copper(board, built)` |
| `src/fenolite/cli/cmd_build.py` (extended) | passes `dsl.copper(design)`; `result.copper = {intents, tracks, vias, regenerated, stale, duplicates}` |
| `examples/blink_routed/` (new; CC0) | `design.py`, `fp-lib-table`, `sym-lib-table` (copies of the blink's tables); a row in `examples/README.md` |
| `tests/data/libs/Frame.pretty/` (new; CC0, format `20241229`) | `Frame_Shapes` (one `circle`, `rect`, `oval`, `roundrect` and filled-polygon `custom` pad, and the courtyard rectangle (−3, −2)–(3, 4) mm), `Frame_Round` (circle courtyard of radius 2 mm), `Frame_NoCourtyard`, `Frame_OpenCourtyard`, `Frame_Trapezoid`, and `Frame_Loop` (a courtyard closed by four lines, added for the courtyard canary); rows in `tests/data/MANIFEST.toml` |
| unit tests | `tests/unit/backends/test_base_types.py` (extended); `tests/unit/backends/kicad/test_frame_pads.py`, `test_frame_custom.py`, `test_frame_extent.py`, `test_frame_issues.py`, `test_copper_uuid.py`, `test_copper_tracks.py`, `test_copper_stitch.py`, `test_copper_merge.py`, `test_copper_issues.py`; `tests/unit/dsl/test_copper_dsl.py`; `tests/unit/lens/test_build_copper.py`, `test_preserve_script_copper.py` (c0019's `test_preserve_copper.py` keeps its tests) |
| oracle tests | `tests/kicad/frame/_framebench.py`, `_framecases.py`, `test_frame_oracle.py`, `test_copper_oracle.py`; probes registered in `tests/kicad/_probes.py` |
| documentation | `docs/formats/kicad/frame.md` (new), `docs/copper.md` (new), sections in `docs/dsl.md`, `docs/lens.md`, `docs/cli-contract.md`, `docs/design-model.md`; `docs/hypotheses.md`, `docs/evidence/sources.md`, `src/fenolite/backends/kicad/PROVENANCE.md`, `LEGAL-ANNEX.md`, `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json`, `CHANGELOG.md` |

## Sources registered by this change

| id | URL | licence | used for |
|---|---|---|---|
| S-0110 | https://www.rfc-editor.org/rfc/rfc9562 | IETF Trust Legal Provisions (BCP 78), stated on the page, as S-0057 | UUID version 8 for vendor-specific use: the `custom_a` (48 bits), version, `custom_b` (12 bits), variant and `custom_c` (62 bits) fields |
| S-0111 | https://docs.python.org/3/library/uuid.html | PSF License Version 2 (stated on the page), as S-0011 | `uuid.UUID(int=…)`; the `version` argument and `uuid8()` of 3.14 |

Existing ids cited:
- S-0001: pad tokens `roundrect_rratio`, `chamfer_ratio`, `chamfer`, `rect_delta`, `options` (anchor), `primitives`, and the drill forms. Task 1.2 widens its "used for" cell with what the page states.
- S-0010: rotation direction; default arc approximation error.
- S-0018: `pts` arcs.
- S-0019 and S-0020: IPC-D-356 frame and oracle runs.
- S-0022 and S-0037: `pcb export ipcd356`, `pcb drc`, `pcb upgrade`.
- S-0038: courtyard and clearance checks. Task 1.2 widens its cell.
- S-0040: the footprint body is S-0001's syntax.
- S-0058: the `courtyards_overlap` rule-severity key in demo projects.

S-0112 to S-0114 stay free.

## Hypotheses registered by this change

| id | backend | statement | test | criterion |
|---|---|---|---|---|
| H-G-FRAME-UUID | kicad | Tracks and vias whose uuid is a Fenolite copper uuid (RFC 9562 version 8, marker `66656e6f-6c69`) load on 9.0.9 and 10.0.6 and keep their uuids through a 10.0.6 re-save (S-0110, S-0020, S-0022) | `tests/kicad/frame/test_copper_oracle.py -k uuid`; probes `pcb-frame-uuid-9`, `-10`, `-keep` | target 9 loads on both majors, target 10 on 10.0.6; every uuid equal after `pcb upgrade --force` |
| H-G-FRAME-SHAPE | kicad | Copper entries of circle, rect, oval, roundrect and filled-polygon custom pads agree with KiCad's clearance check within 20 µm (S-0001, S-0038) | `test_frame_oracle.py::test_shape_canary`; probes `pcb-frame-shape-near`, `-far` | one `clearance` violation per near probe and none for far probes, at 0°, 90°, 180°, 270° and 30° on both sides, on both majors |
| H-G-FRAME-CRTYD | kicad | `placed_extent` agrees with KiCad's `courtyards_overlap` within 20 µm for rectangle, line-loop and circle courtyards (S-0038, S-0058) | `test_frame_oracle.py::test_courtyard_canary`; probes `pcb-frame-crtyd-overlap`, `-gap` | one violation per overlapping pair and none per gapped pair, both sides, both majors |
| H-G-FRAME-CRTYD-2 | kicad | Successor of `H-G-FRAME-CRTYD`, registered during implementation: as that row for rectangle and line-loop courtyards; for circle courtyards, extents 20 µm apart give no violation and extents overlapping by 40 µm give one (S-0038, S-0058) | `test_frame_oracle.py::test_courtyard_canary`; probes `pcb-frame-crtyd-overlap`, `-gap` | one violation per overlapping pair and none per gapped pair, both sides, at 0° and 30°, both majors |
| H-G-FRAME-ROUTE | kicad | Copper resolved from intents joins its pads for KiCad's DRC (S-0022, S-0037) | `test_copper_oracle.py -k route`; probes `pcb-frame-route`, `-route-cut`, `-route-moved` | no unconnected item and no `clearance` or `shorting_items` violation naming a script item; exactly one unconnected item with the cut; none after the moved rebuild |

All start `INFERRED` with result `pending`. Reused rows:
- `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE` and `H-G-PAD-ANGLE-ABS`: `test_pad_positions` is added to them as supporting data at 180° and 270°.
- `H-G-PTS-ARC`, `H-K-UUID-KEEP-2` and `H-K-LIB-DRC`.
- `H-K-DRC-TYPES` (c0020), for the `clearance`, `shorting_items` and `unconnected_items` types.

## Evidence level per behaviour (before merge)

| behaviour | level | proof |
|---|---|---|
| pad positions and rotations | `KICAD-VERIFIED (9.0.x, 10.0.x)` (reused rows) | `test_pad_positions` |
| entries of circle, rect, oval, roundrect, filled-polygon custom pads | `KICAD-VERIFIED (9.0.x, 10.0.x)` for the bench (`H-G-FRAME-SHAPE`); `INFERRED` for other footprints | `test_shape_canary` |
| superset entries, holes | `INFERRED` (containment argued in Decision 3; S-0001 drill forms) | unit tests |
| placed extents | `KICAD-VERIFIED (9.0.x, 10.0.x)` for the bench (`H-G-FRAME-CRTYD`); `INFERRED` elsewhere | `test_courtyard_canary` |
| copper uuids load and survive a re-save | `KICAD-VERIFIED` (load on 9.0.x and 10.0.x, re-save on 10.0.x) | probes |
| routed copper connects its pads; copper follows a moved footprint | `KICAD-VERIFIED (9.0.x, 10.0.x)` for the routed blink (re-save on 10.0.x only) | probes |
| resolution, nets, stitching, merge, DSL, ids, determinism | mechanical | unit tests |
| `frame.EVIDENCE`, `copper.EVIDENCE`, a build envelope with intents | `INFERRED` (lowest wins; the rows cover the bench and the routed blink) | — |

## Budget (21.5 working days; no plan line, the work is new from the dogfood report)

| group | days |
|---|---|
| 1. Registers, format page | 1.0 |
| 2. Copper uuids and probes first | 0.75 |
| 3. Records and protocol | 0.75 |
| 4. Board-frame pads, entries, holes | 2.75 |
| 5. Placed extents and polygons | 2.0 |
| 6. Copper resolution, stitching, merge | 4.5 |
| 7. DSL and the routed example | 1.5 |
| 8. Build and lens | 2.0 |
| 9. Oracle | 4.5 |
| 10. Documentation | 1.0 |
| 11. Closing | 0.75 |
| **total** | **21.5** |

c0019 was planned at 5 days and re-estimated at 7.75; c0008 took about three times its line. The line items above are already split to days.

Cut order, each cut keeping the rest consistent:
1. The shape canary (task 9.2, −1.0). Entries stay `INFERRED` until c0029's parity canaries judge pads through `BoardFrame`.
2. Exact custom primitives (part of task 4.3, −0.5). Custom pads become hull supersets with `exact=False`.
3. `copper_polygon` (part of task 5.2, −0.25).
4. Region stitching (part of task 6.3, −0.25). Stitching along a polyline remains.
5. Stitching clearance (task 6.4, −1.0). Every candidate is placed, and c0029's guard judges the result.

After all cuts: 18.5 days.

## Risks / Trade-offs

- **KiCad may refuse or rewrite version-8 uuids.** The probes of group 2 run before any resolution code. Fallback: `uuid5(FENOLITE_NS, "kicad-copper:<key>:<locator>")`, with stale copper detected only for the current keys, whose highest locators are scanned. Copper of a removed key would then stay, with a documented `--discard-layout` remedy and one new info code. This would be recorded as a refutation of `H-G-FRAME-UUID` with a successor row.
- **KiCad's DRC approximates curves** (0.005 mm default, S-0010). The ±20 µm margins keep verdicts clear. A failing near probe on a curve means the entry rule is wrong, not the margin.
- **Token semantics come from S-0001 only**: the circle's X size, the ratio's base, the anchor default, the drill-oval orientation. The canaries settle the first two for the bench; the others stay `INFERRED` and are flagged where a superset is used.
- **The script owns its copper.** A KiCad edit of script copper is replaced at the next build, with an info. Removing the intent removes the copper, so keeping a hand-edited version means redrawing it in KiCad (Open Question 3).
- **Dependencies on texts not yet archived.**
  - c0019 is proposed and may rename `merge_layout` or its rule; the ADDED `layout-lens` requirement follows it.
  - The MODIFIED "Identifier derivation" copies c0011's text and must be rebased if c0011 changes it.
  - c0027's MODIFIED build requirements are the base that the ADDED build requirement extends.
- **c0029 alignment.** The record fields follow c0029's current text (`core`, `width`, `filled`; `BoardFrame.board_pads` on `KicadBackend`). A rename there is a rename here (Open Question 1).
- **Stitching cost.** It is candidates times nearby obstacles through a `SpatialIndex`, which is small for v0.1 boards. Zones and the board edge are not avoided.
- **Budget.** 21.5 days is more than c0019's; the cut order removes 3 days without losing a brief item.

## Migration Plan

- Additive: no schema, model or layering change. A design without intents builds as before, and `merge_copper` drops nothing from boards written before this change, which hold no copper uuids.
- Implementation order: c0019, c0020 and c0021 first. Within the change, groups 1 and 2 (probes) come before any resolution code.
- Archive order: c0011, then c0019, then this change (MODIFIED "Identifier derivation" and ADDED `layout-lens`), then c0029 (consumes `BoardFrame`), c0030 (`placed_extent(fp).own`, `H-G-FRAME-CRTYD`) and c0031 (re-copies "Identifier derivation").
- Rollback: delete the intents from the script. The next build removes the script copper as stale.

## Open Questions

1. **c0029 alignment.** Does c0029 build `Thick(entry.core, entry.width, entry.filled)` from `PadCopper` as defined here, and may this change's private stitching test later call c0029's `thick_closer_than`? Default: yes to both; the swap is a refactor without behaviour change.
2. **c0022's home for the legality check.** Default: `placement` receives `BoardFrame` from the CLI, as `checks` does; `placed_extents` is enough.
3. **Releasing script copper to the board.** Should an intent flag (`release=True`) hand its existing copper to the board instead of removing it? Default: no for v0.1; redraw in KiCad.
4. **Arcs and blind, buried or micro vias from the copper API.** Default: v0.2a.
5. **Avoiding zones and the board edge while stitching.** Default: no; c0029 and c0022 judge them.
6. **A CLI pad query** (`fenolite pads <board> U1 2 --json`). Default: v0.2a; the Python API serves v0.1.
7. **User question (budget).** This change adds 21.5 days (18.5 after cuts) to v0.1, on top of the batch re-baseline the user is asked to accept. Accept it for v0.1, or move stitching (−2.25 days) to v0.2a? Default: keep it in v0.1 with the cut order.
8. **User question (GUI evidence).** Will the user also move a footprint of the routed blink in the 10.0.6 GUI and save, as supporting data for `H-G-FRAME-ROUTE` beside the token-edit stand-in that c0019 uses? Default: the token edit with `pcb upgrade --force` is the proof; a GUI save is recorded when available.
