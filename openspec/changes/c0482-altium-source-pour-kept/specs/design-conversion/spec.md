## ADDED Requirements

### Requirement: The source's pour is kept
A conversion that goes from Altium through KiCad and back to Altium SHALL write the source's poured
regions (change c0482).
- A conversion to KiCad MUST carry, in the board property `Fenolite.Altium.Pours`:
  - each polygon's region records as read, each with its shape-based twin;
  - the polygon's vertices, its net's name and its record's `LAYER` text;
  - whether the source's own pour fails `pour.check_pour`.
- A computed pour of the Altium writer MUST write the carried records, with the written polygon index,
  when both of these hold:
  - every polygon has a carried pour with its vertices, net and layer;
  - every polygon that fails the copper check failed it in the source too.
  Otherwise the writer MUST compute the pour as before.
- A kept pour MUST NOT be counted as a `zone-fill` change.
- `altium.zones-poured` MUST then say that the regions are the source's.

#### Scenario: The source's pour comes back
- **GIVEN** an authored Altium document with one GND outline poured on F.Cu and on B.Cu
- **WHEN** it is converted to KiCad and back to Altium
- **THEN** the written region records equal the source's except for their polygon index
- **AND** the report counts no `zone-fill` change

#### Scenario: A new fault computes the pour
- **GIVEN** the same carried pours and a via of another net inside them that the source did not have
- **WHEN** the Altium writer writes the document
- **THEN** the pour is computed
