## ADDED Requirements

### Requirement: Footprint overlay primitives are written as the source holds them
An Altium build of a design read from an Altium PCB document SHALL write, per component, the top and bottom
overlay tracks and arcs that the source component holds: the same number, each with its ends (a track) or
its centre, radius and angles (an arc) within one file unit of the source's, on the same layer (change
c0494).
- No overlay track or arc MUST be added to a component, on either side, at any rotation.
- A difference MUST be reported per component by the round-trip comparison of
  `backends.altium.roundtrip`.

#### Scenario: An open outline on both sides
- **GIVEN** an authored PCB document with a footprint whose overlay outline is open at one corner and ends
  in a 90° arc, placed at 0°, 90°, 180° and 270° on the top and the bottom side
- **WHEN** it is imported and built back to a PCB document
- **THEN** each component of the written document holds the source's overlay tracks and arcs, and no other

#### Scenario: Public rows
- **GIVEN** the public PCB documents that the build round-trip tests already read
- **WHEN** each is imported and built back
- **THEN** the overlay comparison reports no added or missing primitive for any component
