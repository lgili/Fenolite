## ADDED Requirements

### Requirement: Board cut-outs of a footprint

The writer SHALL write each closed `Edge.Cuts` outline of a footprint (a polygon of three vertices or more,
or a rectangle with an area) as one board cut-out region of its component: `KIND=0`, `ISBOARDCUTOUT=TRUE`,
the Keep-Out layer, no keep-out flag, the component's index. A board cut-out ring of the written outline
that is such an outline within 10 nm SHALL NOT be written again as a free cut-out. A line, an arc or a
circle of a footprint's edge SHALL be counted lost under `footprint-graphic`.

#### Scenario: A cut-out of a component comes back as one

- **GIVEN** a board whose footprint holds a closed `Edge.Cuts` outline, and an outline whose cut-outs hold
  that ring and another one
- **WHEN** the board is written
- **THEN** the document holds one board cut-out region of the component and one free one
