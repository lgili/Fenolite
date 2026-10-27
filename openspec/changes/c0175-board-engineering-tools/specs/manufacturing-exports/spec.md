## ADDED Requirements

### Requirement: Region renders
`fenolite render BOARD --region X1,Y1,X2,Y2 [--nets] [--open] [--grid LENGTH]` SHALL draw one rectangle of the board with its pads, tracks, vias, slots and filled zones, the pads' net names when `--nets` is given, the open connections as straight lines when `--open` is given, and a grid labelled in board coordinates, under the mutation protocol.
- The render MUST be drawn by Fenolite from the model (SVG, and PNG when the `render` extra is present), so it needs no `kicad-cli`; filled zones MUST be drawn as filled, and the reply MUST say which copper state it used (outline, saved fill, simulated).

#### Scenario: Open connections in a region
- **GIVEN** an authored board with two open connections inside the region
- **WHEN** `fenolite render <board> --region 0mm,0mm,20mm,20mm --nets --open -o views --confirm` runs
- **THEN** the SVG holds two lines of the open-connection class and one label per pad in the region
