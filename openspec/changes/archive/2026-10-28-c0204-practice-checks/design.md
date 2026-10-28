## Context

c0175's design, decision 7 ("Practice checks"), holds the six kinds of this change. `net_copper` shapes every
item per net and layer, `touch_groups` joins them, `crossings.CutLine` gives the spans of a segment inside a
ring, `returns.analyze_returns` gives the referenced share of a track, and `current.capacity_ma` the capacity
of a cross-section by the published fit. What is missing is the copper of a zone that the file does not
hold, or holds from before its outlines changed.

## Decisions

1. **Three copper states per zone layer.** `saved_fill` uses the stored fill. A layer with no fill, or whose
   fill is stale, is `simulated`. A fill is stale when one cell centre of its raster lies outside its zone
   outline, outside the board or in a cut-out, inside a keep-out that forbids pours on the layer, or on copper
   of another net (a pad, track, arc or via): the outlines in force forbid copper the fill holds, so it was
   made before them. A pour whose raster would exceed `MAX_CELLS` (4 000 000) takes its zone outline as the
   copper (`outline`), an upper bound; a fill that large is not tested for staleness. Every row names the
   states it used.
2. **The simulated pour is a raster.** The core has no polygon difference without the `geo` extra, and the
   simulation must not depend on an extra. Cells are squares of `--pour-grid` (0.1 mm by default), aligned on
   the board origin, so zones of one net share cells. A cell is copper when its centre is: inside the zone
   outline, inside the board and at least the clearance from its edges, outside no-pour keep-outs, at least
   clearance plus half the width from copper of another net (and from loose copper), and at least clearance
   plus one cell from a cell of an earlier zone of another net. Zones pour by priority, highest first, then in
   file order; a stored fill of another net counts only when its zone pours earlier. The clearance is the
   largest of the zone's own and the class clearances of the two nets. Islands are cells joined by a side; an
   island that no pad, track, arc or via of the net covers is dropped and counted. No spokes, no minimum width
   and no clearance around holes without copper are simulated: the result places copper to within one cell.
3. **Groups and findings.** The groups of a net are its items joined where they touch on a layer, and the
   islands joined to the items that cover one of their cells. `connectivity` lists the nets that own a zone
   or fall apart; a net with two or more groups of pads is `analysis.net-split`, a warning: it is an open
   net whatever the requirements, as `returns` warns of a split plane. `dead` warns of a fill polygon whose
   group holds no pad (`analysis.copper-dead`) and, with `--dead-distance`, of copper whose exact gap to
   every pad of its net is larger (`analysis.copper-far`).
4. **Decoupling.** A supply pin is a pin of type `power_in`; a capacitor is a part whose reference is `C`
   and a digit. The distance along copper is a shortest path over points: the anchors of the items (pad and
   via positions, track and arc ends), each also placed on every item of the net that covers it on a shared
   layer, and joined by straight steps when they lie on one item. It is exact along straight tracks and a
   lower bound through pads, arcs and pours. The loop area is the polygon pin, capacitor pad, its other pad,
   the part's pad on that other net. A `[[decoupling]]` row judges the distance (`analysis.decoupling-far`,
   error). The stored fills are walked; a simulated pour is not.
5. **Bodies.** The plan view is the outline of the part's bodies placed with the footprint, else its
   courtyard from the backend (`placed_extents`). For each `[[body_copper]]` row, part and forbidden layer,
   copper of a class net that touches the plan view (or a simulated island with a cell in it) is
   `analysis.body-copper` (error); the part's own pads do not count. Without a row there is nothing to
   select: `analysis.input-missing`.
6. **Relief.** A pad joined by thermal relief (its connection, else the zone's; `thru_hole_only` thermal for
   a plated hole) gets a ring: the box of its copper grown by half the zone's thermal gap. The stored fill
   along its four sides gives the spokes and their total width; a span through a corner counts once. With a
   `[[current]]` row of the net and a copper thickness, the capacity of that width by the fit judges the row
   (`analysis.relief-exceeded`, error); no spoke at all is the same error. A simulated pour has no spokes, so
   its width is `null`.
7. **Coupling.** Two pieces are parallel when the sine of their angle is at most 1/100; a stretch is the
   overlap of their projections, its gap `s` the smaller edge gap at its two ends. It counts when `s ≤ 10·h`,
   where its weight falls below 1 %. `h` is the depth through the stack-up to the nearest other copper layer
   that holds a fill, else the board thickness; without both nothing is scored. Broadside is the overlap of
   parallel pieces on neighbouring layers whose centre lines lie closer in plan than their half-widths. The
   victims' reference share comes from `analyze_returns`. No row judges coupling.

## Risks / Trade-offs

- A raster can miss a neck narrower than a cell and can close a gap narrower than a cell; `--pour-grid`
  trades time for detail. The rows name the state, so a reader knows when to refill and measure again.
- A KiCad board file holds no net class, so a `[[body_copper]]` row on a KiCad board sees every net as
  `Default`.

## Open Questions

None.
