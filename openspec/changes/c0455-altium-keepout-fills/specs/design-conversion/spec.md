## ADDED Requirements

### Requirement: Keep-out fills named through KiCad

A conversion of an Altium design to KiCad SHALL name the rule area of each keep-out fill of copper of the
board and of its footprints `Altium.KeepOut/flag<r>/fill/<x1>/<y1>/…/<x4>/<y4>`, r its restriction byte and
the numbers its four corners in the frame of the area, when the area is still the fill's.

#### Scenario: A keep-out fill names its rule area

- **GIVEN** an Altium document with a keep-out fill of a component on the bottom layer
- **WHEN** it is converted to KiCad
- **THEN** the KiCad board holds one rule area of the footprint named `Altium.KeepOut/flag<r>/fill/…` with
  the fill's restriction byte and corners
