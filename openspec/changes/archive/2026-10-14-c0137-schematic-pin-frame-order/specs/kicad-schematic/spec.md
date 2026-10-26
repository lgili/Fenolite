## MODIFIED Requirements

### Requirement: Pin connection points
`fenolite.backends.kicad.schlayout.pin_point(origin, pin, rotation, mirror) -> Point` SHALL return the sheet position at which a pin connects: for a pin at (px, py) in the library frame, whose Y axis points up, the rotation by the instance angle counter-clockwise is applied first, then the mirror to the turned vector (`"x"` negates the turned y, `"y"` the turned x), and the result (px′, py′) gives (x + px′, y − py′) for an instance at (x, y).
- The rotation sense MUST be the one the probes `sch-pin-frame-*` prove on both majors (`kicad-oracle`, "Schematic naming facts are probed").
- The order of rotation and mirror MUST be the one recorded in `docs/formats/kicad/schematic.md` (`H-K-SCH-PINFRAME-ORDER`, read from the demo sheets of the corpus) and asked of `kicad-cli` by "Order of mirror and rotation is asked of the netlist export".
- `schlayout.turned` MUST be the one transform of a library vector into the sheet frame: `pin_point`, `label_angle`, the boxes of a placed unit, the labels of a generated sheet and the own netlist MUST go through it, and no other copy MAY exist.
- `schlayout.PROVED_FRAMES` MUST list the (rotation, mirror) pairs whose probe gave `absent` on both majors, and MUST hold at least `(0, "")`.
- `sch_netlist.frame_evidence(sheets)` MUST give `FRAME_ORDER_EVIDENCE` (`CORPUS-VERIFIED`, `H-K-SCH-PINFRAME-ORDER`) when an instance of the sheets is mirrored and turned by 90 or 270 degrees, and `()` otherwise; `sch_netlist.evidence_of` and the envelope of a KiCad build MUST combine it with the rest of their evidence, so that a sheet without such an instance keeps the evidence it had.

#### Scenario: Unrotated pin
- **GIVEN** an instance at (50.8 mm, 76.2 mm) and a pin at (−12.7 mm, 16.51 mm) in the library frame
- **WHEN** `pin_point` is called with rotation 0 and no mirror
- **THEN** it returns (38.1 mm, 59.69 mm), in nm

#### Scenario: Mirror about the Y axis
- **WHEN** the same pin is asked for with mirror `"y"`
- **THEN** the X of the result is 63.5 mm

#### Scenario: Mirrored quarter turn
- **GIVEN** an instance at the origin and a pin at (−10 mm, 5 mm) in the library frame
- **WHEN** `pin_point` is called with rotation 90 and mirror `"x"`
- **THEN** it returns (−5 mm, −10 mm), in nm: the turn gives (−5 mm, −10 mm) in the library frame, the mirror (−5 mm, 10 mm), the sheet flips y

#### Scenario: Evidence of a mirrored quarter turn
- **GIVEN** the authored sheet of `tests/_pinframe.py`, which holds instances mirrored and turned by 90 and 270 degrees
- **WHEN** `sch_netlist.evidence_of` is asked for it
- **THEN** the level is `CORPUS-VERIFIED` and the hypotheses include `H-K-SCH-PINFRAME-ORDER`; for the generated blink, without such an instance, the evidence is `sch_netlist.EVIDENCE`
