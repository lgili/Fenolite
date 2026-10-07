## ADDED Requirements

### Requirement: Open connections of a net
`fenolite.analysis.connectivity.connectivity(design, *, pads, nets=None) -> ConnectivityReport` SHALL find, for each net of the board, its copper islands and the open connections that would join them, from the shapes of `net_copper` ("Copper of a net as thick shapes") and the `BoardPad` records `pads` (`None` when the caller has none, as for `net_copper`). It MUST be pure and use integers only, as every analysis ("Analysis package and report").
- **Islands.** Two shapes of a net MUST join when they are on the same copper layer and `thick_touch` is true. The joining MUST be done by `geometry.touch_groups` (`geometry-kernel`, "Groups of touching thick shapes"), the one union of touching copper of the package, which `checks.equivalence.routing.pieces` (`design-equivalence`, "Routed connectivity of a net") uses too. The two callers differ only in the shapes they pass: this query takes the pad copper of `BoardPad` and keeps the polygons of a fill apart from an island without a pad; `pieces` shapes a pad from the model alone, so that two backends compare. All shapes of one via, and all shapes of one pad, MUST join across their layers. A fill polygon joins only what it touches, never another island of its zone. An island counts when it holds a pad, a track, an arc or a via; the islands that hold only fills MUST be counted in `fill_islands` and take no part in the connections.
- **Anchors.** The anchors of an island are the `position` of its pads, the `start` and `end` of its tracks and arcs, and the `position` of its vias. Fills have none.
- **Connections.** For a net with `n` counted islands, `open` MUST hold `n − 1` connections, `()` when `n ≤ 1`: the minimum spanning tree over the islands in which the edge between two islands joins their nearest anchors by exact squared distance. Ties MUST go to the smaller pair of `where` texts, then to the smaller pair of positions. Each `OpenConnection` MUST hold `a` and `b`, two `LinkEnd(kind, where, position, layers)` records (`kind` is `pad`, `track`, `arc` or `via`; `where` is `REF-PIN` for a pad and `provenance.locator` otherwise, as `net_copper` names items), and `length`, the distance between them in nanometres rounded to the nearest integer with `math.isqrt`.
- **Report.** `ConnectivityReport.nets` MUST hold one `NetConnectivity(name, pads, islands, fill_islands, open, unsupported)` per net that has a counted island, sorted by name; with `nets` given, only the nets of those names. The report MUST NOT depend on the order of the items of the board.
- **Unsupported items.** An item that cannot be shaped MUST be counted in `unsupported` of its net, the report MUST hold one `analysis.item-unsupported` warning per kind with the count, and its evidence MUST then be `UNVERIFIED`.
- **Evidence.** `fenolite.analysis.connectivity.EVIDENCE` MUST name `H-K-CONN-PARITY` and carry the level of its register row; `fenolite.analysis.EVIDENCE` is not changed.
- `docs/analyses.md` MUST describe the query, its rules, and where it differs from KiCad: a copper drawing that holds a net is not copper of that net in the model, and KiCad may name other items for a connection than these anchors.

#### Scenario: A stub and the far pad
- **GIVEN** a design whose net `N` joins pads `RA-1` and `RB-1` 8.4 mm apart, and a 3 mm track on `F.Cu` from the centre of `RA-1` towards `RB-1`
- **WHEN** `uv run pytest tests/unit/analysis/test_connectivity.py -k stub` computes the report
- **THEN** `N` has 2 islands and one connection whose ends are the free end of the track (`kind` `track`) and `RB-1` (`kind` `pad`), with `length` 5 400 000

#### Scenario: Copper that touches joins
- **GIVEN** nets whose two pads are joined only by two tracks that cross at 70 % of their length, by a track that crosses the far pad and ends 2 mm beyond it, by two parallel tracks that overlap by 0.05 mm, or by a track whose end cap alone overlaps another track
- **WHEN** the report is computed
- **THEN** each net has 1 island and no open connection

#### Scenario: Islands without a pad
- **GIVEN** a net whose two pads are joined, plus a floating track of the net; and a net whose two pads are apart, with a stored fill between them that touches neither
- **WHEN** the report is computed
- **THEN** the first net has 2 islands and one connection to the floating track; the second has 2 islands, `fill_islands` 1, and one connection from pad to pad

#### Scenario: A missing via
- **GIVEN** a net routed from pad `RA-1` on `F.Cu` to a via, on `B.Cu` to a point `P`, and on `F.Cu` from `P` to pad `RB-1`, with no via at `P`
- **WHEN** the report is computed
- **THEN** the net has one connection whose ends are the `B.Cu` track and the `F.Cu` track, both at `P`, with `length` 0

#### Scenario: Order does not matter
- **GIVEN** the bench of the previous scenarios, and a copy whose tracks, arcs, vias and footprints are in reverse order
- **WHEN** `uv run pytest tests/unit/analysis/test_connectivity.py -k order` computes both reports
- **THEN** the two reports are equal

#### Scenario: Matches brute force
- **WHEN** `uv run pytest tests/unit/analysis/test_connectivity.py -k brute` compares, on generated boards, the islands with those of a test-only union over every pair of shapes of a net
- **THEN** the islands and the number of connections are equal for every net

#### Scenario: Islands agree with the equivalence check
- **GIVEN** the bench of the previous scenarios without its fills, whose pads are rectangles, discs and stadiums, for which the pad copper of the frame and the shape from the model are the same
- **WHEN** `uv run pytest tests/unit/analysis/test_connectivity.py -k agree` computes the report and `checks.equivalence.routing.pieces` for the same design
- **THEN** for every net the pads of each counted island equal the pads of one piece, and the numbers of islands and of pieces are equal

#### Scenario: A pin on no net
- **GIVEN** a built board whose pad `R1-1` is alone on the net `unconnected-(R1-Pad1)`, the net KiCad gives a pin on no net
- **WHEN** the report is computed
- **THEN** that net has 1 island and no open connection, as every net of one pad

#### Scenario: Unsupported pads lower the level
- **GIVEN** a board whose footprints have pads
- **WHEN** the report is computed with `pads=None`
- **THEN** it holds one `analysis.item-unsupported` warning naming pads, and its evidence level is `UNVERIFIED`
