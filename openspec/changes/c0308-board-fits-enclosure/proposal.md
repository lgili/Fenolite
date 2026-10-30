## Why

Stage 1 of the enclosure line (`docs/research/enclosures.md`, sections 5.2, 8 and 9). With a box model
(c0307), the most useful step is to start the board from the box: its outline, its mounting holes, the
places where parts may not stand or may only be so tall, and which parts face which wall. Every one of
these already exists in the DSL as a separate call: `board(outline=…)`, `hole()`, `rule_area()`,
`Part.place(…, anchor=MechanicalIntent(…))`. What is missing is one call that derives them from the box,
consistently, and records the fit so that c0309 can judge it and c0310 can draw the faces.

## What Changes

- **`design.fit(box, *, mount, at, rot=0) -> Fit`** records one fit of the design: the box model (an
  `Enclosure` from c0307), the mount option, and the pose of the box origin in the frame of `place()`
  (rotation a multiple of 90°). It generates nothing by itself. `fenolite.dsl` re-exports `Enclosure`,
  `Fit` and `Aperture`.
- **`fit.outline`**: the mount's usable area in the board frame, as a closed path for
  `design.board(outline=…)`, arcs kept. A smaller outline of the user's own is allowed; c0309 says so.
- **`fit.holes(prefix="H")`**: one `design.hole()` per boss, drill from the boss's screw, courtyard from
  the screw head plus the box's obstacle clearance, locked, its placement carrying a `MechanicalIntent`
  whose key names the box, mount and boss and whose status follows the field's basis.
- **`fit.zones()`**: one named rule area per height zone, `enc.top.<zone>` on `F.Cu` and
  `enc.bottom.<zone>` on `B.Cu`; a zone whose limit is zero or less (where the board rests on a boss)
  forbids footprints on that side, so `place`, the build's guard and KiCad's DRC keep parts off it. The
  limits are recorded in the fit, computed from the zone's Z, the board's thickness and the clearances.
- **`fit.face(part, face, *, aperture, gap=mm(1), protrude=0)`**: the part faces that wall (or the lid or
  floor); `Aperture.rect`, `Aperture.circle` and `Aperture.path` give the opening in the face's frame
  with its height above the board and a clearance.
- **The fit record.** The build writes `.fenolite/enclosure.json` (`fenolite.enclosure-fit.v0`): the box
  embedded, its digest, mount, pose, board thickness, generated items and face rules. A design without
  `fit` writes no such file and builds the bytes it built before.

## Capabilities

### New Capabilities

- `enclosure-fit`: the fit record, its schema, pose transform and limits.

### Modified Capabilities

- `design-dsl`: ADDED "Fitting a board to an enclosure", "Fit outline and holes", "Fit zones", "Fit
  faces and apertures" and "Fit record in a build".

## Non-goals

- No judging: c0309 judges outline, holes, heights and faces.
- No placement of parts to their faces: `place` keeps its own rules; a face rule moves nothing.
- No height limits in `RuleSet.heights`: c0309's stage is the single judge of enclosure heights.
- No board upside down in a box, no tilted mount, no rotation other than multiples of 90°.
- No 3D kernel, no STEP (c0306 places a user's STEP).

## Evidence level required

- Generated outline, holes and areas load in KiCad 9.0.x and 10.0.x with no `invalid_outline` and no new
  DRC violation type: `KICAD-VERIFIED` (`H-K-ENCL-FIT-BUILD`).
- Pose transform and limits: `INFERRED` by unit tests against hand-computed values (`H-G-ENCL-POSE`).

## Impact

- New: `src/fenolite/dsl/fit.py`, `src/fenolite/dsl/aperture.py`, tests under `tests/unit/dsl/` and
  `tests/kicad/enclosure/`, `examples/enclosure/fit_box.py`.
- Changed: `dsl/design.py` (`fit`), `dsl/__init__.py`, `model/enclosure.py` (`Fit`, `FaceRule`,
  `ApertureShape`), `tools/gen_schemas.py` (`schemas/fenolite.enclosure-fit.v0.json`), `cli/cmd_build.py`
  (writing the record), `docs/dsl.md`, `docs/enclosures.md`, the agent guide (`dsl-reference` generated,
  `design-script.md`), registers, `openspec/README.md`, `CHANGELOG.md`.
- Depends on c0307.
- Size: about 6 design-days.
