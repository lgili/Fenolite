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

### Requirement: Altium signal layer names through KiCad

A conversion of an Altium design to KiCad SHALL give each copper row that a signal layer reaches the
layer's Altium name as user name when the Altium writer would write another name for that row (`Top
Layer`, `Bottom Layer`, `Mid-Layer <k>` for `In<k>.Cu`). A conversion back SHALL write the layer with that
name.

#### Scenario: Signal layer names come back from KiCad

- **GIVEN** the public row `altium-third-party-pcbdoc-04`, whose inner signal layers are named `Internal Layer
  1` and `Internal Layer 2`
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the KiCad rows `In1.Cu` and `In2.Cu` carry those user names, and the written document names its
  Mid-Layer 1 and 2 so

### Requirement: Altium inner signal layer ids through KiCad

A conversion of an Altium design to KiCad SHALL carry the Altium id of each inner signal layer by KiCad row
when one of them is not the id of its position (Mid-Layer k is id k + 1). The Altium writer SHALL write an
inner signal layer that holds a source's id with that id when the ids of all inner signal layers rise
within 2 … 31, and SHALL number them by position otherwise.

#### Scenario: Inner signal layers keep their ids

- **GIVEN** the public row `altium-third-party-pcbdoc-07`, whose inner signal layers are Mid-Layer 2 and 4
  (ids 3 and 5)
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the written copper chain is 1, 3, 5, 32 with the source's names

### Requirement: Altium planes, copper names and ids through flow A

The KiCad build SHALL type `power` each copper row that a board-level `Fenolite.Altium.Planes` property of
the script names as a plane. A conversion back to Altium SHALL give a copper row without a user name the
name that property carries for it.

#### Scenario: Planes, names and ids survive flow A

- **GIVEN** the public row `altium-third-party-pcbdoc-01`, with two split planes of `(Multiple Nets)` and
  named copper layers
- **WHEN** it is imported to Python, built and the build converted to Altium
- **THEN** the written chain, its names, the plane nets and the Split Plane polygons are the source's

### Requirement: Split plane boundaries travel with the plane

The Altium to KiCad conversion SHALL carry the unflagged, positive-width netless and unowned track boundaries
of a carried split plane as geometry. The return SHALL translate them with the split polygons and
write them as tracks of the restored plane. Records with a polygon index SHALL stay out of this
carrier. A property written before boundary support SHALL still read.

#### Scenario: Two splits keep their dividing stroke

- **GIVEN** a carried split plane with a netless boundary track and a track with a pull-back polygon index
- **WHEN** the board is converted to KiCad and then back to Altium
- **THEN** the dividing track retains its geometry on the plane, and the pull-back track is omitted
