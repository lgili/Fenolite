## MODIFIED Requirements

### Requirement: Clearance on a layer
`fenolite.analysis.distance.analyze_distances(design, *, pads, boundary, pairs=(), within=None, requirements=None, arc_tol=ARC_TOL_NM, groove=None, insulation=False) -> AnalysisReport` SHALL give one `DistanceRow(net_a, net_b, gaps, clearance, creepage, insulation=None, sheets=None)` per selected pair of nets, the names in sorted order.
- `gaps` MUST hold, for each copper layer that carries copper of both nets, a `Measure` of the smallest gap between a shape of one net and a shape of the other on that layer, the gap being that of `geometry-kernel`, "Exact gaps between thick shapes". `low` MUST be `thick_gap_floor` less the bands of the two items and not below 0; `high` MUST be `thick_gap_floor` plus 1 plus the bands; `points` MUST hold `thick_witness`.
- `clearance` MUST be the measure through air: the smallest of the chains through air on the two outer copper layers and of the measure of "Clearance across the board edge". A chain joins a shape of one net to a shape of the other through the conductors of "Creepage over conductors": each link is a gap on one face, measured as `gaps` are, and a conductor is crossed at no length, from one face to the other when it has copper on both outer layers. Without a conductor on the way, a chain is the gap of the two nets on that face; its `low` and `high` are the sums of its links'. Cut-outs do not lengthen it. It is `None` when neither net has copper on an outer layer.
- Gaps on inner layers are distances inside the laminate. They MUST be reported in `gaps` and MUST NOT enter `clearance`.
- Selected pairs MUST be: each pair of `pairs`; each pair of nets that a distance row of `requirements` matches; and, with `within`, every pair of nets with a gap on a layer below `within`, found with one `SpatialIndex` per layer over `thick_bbox` grown by `within`, and, with `insulation`, also every pair whose distance through the laminate ("Insulation between layers") is below `within`. Without any of the three, `rows` is empty and one `analysis.input-missing` warning names `pair selection`.

#### Scenario: Two discs
- **GIVEN** a two-layer board with two through vias of diameter 1 mm, of nets `A` at (0, 0) and `B` at (10 mm, 0)
- **WHEN** `uv run pytest tests/unit/analysis/test_distance.py -k discs` calls `analyze_distances(design, pads=None, boundary=None, pairs=(("A", "B"),))`
- **THEN** the row holds a gap on `F.Cu` and on `B.Cu` with `low == 9_000_000` and `high == 9_000_001`, and `clearance.low == 9_000_000`

#### Scenario: Slot does not lengthen clearance
- **GIVEN** the same board with a rectangular cut-out from (4 mm, −3 mm) to (6 mm, 3 mm) between the vias
- **WHEN** `analyze_distances` runs with the boundary of the board
- **THEN** `clearance.low == 9_000_000` still

#### Scenario: Within finds the close pairs
- **GIVEN** 200 generated tracks on two layers and five nets
- **WHEN** `uv run pytest tests/unit/analysis/test_distance.py -k within` compares the pairs of `within=500_000` with those of a check of every pair of shapes
- **THEN** the two sets of pairs are equal

#### Scenario: A floating track shortens the clearance
- **GIVEN** a two-layer board in a 30 mm × 20 mm outline centred on (5 mm, 0), a 1 mm track of net `A` from (−2 mm, 0) to (0, 0) and one of net `B` from (10 mm, 0) to (12 mm, 0) on `F.Cu`, and a 1 mm track without a net from (5 mm, −2 mm) to (5 mm, 2 mm) on `F.Cu`
- **WHEN** `uv run pytest tests/unit/analysis/test_distance.py -k floating` analyses the pair `A`, `B` with the boundary of the board
- **THEN** the gap on `F.Cu` has `low == 9_000_000`, while `clearance.low == 8_000_000` and `clearance.high == 8_000_002`, the chain crossing the floating track, which `clearance.over` names

### Requirement: Creepage on the board surface
`fenolite.analysis.surface.surface_distance(a, b, boundary, *, limit=None, bridges=()) -> SurfacePath | None` SHALL search the shortest path along the board surface from a terminal of `a` to a terminal of `b`, a terminal being `Terminal(shape: Thick, face, band=0)` with `face` `top` or `bottom` and `band` the bound of the shape's approximation. The surface is the two outer faces inside `boundary.outer`, less the interior of every cut-out, joined by a wall of height `boundary.thickness` along every boundary edge.
- A path MUST be a chain of legs. A leg is a straight segment on one face that passes neither strictly inside a cut-out nor strictly outside `outer`; a wall drop of length `thickness` at a boundary vertex; or a wall crossing through the interior of one boundary edge, straight in the development that unfolds the two faces and the wall into one plane. A leg MAY run along a boundary edge.
- `bridges` are terminals of other copper, the conductors. A path MAY reach a bridge and leave it from any point of its copper at no length, and a conductor given as a bridge on both faces MAY be left on the other face at no length. Copper that is neither a terminal nor a bridge MUST NOT block a leg.
- The search MUST consider paths that bend only at boundary vertices and at bridges: the direct leg between each pair of core pieces of two shapes among the terminals and the bridges, and legs from each core piece to each boundary vertex at the point of the piece nearest to it. Whether a leg is allowed MUST be decided with the kernel's exact predicates on integer or `Fraction` coordinates.
- The length of a leg from a shape MUST be the distance to its core less half its width. Lengths MUST be summed as integers scaled by 2²⁰ per nanometre, each a rounded-down square root, so the reported `length` is an integer with `length ≤ d < length + 2` on a boundary without curved edges. The direction across a wall MUST use a unit normal rounded at 2⁻⁶⁴.
- `SurfacePath` MUST hold `length`, `band` (`boundary.band` times the number of bends of the path at boundary vertices, plus the bands of the two terminals it joins and of the bridges it crosses), `points`, each with its face, `ends`, the indices of those two terminals in `a` and `b`, and `over`, the indices in `bridges` of the conductors the path crosses, in path order.
- The search MAY leave out a leg that cannot lead to a shorter path: no path from a point to a conductor is shorter than their distance in plan view less the half width, and a bridge whose distances in plan view to `a` and to `b` add up to at least the best length known cannot shorten it. Such pruning MUST NOT change the result.
- When `boundary.thickness` is `None`, no wall leg exists, and terminals on opposite faces are joined only through a conductor given on both faces.
- With `limit`, the search MAY stop when no path shorter than `limit` exists, and MUST then return `None`.
- Without `boundary`, or with `boundary.source == "none"`, the surface is one unbounded plane per face: terminals and bridges of the same face are joined by their gaps.
- A terminal or a bridge with a core point strictly outside `outer` or strictly inside a cut-out MUST be left out; `usable_terminals(terminals, boundary)` returns the terminals kept and the count left out, and `analyze_distances` reports the count of terminals left out in one `analysis.item-unsupported` warning.

`analyze_distances` MUST set `creepage` of a row from this search, over the shapes of the two nets on the two outer copper layers, the first copper layer being the `top` face: `low = max(0, length − band)`, `high = length + band + 2`, and `over` the `where` of the conductors crossed. Its bridges MUST be every other shape on the two outer copper layers: the shapes of the other nets and the copper without a net of "Creepage over conductors", a via or a pad with copper on both outer layers being one bridge given on both faces. Its boundary MUST be that of "Creepage grooves" when a groove width applies to the pair. Holes, solder mask, coatings and components MUST be ignored; `docs/analyses.md` MUST list them as limits.

#### Scenario: Around a slot
- **GIVEN** the two vias of "Two discs" and the cut-out from (4 mm, −3 mm) to (6 mm, 3 mm) in a 30 mm × 20 mm outline centred on (5 mm, 0)
- **WHEN** `uv run pytest tests/unit/analysis/test_surface.py -k slot` computes the creepage on the top face
- **THEN** `length == 11_000_000` (4.5 mm to the corner (4 mm, 3 mm), 2 mm along the slot, 4.5 mm from the corner (6 mm, 3 mm)), `band == 0`, the points name the two corners, and `clearance.low` is still 9 mm

#### Scenario: Slot open to the board edge
- **GIVEN** the same vias on a board whose outer ring has a notch from (4 mm, −10 mm) to (6 mm, 3 mm), open at the lower edge
- **WHEN** the creepage is computed with `thickness=None`
- **THEN** `length == 11_000_000`, the path passing the two upper corners of the notch

#### Scenario: Agreement with a grid search
- **GIVEN** generated rectangular boards with up to three rectangular cut-outs on a 0.1 mm grid and two disc terminals on the top face
- **WHEN** `uv run pytest tests/unit/analysis/test_surface.py -k grid` compares `length` with the shortest path of an eight-neighbour grid search at 0.1 mm
- **THEN** `length` is never above the grid's path length plus 1 nm, and never below 0.92 times it (the eight-neighbour metric overstates a straight length by at most 8.3 %)

#### Scenario: Limit stops the search
- **WHEN** the search of "Around a slot" runs with `limit=10_000_000`
- **THEN** it returns `None`, and the row's `creepage` has `bounded is True` and `low == 10_000_000`

#### Scenario: A conductor is crossed at no length
- **GIVEN** the board of "A floating track shortens the clearance" with a track of net `C` in place of the floating track
- **WHEN** `uv run pytest tests/unit/analysis/test_surface_bridges.py -k crossed` calls `surface_distance` with the tracks of `A` and `B` as terminals and the track of `C` as the only bridge
- **THEN** `length == 8_000_000` and `over == (0,)`, the path running 4 mm to the track of `C` and 4 mm from it

#### Scenario: A through via joins the faces
- **GIVEN** the board of "Track above track", 1.6 mm thick, and a through via without a net of diameter 0.6 mm at (10 mm, 4 mm)
- **WHEN** the pair `A`, `B` is analysed
- **THEN** `creepage.low == 2_900_000`, 1.45 mm on each face to the via's pad, which `creepage.over` names, and `clearance.low == 2_900_000`

#### Scenario: Agreement with a grid search over conductors
- **GIVEN** generated rectangular boards with up to three rectangular cut-outs and up to two rectangular conductors on a 0.1 mm grid, and two disc terminals on the top face
- **WHEN** `uv run pytest tests/unit/analysis/test_surface_bridges.py -k grid` compares `length` with the grid search of "Agreement with a grid search" in which the conductors' cells cost nothing
- **THEN** `length` is never above the grid's length plus 1 nm, and never below 0.92 times it

### Requirement: Requirement tables supplied by the user
`fenolite.analysis.requirements.load_requirements(text, *, file="") -> Requirements` SHALL parse a TOML document (`tomllib`) whose top-level key `schema` equals `fenolite.requirements.v0` and which holds any of the arrays `current`, `distance`, `step` and `path`. Every number MUST be a TOML integer; a float, an unknown key, a missing key or another `schema` MUST raise `FormatError` naming the file and the key.
- A selector is a table with exactly one of the keys `net` and `netclass`, whose value is a glob matched as `model.rules.Selector` matches it. A net without a class has the class `Default`.
- `[[current]]`: a selector under `select`, `milliamps` and `temp_rise_mk`. The governing row of a net MUST be the matching row with the largest `milliamps`.
- `[[distance]]`: selectors `a` and `b`; either any of `clearance_nm`, `creepage_nm`, `embedded_nm` and `insulation_nm`, or `millivolts`; and optionally `groove_nm`, the groove width of "Creepage grooves". A row matches a pair of different nets when `a` matches one and `b` the other, in either order. When several rows match a pair, the largest value of each quantity governs, `groove_nm` included.
- `[[step]]`: `up_to_mv` and any of `clearance_nm`, `creepage_nm`, `embedded_nm` and `insulation_nm`: the user's own table from voltage to distance. A distance row with `millivolts` takes its values from the step with the smallest `up_to_mv` that is at least its `millivolts`. Fenolite MUST NOT interpolate between steps. A voltage above every step gives no requirement and one `analysis.requirement-unmatched` warning naming the row.
- `[[path]]`: `from` and `to`, each a non-empty array of pad names `REF-PIN` (split at the last `-`, both parts non-empty), `milliamps` and `temp_rise_mk`, and optionally `drop_mv`: the current the copper between the two sets of pads must carry, the temperature rise the user accepts and the largest voltage drop ("Power path current", "Power path voltage drop"). A pad name of another form MUST raise `FormatError` naming the key.
- A row whose selectors match no net of the design MUST give one `analysis.requirement-unmatched` warning.
- `embedded_nm` MUST be judged against the gaps on inner layers, `clearance_nm` against `clearance`, `creepage_nm` against `creepage` and `insulation_nm` against `insulation`.

#### Scenario: Step lookup without interpolation
- **GIVEN** steps `up_to_mv = 50_000` with `creepage_nm = 1_000_000` and `up_to_mv = 300_000` with `creepage_nm = 3_000_000`, and a distance row with `millivolts = 230_000`
- **WHEN** `uv run pytest tests/unit/analysis/test_requirements.py -k step` resolves the row
- **THEN** the creepage requirement is 3 mm, and with `millivolts = 400_000` there is none and one `analysis.requirement-unmatched` warning

#### Scenario: Floats refused
- **GIVEN** a document with `milliamps = 2.5`
- **WHEN** `load_requirements` parses it
- **THEN** a `FormatError` names `current[0].milliamps`

#### Scenario: Largest row governs
- **GIVEN** two distance rows that match the pair `L`, `N` with `creepage_nm` 2 mm and 4 mm
- **WHEN** the pair is resolved
- **THEN** the creepage requirement is 4 mm

#### Scenario: Path rows
- **GIVEN** a document with a `[[path]]` row `from = ["J1-1"]`, `to = ["Q1-2", "Q2-2"]`, `milliamps = 20000`, `temp_rise_mk = 10000` and `drop_mv = 50`
- **WHEN** `uv run pytest tests/unit/analysis/test_requirements.py -k path` parses it
- **THEN** `paths` holds one row with those values, and the same row with `from = []` or with `from = ["J1"]` raises a `FormatError` naming `path[0].from`

#### Scenario: Insulation and groove keys
- **GIVEN** two distance rows that match the pair `HV`, `LV`, one with `insulation_nm = 400_000` and `groove_nm = 1_000_000`, the other with `millivolts = 230_000`, and a step `up_to_mv = 300_000` with `insulation_nm = 200_000`
- **WHEN** `uv run pytest tests/unit/analysis/test_requirements.py -k insulation` resolves the pair
- **THEN** the insulation requirement is 0.4 mm and the groove width is 1 mm

## ADDED Requirements

### Requirement: Copper fill regions
`fenolite.analysis.fills.fill_regions(design) -> tuple[tuple[FillRegion, ...], int]` SHALL turn each `ZoneFill` of a zone that has a net into one frozen `FillRegion(zone_id, net, layer, where, outer, holes, area2)`, the copper of that fill, and return the regions with the count of fills left out (`H-K-FILL-SLIT`).
- `unfracture(ring)` MUST remove every slit of the stored ring, a slit being a pair of its edges that join the same two points in opposite directions, and chain the remaining edges into rings by exact endpoint equality; it MUST return `None` when they do not chain. `outer` MUST be the ring of largest area and `holes` the others. Points MUST be the stored integer points; nothing is rounded.
- `area2` MUST be twice the area of the stored ring, and MUST equal twice the area of `outer` less those of `holes`.
- A fill whose edges do not chain, or whose two areas differ, MUST be left out and counted; an analysis that uses the regions MUST report the count in one `analysis.item-unsupported` warning naming `fill`.
- `where` MUST be the zone's locator, else its id, followed by `#` and the index of the fill in the zone.
- The function reads the model only, so it MUST give the same regions for a board of any backend. A ring made by `fenolite.geometry.polygon.keyhole_ring(outer, holes)`, the form in which the Altium import stores a pour with holes, MUST come back as its rings: each ring given, up to its starting point and its direction, with the anchor points that `keyhole_ring` put into edges.
- `area_outside(region, hulls)` MUST return, as a `Fraction` of square nanometres, the area of the region outside the given convex hulls: `outer` and each hole clipped exactly by each hull.

#### Scenario: A pour with a hole
- **GIVEN** the authored region `split4` of `tests/_power.py`: two 10 mm squares joined by a neck 4 mm wide and 3 mm long, with a 1.6 mm square hole at the centre of the neck, stored as one ring with one slit pair
- **WHEN** `uv run pytest tests/unit/analysis/test_fills.py -k hole` reads its regions
- **THEN** there is one region, its `holes` hold one ring of four points, and `area2 == 418_880_000_000_000`, twice 209.44 mm²

#### Scenario: A keyhole ring is undone
- **GIVEN** a 20 mm square and two 2 mm square holes inside it, 6 mm apart, and `ring = keyhole_ring(square, holes).ring`
- **WHEN** `uv run pytest tests/unit/analysis/test_fills.py -k keyhole` calls `unfracture(ring)`
- **THEN** it returns an outer ring that holds the four corners of the square and two holes whose point sets are those given, and twice the area of the outer ring less those of the holes is `784_000_000_000_000`, twice 392 mm², the shoelace value of `ring`

#### Scenario: Fills of the corpus chain
- **WHEN** `uv run pytest tests/corpus/test_fill_slits.py -rA` reads every fill of the cached demo boards of tags 9.0.9.1 and 10.0.6
- **THEN** every fill chains into rings with equal areas, none is left out, and the census written to `FENOLITE_CENSUS_OUT` holds the counts of fills, of fills with slits and of holes

### Requirement: Narrowest copper section
`fenolite.analysis.section.narrowest_section(region, a, b, *, arc_tol=ARC_TOL_NM, limit=None) -> Section` SHALL give the narrowest copper section of a fill region between two ports: the smallest length, inside the region, of a closed curve that enters neither port's hull and holds one hull inside it and the other outside (`H-G-AN-SECTION`).
- A port is the frozen record `Port(where, shapes, band)`: the copper of one piece or via group inside the region as `Thick` shapes, and the bound of their approximation. `port_hull(port, *, arc_tol)` MUST be the convex hull of the shapes, each polygonised at `arc_tol` with every point on or inside its copper.
- The search MUST consider the closed curves made of straight chords through the region and of free runs through its holes and around its outer ring, a run never crossing a hull. A chord ends on an edge of a ring or at a hull vertex; a chord between two edges joins their closest points. A curve separates the ports when it crosses a seam, drawn from a point inside one hull to a point inside the other, an odd number of times, crossings being counted on half-open segments. Every crossing and every side MUST be decided with the kernel's exact predicates on integer or `Fraction` coordinates.
- `Section(measure, hull_free)`: `measure.low` MUST be the sum of the chords' rounded-down lengths less the two ports' bands, not below 0, and `measure.high` the sum of their rounded-up lengths plus the bands; `measure.points` MUST be the ends of the chords in order, `measure.items` the two ports' `where` and `measure.layer` the region's layer. When the hulls touch or overlap, `low` and `high` MUST be 0.
- `hull_free` MUST be false when a hole of the region lies inside a port's hull and outside the port's shapes: a curve through that hole may then be shorter, and the measure is only an upper bound of the section of the port's own copper.
- With `limit`, the search MAY stop when no curve shorter than `limit` exists; the measure is then `bounded`, with `low == limit` and `high` `None`.
- The search MAY leave out a chord that cannot shorten the best curve known, which starts as the smaller hull's perimeter; such pruning MUST NOT change the result.

#### Scenario: Neck of a dumbbell
- **GIVEN** the authored region `dumbbell` of `tests/_power.py`: two 10 mm squares joined by a neck 2 mm wide and 3 mm long, and as ports a 1 mm via at the centre of each square
- **WHEN** `uv run pytest tests/unit/analysis/test_section.py -k neck` computes the section
- **THEN** `measure.low == 2_000_000`, `measure.high <= 2_000_001`, both points lie on the walls of the neck, and `hull_free` is true

#### Scenario: Two strips add up
- **GIVEN** the region `split4` of "Copper fill regions" and the same two ports
- **WHEN** the section is computed
- **THEN** `measure.low == 2_400_000`: one chord across each strip of 1.2 mm beside the hole, joined by a free run through it

#### Scenario: Thermal spokes
- **GIVEN** a 20 mm square region whose hole at its centre is the 3 mm square less four spokes 0.5 mm wide along the axes, a 2 mm × 2 mm rectangular pad at the centre that touches the four spokes as one port, and a 1 mm via near a corner as the other
- **WHEN** the section is computed
- **THEN** `measure.low == 2_000_000`, four chords across the spokes

#### Scenario: Around a via
- **GIVEN** a 20 mm square region, a 0.6 mm via at its centre as one port and a 2 mm × 2 mm pad near a corner as the other
- **WHEN** the section is computed
- **THEN** `measure.low` lies between 1 880 000 and 1 884 955 nm: the perimeter of the via's polygonised hull, below π · 0.6 mm

#### Scenario: A hole inside a hull
- **GIVEN** a solid region, a port made of four 0.6 mm vias at the corners of a 2 mm square with the 0.8 mm hole of a foreign via at the square's centre, and a pad far from it as the other port
- **WHEN** the section between the four vias and the pad is computed
- **THEN** `hull_free` is false

#### Scenario: Agreement with a grid cut
- **GIVEN** generated regions on a 0.05 mm grid with up to four rectangular holes and two rectangular ports
- **WHEN** `uv run pytest tests/unit/analysis/test_section.py -k grid` compares `measure.low` with the minimum cut of the four-neighbour graph of the region's cells at 0.05 mm
- **THEN** `measure.low` is never above the grid cut plus 0.05 mm, and never below the grid cut divided by √2 less 0.05 mm

### Requirement: Power path network
`fenolite.analysis.network.path_network(design, *, pads, start, end, arc_tol=ARC_TOL_NM) -> PathNetwork` SHALL build the copper network of the net that holds the pads named in `start` and `end`, each a tuple of `REF-PIN` names, and mark its active part: the copper on a power path between the two sets of pads.
- **Pieces.** The net's tracks and arcs on copper layers, its vias, its pads of `pads` that have copper, and its regions of "Copper fill regions", shaped as `net_copper` shapes them: a via is the disc of its diameter on every layer of its span, also on a layer where an import recorded no pad shape. Graphics on a copper layer, those of a footprint instance included, are not pieces; they MUST be counted in `PathNetwork.issues` as one `analysis.item-unsupported` warning naming `graphic` with their count.
- **Joins.** On each copper layer, two pieces whose copper touches MUST be joined (`thick_touch`), and a via MUST be joined to the pieces its disc touches on each layer of its span. A pad is one node on all its layers.
- **One-dimensional pieces.** A track or an arc MUST be split where its centre line enters or leaves a region of its net on its layer, the parts inside the region being left out because the region is that copper; at the point of its centre line nearest to the position of each pad or via, and to each end of another track or arc, that is joined to it away from its own ends; and where its centre line crosses that of another track or arc of the net.
- **Via groups.** Vias joined to the same pieces on each of their layers MUST form one `ViaGroup`.
- **Ports.** Each piece or via group joined to a region MUST be one port of the region, its shapes being that piece's copper inside the region, or the discs of the group's vias on the region's layer.
- **Active part.** An element (a part of a track or arc, a via group, a region) MUST be active when it lies on a path from a start pad to an end pad that passes each element once, and in series when every such path passes it; a port is active when it joins its region to active copper. Inactive copper carries no direct current and MUST NOT be judged.
- A name that no pad of `pads` holds, or pads of more than one net, MUST give one `analysis.path-unmatched` warning and an empty network; when the net's copper does not join `start` to `end`, one `analysis.path-open` warning MUST name the pads.

#### Scenario: A branch to a capacitor is off the path
- **GIVEN** the authored board `branch` of `tests/_power.py`: net `VBUS`, a 1 mm track on `F.Cu` from pad `J1-1` to pad `U1-1`, and a 0.25 mm track from a point of the first track's body to pad `C1-1`
- **WHEN** `uv run pytest tests/unit/analysis/test_network.py -k branch` builds the network from `J1-1` to `U1-1`
- **THEN** the 1 mm track is split at the branch into two active parts, both in series, and the 0.25 mm track is not active

#### Scenario: Two layers in parallel
- **GIVEN** the authored board `two_strips`: through-hole pads `J1-1` and `U1-1` joined by a region on `F.Cu` and one on `B.Cu`
- **WHEN** the network from `J1-1` to `U1-1` is built
- **THEN** both regions are active, neither is in series, and each has two active ports

#### Scenario: A via array is one group
- **GIVEN** the authored board `via_array`: a region on `F.Cu` holding pad `J1-1`, a region on `B.Cu` holding pad `U1-1` of a part on the bottom side, eight through vias joined to both regions, and two pads of decoupling parts joined to the `F.Cu` region only
- **WHEN** the network from `J1-1` to `U1-1` is built
- **THEN** the eight vias form one active via group in series, and the two decoupling pads are not active ports

#### Scenario: Unknown pad
- **WHEN** the network of the board `branch` from `J1-1` to `U9-1` is built
- **THEN** it is empty, and one `analysis.path-unmatched` warning names `U9-1`

### Requirement: Power path current
`fenolite.analysis.power.analyze_power(design, *, pads, paths=(), requirements=None, temp_rise_mk=None, copper_thickness=None, via_plating=None, resistivity_pohm_m=None, arc_tol=ARC_TOL_NM) -> PowerReport` SHALL give one `PathRow(net, start, end, milliamps, temp_rise_mk, elements, resistance_uohm, drop_mv)` per power path: each pair of `paths`, measured only, and each `[[path]]` row of `requirements`, measured and judged; rows sorted by net, `start` and `end`.
- `elements` MUST hold one `PathElement(kind, where, layer, series, area_nm2, section, ports, capacity_ma, in_range, resistance_uohm)` per active element of "Power path network", sorted by layer, kind and `where`: `kind` is `track`, `arc`, `via-group` or `fill`; `layer` its layer, or the two layers of a via group joined by `/`; `area_nm2` the width times the layer's copper thickness, the sum of c0047's `barrel_area_nm2` over the group's vias, or `section.low` times the thickness for a region.
- A region's `section` MUST be the narrowest copper section between its two active ports or, with more than two, the smallest of the sections between pairs of them, and `ports` MUST name those two ports.
- `capacity_ma` MUST be c0047's `capacity_ma` for `area_nm2` at the path's rise with the layer's factor, and, for a via group, the sum of its vias' capacities with the outer factor. `in_range` follows "Stated range of the fit", the section being a region's width; an element outside the range gives c0047's `analysis.fit-out-of-range` warning.
- Thickness, plating and rise MUST follow c0047's rules: `copper_thickness`, else the stack-up; `via_plating`; the row's `temp_rise_mk`, else the argument. Nothing is assumed: an element whose input is missing has no capacity, and one `analysis.input-missing` warning per missing input counts the elements.
- **Judging** a `[[path]]` row of current `I`: an element whose capacity is below `I` MUST give `analysis.path-exceeded` (error) when it carries the whole current, that is when it is in series and is a part of a track or arc, a via group, or a region with exactly two active ports whose section is `hull_free`; otherwise it MUST give `analysis.path-undecided` (warning), whose message says that its share of the current is not computed. A via group in series whose summed capacity is below `I` fails whatever the split. An element without a capacity is not judged.
- A message MUST give the element, its layer, its capacity and the current in milliamperes, and for a section its two end points in millimetres.

#### Scenario: The branch is not judged
- **GIVEN** the board `branch`, 35 µm of copper, and a `[[path]]` row from `J1-1` to `U1-1` of 2000 mA at 20 K
- **WHEN** `uv run pytest tests/unit/analysis/test_power.py -k branch` runs `analyze_power`
- **THEN** the two parts of the 1 mm track have `capacity_ma == 3244` and no issue is raised, while a `[[current]]` row of 2000 mA at 20 K on `VBUS` gives `analyze_current` one `analysis.current-exceeded` error for the 0.25 mm track (1187 mA)

#### Scenario: A via group in series
- **GIVEN** the board `via_array` with four vias of 0.3 mm drill, `via_plating=25_000`, and a `[[path]]` row of 8000 mA at 10 K
- **WHEN** `analyze_power` runs
- **THEN** the group has `capacity_ma == 7608` and gives one `analysis.path-exceeded` error; with five vias it has 9510 mA and gives none

#### Scenario: A neck in series
- **GIVEN** the region `dumbbell` with a 2 mm × 2 mm pad `J1-1` in one square and `U1-1` in the other in place of the vias, 35 µm of copper, and a `[[path]]` row of 5000 mA at 10 K
- **WHEN** `analyze_power` runs
- **THEN** the region's section is 2 mm with `capacity_ma == 3953`, and one `analysis.path-exceeded` error names the region, 3953 mA, 5000 mA and the two points of the section

#### Scenario: Parallel layers are undecided
- **GIVEN** the board `two_strips`, each region 20 mm × 5 mm between the pads, 50 µm of copper, and a `[[path]]` row of 12 000 mA at 10 K
- **WHEN** `analyze_power` runs
- **THEN** each region's section is 5 mm with `capacity_ma == 9948`, and each gives one `analysis.path-undecided` warning and no error

### Requirement: Power path voltage drop
With `resistivity_pohm_m`, the copper's resistivity in picoohm-metres given by the user, each `PathRow` SHALL hold `resistance_uohm`, an `Interval(low, high)` of the resistance between its two sets of pads in microohms, and a `[[path]]` row SHALL also hold `drop_mv`, the interval of the voltage drop at its current in millivolts (`H-G-AN-NETWORK`).
- **Elements.** Pads and joints are ideal contacts. A part of a track or arc is `ρ·L/(w·t)`, `L` its centre-line length. A via group is its barrels in parallel, `ρ·h/ΣA`, `h` the distance between the middles of its two copper layers by `Stackup.depth` of c0101 and `A` the barrel areas. A region between two active ports lies between `R_s·ℓ²/A` and `R_s·A/w²` (`H-G-AN-POUR`), with `R_s = ρ/t`, `ℓ` the shortest path in the region between the two port hulls (the search of "Creepage on the board surface" on the region as a one-face board), `w` their narrowest copper section and `A` the region's area outside the two hulls (`area_outside`). `region_bounds` MUST return that interval, with `high` `None` when `w` is 0 or not `hull_free`.
- Every value MUST be computed with integers and `Fraction`s, lengths as intervals of square roots, each `low` rounded down and each `high` rounded up.
- `low` MUST be the resistance between the two sets of the active network with every element at its low value and every region of more than two active ports shorted into one node. Lowering an element's resistance or shorting copper never raises the resistance of a network.
- `high` MUST be the resistance of the active network with every element at its high value when every active region has at most two active ports, and otherwise the smallest sum of high values over the chains from a start pad to an end pad that pass each region once, between two of its ports. Raising a resistance or removing copper never lowers it. `high` MUST be `None` when no such chain has a high value.
- `drop_mv` MUST be `milliamps · resistance_uohm / 10⁶`, `low` rounded down and `high` rounded up. Against the row's `drop_mv`, `D`: `drop.low > D` MUST give `analysis.drop-above` (error); `drop.low ≤ D < drop.high`, or `high` `None`, MUST give `analysis.drop-undecided` (warning); `drop.high ≤ D` gives no finding.
- Fenolite MUST NOT assume a resistivity: without one no row has a resistance, and one `analysis.input-missing` warning names `resistivity`. An element without its thickness, plating or depth counts 0 in `low` and makes `high` `None`, counted in the warning of the missing input.

#### Scenario: A strip between two plates
- **GIVEN** the authored board `strip`: a region 20 mm × 5 mm on `F.Cu` between two rectangular pads `J1-1` and `U1-1` that cover its two 5 mm ends to a depth of 1 mm, 50 µm of copper, `resistivity_pohm_m=20_000` (an illustrative value), and a `[[path]]` row of 10 000 mA
- **WHEN** `uv run pytest tests/unit/analysis/test_power.py -k strip` runs `analyze_power`
- **THEN** `resistance_uohm == Interval(1440, 1440)`, both bounds being `R_s · 18 mm / 5 mm` with `R_s` 400 µΩ, and `drop_mv == Interval(14, 15)`

#### Scenario: Two strips in parallel
- **GIVEN** the board `two_strips`, each region the strip of "A strip between two plates", with the same inputs
- **WHEN** the resistance is computed
- **THEN** it is `Interval(720, 720)`

#### Scenario: Drop judged
- **WHEN** the strip's row has `drop_mv` 10, then 14, then 15
- **THEN** the issues hold `analysis.drop-above`, then `analysis.drop-undecided`, then no drop finding

#### Scenario: Agreement with a finite-difference solution
- **GIVEN** the authored regions `strip`, `dumbbell` and `split4`, each between two pads, and the path of the board `two_strips` on its two layers
- **WHEN** `uv run pytest tests/unit/analysis/test_power.py -k fdm` solves Laplace's equation on them on a 0.05 mm grid, in the test
- **THEN** each grid resistance lies inside `resistance_uohm` widened by 2 %, and the test records the width of each interval

#### Scenario: Resistivity not given
- **WHEN** `analyze_power` runs on the strip without `resistivity_pohm_m`
- **THEN** `resistance_uohm` and `drop_mv` are `None`, and one `analysis.input-missing` warning names `resistivity`

### Requirement: Insulation between layers
With `insulation=True`, `analyze_distances` SHALL set the `insulation` and `sheets` of each row: the shortest distance through the laminate between copper of the two nets on two different copper layers, and the number of dielectric entries of `Board.stackup` between those two layers (`H-G-AN-INSUL`).
- For copper layers `U` above `L` in `Board.layers`, with copper of one net on one and of the other net on the other, the distance MUST be `√(g² + h²)`: `g` the smallest gap in plan view between their shapes, measured as `gaps` are, and `h` the depth of the top face of `L` less the depth of the bottom face of `U` by `Stackup.depth` of c0101. `low` MUST be the rounded-down root with `g` at its low value and `high` the rounded-up root with `g` at its high value; `points` MUST hold the plan witness, `layer` MUST be `U/L` and `items` the two shapes' `where`.
- `insulation` MUST be the measure of smallest `low` over the pairs of layers, ties broken by layer order, and `sheets` the count of entries of kind `dielectric` strictly between its two layers. Gaps on one inner layer stay in `gaps`, judged with `embedded_nm`.
- Copper of any net on a layer between `U` and `L` is not considered; `docs/analyses.md` MUST list it as a limit.
- Without `Board.stackup`, or when a copper layer has no entry in it, `insulation` and `sheets` MUST be `None` for the pairs concerned, and one `analysis.input-missing` warning MUST name `stack-up` with their count. Fenolite MUST NOT assume a thickness.
- `insulation_nm` MUST be judged against `insulation` as "Measures" states, with `analysis.insulation-below` and `analysis.insulation-undecided`.

#### Scenario: Copper over copper
- **GIVEN** a four-layer board with the stack-up `F.Cu` 35 µm, a 200 µm prepreg, `In1.Cu` 35 µm, a 1000 µm core, `In2.Cu` 35 µm, a 200 µm prepreg, `B.Cu` 35 µm, and 1 mm tracks of net `HV` on `In1.Cu` and of net `LV` on `In2.Cu`, one above the other
- **WHEN** `uv run pytest tests/unit/analysis/test_insulation.py -k overlap` runs `analyze_distances(design, pads=None, boundary=None, pairs=(("HV", "LV"),), insulation=True)`
- **THEN** `insulation.low == insulation.high == 1_000_000`, its layer is `In1.Cu/In2.Cu`, `sheets == 1`, and a distance row with `insulation_nm = 1_200_000` gives one `analysis.insulation-below` error

#### Scenario: Offset in plan view
- **GIVEN** the same stack-up, a track of `HV` on `F.Cu` and one of `LV` on `In1.Cu` whose edges lie 0.3 mm apart in plan view
- **WHEN** the pair is analysed
- **THEN** `insulation.low == 360_555` and `insulation.high == 360_556`, that is `√(0.3² + 0.2²)` mm

#### Scenario: No stack-up
- **WHEN** the pair of "Copper over copper" is analysed on the same board without its stack-up
- **THEN** `insulation is None` and one `analysis.input-missing` warning names `stack-up`

### Requirement: Creepage grooves
`fenolite.analysis.grooves.bridge_grooves(boundary, width) -> GrooveResult(boundary, bridged, counted)` SHALL return the boundary on which a creepage path crosses every groove narrower than `width`, the groove width the user gives, as if the groove were not there (`H-G-AN-GROOVE`).
- A cut-out MUST be bridged, that is left out of the returned boundary, when it has a double normal shorter than `width`: a chord inside it whose two ends meet its boundary at right angles, an end at a vertex counting as at right angles when the chord's direction lies between the normals of the vertex's two edges. Lengths MUST be compared as exact squares (`double_normal2`).
- A pocket of the outer ring MUST be filled, the ring following the pocket's mouth, when the mouth is shorter than `width`. A pocket is the region between a segment that joins two consecutive vertices of the ring's convex hull and is not an edge of the ring, its mouth, and the chain of the ring between them, the hull keeping every ring vertex that lies on its edges; the pockets of a pocket's chain, taken the same way, are pockets too. Pockets MUST be decided from the deepest.
- `bridged` and `counted` MUST count the cut-outs and pockets bridged and kept.
- `analyze_distances(…, groove=None)` MUST take for each pair the largest of `groove` and of the `groove_nm` of the distance rows that match the pair, and use the returned boundary for that pair's creepage only; the clearance and the terminals' usability keep the given boundary. `summary.grooves` MUST map each width used to its counts.
- Without a groove width every cut-out and pocket counts, as in c0047; a pair with a creepage requirement whose creepage path bends at a vertex of a cut-out or of a pocket, or crosses its wall, MUST be counted in one `analysis.input-missing` warning naming `groove width`.

#### Scenario: A slot narrower than the groove width
- **GIVEN** the board of "Around a slot"
- **WHEN** `uv run pytest tests/unit/analysis/test_grooves.py -k slot` analyses the pair with a groove width of 2 mm, then 3 mm
- **THEN** the creepage is 11 mm with 2 mm, the slot's width not being below it, and 9 mm with 3 mm, the slot bridged

#### Scenario: A notch is filled
- **GIVEN** the board of "Slot open to the board edge"
- **WHEN** the pair is analysed with a groove width of 3 mm
- **THEN** the notch, whose mouth is 2 mm, is filled, and the creepage is 9 mm

#### Scenario: A T-shaped cut-out is bridged whole
- **GIVEN** the vias of "Two discs" in the outline of "Around a slot", with a cut-out made of a stem from (4.5 mm, −3 mm) to (5.5 mm, 1 mm) and a head from (2 mm, 1 mm) to (8 mm, 5 mm)
- **WHEN** the pair is analysed with a groove width of 1.1 mm
- **THEN** the cut-out is bridged, the stem's 1 mm being below the width, and the creepage is 9 mm

#### Scenario: No groove width
- **GIVEN** the board of "Around a slot" and a distance row with `creepage_nm = 12_000_000` and no `groove_nm`
- **WHEN** the pair is analysed without a groove width
- **THEN** the creepage is 11 mm, the issues hold one `analysis.creepage-below` error and one `analysis.input-missing` warning naming `groove width` and 1, and the evidence level is `UNVERIFIED`

### Requirement: Creepage over conductors
`Measure` SHALL gain, after `bounded`, the field `over: tuple[str, ...] = ()`: the `where` of the conductors that a clearance chain of "Clearance on a layer" or a creepage path of "Creepage on the board surface" crosses, in order (`H-G-AN-OVER`). A conductor is a shape on an outer copper layer that belongs to neither net of the pair: a shape of another net from `net_copper`, or copper without a net from `fenolite.analysis.copper.loose_copper(design, *, pads, arc_tol=ARC_TOL_NM) -> tuple[CopperShape, ...]`, which shapes the tracks, arcs, vias, pads and fills that have no net as `net_copper` shapes the others. Graphics on a copper layer, those of a footprint instance included, are not conductors: a distance report that used `loose_copper` on a board that holds any MUST give one `analysis.item-unsupported` warning naming `graphic` with their count.
- A pair whose clearance or creepage crosses copper of a third net MUST give one `analysis.creepage-over` info naming the pair and those nets, because the distances from each net of the pair to a third net are the ones its voltage acts across; its hint names the pairs to select.
- `DistanceRow` SHALL gain, after `creepage` and with defaults, `insulation: Measure | None = None` and `sheets: int | None = None`, set by "Insulation between layers".

#### Scenario: A floating via
- **GIVEN** the tracks of `A` and `B` of "A floating track shortens the clearance" and, in place of the floating track, a through via without a net of diameter 1 mm at (5 mm, 0)
- **WHEN** `uv run pytest tests/unit/analysis/test_surface_bridges.py -k floating_via` analyses the pair
- **THEN** `creepage.low == 8_000_000`, `creepage.over` names the via, `clearance.low == 8_000_000`, and no `analysis.creepage-over` info is raised

#### Scenario: A third net
- **GIVEN** the same tracks and a 1 mm track of net `C` from (5 mm, −2 mm) to (5 mm, 2 mm)
- **WHEN** the pair `A`, `B` is analysed
- **THEN** `creepage.low == 8_000_000`, `creepage.over` names the track of `C`, and one `analysis.creepage-over` info names `A`, `B` and `C`

### Requirement: Power and insulation kinds
`fenolite analyze` SHALL accept `power` and `insulation` in `--kinds`, neither in the default set, so that without `--kinds` the command runs the three kinds of "Analyze command" and its reply holds neither `power` nor `insulation`.
- Options: `--path FROM TO` (repeatable), `FROM` and `TO` each one or more `REF-PIN` names joined by commas; `--resistivity NANOOHM_METRES`, a decimal number of at most three decimals, passed on in picoohm-metres; `--groove-width LENGTH`. `--path` and `--resistivity` MUST be usage errors (`FEN-2001`, exit 2) when `power` is not among the kinds, and `--groove-width` when `creepage` is not.
- With `power`, the command MUST call `analyze_power` with the backend's pads when it satisfies `BoardFrame`, the paths of `--path`, the `[[path]]` rows of `--requirements` and the options of "Analyze command"; `result.power` MUST hold the rows as JSON objects with the field names of the records, and `result.summary.power` the report's summary.
- With `insulation`, `analyze_distances` MUST be called with `insulation=True`; the rows of `result.distances` keep `insulation` and `sheets` only then, as unselected kinds are left out of each row.
- `result.inputs` MUST gain `paths`, `resistivity_pohm_m` and `groove_nm`.
- The power report's issues join the envelope's `issues`; an issue of severity `error` gives exit code 5. The command stays read-only and runs no tool; `docs/cli-contract.md` MUST document the kinds and options under `analyze`.
- The kinds MUST run on every board that "Analyze command" reads, whatever backend detects it. On an imported Altium board the reply MUST combine the import's evidence as the three default kinds do, and a path whose copper the import does not hold MUST give `analysis.path-open`, never a guessed join.

#### Scenario: A path from the command line
- **GIVEN** the authored board `tests/data/analysis/strip_10.kicad_pcb`, the board `strip` written for target 10
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_power.py -k strip` runs `fenolite analyze <board> --kinds power --path J1-1 U1-1 --copper-thickness 50um --resistivity 20 --json`
- **THEN** the exit code is 0, `result.power` holds one row whose `resistance_uohm` has `low` and `high` 1440, and its `drop_mv` is `null`

#### Scenario: A path on an imported Altium board
- **GIVEN** `examples/blink_routed/design.py` built with `--target altium --confirm` into a temporary directory, whose track `led_a` runs from `R1` pad `2` through one via to `D1` pad `2`
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_power.py -k altium` runs `fenolite analyze <dir>/blink_routed.PcbDoc --kinds power --path R1-2 D1-2 --copper-thickness 35um --resistivity 20 --json`
- **THEN** the exit code is 0, `result.power` holds one row on the net `LED_A` whose elements are tracks and one via group, its `resistance_uohm` has a `low` above 0, and `evidence.level` is not above the level of the Altium import

#### Scenario: Default kinds unchanged
- **WHEN** `fenolite analyze tests/data/kicad/board/two_layer.kicad_pcb --temp-rise 10 --copper-thickness 35um --json` runs
- **THEN** `result` holds no `power`, and no row of `result.distances` holds `insulation`

#### Scenario: Usage errors
- **WHEN** `fenolite analyze <board> --path J1-1 U1-1 --json` and `fenolite analyze <board> --kinds current --groove-width 1mm --temp-rise 10 --json` run
- **THEN** both exit 2 with `FEN-2001`

### Requirement: Power and insulation codes
`fenolite.analysis.codes.ISSUE_CODES` SHALL also hold these keys, which are codes this capability emits ("Findings and issue codes"), `docs/cli-contract.md` MUST document them under `analyze`, and `src/fenolite/cli/data/explain.toml` MUST hold one table for each (`cli-contract`, "Explain command"). `analysis.input-missing`, `analysis.item-unsupported`, `analysis.fit-out-of-range` and `analysis.requirement-unmatched` keep their meaning for the new kinds.

| code | severity | meaning |
|---|---|---|
| `analysis.path-unmatched` | warning | a power path names a pad the board does not hold, or pads of more than one net |
| `analysis.path-open` | warning | the copper of the net does not join the start pads to the end pads |
| `analysis.path-exceeded` | error | an element that carries the whole current of the path has a capacity below it |
| `analysis.path-undecided` | warning | an element whose share of the current is not computed, or whose section is only a bound, has a capacity below the whole current |
| `analysis.drop-above` | error | the low end of the drop is above `drop_mv` |
| `analysis.drop-undecided` | warning | `drop_mv` lies inside the drop interval, or the drop has no high end |
| `analysis.insulation-below` | error | `insulation.high` is below `insulation_nm` |
| `analysis.insulation-undecided` | warning | `insulation_nm` lies inside the insulation interval |
| `analysis.creepage-over` | info | a clearance or a creepage of the pair crosses copper of a third net |

#### Scenario: Codes in the table
- **WHEN** `uv run pytest tests/unit/analysis/test_findings.py -k power_codes` reads `ISSUE_CODES` and calls `issue("analysis.creepage-over", "x", severity="warning")`
- **THEN** the nine codes are keys with the severities of this table, and the call raises `ValueError`

#### Scenario: Codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** the nine codes appear in `docs/cli-contract.md`

#### Scenario: Codes explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs, and then `uv run fenolite explain analysis.path-exceeded --json`
- **THEN** the test passes with a table for each of the nine codes, and the command exits 0 with a non-empty `result.meaning` and `result.fix`

### Requirement: Power and insulation evidence
`fenolite.analysis.power.EVIDENCE` SHALL be `Evidence(Level.INFERRED, hypotheses=("H-G-AN-NECKFIT", "H-G-AN-NETWORK", "H-G-AN-POUR", "H-G-AN-SECTION"))`, `fenolite.analysis.insulation.EVIDENCE` SHALL be `Evidence(Level.INFERRED, hypotheses=("H-G-AN-INSUL",))`, `fenolite.analysis.grooves.EVIDENCE` SHALL be `Evidence(Level.INFERRED, hypotheses=("H-G-AN-GROOVE",))` and `fenolite.analysis.surface.BRIDGE_EVIDENCE` SHALL be `Evidence(Level.INFERRED, hypotheses=("H-G-AN-OVER",))`; `fenolite.analysis.EVIDENCE` does not change.
- `PowerReport(rows, issues, summary, evidence)` MUST be a frozen dataclass with `findings() -> Findings`, under the rules of "Analysis package and report": pure, integers, no float, sorted, equal inputs giving equal reports. Its evidence MUST be `Evidence.combine` of `fenolite.analysis.EVIDENCE` and `power.EVIDENCE`, and `UNVERIFIED` when it holds an `analysis.input-missing`, `analysis.item-unsupported` or `analysis.path-unmatched` issue.
- A distance report MUST also combine `BRIDGE_EVIDENCE`, `grooves.EVIDENCE` when a groove width was used, and `insulation.EVIDENCE` when insulation was measured.
- These levels MUST stay `INFERRED` until an independent tool computes the same quantity; the grid cut, the finite-difference solution and the KiCad probes MUST NOT raise them.
- Fenolite MUST ship no resistivity, groove width, insulation distance or sheet count. `docs/analyses.md` MUST hold the sections "Power paths", "Insulation between layers", "Grooves" and "Conductors on the path", each with its definitions, its limits and its row of the oracle table, and MUST state the two bounds of a region with S-0681 and S-0682.

#### Scenario: Evidence constants
- **WHEN** `uv run pytest tests/unit/analysis/test_report.py -k power_evidence` reads the four constants
- **THEN** each level is `INFERRED`, and each hypothesis id is registered in `docs/hypotheses.md`

#### Scenario: The page states the model
- **WHEN** `uv run pytest tests/unit/analysis/test_facts_page.py -k power` reads `docs/analyses.md`
- **THEN** it finds the four sections and the sources S-0681 and S-0682, both registered in `docs/evidence/sources.md`, and every resistivity in an example is marked as illustrative

### Requirement: Power and insulation KiCad probes
The KiCad test suite SHALL record the behaviours of KiCad's DRC that this change measured, as probes registered in `tests/kicad/_probes.py` with the majors below. Each bench is written by `write_board`, its rules hold a canary scoped to its own net, and a probe MUST record `equal` when KiCad behaves as the table states, `different` otherwise, and `absent` when the canary did not fire. The outcomes MUST be written to `docs/evidence/board-analyses.md` and to the register rows; they are supporting data and MUST NOT gate this change or raise a level.

| probe | majors | bench | behaviour measured on 2026-10-05 |
|---|---|---|---|
| `analysis-groove-slot` | 10 | c0047's slot bench with `min_groove_width` of 3 mm in the project | the creepage KiCad reports stays 11 mm (`H-K-AN-GROOVE`) |
| `analysis-creepage-split` | 10 | tracks of `A` and `B` 9 mm apart and a 1 mm track of `C` across | creepage rules on `A`–`C` and `C`–`B` report 4 mm each, and the rule on `A`–`B` nothing (`H-K-AN-SPLIT`) |
| `analysis-neck-plain` | 10 | the `dumbbell` pour, refilled | `connection_width` reports 2 mm at a minimum of 2.05 mm and nothing at 1.95 mm (`H-K-AN-NECK`) |
| `analysis-neck-split` | 10 | a neck 4 mm wide with a 0.6 mm via of another net at its centre, refilled | at a minimum of 2.45 mm, `connection_width` reports a width that is neither 1.2 mm nor 2.4 mm (`H-K-AN-NECK`) |
| `insulation-layers` | 9, 10 | 1 mm tracks of `A` on `In1.Cu` and of `B` on `In2.Cu`, one above the other | `clearance` and `physical_clearance` rules of 1 mm report nothing between them (`H-K-AN-LAYERS`) |

#### Scenario: Probes recorded
- **WHEN** `uv run pytest tests/kicad/analysis/test_power_probes.py -rA` runs on the local KiCad 10.0.6, and its `layers` case inside the pinned 9.0.9 image
- **THEN** each probe holds one of `equal`, `different` and `absent`, and the test fails only when a probe is missing

#### Scenario: Benches are hermetic to build
- **WHEN** `uv run pytest tests/unit/analysis/test_power_benches.py` builds the five benches in `tmp_path` without KiCad
- **THEN** each reads back with `read_board`, Fenolite gives 11 mm of creepage on the slot bench and 8 mm on the split bench, and a section of 2 mm on the stored fill of the plain neck
