## ADDED Requirements

### Requirement: Keep-outs of a library footprint give no copper
The Altium library import SHALL make no graphic of a keep-out track, arc, fill or region on a copper layer of a library footprint, nor of a polygon cut-out on a copper, the Keep-Out or the Multi-Layer layer. Each MUST be counted under the census category `footprint-keepouts`, and the hint of `altium.import.unmapped` MUST name change c0411, which gives footprint definitions rule areas.

#### Scenario: An authored library with keep-outs
- **GIVEN** a PcbLib footprint with a keep-out track on Top, a polygon cut-out on Top, a keep-out region on
  Bottom, and a flagged and a plain track on the Keep-Out layer
- **WHEN** it is imported
- **THEN** the footprint holds no copper graphic, its two Keep-Out layer tracks stay `Altium.KeepOut`
  graphics, and `altium.import.unmapped` names `footprint-keepouts 3` with a hint that names c0411
