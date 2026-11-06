## ADDED Requirements

### Requirement: The Altium frame travels through KiCad

A conversion of an Altium design to KiCad SHALL write the source board's origin (`ORIGINX`, `ORIGINY`), in
the frame of the design, and the low corner of the KiCad board's edge as a board property
`Fenolite.Altium.Frame`. A conversion of a KiCad board that carries it back to Altium SHALL write the board
at its KiCad coordinates, Y negated, with the origin at the carried origin moved by the translation of the
edge's corner. When that would put a point of the outline at a negative coordinate, the conversion SHALL
anchor the board at its corner, as before, and report the change under `outline`.

#### Scenario: Row -04 comes back where it was

- **GIVEN** the public row `altium-third-party-pcbdoc-04`, whose origin lies 29.528 mil above its
  outline's low corner
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the written `ORIGINX`, `ORIGINY` and outline vertices equal the source's

#### Scenario: Flow A keeps the frame

- **GIVEN** the public row `altium-third-party-pcbdoc-04` imported with `import --to python` and built
- **WHEN** the built board is converted to Altium
- **THEN** the written origin, outline vertices and component positions equal the source's

#### Scenario: A board moved in KiCad keeps its origin with it

- **GIVEN** a converted board whose items KiCad moved by (10 mm, 5 mm)
- **WHEN** it is converted back to Altium
- **THEN** the written origin is the source's moved by (10 mm, −5 mm) in Altium's frame
