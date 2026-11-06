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
