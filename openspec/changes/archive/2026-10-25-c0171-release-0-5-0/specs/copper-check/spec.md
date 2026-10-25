## MODIFIED Requirements

### Requirement: Copper to board edge clearance
`check_copper` SHALL judge every copper shape against every ring of `BoardFrame.board_edges`, each a closed line of width 0 whose arcs are polygonised at `ARC_TOL_NM`. A gap from the copper to the edge line below the edge clearance in force (`ClearanceResolver.edge`: the governing `edge_clearance` rule, else `DesignRules.min_edge_clearance`) MUST give one `copper.edge-clearance` per item and ring, with the rule's severity, naming the item, the ring, the gap and the limit. An arc of a ring MUST be widened by twice its band (`ARC_TOL_NM + 1`), so that no violation is missed, except for a zone fill: KiCad's filler cuts a fill to the edge clearance around the true arc, so a fill MUST be judged against the arc's polygonisation with the limit lowered by the band, the arc narrowed by its band as for a fill along a copper arc ("Clearance findings").

#### Scenario: A pad near a slot
- **GIVEN** the shared fixture with a plated hole part of 2 mm copper whose copper lies 0.47 mm from slot `S1`, and a board minimum of 0.5 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper_edges.py -k slot` runs `check_copper`
- **THEN** it gives one `copper.edge-clearance` error naming the part's pad, `slot S1`, 0.47 mm and 0.5 mm, and none at 0.52 mm

#### Scenario: A rule for one net
- **GIVEN** an `edge_clearance` rule of 1 mm for the net `HV` and a board minimum of 0.5 mm
- **WHEN** a track of `HV` lies 0.8 mm from the board ring and a track of `GND` 0.8 mm from it
- **THEN** only the `HV` track gives `copper.edge-clearance`, whose explanation names the rule as governing

#### Scenario: A fill along a curved edge
- **GIVEN** a board ring whose upper side is an arc, a board minimum of 0.3 mm, a fill and a track on another layer whose edges lie 0.5 µm outside 0.3 mm from the top of the arc
- **WHEN** `uv run pytest tests/unit/checks/test_copper_edges.py -k curved` runs `check_copper`
- **THEN** the track gives `copper.edge-clearance` and the fill does not; with both 2 µm inside 0.3 mm, both do
