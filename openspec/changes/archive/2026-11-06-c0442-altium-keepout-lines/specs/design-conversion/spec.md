## ADDED Requirements

### Requirement: Keep-out strokes carry their form

A conversion of an Altium board to KiCad SHALL name each rule area made from a plain track, arc or circle
of the Keep-Out layer (one that has no keep-out record in the source document) with that stroke:
`Altium.KeepOut/line/x1/y1/x2/y2/w`, `/arc/x1/y1/xm/ym/x2/y2/w` or `/circle/cx/cy/ex/ey/w`, the second ring
of a circle with `/2` added. Numbers are nanometres in the frame of the area. A rule area from a drawing
with a keep-out record, or from a filled shape, SHALL have no such name.

#### Scenario: Plain strokes name their rule areas

- **GIVEN** a board drawing a line, an arc with a keep-out record, a circle and a filled square on the
  Keep-Out layer, and a footprint drawing a line there
- **WHEN** its drawings are converted into rule areas
- **THEN** the line's area, the circle's two areas and the footprint's area are named with their strokes,
  and the arc's and the square's areas have no name
