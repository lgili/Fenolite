## ADDED Requirements

### Requirement: Footprint rule areas round-trip
The KiCad footprint reader SHALL project a footprint `zone` with `keepout` into the footprint's rule areas, and the writer MUST write them back so that a footprint read and written without a change keeps its bytes. Every other footprint zone MUST stay opaque.

#### Scenario: A footprint with a rule area
- **GIVEN** a `.kicad_mod` with one keep-out zone
- **WHEN** it is read and written again
- **THEN** the bytes are unchanged and the definition holds one rule area
