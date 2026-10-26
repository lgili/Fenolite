## ADDED Requirements

### Requirement: Anchored points in script copper
`resolve_copper` SHALL accept an anchor wherever an intent holds a point, in addition to the elements and fields that "Copper module", "Tracks from intents", "Single vias" and "Stitching vias" read: a path element, the `at` of a via step or of a via intent, the `mid` and the `end` of an arc step, and the `along` points, the `region` points and the `origin` of a stitch. It SHALL replace each anchor by its board point before any other rule reads the intent.
- An anchor is an object with `component`, `number`, `index` and `offset`, read by attribute through the protocol `AnchorLike`, which `copper` exports in addition to the names of "Copper module". An element or a field that has `offset` MUST be read as an anchor, never as a pad end.
- Its point MUST be `part_frame(design, component, number=number, index=index).point(offset)` (`board-frame`, "Anchor points in a part's frame"), on the design given to `resolve_copper`. A build gives the design at its effective placements (`design-dsl`, "Copper intents in a build"), so anchored copper follows a part that was placed in KiCad or by `fenolite place`.
- An anchor is a point and nothing more: it joins no pad and gives no net. A track's net still comes from its pad ends, and a via or a stitch names its net ("Nets of script copper").
- An anchor that cannot be resolved MUST make its intent create nothing, while the next intents are still resolved, with a code of "Copper issue codes" and its severity: `kicad.copper.pad-not-found` when no footprint matches the component, no pad has the number, or the index is beyond the pads of the number; `kicad.copper.bad-intent` when the pads of the number lie at more than one position and no index is given; `kicad.copper.end-unplaced` when `unplaced` names the component, by path or reference, as for a pad end. Each issue MUST name the intent's key and the anchor's component, and its number when it has one.
- The locator and the uuid of an item are those of the element or candidate the anchor stands for ("Copper uuids and ids"), so resolving again after the part moved regenerates the same items ("Script copper is regenerated"). An intent without an anchor MUST resolve as before.

#### Scenario: A via anchored beside a pad
- **GIVEN** the blink built for target 10, whose `U1` sits at 0° on the top, and the via intent `fan9` on `VIN` at `Anchor("U1", "9", None, Point(0, 1_000_000))` with diameter 0.6 mm and drill 0.3 mm
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_anchor.py -k beside` resolves it
- **THEN** the design gains one via at the position of the record of `U1` pad `9` plus (0, 1 mm), on `VIN`, with the uuid `copper_uuid("fan9", "via")`

#### Scenario: Anchored copper follows a turned part
- **GIVEN** the result of "A via anchored beside a pad", in which the footprint of `U1` is then placed again with `place_footprint` at the same point at 90°
- **WHEN** it is resolved again with `fan9` and `issues=found`
- **THEN** the via lies at the record of pad `9` plus (1 mm, 0), which `part_frame(design, "U1", number="9").point(Point(0, 1_000_000))` returns, with the same uuid, and `found` holds one `kicad.copper.regenerated` naming that uuid

#### Scenario: An anchor is not a pad end
- **GIVEN** the blink and a track intent `stub` without net, width 0.3 mm, whose path is `PadEnd("R1", "2", None)` then `Anchor("R1", "2", None, Point(1_000_000, 0))`, and a track intent `loose` whose path holds two anchors and no pad end, without net
- **WHEN** both are resolved with `issues=found`
- **THEN** `stub` creates one track from `R1` pad `2` to the point 1 mm beside it, on `LED_A`, the net of its pad end; `loose` creates nothing, and `found` holds one `kicad.copper.no-net` naming it

#### Scenario: Anchors that cannot be resolved
- **GIVEN** the blink and via intents anchored to `R9`, which has no footprint, to pad `7` of `R1`, and to `D1`
- **WHEN** they are resolved with `unplaced=("D1",)` and `issues=found`
- **THEN** no via is created, and `found` holds two `kicad.copper.pad-not-found`, naming `R9` and `R1` with `7`, and one `kicad.copper.end-unplaced` naming `D1`

#### Scenario: An anchor on a shared number needs an index
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0) for `J1`, its two pads `1` at (−2 mm, 0) and (2 mm, 0), and the via intents `a` at `Anchor("J1", "1", None, Point(0, 0))` and `b` at `Anchor("J1", "1", 1, Point(0, 0))` on `GND`
- **WHEN** they are resolved with `issues=found`
- **THEN** `a` creates nothing and `found` holds one `kicad.copper.bad-intent` naming `a`, `J1` and `1`; `b` creates one via at (2 mm, 0)

## MODIFIED Requirements

### Requirement: Stitching vias
`resolve_copper` SHALL turn each stitch intent (`key`, `net`, `pitch`, `along`, `region`, `origin`, `diameter`, `drill`, `clearance`, `margin`) into through vias of its net, along a polyline, on a grid inside a region, or on a grid inside a pad of its net, keeping clear of other copper.
- Exactly one of `along` (at least two points) and `region` (at least three points forming a simple ring, or one pad reference) MUST be given, `pitch` MUST be positive and `margin` not negative; otherwise `kicad.copper.bad-intent`. Anchors among these points and in `origin` are replaced by their points first ("Anchored points in script copper").
- **Along.** Each segment of the polyline MUST be divided into the fewest equal parts no longer than `pitch` (the smallest `n ≥ 1` with `n²·pitch²` at least the squared length). The candidates MUST be the division points, each vertex once, rounded half to even, numbered `k = 0, 1, …` from the first vertex.
- **Region.** The candidates MUST be the grid points `(i, j)`, for integers `i` and `j`, that lie inside the region at a distance of at least `diameter / 2 + margin` from every edge, decided exactly, in order of `j` then `i`. The grid point `(i, j)` MUST be `origin + (i·pitch, j·pitch)` in the board frame when `origin` is a point, and `part_frame(design, component, number=number, index=index).point(offset + (i·pitch, j·pitch))` when `origin` is an anchor, so that the grid turns with the anchor's part and is mirrored with its bottom side.
- **Pad region.** A `region` that has `component` is a pad reference (`component`, `number`, `index`). It MUST name its pads as an anchor at offset (0, 0) does, with the codes of "Anchored points in script copper": one pad with `index`, else every pad of the number, which MUST lie at one position. Every pad named MUST be on the stitch's net, else `kicad.copper.net-conflict`, and one at least MUST have a copper entry on the outer copper layer of the part's side (`F.Cu` on the top, `B.Cu` on the bottom), else `kicad.copper.layer-mismatch`. When `origin` is a point, the grid is that of an anchor at the pads' position with offset (0, 0); when it is an anchor, the grid is that anchor's. A grid point MUST be a candidate when the disc of radius `r = diameter / 2 + margin` around it lies inside one of those copper entries: for an entry of core `K` and width `w`, when `K` is a filled ring and the point lies inside it, its distance to the edges of `K` MUST be at least `r − w / 2`; otherwise its distance to `K` MUST be at most `w / 2 − r`. Both are decided exactly with integers and `Fraction`.
- **Clearance.** A candidate MUST be dropped when its via disc comes closer than `clearance` to a copper entry or hole of any pad (`board-frame`), the copper entries of the pads of its own pad region excepted, or to a track, arc or via of another net or of no net, or when it touches a via of its own net. Existing items, the vias of earlier intents and the candidates already kept MUST count. Distances MUST be decided exactly with integers and `Fraction`, using c0005's predicates; an arc MUST count as its polyline of `Arc.polygonize(DEFAULT_TOL)` with its width grown by `2·DEFAULT_TOL + 2`. Zones MUST NOT count.
- **Keep-outs and the edge.** A candidate MUST also be dropped when its via disc meets the outline of a `Keepout` with `no_vias` on a copper layer (a through via crosses every copper layer), or comes closer than the edge clearance in force to a ring of `board_outline`: the `min` of the governing board-wide `edge_clearance` rule in `rulemap.rule_order`, else the project's `min_copper_edge_clearance` (`H-K-STITCH-AVOID`). A candidate that lies off the board, outside the board ring or inside a cut-out, MUST be dropped too. Without a closed outline the edge MUST NOT be checked. On a rebuild the rule areas and the outline of the existing board MUST count, because the lens keeps them. These candidates are dropped candidates for the count below. This bullet applies to the candidates of a pad region as to any other: the exception of "Clearance" covers only the copper entries of the region's own pads.
- `clearance` MUST be the intent's, else the clearance of the class of its net, else `kicad.copper.size-missing`.
- The dropped candidates of an intent MUST give one `kicad.copper.stitch-skipped` info with their count, and an intent that keeps no candidate one `kicad.copper.stitch-empty` warning.

#### Scenario: Along a line
- **GIVEN** a design without copper near the line (0, 0)–(10 mm, 0), and a stitch intent on `GND` along it with pitch 3 mm, diameter 0.6 mm, drill 0.3 mm and clearance 0.2 mm
- **WHEN** it is resolved
- **THEN** it creates five vias at x = 0, 2.5, 5, 7.5 and 10 mm, with the locators `via[0]` to `via[4]`

#### Scenario: Region with margin and a pad to avoid
- **GIVEN** `Mini_R_0603` placed at (5 mm, 5 mm), 0°, with both pads on `LED_DRV`, and a stitch intent on `GND` in the square (0, 0)–(10 mm, 10 mm) with pitch 2.5 mm, origin (0, 0), diameter 0.6 mm, drill 0.3 mm, margin 0.2 mm and clearance 0.2 mm
- **WHEN** it is resolved with `issues=found`
- **THEN** it creates the eight vias at (2.5·i, 2.5·j) mm for i and j in 1, 2, 3 except (5 mm, 5 mm), with the locators `via[i,j]`, and `found` holds one `kicad.copper.stitch-skipped` with the count 1

#### Scenario: Own-net via touched
- **GIVEN** the region of the previous scenario without the footprint and with an existing `GND` via of diameter 0.6 mm at (5 mm, 5 mm)
- **WHEN** the stitch is resolved
- **THEN** no new via is placed at (5 mm, 5 mm) and the other eight are created

#### Scenario: Fence across a keep-out
- **GIVEN** the line of "Along a line" crossing a `Keepout` with `no_vias` on both copper layers that covers x from 4 mm to 6 mm
- **WHEN** the stitch is resolved with `issues=found`
- **THEN** no via is created at x = 5 mm, the others are, and `found` holds one `kicad.copper.stitch-skipped` with the count 1

#### Scenario: Fence along the edge
- **GIVEN** a design with a closed outline whose left edge is the line x = 0, a board-wide `edge_clearance` rule of 0.5 mm, and a stitch intent along the line x = 0.4 mm with diameter 0.6 mm
- **WHEN** the stitch is resolved
- **THEN** no via is created, and one `kicad.copper.stitch-empty` warning is given

#### Scenario: Thermal array in a pad
- **GIVEN** `Frame_Anchor` placed for `U1` at (20 mm, 20 mm), 0°, on the top, its 3 mm × 3 mm pad `4` (at (1 mm, 0) in the footprint) on `GND`, and a stitch `ep` on `GND` whose `region` is the pad reference (`U1`, `4`, `None`) and whose `origin` is a point, with pitch 1 mm, diameter 0.6 mm, drill 0.3 mm, margin 0.1 mm and clearance 0.2 mm
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_stitch.py -k pad_region` resolves it with `issues=found`
- **THEN** it creates nine vias at (21 + i, 20 + j) mm for i and j in −1, 0 and 1, with the locators `via[i,j]`, and `found` holds no issue: the pad is no obstacle to its own array

#### Scenario: The grid turns with the part
- **GIVEN** the stitch of "Thermal array in a pad" with `U1` placed at (20 mm, 20 mm), 30°, on the bottom
- **WHEN** it is resolved
- **THEN** the nine vias lie at `part_frame(design, "U1", number="4").point(Point(i·1_000_000, j·1_000_000))` for i and j in −1, 0 and 1, with the same locators `via[i,j]` as at 0°

#### Scenario: A pad region of another net
- **GIVEN** the design of "Thermal array in a pad" with `Mini_Edge_Cases` also placed for `J1` at (40 mm, 20 mm), the stitch `ep` on `VIN`, the net of pad `1` of `U1`, instead of `GND`, and a stitch `j1` on `GND` whose region is pad `1` of `J1`, whose two pads `1` lie at different positions, without an index
- **WHEN** they are resolved with `issues=found`
- **THEN** neither creates a via, and `found` holds one `kicad.copper.net-conflict` naming `ep`, `U1` and `4`, and one `kicad.copper.bad-intent` naming `j1`, `J1` and `1`

#### Scenario: A keep-out across a pad region
- **GIVEN** the design of "Thermal array in a pad" with a `Keepout` with `no_vias` on both copper layers that covers x from 21.6 mm to 22.4 mm over the height of pad `4`
- **WHEN** the stitch `ep` is resolved with `issues=found`
- **THEN** it creates the six vias at (20 mm, 20 + j mm) and (21 mm, 20 + j mm) for j in −1, 0 and 1, and `found` holds one `kicad.copper.stitch-skipped` with the count 3: the pad's own copper is no obstacle, the keep-out still is
