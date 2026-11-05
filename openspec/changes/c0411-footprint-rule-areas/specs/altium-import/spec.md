## ADDED Requirements

### Requirement: Keep-outs of a footprint are its rule areas
The Altium import SHALL make rule areas of a footprint, never copper and never a loss, of the keep-outs of a library footprint or of a component: keep-out tracks and arcs as bands, keep-out fills and regions as their outlines, and polygon cut-outs as pour-only areas, with the layers and restrictions of the board import.

#### Scenario: The authored library against `fp upgrade`
- **GIVEN** the authored PcbLib of change c0410
- **WHEN** it is imported by Fenolite and written as a KiCad footprint, and also upgraded by `kicad-cli fp
  upgrade` 10.0.6
- **THEN** both footprints hold the same rule areas: layers, restrictions, boxes within 10 µm and areas
  within 1 %
