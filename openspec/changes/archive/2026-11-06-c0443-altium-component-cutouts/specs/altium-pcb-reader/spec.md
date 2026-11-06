## ADDED Requirements

### Requirement: Board cut-outs of a component

The import SHALL read a region with `KIND=0` and `ISBOARDCUTOUT=TRUE` that a component owns as a closed
`Edge.Cuts` polygon of width 0 in that component's footprint, in its pad frame, and not as a drawing of the
Keep-Out layer nor as a rule area. The design's board edges (`board_edges`) SHALL include each such outline,
placed on the board.

#### Scenario: A cut-out of a component is read as an edge of its footprint

- **GIVEN** a PCB document whose component owns a board cut-out region
- **WHEN** it is read
- **THEN** the footprint holds one `Edge.Cuts` polygon of the region's ring and no rule area, and the
  board edges hold the ring beside the board's
