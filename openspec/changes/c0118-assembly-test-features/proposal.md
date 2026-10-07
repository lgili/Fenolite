## Why

A contract manufacturer needs fiducials, tooling holes, and test points with their list. A script cannot place them and nothing reports them; the review of 2026-10-05 (`docs/roadmap.md`, Gaps to a complex board) found no owner.

Measured with `kicad-cli` 10.0.6 and 9.0.9:

- KiCad marks a fiducial or test-point pad with `(property pad_prop_…)`; only the copper Gerber attribute changes. The model has no field for it.
- KiCad's own fiducial and test-point footprints carry no mark; marking a placed copy gives `lib_footprint_mismatch`.
- KiCad's fiducials keep copper away with the pad's own clearance, which Fenolite's copper check ignores; a keep-out holds on both checks.
- IPC-D-356 gives each test pad its net, side and mask opening.

## What Changes

- **Model.** `Pad.fab_property` (`bga`, `fiducial_global`, `fiducial_local`, `test_point`, `heatsink`, `castellated`, `mechanical`, `press_fit`), read and written on boards and footprint files.
- **Script.** `design.fiducial()`, `design.test_point()` and `design.tooling_hole()` add parts with footprints and symbols generated in `Fenolite_Assembly`. Fiducials and tooling holes get a copper keep-out (c0103) and are locked. Authored pads take `fab_property=`.
- **Report.** `fenolite testpoints PATH`: test points with net, position and access, fiducials, holes, net coverage, findings against the user's values, a CSV.
- **Placement table (c0064).** Fiducial rows are marked; a template can drop them.
- **Altium.** The new parts are left out, with an info.
- **Panel.** Open for the maintainer: no step, an own step, or an external tool behind a process boundary.

**Limits.** Roles come from pad marks and generated library names: a third-party board shows only marked pads. Clear areas are fixed octagons. Access comes from copper and mask layers, not from probe size; coverage counts nets of two pads or more. `press_fit` needs KiCad 10; `castellated` and `mechanical` need a through-hole pad. Until c0077, KiCad's own outputs show generated parts without a reference.

Size: 5.5 design-days; cut order in the design.

## Capabilities

### New Capabilities
- `assembly-test-features`: the test-point report, coverage, findings, codes and evidence.

### Modified Capabilities
- `design-model`: ADDED "Assembly and test pad properties in the model".
- `kicad-file-backend`: ADDED "Assembly and test pad properties on boards and footprints"; MODIFIED "IPC-D-356 parsing".
- `design-dsl`: ADDED "Fiducials in the DSL", "Test points in the DSL", "Tooling holes in the DSL", "Assembly and test features in a build".
- `dsl-footprint-authoring`: ADDED "Assembly and test properties on authored pads".
- `assembly-outputs` (c0064): ADDED "Fiducial rows in the placement table".
- `cli-contract`: ADDED "Testpoints command".
- `altium-build`: ADDED "Assembly and test features in an Altium build".
- `kicad-oracle`: ADDED "Assembly and test pad properties are probed", "Assembly and test features pass the oracle", "Test-point report agrees with IPC-D-356".

## Non-goals

- Panels: nowhere, because the maintainer chooses first (design, Open Questions).
- Part heights; local fiducials kept near a part: c0113.
- Vias as test points: c0112 opens a via; nowhere in the report, because KiCad marks no via.
- Polarity marks: nowhere, because no KiCad check or output reads them.
- A fabricator profile: nowhere, because rule minimums (c0054, c0071) hold those limits.
- A pad's own clearance in the copper check: c0068's open question.
- Marks on library copies: nowhere, because KiCad reports a mismatch.
- Fixture machine files: nowhere, because `export --ipcd356` (c0024) is the neutral file.
- Altium test-point flags: roadmap Phase 4.

## Evidence level required

- New rows `H-K-PAD-FABPROP`, `H-K-PAD-FABPROP-LIB`, `H-K-FIDUCIAL-FORM`, `H-K-TESTPOINT-D356` (both majors) and `H-K-FIDUCIAL-KEEPOUT` (refill on 10.0.6): `KICAD-VERIFIED` before merge.
- The report: `INFERRED` until `H-K-TESTPOINT-D356` holds. Script calls, coverage, findings: unit scenarios.

## Impact

- New: `dsl/assembly.py`, `exports/testpoints.py`, `cli/cmd_testpoints.py`.
- Changed: model, schemas, `backends/kicad/`, `dsl/footprint.py`, `exports/`, `lens/altium.py`, docs.
- Depends on c0102, c0103 and c0064.
