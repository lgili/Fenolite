## Why

A contract manufacturer needs fiducials, tooling holes, and test points with their list. A script cannot place them and nothing reports them; the complex-board review of 2026-10-05 found no owner, and `origin/dev` at `9aba2dff` still has none (`Pad` has no mark field, `pad_prop_*` appears only in the token inventory, and there is no `cmd_testpoints.py` or `dsl/assembly.py`). Milestone v0.4 (written as "v0.2c" before the renaming of 2026-10-07).

Measured with `kicad-cli` 10.0.6 and 9.0.9:

- KiCad marks a fiducial or test-point pad with `(property pad_prop_…)`; only the copper Gerber attribute changes. The model has no field for it.
- KiCad's own fiducial and test-point footprints carry no mark; marking a placed copy gives `lib_footprint_mismatch`.
- KiCad's fiducials keep copper away with the pad's own clearance, which Fenolite's copper check ignores; a keep-out holds on both checks.
- IPC-D-356 gives each test pad its net, side and mask opening.

## What Changes

- **Model.** `Pad.fab_property` (`bga`, `fiducial_global`, `fiducial_local`, `test_point`, `heatsink`, `castellated`, `mechanical`, `press_fit`), read and written on boards and footprint files.
- **Script.** `design.fiducial()`, `design.test_point()` and `design.tooling_hole()` add parts with footprints and symbols generated in `Fenolite_Assembly`. Fiducials and tooling holes get a copper keep-out (c0103's `rule_area`) and are locked; a tooling hole is c0102's hole part under its own library name. By the maintainer's decision of 2026-10-07 these two calls of c0102 and c0103 are the ones that exist: c0096 (implemented on its branch with `Design.hole()` and `Design.keepout()`) adapts to them. Authored pads take `fab_property=`.
- **Report.** `fenolite testpoints PATH`: test points with net, position and access, fiducials, holes, net coverage, findings against the user's values, a CSV, and with `--manifest` its manifest entry of the derived kind `testpoints`.
- **Placement table (c0064).** Fiducial rows are marked; a template can drop them.
- **Altium.** An Altium build writes test points as ordinary parts and names their unwritten mark in an info; it leaves fiducials and tooling holes out, with an info, because the PCB library writer on `dev` refuses a pad without a number and a surface pad without copper.
- **Panel.** Open for the maintainer: no step, an own step, or an external tool behind a process boundary.

**Limits.** Roles come from pad marks and generated library names: a third-party board shows only marked pads. Clear areas are fixed octagons. Access comes from copper and mask layers, not from probe size; coverage counts nets of two pads or more. `press_fit` needs KiCad 10; `castellated` and `mechanical` need a through-hole pad. Until c0077, KiCad's own outputs show generated parts without a reference.

Size: 5.75 design-days; cut order in the design.

## Capabilities

### New Capabilities
- `assembly-test-features`: the test-point report, coverage, findings, codes and evidence.

### Modified Capabilities
- `design-model`: ADDED "Assembly and test pad properties in the model".
- `kicad-file-backend`: ADDED "Assembly and test pad properties on boards and footprints"; MODIFIED "IPC-D-356 parsing".
- `design-dsl`: ADDED "Fiducials in the DSL", "Test points in the DSL", "Tooling holes in the DSL", "Assembly and test features in a build".
- `dsl-footprint-authoring`: ADDED "Assembly and test properties on authored pads".
- `assembly-outputs` (c0064): ADDED "Fiducial rows in the placement table".
- `cli-contract`: ADDED "Testpoints command"; MODIFIED "Manifest option of producing commands" (c0116 modifies it first).
- `manufacturing-exports`: MODIFIED "Artefact states" (the derived kind `testpoints`; order c0116, c0117, c0118, c0105).
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
- Altium test-point and fiducial flags on a pad record: nowhere yet, because no public source read for Fenolite says where a pad record holds them; a change that brings the fact row first can write them, and the info of this change names what is missing until then.
- `fenolite pads` (c0066) showing the mark: nowhere in this change; `testpoints` and `inspect` show it.

## Evidence level required

- New rows `H-K-PAD-FABPROP`, `H-K-PAD-FABPROP-LIB`, `H-K-FIDUCIAL-FORM`, `H-K-TESTPOINT-D356` (both majors) and `H-K-FIDUCIAL-KEEPOUT` (refill on 10.0.6): `KICAD-VERIFIED` before merge.
- The report: `INFERRED` until `H-K-TESTPOINT-D356` holds. Script calls, coverage, findings: unit scenarios.

## Impact

- New: `dsl/assembly.py`, `exports/testpoints.py`, `cli/cmd_testpoints.py`.
- Changed: model, schemas, `backends/kicad/`, `dsl/footprint.py`, `exports/`, `lens/altium.py`, docs.

## Prerequisites

- `0.3.0` is released from `dev` (c0085, c0086 and c0126 archived: the Altium requirement of this change is written on their PCB library and document rules).
- c0102 on `dev`: generated definitions, the pinless symbol holder, unnumbered hole pads and `Fenolite_Holes:Hole`.
- c0103 on `dev`: `Design.rule_area`, `Design.rule_areas`, its uniqueness check and the copper check's `copper.keepout`.
- c0116 and c0117 on `dev` before this change's deltas of "Artefact states" and "Manifest option of producing commands" are regenerated (order c0116, c0117, c0118, c0105).
- c0096: by the maintainer's decision 2 of 2026-10-07 it adapts to c0102 and c0103. If it lands first, its `Design.hole()` and `Design.keepout()` must already be the calls of c0102 and c0103, and its check of duplicate drill intents must not report a tooling hole of this change (task 3.4). c0097 and c0099: nothing here touches them.
- Already on `dev` (archived): c0064, c0065, c0066. Not prerequisites: c0077 (references on generated parts in KiCad's own outputs), c0080 (the guide lines), c0113 (local fiducials near a part).
