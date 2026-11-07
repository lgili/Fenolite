## ADDED Requirements

### Requirement: A flip writes Altium's frame of a bottom part
A `flip` MUST write the component's `ROTATION` as `(180 − R) mod 360`. It MUST turn each pad of the
component to `(180 − r) mod 360`, so that the pads read in the component's frame are the footprint
mirrored in Y on the bottom, as Altium places a bottom part. A flip of a body MUST set `BODYPROJECTION` to 1
on the bottom and 0 on the top, and MUST keep the values of `MODEL.3D.ROTZ` and `MODEL.2D.ROTATION`, as
Altium's own flip does (S-2123). A body flipped to the bottom with `TEXTUREROTATION` 0 MUST take Altium's
360. A flip back MUST restore every other record of the component.

#### Scenario: The frame of a flipped part
- **GIVEN** the kit board, with `D1` and `R1` on the top at rotation 0, and `R1` turned to 90 by a session
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_flip_frame.py -k frame` flips both to the
  bottom
- **THEN** `D1` reads `ROTATION` 180 and `R1` 90. Every pad of both, taken into the component's frame and
  mirrored in Y, is at the place and the rotation it had in the top frame. A flip back gives the records
  of the source.

#### Scenario: A body follows the side
- **GIVEN** the kit board with an authored extruded body on `D1`, `BODYPROJECTION=0`, `MODEL.3D.ROTZ` 0
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_flip_frame.py -k body` flips `D1` and back
- **THEN** the body reads `BODYPROJECTION=1`, `MODEL.3D.ROTZ` and `MODEL.2D.ROTATION` 0 and
  `TEXTUREROTATION` 360 after the first flip. After the flip back, every key of the body is that of the
  source but `TEXTUREROTATION`, which stays 360.

#### Scenario: Altium keeps the flip after a save
- **GIVEN** Fenolite's flip of `D1` in `J01-resave.PcbDoc` (Part J case J9), and the same board with a
  body on `D1`
- **WHEN** the VM agent opens each in Altium Designer, saves it, reopens it and reads it
- **THEN** `D1` is on the Bottom Layer, its pads stay where Fenolite put them, its designator stays on
  Bottom Overlay, and its body projects from the bottom
