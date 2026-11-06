## ADDED Requirements

### Requirement: Keep-out lines of the Keep-Out layer

The writer SHALL write a rule area whose name carries a stroke (`Altium.KeepOut/<kind>/<numbers>`, change
c0442) as that stroke when the area is intact. Intact means three things:

- its outline is the band of the stroke within 10 nm;
- it forbids tracks, vias, pads and poured copper;
- it does not forbid footprints.

The stroke SHALL be a track or an arc on the Keep-Out layer without the keep-out flag, free for a board's
area and owned by its component for a footprint's, with the stroke's width. The two rings of a circle
SHALL give one full arc, and only when both are intact. Each such area SHALL be counted written under
`keep-out`. A marked area that is not intact SHALL be written as any rule area is.

#### Scenario: A keep-out line comes back as a line

- **GIVEN** a board whose Keep-Out layer holds a line, an arc and a circle without a keep-out record, and a
  footprint holding such a line, converted into rule areas
- **WHEN** the board is written as a PCB document
- **THEN** the Keep-Out layer holds one free track, two free arcs and one track of the component, none with
  the keep-out flag, and no keep-out region for them

#### Scenario: An edited keep-out line stays an area

- **GIVEN** those rule areas, the line's no longer forbidding vias and the arc's moved by 1 mm
- **WHEN** the board is written
- **THEN** both are written as keep-out regions and only the circle comes back as an arc
