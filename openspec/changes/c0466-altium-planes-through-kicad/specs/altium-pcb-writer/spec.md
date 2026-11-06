## ADDED Requirements

### Requirement: Carried plane splits, names and pull-backs

Given split polygons for an internal plane (`PcbDocSpec.plane_splits`), the writer SHALL write one Split
Plane polygon per split, on the split's net, instead of the board outline on the plane's net. It SHALL
accept `(Multiple Nets)` as the net of such a plane. It SHALL write each plane's pull-back
(`StackSpec.pullbacks`, else 20 mil), and it SHALL name a plane after `PcbDocSpec.plane_names` where the
spec gives a name. Without them, the document SHALL be as before.

#### Scenario: A (Multiple Nets) plane with two splits

- **GIVEN** a four-layer spec whose first plane is `(Multiple Nets)` with splits on `GND` and `VCC`, named
  `Ground Plane`, with a pull-back of 30 mil
- **WHEN** the document is written
- **THEN** `PLANE1NETNAME` is `(Multiple Nets)` and Internal Plane 1 is named `Ground Plane`
- **AND** `Polygons6` holds two Split Plane polygons on that layer, on `GND` and `VCC`
- **AND** the plane's `PULLBACKDISTANCE` is 30 mil
