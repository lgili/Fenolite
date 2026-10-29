## Context

c0175's decision 6 plans six calls of a design script that generate zones and rule areas from geometry.
What exists: `Design.zone()` and `Design.rule_area()` record zones and keep-outs that `to_model` lowers;
copper intents (`track`, `via`, `stitch`) are recorded as plain data and resolved by the KiCad build after
placement (`backends.kicad.copper.resolve_copper`), with uuids derived from their keys so a rebuild replaces
them; the plane fan-out of `route` (`backends.kicad.fanout.plan_fanout`) places one track and one via per SMD
pad of a plane net, exactly, and is `KICAD-VERIFIED`. The package layering forbids `dsl` to import
`geometry` or a backend: the script cannot know where a pad ends up, nor compute with polygons.

## Decisions

1. **Recorded by the script, resolved by the build.** Each call checks its arguments and records a frozen
   record in `Design.generated` under the key `<call>.<name>` (the name defaults to the net, the part's
   reference or the class). `fenolite.dsl.generated(design)` returns them as plain data with component paths
   and net names, points in the written board frame. The KiCad build calls
   `backends.kicad.generate.resolve_generated` after `resolve_copper` and the meanders, on the placed design,
   so the generators see the pads and the script copper. c0175 asked for a `DslError` when a spine leaves
   the board and when a barrier comes out in pieces; both need the placed board or the board's ring, so
   they are build errors (`kicad.generate.off-board`, `kicad.generate.pieces`), and the build writes nothing.
2. **Ordinary items, named by the call.** A generated zone is a locked `Zone` with the id the script's
   `zone()` of the same name would get, so `zones.merge_zones` replaces it on a rebuild and removes it when
   the call is gone (`kicad.zone.orphan`); a generated rule area is a `Keepout` with the id of a `rule_area()`
   of its name, marked by `boarditems.mark_items`; a generated track or via carries `copper_uuid(key,
   locator)` as script copper does. Names are `<call>.<name>`, with a suffix for each piece (`band.VIN`, `barrier.HV.0.a`), which `AREA_NAME`
   accepts, so a rule can select a generated area. A name that a script zone or rule area already holds
   is `kicad.generate.name-taken`.
3. **The band: cells, levels and 45° steps.** The spine is a polyline of horizontal and vertical segments
   (checked at the call). Each side of each segment is cut into cells one `step` long; a side's offset takes
   the levels `width/2 + k·step` up to `max_width/2`. A cell's level is the highest whose rectangle keeps
   `clearance` from the copper of other nets on the band's layers (pads, holes, tracks, arcs and vias of the
   placed design, judged exactly with `geometry.thick`). A cell boundary takes the lower level of its two
   cells, and neighbouring boundaries differ by at most one level: a change of one level across one cell is
   a 45° edge, and the edge inside a cell never rises above that cell's level. A shorter last cell is flat,
   end cells are flat, and a segment shorter than five widths widens by at most one level. The band is one
   zone: its outline walks the left edge of every segment from the start and the right edge back. On the
   inside of a turn both segments are flat over `max_width/2` from the joint, so the two edges meet in one
   point; on the outside the corner square is added, cut by `width/4`, and both levels are lowered until
   that square keeps the clearance too. The ends are bevelled by `width/4`. A segment shorter than
   `max_width` is refused at the call, and an outline that crosses itself (two runs closer than the band)
   is `kicad.generate.crossing`. A cell whose base level breaks the clearance gives
   `kicad.generate.band-narrow`; the fill carves it.
   - **Why cells of one step.** Then every change of level is exactly 45° with integer points, and no
     search is needed. A smaller `step` follows the obstacles more closely at the cost of more points.
   - **Why one zone.** A first form wrote one zone per segment and per joint; KiCad reports two
     overlapping zones of one priority as `zones_intersect` even on one net (`docs/formats/kicad/drc.md`,
     "Generated copper").
4. **Convex envelopes instead of a union.** Without the `geo` extra the core has no polygon union, so the
   keep-outs are convex: a disc of radius `r` is a polygon of `sides` sides whose vertices lie at
   `r / cos(π/sides)` from the centre, rounded outward and checked exactly (every edge keeps `r` from the
   centre); the envelope of a set of shapes is the convex hull of their disc polygons.
   - `keepout_ring`: around each hole of the target part, the disc polygon of `drill/2 + setback` (a slot:
     the hull of its two end discs).
   - `body_keepout`: the hull of the part's plan view (its body outlines, else the courtyard of its own
     side, as `analysis.practice.plan_views` takes it), each point grown by a disc polygon of `setback`.
   - `barrier`: the class's copper (pads of its nets on any layer, and their tracks, arcs and vias) is
     grouped: two groups whose outer envelopes meet are one piece. A piece's inner envelope is the hull of its
     copper, its outer envelope the hull grown by `setback`; the barrier is the band between them, written
     as two rule areas (the band cut by a vertical line through the inner envelope), because a rule area of
     the model has no hole. More than one piece is `kicad.generate.pieces` unless `pieces=True`. A pad of
     another net inside an outer envelope is `kicad.generate.encloses` (warning): a convex envelope may close
     around it, and its tracks could not leave.
5. **Fan-out reuses the plane fan-out.** `fanout_zone(net, side=…)` needs a zone of the net on a layer
   other than the side's outer copper layer (`kicad.generate.no-zone`). It calls `plan_fanout` with all pads
   (all are obstacles), the zone's layers as plane layers, the board's rings and edge clearance, sizes from
   the arguments or the net's class (`kicad.generate.size-missing`), and the larger of the given clearance
   and the class clearances of the two nets. It keeps the joints of the pads on the chosen side (and of
   `refs`, when given); dropping joints frees room, so the rest stays clear. A pad without a joint keeps
   `kicad.fanout.failed`.
6. **Stitching reuses the stitch filter.** `stitch_pieces(net, layers=…)` takes the zones of the net on the
   listed layers, generated bands included; two zones on different layers whose outlines overlap are an
   overlap. Its candidates are the grid points at `pitch` (from the board frame origin) inside both outlines,
   `diameter/2 + margin` from their edges and clear of the zones of other nets on those layers (a via
   there would join one piece only); `copper.stitch_vias`, a public wrapper of the filter of
   `stitch()`, keeps those clear of other copper, of rule areas that forbid vias and of the edge. An overlap
   with fewer than `min_vias` vias is `kicad.generate.stitch-short` (warning).
7. **Order.** Keep-outs first (rings, bodies, barriers), then bands, then fan-outs, then stitches, each kind
   in key order: fan-out and stitch vias respect the generated keep-outs, and stitches find the bands.
8. **Altium.** The Altium target resolves script copper through a KiCad build of the script and drops its
   zones; generated items are refused there (`kicad.generate.altium`) rather than half carried.

## Risks / Trade-offs

- Convex envelopes cover more than the copper they surround: a barrier may close around a pad of another
  net, which `kicad.generate.encloses` names; `pieces=True` and a smaller `setback` shrink it.
- A band cell tests rectangles against every obstacle near it: a long spine with a small `step` costs
  `cells × levels` exact tests, bounded by a spatial index.
- A stitch via inside both outlines may fall where a fill is carved away around other copper; it keeps the
  clearance in force, and DRC on the bench measures it.

## Open Questions

None.
