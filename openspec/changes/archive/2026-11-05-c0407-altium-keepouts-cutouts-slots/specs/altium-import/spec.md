## ADDED Requirements

### Requirement: Keep-outs and polygon cut-outs on copper are rule areas
The Altium board import SHALL make a rule area, never copper, of a polygon cut-out (a region of `KIND=1`) and of a track, arc, fill or region on a copper layer whose second flag byte is 2 (a keep-out), whether the primitive is free or belongs to a component.

- A polygon cut-out MUST forbid poured copper alone. It is on its copper layer, or on every copper layer of
  the board when it lies on the Keep-Out or the Multi-Layer layer.
- A keep-out track or arc MUST give the band its width covers, with round ends. A full circle gives two half
  bands.
- A keep-out fill or region MUST give its outline.
- Each keep-out is on its own layer. A region keeps the restrictions it holds (`KEEPOUTRESTRICTIONS`, else
  `KEEPOUTRESTRIC`); a track, arc or fill takes every restriction.
- A keep-out of a component becomes a rule area of the board, in the board's frame.
- Drawings on the Keep-Out layer stay graphics of `Altium.KeepOut`.

#### Scenario: A polygon cut-out on Top
- **GIVEN** an authored document with a region of `KIND=1` on Top without a net
- **WHEN** it is imported
- **THEN** the board holds no copper graphic for it and one rule area on `F.Cu` that forbids pours alone,
  as KiCad 10.0.6's `pcb import` makes of the same document

#### Scenario: A keep-out track on Top
- **GIVEN** the same document with a 0.5 mm track on Top whose keep-out flag is set
- **WHEN** it is imported
- **THEN** the board holds no track for it and one rule area on `F.Cu`: the band of 0.5 mm along the
  track, with every restriction

#### Scenario: Polygon cut-outs of a public document
- **GIVEN** the public row `altium-third-party-pcbdoc-06`, with thirteen regions of `KIND=1` on Top,
  Bottom and Multi-Layer
- **WHEN** it is imported
- **THEN** the board holds thirteen pour-only rule areas and no graphic of layer 74
