## ADDED Requirements

### Requirement: Fills of a converted board

The writer SHALL write a filled rectangle, or a filled polygon of four corners that is a rectangle within
10 nm, whose KiCad uuid is tagged as an Altium fill as one fill record of its layer, net and owner: the
50-byte form with the rotation of its first edge. Any other filled shape SHALL stay a region.

#### Scenario: A fill comes back as a fill

- **GIVEN** a KiCad board converted from an Altium document with a free fill and a fill of a component
- **WHEN** the board is converted to Altium
- **THEN** the document holds two fill records, one of them with the component's index, and no region in
  their place

#### Scenario: A component's copper fill of no net comes back

- **GIVEN** a footprint without net ties that holds a tagged fill of no net on a copper layer (row `-04`'s
  J1 holds six on the Top Layer)
- **WHEN** the board is converted to Altium
- **THEN** each is a fill record of no net on that layer with the component's index, and a copper graphic
  of no net that is not tagged stays refused

### Requirement: Keep-out strokes of a converted board

The writer SHALL write a rule area named with the marker of a keep-out stroke (`Altium.KeepOut/flag<r>/…`)
as a keep-out track or arc of its signal layer, with the keep-out flag and the restriction byte r in the
long form (49 bytes for a track, 60 for an arc), of the area's component for an area of a footprint, when the
area is still its stroke's: one layer, what r forbids and no more, and the band of the stroke as its outline.
The two rule areas of a circle SHALL give one arc. Any other area SHALL stay a keep-out region.

#### Scenario: A keep-out stroke comes back as a stroke

- **GIVEN** a KiCad board converted from an Altium document with a keep-out circle of a component on the top
  layer that forbids everything (r = 31)
- **WHEN** the board is converted to Altium
- **THEN** the document holds one keep-out arc of the component on the top layer, in the 60-byte form with
  the byte 31, and no keep-out region in its place

#### Scenario: An edited keep-out stroke stays an area

- **GIVEN** the area of a keep-out stroke edited to forbid vias too
- **WHEN** the board is written as an Altium document
- **THEN** the area is a keep-out region and no keep-out track is written for it

#### Scenario: A plain circle of the Keep-Out layer comes back whole

- **GIVEN** the two rule areas that a conversion makes of a circle drawn on the Keep-Out layer without the
  keep-out flag (change c0442)
- **WHEN** the board is written as an Altium document
- **THEN** the document holds one arc of the Keep-Out layer for them and no keep-out region

### Requirement: Texts on Mechanical 17 to 32

The writer SHALL write a text on Mechanical 17 to 32 whose Altium bag holds the source's bytes from 137 on
of its first subrecord (`text_tail`) in the source's 232- or 252-byte form: the layer byte of Mechanical 16,
its 137 bytes, then those bytes with the layer's long id at 226. Every other text SHALL keep the 137-byte
form.

#### Scenario: A text on Mechanical 17 to 32 keeps its long id

- **GIVEN** an Altium document with a 252-byte text whose layer byte is 72 and whose long id at 226 is
  Mechanical 20, and a 137-byte text on Mechanical 16
- **WHEN** it is converted to KiCad and back
- **THEN** the first text comes back with 252 bytes, the byte 72, the long id of Mechanical 20 and the same
  bytes from 137, and the second in the 137-byte form

### Requirement: Width 0 on mechanical layers

The writer SHALL write a line or an arc of width 0 on a layer the document names as Mechanical 1 to 32
(`Mech.<n>` of a board that was read, or a KiCad user layer named after a mechanical layer), free or of a
component, with width 0. A drawn shape of width 0 on any other layer (copper, `F.Fab` and the other
layers of the fixed KiCad map), a drawn rectangle, circle or polygon of width 0 and a
negative width SHALL stay refused.

#### Scenario: A line of width 0 on a mechanical layer

- **GIVEN** an Altium document with a free track, a component track and a component arc of width 0 on
  Mechanical 1
- **WHEN** it is converted to KiCad and back
- **THEN** the document holds the three of them on Mechanical 1 with width 0, and a line of width 0 on a
  silkscreen or copper layer is still refused
