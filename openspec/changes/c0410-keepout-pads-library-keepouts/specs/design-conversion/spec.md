## ADDED Requirements

### Requirement: Keep-Out layer rule areas forbid pads
Each rule area that a conversion of an Altium board to KiCad makes of a Keep-Out layer drawing SHALL forbid tracks, vias, pads and poured copper, as KiCad 10.0.6's `pcb import` does for keep-out tracks and regions.

#### Scenario: Restrictions match KiCad's import
- **GIVEN** the authored c0407 document with a ring of keep-out tracks, a keep-out track on Top and a
  polygon cut-out
- **WHEN** it is converted to KiCad and also imported by `kicad-cli pcb import` 10.0.6
- **THEN** the six rule areas hold the same restrictions on both sides: five forbid tracks, vias, pads and
  pours, and the cut-out forbids pours alone
