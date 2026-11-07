## ADDED Requirements

### Requirement: A carried origin keeps the document frame

Given a document origin (`write_design(frame_origin=…)`), the Altium writer SHALL write a board that was
not read from a PCB document in the document frame, each point at `(x, −y)`, and SHALL write `ORIGINX` and
`ORIGINY` at that origin. When a point of the outline would lie at a negative coordinate, it SHALL anchor
the board at its corner as without an origin and record a change of kind `outline`.

#### Scenario: An origin above the corner

- **GIVEN** a board read from KiCad whose outline's low corner is at (25.4 mm, −55.4 mm) in the frame of the
  design, and the frame origin (25.4 mm, 26.162 mm) in the document's
- **WHEN** it is written
- **THEN** the outline's lowest vertex is at 1000 mil, 1000 mil, `ORIGINX` is 1000 mil and `ORIGINY`
  1030 mil

#### Scenario: A board below KiCad's X axis is anchored

- **GIVEN** a board read from KiCad whose outline lies at positive KiCad Y, and a frame origin
- **WHEN** it is written
- **THEN** it is anchored at its corner, `ORIGINX` and `ORIGINY` are 1000 mil, and one `outline` change
  holds the reason `FRAME_ANCHORED`
