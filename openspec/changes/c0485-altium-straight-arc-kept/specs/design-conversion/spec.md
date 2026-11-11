## ADDED Requirements

### Requirement: A straight Altium arc is kept
A conversion that goes from Altium through KiCad and back to Altium SHALL write the source's arc record of
an arc whose three points lie on one line (change c0485).
- A conversion to KiCad MUST carry, in the board property `Fenolite.Altium.StraightArcs`, each such arc's
  pair `arc` as read, with its layer, width and net name.
- The Altium writer of a conversion MUST write the carried record, not a track, for a track or a straight
  arc of the same layer, width and net whose ends lie within `ARC_TOLERANCE` of the record's in the written
  document's frame. It MUST find the record by that content, not by uuid.
- A track or arc that matches no record MUST be written as before.
- An arc written back with its record MUST NOT be counted as changed.

#### Scenario: A straight arc comes back
- **GIVEN** an authored Altium document with one GND arc record whose three points lie on one line
- **WHEN** it is converted to KiCad and back to Altium
- **THEN** the written document holds the source's arc record and its one track
- **AND** the report counts no `arc` change

#### Scenario: A script's track comes back as the arc
- **GIVEN** the KiCad board of that conversion with the arc replaced by a track with another uuid
- **WHEN** it is converted to Altium
- **THEN** the written document holds the source's arc record

#### Scenario: An edited track stays a track
- **GIVEN** the KiCad board of that conversion with the arc's end moved by 1 um
- **WHEN** it is converted to Altium
- **THEN** it is written as a straight track
