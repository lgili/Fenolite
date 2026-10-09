## Context

- **Where this comes from.** c0047 left, as non-goals, "current flow: parallel paths, pours, planes, thermal reliefs", "resistance, voltage drop", "distances through solid insulation" and "the effect of floating copper between two nets on creepage", and, as open questions, "holes and narrow grooves" and "third-net copper on the path", each pointing to a follow-up. The review of 2026-10-05 lists them as its gaps on power copper and on insulation, and milestone v0.4 (`docs/roadmap.md`, "The complex board, c0100–c0120"; the branch the proposal was written on called the group v0.2c) gives them to this change.
- **The code** (read on 2026-10-05 and again at `origin/dev` `9aba2dff` on 2026-10-07; `src/fenolite/analysis/` and `cli/cmd_analyze.py` have no commit between the two):
  - `analysis/current.py`: one row per track, arc and via; the governing `[[current]]` row of a net judges every item of the net, so a 0.25 mm branch of a 20 A net fails.
  - `analysis/copper.py::net_copper`: thick shapes per net and layer, as `checks.copper` builds them; copper without a net is left out; a fill is one filled ring.
  - `analysis/surface.py`: Dijkstra over boundary vertices and two terminal sets, walls, crossings through edges, pruning by plan distance; copper does not block a leg.
  - `analysis/distance.py`: pair selection (`pairs`, distance rows, `within`), the gap per layer, `clearance` from the outer gaps and the edge interval.
  - `analysis/requirements.py`: schema `fenolite.requirements.v0`, arrays `current`, `distance`, `step`, closed keys; `analysis/codes.py`: ten codes; `cli/cmd_analyze.py`: kinds `current`, `clearance`, `creepage`, a board read through `registry.for_path`, and pads from any backend that satisfies `BoardFrame`.
  - `model.board.ZoneFill(layer, polygon, island)`: one stored ring per fill, no field for holes. `Board.stackup`: entries top to bottom with a thickness; no reader fills it until c0101, which adds `Stackup.depth(name)` and `between(upper, lower)` and keeps one entry per dielectric sheet.
  - The kernel has `thick_gap_floor`, `thick_touch`, `thick_witness`, `convex_hull`, `clip_convex` (two convex polygons), `intersection_point`, `point_in_ring`, `area2`, `assemble_rings`, `floor_sqrt`, `ceil_sqrt`, `Circle.polygonize` and `SpatialIndex`, and no union, difference or offset. Since c0122 (archived on 2026-10-07) `geometry.polygon.keyhole_ring(outer, holes)` builds the ring this change takes apart: holes joined to the ring around them by bridges of zero width walked once in each direction. The Altium import stores a pour with holes that way.
  - Other code that moved on `dev` and is only read here: `checks/copper.py` judges a via of an Altium import that has no pad shape on a layer by its hole there (c0132: `AltiumBackend.design_rules` hands the check such a via in parts; the `Via` of the model keeps one diameter); `FootprintInstance.graphics` exists (c0126, open on `dev`) and may hold copper graphics; `explain` (c0066) needs an entry in `cli/data/explain.toml` for every issue code, and `tests/unit/cli/test_explain_cmd.py` fails without it.
- **Measured on 2026-10-05.** The scripts, command lines and outputs are kept with the review's probes; nothing was measured again at `9aba2dff`, and tasks 1.2 and 11.1 repeat the runs as recorded probes. Each run is `kicad-cli pcb drc --format json --severity-all` on a bench written by `write_board` for target 10 (target 9 for 9.0.9), with a rules file holding a canary.
  1. *Groove width (10.0.6).* c0047's slot bench: two 1 mm tracks whose round ends lie 9 mm apart, a 2 mm × 6 mm cut-out between them. The project file sets `board.design_settings.rules.min_groove_width` to 0, 1, 1.99, 2, 2.01, 3, 10 or 25 mm; a creepage rule of 30 mm on the two nets always fails, so its text gives KiCad's actual value: 11.0000 mm in every run. A 0.5 mm slot with 0, 0.49 and 0.51 mm: 10.7361 mm. The 2 mm slot turned by 45°, with 1.9, 2.1 and 3 mm: 11.8133 mm. A T-shaped cut-out with a 1 mm stem, with 0, 1.1 and 4.1 mm: 10.8167 mm. c0047's notch: 11.0000 mm at every setting. Fenolite's creepage on the same boards is 11, 10.736102, 11.813297, 10.816653 and 11 mm. The project file is read: a `min_copper_edge_clearance` of 15 mm in it gives `copper_edge_clearance`. On 9.0.9 a creepage rule reports nothing on this bench (c0071, `H-K-DRU-KIND-2`).
  2. *Conductors on the path (10.0.6).* The same two tracks without the slot: 9.0000 mm. A 1 mm track of net C across the line between them: no creepage violation for A and B; with rules on A–C and C–B, 4.0000 mm each. A track without a net across the line, 1 mm or 0.5 mm wide: no violation for A and B. A 1 mm via of net C on the line: 9.0000 mm. A track of C beside the line: 9.0000 mm.
  3. *Connection width (10.0.6).* A zone of two 10 mm squares joined by a neck 3 mm long, refilled with `--refill-zones --save-board`, a board-wide `connection_width` rule. Neck 2 mm wide: "actual 2.0000 mm" at a minimum of 2.05 mm, nothing at 1.95 mm. Neck 4 mm: "actual 4.0000 mm" at 4.05 mm. Neck 4 mm with a 0.6 mm via of net Q at its centre, zone clearance 0.5 mm: nothing at 1.15 and 1.25 mm, "actual 1.6968 mm" at 2.35 and 2.45 mm, while each strip beside the hole is 1.2 mm wide and the section across both is 2.4 mm. That pour reads back as one ring of 124 points with one slit pair. A first run with c0047's canary, a 3 mm clearance on every pair, removed the neck's copper around the via: a bench with a zone needs the canary scoped to its own net, as c0071 found.
  4. *Copper on two layers (10.0.6 and 9.0.9).* A four-layer bench: 1 mm tracks of A on In1.Cu and of B on In2.Cu, one above the other; rules `clearance` and `physical_clearance` of 1 mm on A and B. Neither major reports anything between them; the canary fires (9.0.9: "actual 0.7500 mm"). The same tracks both on In1.Cu, 0.5 mm apart: both rules report "actual 0.5000 mm" on 10.0.6. 9.0.9's `pcb drc` has no `--refill-zones`; it printed its usage.
  5. *Fills as stored.* The review's four-layer build of 600 parts, a board generated by a script authored for Fenolite and not committed, filled by 10.0.6: each plane is one ring, In1.Cu of 12 065 points with 300 slit pairs, In2.Cu of 14 182 points with 369; holes have 31 points (median) up to 455. Removing the pairs of opposite edges and chaining the rest takes 0.15 to 0.27 s per plane, and the stored ring's shoelace area equals the outer ring's less the holes'. Corpus (S-0058): 5 readable boards of tag 9.0.9.1 (24 fills, 6 with slits, 238 holes) and 16 of tag 10.0.6 (339 fills, 88 with slits, 6223 holes); the two areas agree on every fill.
  6. *Cost on a plane of that generated board.* Pairs of holes of those planes closer than 2 mm by a box test: 78 and 158. Their exact distance by brute force over edge pairs: 76 to 130 ms per pair; by `thick_gap_floor`, which indexes the edges of a ring of 16 pieces or more: 1.8 to 14.6 ms per pair, 0.3 to 1.1 s per plane. The narrowest web between two holes is 0.439 mm on both planes.
- **No tool computes these quantities from a board.** KiCad's connection width is another width (measurement 3), its creepage stops at other copper (2) and ignores its own groove setting (1), its DRC judges no distance between layers (4), and its calculator is GUI-only (c0047).

## Goals / Non-Goals

**Goals:**
- Analyse the copper a power current crosses: which copper carries it, its narrowest sections and via groups, a bounded resistance and drop.
- Measure the distance through the laminate between copper of two nets on two layers.
- Make creepage and clearance conservative where the review found them optimistic: narrow grooves and conductors on the path.
- Keep c0047's rules: exact geometry, nothing assumed, values from the user only, findings only against requirements, every value labelled.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Changing `[[current]]` rows or `analyze_current`.
- A field solver in the package.

## Decisions

1. **A path, not a net, is the unit of power analysis.** A `[[path]]` row names the pads where the current enters and those where it leaves, the current, the rise the user accepts and the largest drop. Copper on no path between the two sets carries no direct current, which is exact, so a branch to a capacitor is not judged.
   - Rejected: making `[[current]]` skip branches. A net-wide row cannot tell a branch from the main path without knowing where the current enters. It keeps c0047's meaning, "every item carries this", and `docs/analyses.md` sends power nets to paths.
   - Rejected: inferring sources and loads from pin types or part kinds. Fenolite does not guess where current flows.

2. **The copper network joins all touching copper.** Pieces are the net's tracks and arcs, vias, pads (c0028's `BoardPad`) and fill regions (Decision 3); pieces that touch on a layer are joined, because they conduct. Tracks and arcs are one-dimensional and are split at their joints: where the centre line enters or leaves a fill region of the net (the part inside is the region's copper and is dropped), at the point nearest to a pad, a via or another item's end that touches the body, and at crossings. Vias joined to the same pieces form one via group, which is one port of each region it touches. An element on a path from start to end that passes each element once is active; an element that every such path passes is in series.
   - Rejected: c0106's length graph. It joins items only at their ends, by its own decision, and two crossing tracks conduct.
   - Rejected: islands only (connected copper per layer). They give no resistance of a track and no current per element.

3. **Fill regions come from the stored fill; holes from removing slits.** Measurement 5: a stored fill is one ring whose holes join it by slits, pairs of edges between the same two points in opposite directions. Removing those pairs and chaining the rest by exact endpoint equality gives the outer ring and the holes; the stored ring's shoelace area is already the region's area. A ring that does not chain is left out and counted.
   - The same code reads an Altium import. Its pours with holes are rings made by `keyhole_ring` (c0122), whose bridges are slits of two opposite edges, so `unfracture` undoes them. `keyhole_ring` may put an anchor point into an edge, with its `x` rounded half to even, so the rings that come back are the ones given plus those anchor points, and the area test of this decision still decides. `unfracture` lives in `analysis/fills.py`, beside its one user, and a unit test holds the two functions together (scenario "A keyhole ring is undone").
   - Rejected: `unfracture` in `geometry/polygon.py` beside `keyhole_ring`. The kernel would gain a function with one caller; it can move when a second caller appears.
   - Rejected: holes by polygon booleans. The kernel has none, and c0047 kept the optional boolean backends out of the modules this change builds on. If c0099 lands, its `analysis/body_volumes.py` imports `geometry.boolean.select_backend`; that is its own module, and the modules of this change still import no boolean backend.

4. **The narrowest section is a shortest separating curve, found exactly.** The section of a region between ports P and Q is the smallest length, inside the region, of a closed curve that enters neither port's hull and holds one of them inside and the other outside. The whole current through the region from P to Q crosses every such curve, so the smallest one gives the largest mean current density.
   - *Ports.* A port is the copper of one piece or via group inside the region. Its hull is the convex hull of that copper, each shape polygonised at `arc_tol` with its points on or inside the copper, so the hull never exceeds the exact convex hull of the copper.
   - *Search.* A shortest curve is a chain of straight chords through copper and free runs through holes and around the outside; a run never crosses a hull, so a hull that touches a ring splits it into stretches. Chords end on ring edges or at hull vertices; a chord between two edges joins their closest points. The search is Dijkstra on chord ends and hull vertices, on the graph doubled by the parity of crossings with a seam from a point inside one hull to a point inside the other, counted on half-open segments; a curve of odd parity separates the ports. Candidates come from a spatial index of edge boxes and are pruned by the best curve known, which starts at the smaller hull's perimeter. Distances are exact squares, through `thick_gap_floor` where a ring is long (measurement 6).
   - *Interval.* `low` sums the rounded-down chord lengths less the ports' bands; `high` the rounded-up lengths plus the bands.
   - *A hole inside a hull.* When a hole of the region lies inside a port's hull, between that port's shapes, a curve through it may be shorter than the hull allows. The section is then flagged `hull_free == False`: an upper bound of the real one, judged only as undecided.
   - Rejected: KiCad's connection width as the measure or its check. On two parallel strips it reports 1.6968 mm, neither a strip (1.2 mm) nor the section (2.4 mm) (measurement 3); it brackets a plain neck only, which is recorded (Decision 14).
   - Rejected: the smallest local width of the copper. Two parallel strips carry the current together; the section adds them.
   - Rejected: a raster cut in the package. Its error follows the pitch, and the webs of a plane (0.439 mm, measurement 6) need a fine one. It is the tests' oracle.

5. **A section's capacity is c0047's fit at the section, as an estimate.** The section times the copper thickness is the cross-section given to `capacity_ma`, with the layer's factor. The fit was stated for a long isolated conductor; around a short neck the pour spreads heat, so it is expected not to overstate, and nothing measures that (`H-G-AN-NECKFIT`). A section wider than the fit's stated width (400 mils) is `in_range == False`, with c0047's `analysis.fit-out-of-range`.
   - Rejected: a heat model of the pour. c0047 Decision 2 holds: no public source fixes its coefficients.

6. **Judge the whole current only where the topology says it flows.** By Kirchhoff's current law the whole current crosses every element in series, and a region in series with exactly two active ports carries it across the section between them. Those elements fail below the current (`analysis.path-exceeded`). A via group in series fails when the sum of its vias' capacities is below the current, whatever the split, because no split carries more than the sum; above it, the estimate assumes the equal split, and crowding at the group's edge is a limit. Any other element is judged at the whole current, which bounds its share, and is `analysis.path-undecided` below it; so is a section that is not `hull_free`.
   - Rejected: the maximum flow over the elements' capacities. It is the best possible split, but physics, not Fenolite, chooses the split, so it would overstate capacity.
   - Rejected: an error for every element below the whole current. Two layers in parallel would always fail.

7. **Resistance and drop are an interval, from Dirichlet's principle and monotonicity.** The model (`H-G-AN-NETWORK`): pads and joints are ideal contacts; a track or arc part is `ρ·L/(w·t)`, `L` its centre-line length; a via group is its barrels in parallel, `ρ·h/ΣA`, `h` the distance between the middles of its two copper layers by c0101's `Stackup.depth`, `A` c0047's barrel areas.
   - *A region between two ports* (`H-G-AN-POUR`). With `R_s = ρ/t`, `A` the region's area outside the two hulls, `ℓ` the shortest path in the region between the hulls (c0047's surface search on the region as a one-face board) and `w` their section: `R_s·ℓ²/A ≤ R ≤ R_s·A/w²`. Both follow from Dirichlet's principle (S-0682). The trial potential `min(d/ℓ, 1)`, `d` the distance in the region from one hull, has a gradient of at most `1/ℓ` on `A`, so the conductance is at most `A/(R_s·ℓ²)`. Every level line of the true potential separates the ports, so it is at least `w` long, and the co-area formula with the Cauchy–Schwarz inequality makes the conductance at least `w²/(R_s·A)`. These are the extremal-length bounds with the metric 1 for the joining and the separating curves (S-0681). For a strip between two plates both equal `R_s·L/W`.
   - *The path.* Lowering an element's resistance or shorting copper never raises a network's resistance; raising one or removing copper never lowers it (both follow from the minimum of the energy). `low` is the network with every element at its low value and every region of more than two active ports shorted into one node. `high` is the network at the high values when every active region has at most two active ports; otherwise it is the smallest sum of high values over the chains from start to end that pass each region once.
   - *Numbers.* Resistivity in picoohm-metres, lengths in nanometres, resistance in microohms (`1000·ρ·L/(w·t)`), drop in millivolts (`I·R/10⁶`); integers and `Fraction`s throughout, `low` rounded down and `high` up.
   - Rejected: a finite-difference solver in the package. A plane needs 10⁵ to 10⁶ cells at the pitch of its webs, too slow in integer Python, and its error has no bound. It is the tests' oracle.
   - Rejected: regions as ideal nodes only. The drop of a path through a pour would vanish.

8. **Nothing is assumed.** Resistivity, copper thickness, plating, rise and depths come from the user or the stack-up. A missing input leaves the value out and is counted in `analysis.input-missing`, which lowers the reply to `UNVERIFIED`; in the drop, a missing value counts 0 in `low` and removes `high`.
   - Rejected: the resistivity of annealed copper as a default. It is a standard's value at one temperature, and the user's copper and temperature differ.

9. **Insulation is the plan gap combined with the stack-up depth.** For copper of the two nets on layers `U` above `L`, the distance through the laminate is `√(g² + h²)`: `g` the smallest plan gap of their shapes, as `gaps` measure it, and `h` the depth of `L`'s top face less that of `U`'s bottom face (c0101's `Stackup.depth`). The smallest over the pairs of layers is the row's `insulation`, and `sheets` counts the dielectric entries between those two layers (one per sheet in c0101). Measurement 4: no KiCad check measures it.
   - Rejected: the dielectric thickness alone. It ignores an offset in plan view.
   - Rejected: judging the sheet count (proposal, Non-goals).

10. **Grooves: cut-outs by their shortest double normal, pockets by their mouth.** A cut-out is bridged whole when it has a double normal, a chord inside it meeting its boundary at right angles at both ends, shorter than the user's groove width; for a slot that is its width. A pocket of the outer ring is filled when its mouth is shorter; pockets come from the ring's convex-hull tree, deepest first, so a notch inside a wide concavity is found. Bridging can only shorten a creepage. Measurement 1: KiCad applies no groove width to cut-outs, so there is neither a bracket nor a value to write.
    - Rejected: the smallest width between two parallel lines. A bent groove would count where its arms are narrow.
    - Rejected: the largest disc inside the cut-out. It needs a medial axis, which the kernel lacks.
    - Rejected: crossing a groove where the chord through it is short. The shortest path may then bend inside an edge, which c0047's vertex search does not consider.
    - Without a groove width every groove counts, as in c0047, and a pair judged for creepage whose path bends at a groove or crosses its wall raises `analysis.input-missing` naming `groove width`. A pair that is only measured raises nothing, so c0047's scenario "Measured only" holds.

11. **Conductors on the path are crossed at no length, and named.** Copper on an outer layer of a net other than the pair's, and copper without a net (`loose_copper`), become bridges of the surface search and links of the clearance chain: a path reaches a conductor and leaves it anywhere at no length, and a via or a pad with copper on both outer layers joins the two faces. `Measure.over` names the conductors in order. When one belongs to a third net, an info says that the distances to that net are the ones its voltage acts across. Measurement 2: KiCad stops at a crossing track and judges the halves only under rules for them, and it ignores a via.
    - Rejected: ignoring conductors, as c0047 does. A floating conductor shortens the leakage path.
    - Rejected: KiCad's split. It leaves the pair without a value; Fenolite gives the pair the conservative value and names the conductor.

12. **Records, kinds and codes are added beside c0047's.** `PowerReport` is a record of its own, as c0106's `LengthReport` is, so "Analysis package and report" keeps its two row kinds. `Measure.over`, `DistanceRow.insulation` and `DistanceRow.sheets` come last, with defaults. The kinds and codes come through ADDED requirements, as c0106's do; `power` and `insulation` are not in the default set, so a reply without them is unchanged.
    - Rejected: modifying "Analyze command" and "Findings and issue codes". c0106's design notes that both changes add through ADDED requirements so that neither re-bases.

13. **The requirements file stays `fenolite.requirements.v0`, extended.** New array `path`; new keys `insulation_nm` and `groove_nm` on distance rows and `insulation_nm` on steps. Every existing file stays valid.
    - Rejected: a schema `v1`. A new version for additions only, before 1.0.

14. **KiCad's behaviours are recorded probes, supporting only.** Measurements 1 to 4 become probes on 10.0.6, and on 9.0.9 for the layers. If a later KiCad bridges grooves or judges across layers, the probe changes and a bracket becomes possible. They gate nothing and raise no label.
    - Rejected: gating on them, or raising a level from them. c0047 Decision 12's reason holds: two tools with their own, partly undocumented definitions agreeing on a few benches do not verify a board.

15. **Changes in flight** (checked on 2026-10-05 and at `origin/dev` `9aba2dff` on 2026-10-07). The three living texts of "Clearance on a layer", "Creepage on the board surface" and "Requirement tables supplied by the user" are the ones the deltas were made from; no open change on `dev` holds a delta of `board-analyses`, and no other proposal of v0.4 modifies these three. c0101 adds "Stack-up thicknesses in analyze" and the helpers used here; this change lands after it. c0102 modifies "Board boundary", which this change only consumes: c0102's slots are cut-outs that grooves may bridge, and its plated holes without a net are conductors. c0105 and c0106 add requirements only. c0111's thermal vias in a pad become one via group.
    - Rejected: summing the stack-up entries in this change so as not to wait for c0101. No reader or script fills `Board.stackup` before c0101, so insulation would work on no real board; c0101's `Stackup.depth` is the one definition of a depth.

16. **The second backend: `analyze` reads an imported Altium board, with stated limits.** `cmd_analyze` takes the backend that detects the file, and `AltiumBackend` gives board-frame pads (`backends/altium/frame.py`) on `dev`. So `--kinds power` and `--kinds insulation` run on a `.PcbDoc` with no code of their own.
    - Fills: read from `ZoneFill.polygon` as on a KiCad board (Decision 3). `H-K-FILL-SLIT` covers KiCad files only; on an import the ring is Fenolite's own, and the unit test is the proof.
    - Planes: copper of an inner plane layer that the import does not hold as a fill is not in the model, so a path through it is `analysis.path-open`. The reply says so by that warning; nothing is guessed.
    - Vias without a pad shape on a layer (c0132): the network takes its shapes from `net_copper`, which gives a via its diameter on every layer of its span. A join made only by a removed pad would count copper that does not touch. It is a limit, written in `docs/analyses.md`; Altium removes a pad only where nothing touches the via, so it needs a fill that reaches the removed pad but not the hole. A follow-up can take the via in the parts the Altium backend already hands the copper check.
    - Stack-up: insulation and barrel heights need `Stackup.depth` (c0101). Until an import fills it, they give `analysis.input-missing` naming `stack-up`.
    - Evidence: the reply combines the evidence of the import, which the command already passes, so a power report of an imported board is never above the import's level.
    - No requirement names a backend: every ADDED requirement is stated on the model. Scenario "A path on an imported Altium board" proves the command.

17. **Copper graphics are counted, not used.** The copper graphics of a footprint instance (c0126) and board graphics on a copper layer are no pieces of the network and no conductors of a path. `path_network` and `loose_copper` count them, and each analysis reports one `analysis.item-unsupported` warning naming `graphic`, which makes the reply `UNVERIFIED`, as c0126 asks of a consumer that cannot use them.
    - Rejected: shaping them as copper in this change. A graphic has no net, and a net-tie bridge (c0114) would join two nets through one.

18. **Issue codes get their explain entries with the codes.** Task 5.1 adds the nine tables to `src/fenolite/cli/data/explain.toml`, each with `meaning`, `fix` and `see = "analyze"` (the heading of `docs/cli-contract.md`), because the explain test fails the moment `ISSUE_CODES` holds a code without a table.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/analysis/fills.py` (new) | `FillRegion(zone_id, net, layer, where, outer, holes, area2)`; `unfracture(ring) -> tuple[Ring, tuple[Ring, ...]] \| None`; `fill_regions(design) -> tuple[tuple[FillRegion, ...], int]` (the regions and the count left out); `area_outside(region, hulls) -> Fraction` |
| `src/fenolite/analysis/section.py` (new) | `Port(where, shapes, band)`; `port_hull(port, *, arc_tol) -> Ring`; `Section(measure, hull_free)`; `narrowest_section(region, a, b, *, arc_tol=ARC_TOL_NM, limit=None) -> Section` |
| `src/fenolite/analysis/network.py` (new) | `Element(kind, where, entity_ids, layer, length_nm, width, ends, active, series)`; `ViaGroup(vias, layers, pieces)`; `RegionUse(region, ports, active_ports)`; `PathNetwork(net, start, end, elements, regions, groups, issues)`; `path_network(design, *, pads, start, end, arc_tol=ARC_TOL_NM) -> PathNetwork` |
| `src/fenolite/analysis/power.py` (new) | `EVIDENCE`; `Interval(low, high)`; `PathElement(kind, where, layer, series, area_nm2, section, ports, capacity_ma, in_range, resistance_uohm)`; `PathRow(net, start, end, milliamps, temp_rise_mk, elements, resistance_uohm, drop_mv)`; `PowerReport(rows, issues, summary, evidence)` with `findings()`; `region_bounds(region, a, b, *, sheet_uohm, arc_tol=ARC_TOL_NM) -> Interval`; `analyze_power(design, *, pads, paths=(), requirements=None, temp_rise_mk=None, copper_thickness=None, via_plating=None, resistivity_pohm_m=None, arc_tol=ARC_TOL_NM) -> PowerReport` |
| `src/fenolite/analysis/insulation.py` (new) | `EVIDENCE`; `layer_depths(board) -> Mapping[str, tuple[Nm, Nm]] \| None`; `insulation_between(shapes_a, shapes_b, *, depths, stackup) -> tuple[Measure \| None, int \| None]` |
| `src/fenolite/analysis/grooves.py` (new) | `EVIDENCE`; `GrooveResult(boundary, bridged, counted)`; `double_normal2(ring) -> Fraction \| None` (the squared length of the shortest double normal); `Pocket(chain, mouth)`; `pockets(outer) -> tuple[Pocket, ...]`; `bridge_grooves(boundary, width) -> GrooveResult` |
| `src/fenolite/analysis/surface.py` | `surface_distance(a, b, boundary, *, limit=None, bridges=())`; `SurfacePath.over`; `BRIDGE_EVIDENCE` |
| `src/fenolite/analysis/distance.py` | `analyze_distances(…, groove=None, insulation=False)`; the clearance chain over conductors; `summary.grooves` |
| `src/fenolite/analysis/report.py` | `Measure.over`; `DistanceRow.insulation`, `DistanceRow.sheets` |
| `src/fenolite/analysis/copper.py` | `loose_copper(design, *, pads, arc_tol=ARC_TOL_NM) -> tuple[CopperShape, ...]` |
| `src/fenolite/analysis/requirements.py` | `PathReq(start, end, milliamps, temp_rise_mk, drop_mv)`; `Requirements.paths`; `DistanceReq.insulation_nm`, `.groove_nm`; `Step.insulation_nm`; `Requirements.insulation_for(a, b, circuit) -> Nm \| None` and `groove_for(a, b, circuit) -> Nm \| None`, beside `distance_for`, whose triple is unchanged |
| `src/fenolite/analysis/codes.py` | the nine codes of "Power and insulation codes" |
| `src/fenolite/cli/data/explain.toml` | one table per new code |
| `src/fenolite/analysis/__init__.py` | re-exports `analyze_power`, `PowerReport` |
| `src/fenolite/analysis/PROVENANCE.md` | rows for S-0681 and S-0682, facts only |
| `src/fenolite/cli/cmd_analyze.py` | kinds `power` and `insulation`; `--path`, `--resistivity`, `--groove-width`; `result.power`; additions to `inputs` |
| `docs/analyses.md` | sections "Power paths", "Insulation between layers", "Grooves", "Conductors on the path": definitions, the two bounds with S-0681 and S-0682, the limits, the oracle rows; the requirements file |
| `docs/cli-contract.md` | `analyze`: the kinds, options, result keys and nine codes |
| `docs/evidence/board-analyses.md` | the probe outcomes, the fill census, timings |
| `tests/_power.py` (new) | authored regions and paths (dumbbell, split neck, spokes, strip, two strips, branch, via array), `grid_cut(…)`, `fdm_resistance(…)`; test code, floats allowed |
| `tests/data/analysis/strip_10.kicad_pcb` (new, authored, in `tests/data/MANIFEST.toml`) | the strip path as a KiCad board for the command test |
| `tests/unit/analysis/test_fills.py`, `test_section.py`, `test_network.py`, `test_power.py`, `test_insulation.py`, `test_grooves.py`, `test_surface_bridges.py`, `test_power_benches.py`; `tests/unit/cli/test_analyze_power.py` (new) | hermetic tests |
| `tests/kicad/analysis/_powerbench.py`, `test_power_probes.py` (new); `tests/kicad/_probes.py` (rows); `tests/corpus/test_fill_slits.py` (new) | recorded probes; the census |

Layering: every module of `analysis` imports the standard library, `core`, `model`, `geometry` and `backends.base` only; `cmd_analyze` imports `analysis` and `backends`. Every edge is in "Allowed import edges", unchanged.

## Sources registered by this change

| id | source | licence | used for |
|---|---|---|---|
| S-0681 | https://en.wikipedia.org/wiki/Extremal_length | CC BY-SA 4.0 (the page footer; facts only) | read as rendered on 2026-10-08: the extremal length of a family of curves (metrics, length, area); one metric gives the lower bound, squared length over area; the metric 1 on a rectangle; the reciprocal values of the two families of a rectangle and of an annulus; the effective resistance of a resistor network on a graph as the edge extremal length of its paths. No upper bound of the form area over a squared length, and nothing about a conductor that is not a graph |
| S-0682 | https://en.wikipedia.org/wiki/Dirichlet%27s_principle | CC BY-SA 4.0 (the page footer; facts only) | read as rendered on 2026-10-08: the solution of the boundary problem is the minimiser of the Dirichlet energy among the functions with its boundary values. Nothing about resistance or conductance |

Both pages were read on 2026-10-05 by the proposal and again on 2026-10-08, as rendered by the fetch tool (a summary, not the text), when the rows were corrected. As read, neither page states `R_s·ℓ²/A ≤ R ≤ R_s·A/w²`: the two bounds of Decision 7 are Fenolite's own derivation from the two facts above, carried by `H-G-AN-POUR` (`INFERRED`, settled against a finite-difference solution). The proposal first reserved S-0450 and S-0451; `dev` gave those to KiCad's ERC schemas (c0062), so the two rows were renumbered on 2026-10-07 into the block S-0680–S-0699 handed to this group (`dev` ends at S-0601; c0113 holds S-0680). Cited without a change of level: S-0269 and S-0270 (the fit and the barrel), S-0020, S-0022 and S-0029 (`kicad-cli` 10.0.6, `pcb drc`, the 9.0.9 image), S-0058 (the corpus demo boards), S-0272 (custom rules). No standard was read.

## Hypotheses registered by this change

| id | backend | statement | settling test | criterion |
|---|---|---|---|---|
| H-G-AN-SECTION | general | The search of "Narrowest copper section" finds, within its interval, the smallest length inside a region of a closed curve that separates two port hulls | `tests/unit/analysis/test_section.py` | hand-computed cases equal; never above the grid cut plus one cell, never below the grid cut divided by √2 less one cell |
| H-G-AN-NECKFIT | general | c0047's fit at a section's cross-section does not overstate the current a pour carries across that section at the given rise | `tests/unit/analysis/test_power.py -k neck` | no oracle; the test checks the arithmetic of "A neck in series"; stays `INFERRED` |
| H-G-AN-POUR | general | The direct-current resistance of a region between two ideal port hulls lies between `R_s·ℓ²/A` and `R_s·A/w²` (S-0681, S-0682) | `tests/unit/analysis/test_power.py -k fdm` | a finite-difference solution of authored regions inside the interval widened by 2 % |
| H-G-AN-NETWORK | general | The network of Decision 7 (ideal contacts, uniform tracks and barrels, region bounds) gives an interval that holds the direct-current resistance of a path | `tests/unit/analysis/test_power.py -k fdm` | a finite-difference solution of the path of `two_strips`, on both layers, inside the interval widened by 2 % |
| H-G-AN-INSUL | general | `√(g² + h²)` with the stack-up depth is the shortest distance through the laminate between copper on two layers, copper on layers between them left out | `tests/unit/analysis/test_insulation.py` | hand-computed cases equal |
| H-G-AN-GROOVE | general | Bridging cut-outs by their shortest double normal and pockets by their mouth never lengthens a creepage, and bridges every straight slot narrower than the width | `tests/unit/analysis/test_grooves.py` | hand-computed cases; on generated boards the bridged creepage is never above the unbridged one |
| H-G-AN-OVER | general | Crossing conductors at no length gives the shortest surface path that may pass over them, within c0047's band | `tests/unit/analysis/test_surface_bridges.py` | hand-computed cases; a grid search whose conductor cells cost nothing |
| H-K-AN-GROOVE | kicad | On `kicad-cli` 10.0.6, `rules.min_groove_width` above a cut-out's width leaves KiCad's creepage around the cut-out unchanged (S-0020, S-0272) | `tests/kicad/analysis/test_power_probes.py -k groove` | probe `analysis-groove-slot` = `equal` |
| H-K-AN-SPLIT | kicad | On 10.0.6, a track of a third net across the path stops KiCad's creepage between two nets: rules on each net and the third report their halves, none on the pair; a via on the path is ignored (S-0020, S-0272) | `tests/kicad/analysis/test_power_probes.py -k split` | probe `analysis-creepage-split` = `equal` |
| H-K-AN-NECK | kicad | On 10.0.6, a `connection_width` rule reports the width of a plain neck of a refilled pour, and on two parallel strips a width that is neither a strip's nor the section (S-0020) | `tests/kicad/analysis/test_power_probes.py -k neck` | probes `analysis-neck-plain` and `analysis-neck-split` = `equal`; the 9.0.9 run of task 1.2 recorded |
| H-K-AN-LAYERS | kicad | On 9.0.9 and 10.0.6, `clearance` and `physical_clearance` rules report nothing between copper of two nets on two layers one above the other (S-0020, S-0029) | `tests/kicad/analysis/test_power_probes.py -k layers` | probe `insulation-layers` = `equal` on both majors, the canary firing |
| H-K-FILL-SLIT | kicad | A stored `filled_polygon` is one ring whose holes join it by slits of two opposite edges, and its shoelace area is the outer ring's less the holes' (S-0058) | `tests/corpus/test_fill_slits.py` | every fill of the cached demo boards of tags 9.0.9.1 and 10.0.6 |

- No row `H-G-AN-SECTION`, `-NECKFIT`, `-POUR`, `-NETWORK`, `-INSUL`, `-GROOVE`, `-OVER`, `H-K-AN-GROOVE`, `-SPLIT`, `-NECK`, `-LAYERS` or `H-K-FILL-SLIT` exists in `docs/hypotheses.md` or in an open change on `dev` (checked at `9aba2dff`; `dev` holds `H-G-AN-EDGE`, `-FIT`, `-GAP`, `-PATH` and `-VIA`). `H-G-AN-PATH` is c0047's surface path; a "power path" of this change is another thing, and `docs/analyses.md` says so where both appear.
- All rows start `INFERRED`, with the measurements of Context as their first record. Task 12.2 raises the `H-K-` rows to `KICAD-VERIFIED` with their scope once their probes have run, and `H-K-FILL-SLIT` to `CORPUS-VERIFIED`; the `H-G-` rows stay `INFERRED`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof | oracle that could exist |
|---|---|---|---|
| fill regions | mechanical; the slits `CORPUS-VERIFIED` | `test_fills.py`; `tests/corpus/test_fill_slits.py` | — |
| narrowest sections | `INFERRED` (`H-G-AN-SECTION`) | `test_section.py`: hand-computed cases, grid cut | KiCad's connection width, on plain necks only (recorded) |
| network, active part, series | mechanical | `test_network.py` | — |
| capacity of elements and sections | `INFERRED` (`H-G-AN-FIT`, `H-G-AN-VIA`, `H-G-AN-NECKFIT`) | `test_power.py` | KiCad's calculator, GUI only |
| resistance and drop | `INFERRED` (`H-G-AN-POUR`, `H-G-AN-NETWORK`) | `test_power.py -k fdm` | a field solver run as a subprocess; none chosen |
| insulation | `INFERRED` (`H-G-AN-INSUL`) | `test_insulation.py` | none; KiCad judges none (`H-K-AN-LAYERS`) |
| grooves | `INFERRED` (`H-G-AN-GROOVE`) | `test_grooves.py` | KiCad's groove setting, if a later version applies it (`H-K-AN-GROOVE`) |
| conductors on the path | `INFERRED` (`H-G-AN-OVER`) | `test_surface_bridges.py`, `test_distance.py` | none; KiCad splits the path (`H-K-AN-SPLIT`) |
| requirements, codes, command | mechanical | `test_requirements.py`, `test_findings.py`, `test_analyze_power.py` | — |
| KiCad behaviours | recorded on 10.0.6, the layers also on 9.0.9; never gating | `test_power_probes.py` | — |

`fenolite.analysis.EVIDENCE` keeps its level and hypotheses. A power report is `UNVERIFIED` when it holds `analysis.input-missing`, `analysis.item-unsupported` or `analysis.path-unmatched`.

## Risks / Trade-offs

- [A section search on a plane with hundreds of holes is slow] → candidates from an edge index, pruned by the best curve, which starts at a hull's perimeter (about 2 mm for a via); measurement 6 puts every chord of a plane at about 1 s. Task 3.2 records the time of a section on the largest fill of the cached demo boards. Above c0047's 60 s for one pair, the search stops at its limit and the section is undecided.
- [The upper bound `R_s·A/w²` is loose on a pour with a neck] → the interval is reported as it is, so the drop is often undecided; the finite-difference test records how wide it is on the authored dumbbell.
- [A user reads an estimate as a verdict] → every capacity and drop is `INFERRED`; `docs/analyses.md` and the command help say what the model leaves out.
- [Crossing a third net's copper makes a pair's creepage shorter than its owner expects] → the row names the conductor, and the info names the pairs to select; this is the conservative value.
- [Many conductors near a pair on a dense board] → a conductor whose plan distances to the two nets sum to more than the best path cannot help and is never added; timings are recorded.
- [c0101 slips] → insulation and barrel resistance wait for it; sections, capacities and grooves do not need it.
- [A later KiCad changes a recorded behaviour] → its probe changes, and nothing gates on it.
- [Two copper builders, `net_copper` and the network] → the network takes its shapes from `net_copper` and `loose_copper`; a test compares them.

## Migration Plan

- The default kinds stay. Their replies change in two ways: creepage and clearance can be shorter where copper of another net or of none lies on the path, the measure naming it in `over`; a pair judged for creepage whose path passes a groove without a groove width gets `analysis.input-missing` and `UNVERIFIED`. `CHANGELOG.md` says both.
- Requirements files: additive; every existing file loads unchanged. The other direction does not hold: a file with a `[[path]]` row, `insulation_nm` or `groove_nm` is refused by 0.2.x and 0.3.0, whose loaders accept a closed set of keys. `docs/analyses.md` says so beside the new keys.
- No model key, no schema file and no `.fenolite/` document changes, so every pinned output of 0.2.0 keeps its bytes.
- Rollback: remove the new modules and their tests, restore the three modified texts and their code, remove the probe and register rows.

## Budget (9.75 days)

| part | days |
|---|---|
| registers, sources, the 9.0.9 neck probe, docs skeleton | 0.5 |
| fill regions and the corpus census | 0.5 |
| narrowest section: chords, hulls, parity, interval | 0.75 |
| narrowest section: ports inside holes, hull flag, limit, grid cut | 0.75 |
| path network: pieces, joins, splits, via groups, ports | 0.75 |
| path network: active part and series | 0.5 |
| path current: elements, capacities, judging, `[[path]]` rows | 0.5 |
| resistance and drop: element values, region bounds, network interval, judging | 0.75 |
| finite-difference oracle and timings | 0.25 |
| insulation between layers | 0.75 |
| grooves: cut-outs | 0.5 |
| grooves: pockets, width per pair, missing width | 0.25 |
| conductors: loose copper, bridges in the surface search, `over`, the info | 0.75 |
| conductors: clearance chains, both faces, grid check | 0.5 |
| command, codes, contract docs | 0.5 |
| recorded KiCad probes | 0.5 |
| `docs/analyses.md` and closing | 0.75 |
| **total** | **9.75** |

Cut order: (1) the neck probes (−0.25; `H-K-AN-NECK` is not registered); (2) clearance chains over conductors (−0.25; the clearance stays c0047's, a limit); (3) pockets (−0.25; notches count, a limit); (4) the drop's upper end (−0.5; `high` is always `None`, so a drop requirement is never met, only failed or undecided); (5) the drop (−0.5; with the finite-difference oracle). After the five cuts: 8 days. Not optional: fill regions, sections, the path network and its judging, via groups, insulation, bridging of cut-outs, conductors on the creepage path, the `[[path]]` rows and the command.

## Open Questions

- **Is a bounded drop inside the plan's N9?** Closed by the maintainer on 2026-10-07: the voltage drop fits the plan. It is a measure against a limit of the user, with no field solver; non-goal N9 stands. Cuts 4 and 5 stay in the cut order for budget only.
- **Crowding in via groups.** Default: the equal split above the sum test, documented. A user margin would be a new key; not added.
- **Copper on a layer between two insulated layers.** Default: ignored and listed. A follow-up could report the copper crossed, as `over` does on the surface.
- **A sheet-count requirement.** Default: data only (`sheets`).
- **Groove width per row or per board.** Default: both, the largest governing a pair.
- **`[[current]]` rows on power nets.** Default: unchanged; `docs/analyses.md` sends power nets to paths. A hint in `analysis.current-exceeded` would modify c0047's text.
- **Hulls of concave pads.** Default: the convex hull, so a cut may not dent into a custom pad's notch; listed as a limit.
- **Writing a groove width to KiCad.** Default: no. If `analysis-groove-slot` changes on a later KiCad, a follow-up can write `rules.min_groove_width` and bracket it.
- **Vias of an import without a pad on a layer.** Default: joined by the disc `net_copper` gives them (Decision 16), a stated limit. A follow-up takes the parts c0132 gives the copper check if a real board shows a false join.
