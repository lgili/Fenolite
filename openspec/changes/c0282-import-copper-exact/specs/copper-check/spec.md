## MODIFIED Requirements

### Requirement: Copper items and their shapes
`check_copper` SHALL turn each board copper item into one or more `Thick` shapes, each on one copper layer and one net. A track is its `start`–`end` segment at its `width`; an arc is its exact `geometry.Arc(start, mid, end)` core at its unchanged `width`. Both keep their `layer`. Via, pad and fill shapes and unsupported items MUST follow the requirements below; arc polygonisation bands MUST NOT alter copper boundaries.

#### Scenario: Arc copper retains its width
- **GIVEN** an authored circular arc with integer start, mid, end and width
- **WHEN** the copper items are built with different positive `arc_tol` values
- **THEN** its exact circular core, layer, net and width are unchanged

#### Scenario: Via span on four layers
- **GIVEN** a four-layer board whose copper layers are `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu` in table order, a blind via with `layers == ("F.Cu", "In1.Cu")` and a through via
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k span` builds the copper items
- **THEN** the blind via has shapes on `F.Cu` and `In1.Cu` only, and the through via on all four layers

#### Scenario: Outline is not copper
- **GIVEN** a zone on net `GND` on `F.Cu` without fills whose outline covers a track of net `VIN`
- **WHEN** `check_copper` runs
- **THEN** it reports no `copper.short` and no `copper.clearance`

#### Scenario: Pads without a frame
- **GIVEN** a board with two footprints of two pads each
- **WHEN** `check_copper(design, pads=None)` runs
- **THEN** `summary.unsupported` holds `pad: 4`, and the issues hold one `copper.item-unsupported` warning naming 4 pads

#### Scenario: Mounting holes are not unsupported
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0), 0°, on the top of a two-layer board, whose unnumbered `np_thru_hole` pad has no copper entry (`board-frame`, "Pad copper entries")
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k npth` runs `check_copper` with the pads of `KicadBackend().board_pads(design)`
- **THEN** `summary.unsupported` holds no `pad` count, and no `copper.item-unsupported` warning names a pad

### Requirement: Shorts
`check_copper` SHALL report one `copper.short` error for each judged item pair whose supplied copper shapes touch or overlap on a shared layer (`thick_touch`), whatever the clearance in force. Arc cores MUST retain their true width without narrowing. The finding and message MUST retain the short metadata defined below.

#### Scenario: Via touching a track of another net
- **GIVEN** a via of net `GND` with diameter 0.6 mm whose centre is 0.425 mm from the centre line of a 0.25 mm track of net `VIN` on `F.Cu`
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k touch` runs `check_copper`
- **THEN** it reports one `copper.short` error naming `GND`, `VIN` and `F.Cu`, and with the centre 1 nm farther it reports no short

#### Scenario: Short reported without any clearance
- **GIVEN** the same overlap in a design without rules, net classes or board minimum
- **WHEN** `check_copper` runs
- **THEN** it still reports the `copper.short`

### Requirement: Clearance findings
`check_copper` SHALL report one `copper.clearance` per judged, non-shorting item pair whose exact gap on a shared layer is strictly below the governing clearance minus the injected `tolerance`. A nonpositive threshold gives no clearance finding. Arc and zone pairs MUST use this same comparison without widening, narrowing or a second zone comparison. Direct calls with `tolerance=0` remain strict; finding metadata MUST follow the requirement below.

#### Scenario: Strict comparison
- **GIVEN** two 0.25 mm tracks of nets `A` and `B` on `F.Cu` whose edges are 0.2 mm apart, and a class clearance of 0.2 mm on both nets
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k strict` calls `check_copper` with its default zero tolerance
- **THEN** it reports no finding, and with the edges 1 nm closer it reports one `copper.clearance` error with gap 199 999 nm, clearance 200 000 nm and source `class:<class name>`

#### Scenario: Warning rule
- **GIVEN** the same pair at 0.15 mm and a governing rule of 0.2 mm with severity `warning`
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.clearance` warning naming the rule

#### Scenario: Arc band never hides a violation
- **GIVEN** a 0.25 mm arc track and a track of another net whose true edge gap is 5 µm below a 0.2 mm clearance
- **WHEN** `check_copper` runs with different positive `arc_tol` values and zero tolerance
- **THEN** it reports one `copper.clearance` finding with the same exact gap and governing clearance

#### Scenario: A fill cut around an arc is not reported
- **GIVEN** a 0.25 mm arc track of net `B` and a fill of net `A` whose zone has a clearance of 0.5 mm, the fill's edge at a true distance of exactly 0.5 mm from the arc, both nets in a class of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k zone_arc` runs `check_copper` with zero tolerance
- **THEN** it reports no finding; with the fill's edge 5 µm closer it reports one `copper.clearance` with source `zone`; and at 0.19 mm it reports clearance 500 000 nm and source `zone`, as for a straight track

#### Scenario: The widened arc keeps the value without the zone
- **GIVEN** the former widened-arc fixture, now using exact cores, with zone clearance 200 001 nm, class clearance 200 000 nm and true edge gap 200 000 nm
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k zone_arc` runs `check_copper` with zero tolerance
- **THEN** it reports clearance 200 001 nm and source `zone`; without a zone value, the class equality is clean

### Requirement: Rule areas in the copper check
`check_copper` SHALL pass each item's named rule areas per layer to `ClearanceResolver.subject` as `areas` (`H-K-AREA-COND`). An item lies in a named `Keepout` of `design.board.keepouts` on a listed layer when its copper shape touches or overlaps the filled outline (`thick_touch`). Arcs MUST use their true width without narrowing. Fills count; zone outlines do not. Membership of either area carrying a name grants that name.

#### Scenario: Larger clearance inside a high-voltage area
- **GIVEN** a rule area `HV` on `F.Cu` and `B.Cu`, a clearance rule with `selector_a = area HV` and `min = 2 mm`, and two pairs of tracks of different nets 1 mm apart, one inside the area and one outside
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k area` runs `check_copper`
- **THEN** it reports one `copper.clearance` with source `rule:<name>` for the pair inside and nothing for the pair outside

#### Scenario: Neck-down inside a BGA area
- **GIVEN** a board-wide clearance rule of 0.2 mm, then a rule of priority 1 with `selector_a = area BGA` and `min = 0.1 mm`, and two pairs 0.15 mm apart, one inside the area and one outside
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.clearance` for the pair outside and none for the pair inside

#### Scenario: An area on one layer
- **GIVEN** the rule area `HV` on `F.Cu` only, the 2 mm rule, and a pair 1 mm apart on `B.Cu` under the area
- **WHEN** `check_copper` runs
- **THEN** it reports no finding for the pair

#### Scenario: Copper just outside the area
- **GIVEN** the 2 mm rule and a pair whose first track's copper ends 50 µm outside the area, and again with the area reaching 50 µm into that copper
- **WHEN** `check_copper` runs on both
- **THEN** it reports nothing for the first and one `copper.clearance` for the second

#### Scenario: Opaque area outline
- **GIVEN** a board read from a file whose rule area `HV` has an arc in its `pts`
- **WHEN** `check_copper` runs
- **THEN** `summary.unsupported` holds `rule-area: 1`, the issues hold one `copper.item-unsupported` naming it, and no item lies in `HV`

### Requirement: Copper to board edge clearance
`check_copper` SHALL compare every copper shape with every ring of `BoardFrame.board_edges`, each a closed zero-width segment/circular-arc core. Exact gaps strictly below the governing `ClearanceResolver.edge` value MUST give one `copper.edge-clearance` per item and ring. Edge clearance stays strict for every item kind, independently of injected copper tolerance and `arc_tol`; no arc band or fill exception applies. Edge metadata MUST follow the requirement below.

#### Scenario: A rule for one net
- **GIVEN** an `edge_clearance` rule of 1 mm for the net `HV` and a board minimum of 0.5 mm
- **WHEN** a track of `HV` lies 0.8 mm from the board ring and a track of `GND` 0.8 mm from it
- **THEN** only the `HV` track gives `copper.edge-clearance`, whose explanation names the rule as governing

#### Scenario: A fill along a curved edge
- **GIVEN** a board ring whose upper side is an arc, a board minimum of 0.3 mm, a fill and a track on another layer whose edges lie 0.5 µm outside 0.3 mm from the top of the arc
- **WHEN** `uv run pytest tests/unit/checks/test_copper_edges.py -k curved` runs `check_copper`
- **THEN** neither item gives `copper.edge-clearance`; with both 2 µm inside 0.3 mm, both do

#### Scenario: A pad near a slot
- **GIVEN** the shared fixture with a plated hole part of 2 mm copper whose copper lies 0.47 mm from slot `S1`, and a board minimum of 0.5 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper_edges.py -k slot` runs `check_copper`
- **THEN** it gives one `copper.edge-clearance` error naming the part's pad, `slot S1`, 0.47 mm and 0.5 mm, and none at 0.52 mm

## ADDED Requirements

### Requirement: Arc verdicts use true distances
The copper check SHALL decide copper pairs, rule-area membership and edge clearance with exact circular arc cores. Arc polygonisation bands MUST NOT change these verdicts. The governing copper clearance minus the injected tolerance applies to zone pairs too; edge clearance stays strict. `arc_tol` remains accepted and reported for compatibility.

#### Scenario: Clearance within the previous band
- **GIVEN** authored arc pairs at the exact clearance and at 500 nm and 501 nm below it
- **WHEN** the check runs with 500 nm tolerance and different positive arc_tol values
- **THEN** the first two are clean and the third is a finding, independently of arc_tol

### Requirement: Via copper layer span
A via SHALL be a point at `position` with width `diameter`, on every copper layer of its span. The span MUST follow `Board.layers` table order from `layers[0]` through `layers[1]` inclusive. A `through` via, or a via whose `layers` does not name two board copper layers, MUST span all copper layers.

#### Scenario: Layer span metadata follows the board table
- **GIVEN** copper layers `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu` in table order, a blind via with `layers == ("F.Cu", "In1.Cu")` and a through via
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k span` builds the copper items
- **THEN** the blind via has shapes on `F.Cu` and `In1.Cu` only, and the through via on all four layers

### Requirement: Pad copper shape metadata
Each `PadCopper` entry of a pad's `BoardPad` record SHALL yield `Thick(entry.core, entry.width, entry.filled)` on `entry.layer`, with the pad's net. An `exact=False` entry is a superset and MUST be judged as given so no clearance violation is missed. A short it gives MUST carry ` (approximated pad shape)` in its message; such entries MUST count in `summary.approximated`.

#### Scenario: Approximated pad short metadata
- **GIVEN** a pad copper entry with `exact=False` touching another net
- **WHEN** `check_copper` reports the short
- **THEN** its message retains ` (approximated pad shape)` and `summary.approximated` counts the entry

### Requirement: Zone fill copper and exclusions
A `ZoneFill` SHALL be its `polygon` as a filled ring of width 0, on the fill's `layer`, with the zone's net. Zone outlines, rule areas (`Keepout`), graphics, texts, holes and pads of kind `np_thru_hole` MUST NOT be copper.

#### Scenario: Empty zone fill does not create copper
- **GIVEN** a zone on net `GND` on `F.Cu` without fills whose outline covers a track of net `VIN`
- **WHEN** `check_copper` runs
- **THEN** it reports no `copper.short` and no `copper.clearance`

### Requirement: Unsupported copper shape accounting
An item whose shape is refused SHALL be left out, counted by kind in `summary.unsupported`, and reported by one `copper.item-unsupported` warning per kind naming the count. This includes pad entries refused by `Thick` (`GeometryError`), fills refused by `Polygon`, and arc points refused by `geometry.Arc`. Missing pad records and entries MUST follow the unsupported-pad requirement below.

#### Scenario: Refused copper shapes are counted
- **GIVEN** a fill polygon and arc points that their geometry constructors refuse
- **WHEN** `check_copper` runs
- **THEN** both items are left out and counted by kind, with one warning naming each count

### Requirement: Unsupported pad eligibility
A non-`np_thru_hole` pad whose `layers` name a copper layer SHALL count as unsupported when its board-frame record has no copper entry, or when `pads=None`. A pad without a copper layer and every `np_thru_hole` pad MUST be excluded from both copper and unsupported counts. Unsupported pads MUST use the warning and count metadata above.

#### Scenario: Missing frame counts eligible copper pads
- **GIVEN** a board with two footprints of two copper pads each
- **WHEN** `check_copper(design, pads=None)` runs
- **THEN** `summary.unsupported` holds `pad: 4`, and one `copper.item-unsupported` warning names 4 pads

#### Scenario: Nonplated holes stay excluded
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0), 0°, on top of a two-layer board, whose unnumbered `np_thru_hole` pad has no copper entry
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k npth` runs `check_copper` with `KicadBackend().board_pads(design)`
- **THEN** `summary.unsupported` holds no `pad` count, and no unsupported-pad warning is emitted

### Requirement: Short finding metadata
A short `CopperFinding` MUST hold code, severity, layer, a `thick_witness` point, both items as `CopperRef(kind, where, entity_id, net)`, gap 0, and the clearance in force with its source when one exists. Its message MUST name both nets (`<no net>` for an item without a net), the layer and the point in millimetres.

#### Scenario: Short fields survive exact arc checking
- **GIVEN** an authored short involving a circular arc and a governing clearance
- **WHEN** `check_copper` reports it
- **THEN** the finding retains both item references, gap 0, the witness, layer, severity, governing clearance and source, and its message names both nets and the point

### Requirement: Clearance finding metadata
A clearance `CopperFinding` MUST keep code, layer, `thick_witness`, both `CopperRef(kind, where, entity_id, net)` items, gap floored to whole nm (`thick_gap_floor`), original governing clearance and source. Severity MUST be the rule's, or `error` for class, zone or floor. Its message MUST name both nets, layer, point, gap and clearance in millimetres, and source.

#### Scenario: Tolerance preserves the governing metadata
- **GIVEN** a 200 000 nm governing clearance, 500 nm tolerance and exact gap 199 499 nm
- **WHEN** `check_copper` reports the violation
- **THEN** the finding keeps gap 199 499 nm, clearance 200 000 nm, the governing source and severity, both items and the witness

### Requirement: Rule area membership accounting
Rule-area membership SHALL be computed once per item and layer using a spatial index of area boxes, without changing any copper shape or any pair of "Pairs that are judged". `summary.rule_areas` MUST report the number of named rule areas used.

#### Scenario: Membership leaves copper pairs unchanged
- **GIVEN** identical copper with and without a valid named rule area
- **WHEN** the copper items and membership are built
- **THEN** shapes and eligible item pairs are unchanged, membership is layer-specific and the area count is reported

### Requirement: Unsupported rule area accounting
A `Keepout` whose outline is empty or refused by `Polygon` MUST be left out, counted under `summary.unsupported["rule-area"]` and reported by one `copper.item-unsupported` warning naming the count. Its name MUST match no item and its keep-out settings MUST remain unjudged.

#### Scenario: Opaque area settings stay unjudged
- **GIVEN** a board read from a file whose rule area `HV` has an arc in its opaque `pts`
- **WHEN** `check_copper` runs
- **THEN** `summary.unsupported` holds `rule-area: 1`, one warning names it, and no item lies in `HV`

### Requirement: Edge clearance finding metadata
`ClearanceResolver.edge` SHALL use the governing `edge_clearance` rule, else `DesignRules.min_edge_clearance`. An edge-clearance finding MUST retain that severity and name the copper item, ring, gap and limit.

#### Scenario: Slot finding keeps severity and dimensions
- **GIVEN** a plated-hole part with 2 mm copper lying 0.47 mm from slot `S1`, and a board minimum of 0.5 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper_edges.py -k slot` runs `check_copper`
- **THEN** one `copper.edge-clearance` error names the part's pad, `slot S1`, 0.47 mm and 0.5 mm, and none is reported at 0.52 mm
