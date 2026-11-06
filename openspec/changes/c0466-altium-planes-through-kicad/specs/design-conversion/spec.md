## ADDED Requirements

### Requirement: Altium internal planes through KiCad and back

A conversion of an Altium design to KiCad SHALL write each internal plane of the copper chain as a copper
row of type `power`, with the plane's Altium name as the row's user name when a record field can hold it.
It SHALL carry each plane whose net is a net of the design, or `(Multiple Nets)` with Split Plane polygons,
in the board property `Fenolite.Altium.Planes`, with:
- its row;
- its net;
- its pull-back;
- its Split Plane polygons, each with its net and its straight ring;
- the board's corner.

The conversion back SHALL write each carried plane whose row is still a `power` row and whose nets the
design holds as an internal plane, with:
- its carried net;
- its pull-back;
- the row's user name as its name;
- its Split Plane polygons, moved with the board.

It SHALL count every other carried plane lost under `plane`, with a reason. The read-back SHALL hold no
per-layer rule that the source does not hold.

#### Scenario: Split planes come back from KiCad

- **GIVEN** public row `-01`, whose Ground Plane and Power Plane are `(Multiple Nets)` with 2 and 6 Split
  Plane polygons
- **WHEN** it is converted to KiCad and back to Altium
- **THEN** the KiCad rows `In1.Cu` and `In2.Cu` are `power` rows named `Ground Plane` and `Power Plane`
- **AND** the written copper chain is 1, 39, 40, 32, with those names and `PLANE1NETNAME` and
  `PLANE2NETNAME` `(Multiple Nets)`
- **AND** the document holds the 8 Split Plane polygons with the source's nets and vertices
- **AND** the read-back holds as many `track_width` rules as the source

#### Scenario: Single-net planes with splits come back

- **GIVEN** public row `-02`, whose planes are on `GND` and `5V` with 1 and 4 Split Plane polygons
- **WHEN** it is converted to KiCad and back to Altium
- **THEN** the planes come back on `GND` and `5V`, named `GND` and `POWER`, with their 5 polygons

#### Scenario: A plane edited away in KiCad is lost

- **GIVEN** the KiCad conversion of a document with a carried plane on `In1.Cu`, whose row was made a
  `signal` row
- **WHEN** it is converted to Altium
- **THEN** `In1.Cu` is written as Mid-Layer 1
- **AND** the report holds one `plane` loss for it
