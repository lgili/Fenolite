## ADDED Requirements

### Requirement: Assembly and test pad properties are probed
`tests/kicad/assembly/test_pad_properties.py` SHALL build a bench of marked pads, on authored footprints and on copies of library footprints, for each target the running major loads, and SHALL record the probes of `H-K-PAD-FABPROP` and `H-K-PAD-FABPROP-LIB` in `tests/kicad/_probes.py`:
- `pad-fabprop-<value>`, one per value of `PadFabProperty`: the board loads, and its copper Gerber flashes the pad with the aperture function that `docs/formats/kicad/board.md` gives for the value. For `press_fit` the 9.0.9 outcome records that the mark is dropped on load.
- `pad-fabprop-outputs`: `pcb export pos --format csv` and `pcb export ipcd356` of the bench are equal with and without the marks.
- `pad-fabprop-padstack`: DRC reports `padstack` for `castellated` and for `mechanical` on an SMD pad, and not on a through-hole pad.
- `pad-fabprop-lib-mismatch`: DRC reports `lib_footprint_mismatch` for a library copy marked where its library pad is not; `pad-fabprop-lib-same`: no such violation for an authored footprint whose written `.kicad_mod` holds the same mark.
- On 10.0.6, the bench re-saved by `pcb upgrade --force` MUST keep every mark.

#### Scenario: Marks on both majors
- **WHEN** `uv run pytest tests/kicad/assembly/test_pad_properties.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** every probe matches the outcome recorded in the probe file of that version

### Requirement: Assembly and test features pass the oracle
`tests/kicad/assembly/test_features_oracle.py` SHALL build the variant of "Features in a build" (`design-dsl`, "Assembly and test features in a build") for each target the running major loads, and SHALL record:
- `asm-fiducial-drc`: no DRC violation names a fiducial, a test point or a tooling hole;
- `asm-fiducial-mask`: the mask Gerber of each fiducial's side flashes a circle of its mask diameter at its centre;
- `asm-fiducial-d356`: each fiducial's copper pad is one `327` record on no net, with `covered` `bottom` on the top side and `top` on the bottom side;
- `asm-tooling-drill`: the non-plated drill file holds the tooling hole's diameter at its centre;
- `asm-features-pos`: `pcb export pos --format csv` lists the fiducials at their positions and no test point or tooling hole;
- `asm-keepout-track`: with a track drawn by token edit through `clear_FID1`, DRC reports `items_not_allowed` naming it, and nothing naming the fiducial's pads;
- `asm-keepout-fill` (10.0.6): with a zone over the board refilled by `fenolite fill`, no fill lies closer to a fiducial's centre than the apothem of its keep-out, less 1 µm.

#### Scenario: Built features on both majors
- **WHEN** `uv run pytest tests/kicad/assembly/test_features_oracle.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** every probe of the running major matches its recorded outcome: `asm-fiducial-drc` `absent`, `asm-keepout-track` `present`, the other five `equal`

### Requirement: Test-point report agrees with IPC-D-356
`tests/kicad/assembly/test_testpoints_d356.py` SHALL compare the test-point rows of `exports.testpoints.report` with the records of `pcb export ipcd356`, read with `read_ipcd356`, on a bench that holds a top SMD, a bottom SMD and a through-hole test point of `design.test_point()` and an authored SMD pad marked `test_point` on `F.Cu` only, for each target the running major loads:
- each row MUST have exactly one `317` or `327` record within ±2 export units of its position (Y up), on its net;
- the record's `side` MUST be `top`, `bottom` or `both` as the pad's copper is on `F.Cu`, on `B.Cu` or on both, and that side less the sides of its `covered` MUST equal the row's `access`, `none` when nothing is left;
- the probe `asm-testpoint-d356` records the outcome, and `H-K-TESTPOINT-D356` cites it.

#### Scenario: Four kinds of test pad
- **WHEN** `uv run pytest tests/kicad/assembly/test_testpoints_d356.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** the four rows have the access `top`, `bottom`, `both` and `none`, their records hold `S2`, `S1`, `S0` and `S3`, and `asm-testpoint-d356` is `equal`
