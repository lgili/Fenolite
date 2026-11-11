## ADDED Requirements

### Requirement: A derived courtyard is not written back to Altium
A courtyard that the Altium import derived SHALL NOT be written to an Altium document (change c0489).
- The Altium writer MUST skip a footprint graphic with the pair `derived=courtyard`, and the conversion
  report MUST give it no row.
- A conversion to KiCad MUST write the derived courtyard as a footprint polygon on `F.CrtYd` or `B.CrtYd`,
  and MUST carry each one, with its footprint's reference, layer and points, in the board property
  `Fenolite.Altium.DerivedCourtyards`.
- A conversion from KiCad to Altium MUST skip a courtyard polygon that matches a carried one by footprint
  reference, layer and points within 1 nm in the written document's frame. It MUST find it by that content,
  not by uuid.
- A courtyard polygon that matches no carried one MUST be written as before.

#### Scenario: Altium to Altium through KiCad
- **GIVEN** an authored PCB document with one footprint that gets a derived courtyard
- **WHEN** it is converted to KiCad and back to Altium
- **THEN** the KiCad board holds the courtyard on `F.CrtYd`, and the Altium document holds the same
  primitives as the source and no courtyard drawing

#### Scenario: An edited courtyard is kept
- **GIVEN** the KiCad board of that conversion with one courtyard point moved by 0.1 mm
- **WHEN** it is converted to Altium
- **THEN** the courtyard is written as a drawing of the footprint
