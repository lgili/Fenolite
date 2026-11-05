## ADDED Requirements

### Requirement: Level 3 compares slot length and axis
Level 3 SHALL compare the length and the axis of each pad's slot hole, read by its extents: the length is the longer of `Pad.drill` and `Padstack.hole_length`, and the axis, in the footprint's frame and modulo a half turn, lies along that longer side (`Pad.rotation + Padstack.hole_rotation`, plus a quarter turn when `Pad.drill` is the longer). A `pad-slot` difference MUST be reported when only one pad has a slot hole, or when the lengths or the axes differ beyond the tolerances. A slot whose two numbers are equal is a round hole.

#### Scenario: One slot held two ways
- **GIVEN** a slot held as drill 2.15 mm, length 1.0 mm and hole rotation 0° on one side, and as drill 1.0
  mm, length 2.15 mm and hole rotation 90° on the other
- **WHEN** the two designs are compared at level 3
- **THEN** no `pad-slot` and no `pad-drill` difference is reported

#### Scenario: A longer slot
- **GIVEN** the same slot held as drill 1.0 mm and length 3.0 mm at hole rotation 90° on the other side
- **WHEN** the two designs are compared at level 3
- **THEN** one `pad-slot` difference names `2150000@90000000` and `3000000@90000000`

#### Scenario: A slot along the other axis
- **GIVEN** the slot held as drill 1.0 mm and length 2.15 mm at hole rotation 0° on the other side
- **WHEN** the two designs are compared at level 3
- **THEN** one `pad-slot` difference names `2150000@90000000` and `2150000@0`

#### Scenario: KiCad's oval of an Altium slot
- **GIVEN** an authored PcbLib with slot pads in both orders of the two numbers and on turned pads
- **WHEN** it is upgraded by `kicad-cli fp upgrade` 10.0.6 and imported by Fenolite
- **THEN** every slot KiCad encodes has the same length, width and axis on both sides
