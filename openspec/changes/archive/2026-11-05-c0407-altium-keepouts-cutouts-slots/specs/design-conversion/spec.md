## ADDED Requirements

### Requirement: Keep-Out layer drawings of a converted Altium board
A conversion of an Altium board to KiCad SHALL make one rule area on every copper layer per drawing of the Keep-Out layer: a line, an arc or a circle drawn with a width the band that width covers, and a filled polygon or rectangle (or a closed outline of width 0) its outline.

- The rule areas are what KiCad 10.0.6's `pcb import` writes for keep-out tracks.
- Strokes MUST NOT be joined into one area over what they enclose.
- A stroke of width 0 covers no area and is reported as a loss.

#### Scenario: A ring of keep-out tracks
- **GIVEN** an authored document with four 1 mm keep-out tracks round a 10 mm square on the Keep-Out layer
- **WHEN** it is converted to KiCad
- **THEN** the board holds four rule areas on `F.Cu` and `B.Cu`, each 1 mm wide and 11 mm long, the inside
  of the square in none of them; the layers, boxes and areas match KiCad's import of the same document

#### Scenario: Open keep-out strokes of a public document
- **GIVEN** the public row `altium-third-party-pcbdoc-01`, with 12 lines and 8 arcs on the Keep-Out layer
- **WHEN** it is converted to KiCad
- **THEN** each is a changed rule area and none is a `graphic` loss
