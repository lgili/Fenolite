## ADDED Requirements

### Requirement: Keep-out fills of a converted board

The writer SHALL write a rule area named with the marker of a keep-out fill
(`Altium.KeepOut/flag<r>/fill/<corners>`) as a fill record of its signal layer in the 50-byte form, with the
keep-out flag and the restriction byte r at 46, of the area's component for an area of a footprint, when the
area is still its fill's: one layer, what r forbids and no more, and the four corners, a rectangle, as its
outline. Any other area SHALL stay a keep-out region.

#### Scenario: A keep-out fill comes back as a fill

- **GIVEN** a KiCad board converted from an Altium document with a keep-out fill of a component on the
  bottom layer with the restriction byte 24
- **WHEN** the board is converted to Altium
- **THEN** the document holds one fill record of the component on the bottom layer with the keep-out flag
  and the byte 24, and no keep-out region in its place

#### Scenario: An edited keep-out fill stays an area

- **GIVEN** the area of a keep-out fill edited to forbid vias too
- **WHEN** the board is written as an Altium document
- **THEN** the area is a keep-out region and no fill record is written for it
