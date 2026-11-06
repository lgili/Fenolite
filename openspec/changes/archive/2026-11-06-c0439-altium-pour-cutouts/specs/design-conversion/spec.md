## ADDED Requirements

### Requirement: Copper shapes keep their net

A conversion from KiCad to Altium SHALL give each copper graphic of the board the net its KiCad slot names,
as a build does, so a netted copper shape is written with its net.

#### Scenario: A netted copper polygon

- **GIVEN** the authored board `polygon_cutouts.kicad_pcb`, whose filled polygon on F.Cu is on net `A`
- **WHEN** it is converted to Altium and read back
- **THEN** the polygon is a region on Top with the net `A`, and nothing is unexplained
