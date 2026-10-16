## ADDED Requirements

### Requirement: Copper to board edge clearance
`check_copper` SHALL judge every copper shape against every ring of `BoardFrame.board_edges`, each a closed line of width 0 whose arcs are polygonised at `ARC_TOL_NM`. A gap from the copper to the edge line below the edge clearance in force (`ClearanceResolver.edge`: the governing `edge_clearance` rule, else `DesignRules.min_edge_clearance`) MUST give one `copper.edge-clearance` per item and ring, with the rule's severity, naming the item, the ring, the gap and the limit.

#### Scenario: A pad near a slot
- **GIVEN** the shared fixture with a plated hole part of 2 mm copper whose copper lies 0.47 mm from slot `S1`, and a board minimum of 0.5 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper_edges.py -k slot` runs `check_copper`
- **THEN** it gives one `copper.edge-clearance` error naming the part's pad, `slot S1`, 0.47 mm and 0.5 mm, and none at 0.52 mm

#### Scenario: A rule for one net
- **GIVEN** an `edge_clearance` rule of 1 mm for the net `HV` and a board minimum of 0.5 mm
- **WHEN** a track of `HV` lies 0.8 mm from the board ring and a track of `GND` 0.8 mm from it
- **THEN** only the `HV` track gives `copper.edge-clearance`, whose explanation names the rule as governing

### Requirement: Drilled holes against cut-outs and holes
`check_copper` SHALL give `copper.hole-in-cutout` (error) for a pad drill, via drill or board hole whose area overlaps the area of a cut-out or slot or crosses the board ring, and `copper.hole-overlap` (warning) for two drilled holes whose areas overlap. No clearance value is applied to holes.

#### Scenario: A via drilled into a slot
- **GIVEN** the shared fixture with a via whose drill overlaps slot `S1`
- **WHEN** `uv run pytest tests/unit/checks/test_copper_holes.py` runs `check_copper`
- **THEN** it gives one `copper.hole-in-cutout` naming the via and `slot S1`

#### Scenario: Two drilled slots in an L
- **GIVEN** two hole parts with oval NPTH pads that overlap
- **WHEN** `check_copper` runs
- **THEN** it gives one `copper.hole-overlap` warning naming both pads
