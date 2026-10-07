## Context

- **Scope.** Milestone v0.4. The complex-board review of 2026-10-05 found three gaps that no change and no roadmap line owned: fiducials, tooling holes and panels; test points and a test-point report; and assembly checks beyond KiCad's DRC (part height, polarity marks, test-point coverage, a fabricator profile). The row of c0118 takes fiducials, tooling holes, test points, the report and coverage. A panel is left to the maintainer (Open Questions). The other parts of the third gap go elsewhere (proposal, Non-goals).
- **What exists** (`origin/dev` at `9aba2dff`, read on 2026-10-07):
  - *Model.* `Pad(number, shape, size, position, kind, rotation, drill, layers, net_id, padstack, zone_connection)`: no mark for a fiducial or a test point, no mask margin, no clearance of its own. `FootprintInstance.attributes` holds `smd`, `through_hole`, `board_only`, `exclude_from_pos_files`, `exclude_from_bom`, `dnp`. `Board.keepouts` exists; the writer writes it; no script call on `dev` makes one (`dsl/design.py` has no `keepout`, `rule_area` or `hole`). The branch of c0096 adds `Design.keepout()` and `Design.hole()`; by the maintainer's decision of 2026-10-07 they become c0103's `rule_area` and c0102's hole part.
  - *KiCad backend.* `_fpmap.read_pad` models number, kind, shape, `at`, `size`, `drill`, `layers`, `net`, `zone_connect` and `uuid`; a pad's `(property pad_prop_…)` stays an opaque slot. Created pads follow `CANONICAL_ORDER["pad"]`; `mod.prepare_authored_definition` gives authored pads modelled slots for number, kind, shape, position, size, drill, layers and ids. The token inventory lists `pad_prop_mechanical` (since 9) and `pad_prop_pressfit` (since 10; 9.0.9 loads the pad and drops the mark) and no other mark; 9.0.9 loads the six others (measurement 2). `ipcd356.read_ipcd356` reads `317` and `327` records with the access side, not the mask code.
  - *Script.* `Footprint.pad` refuses an empty number; c0102 proposes `design.hole()`, generated definitions in `Fenolite_Holes` and unnumbered hole pads. `cmd_build` builds every entry of `Design.footprints` and `Design.symbols` from its `.definition`. c0103 proposes `design.rule_area(name, outline, *, layers=None, forbid=())`.
  - *Assembly tables* (c0064, archived). `exports.placement.rows_from_model` gives one row per footprint without `exclude_from_pos_files`, with `mount` from the attributes. `fenolite pnp` reads the board file and renders through a template whose `[placement]` table holds origin, Y axis, units, decimals and side names (`cli/_assembly.py`).
  - *Checks.* The copper check does not model a pad's own clearance (c0068, Open Questions; one demo board holds 115 such pads).
  - Authored footprints reach the board without a Reference field (c0077, agent track, not on `dev`).
  - *Altium build* (c0085, c0086, c0126 on `dev`). An authored footprint goes through `pcblib.check_footprint`: a pad without a number is refused (`pcblib.py:157`, `text_problem` of an empty text), and so is a surface pad without a copper layer (`pcblib.py:173`). A refused footprint gives `altium.footprint-unsupported`, and the PCB document is then not written (`altium.pcbdoc-not-written`, living "PCB document output"). A numbered SMD or through-hole pad with copper is accepted. No Altium module reads or writes a test-point or fiducial flag of a pad; `docs/formats/altium/` holds no fact row for one.
  - *Manifest and paging* (c0065, c0066, archived). `pnp` and `bom` take `--manifest`; "Artefact states" lists the derived kinds; a command declares `paged`.
- **KiCad's libraries and the corpus** (S-0018, S-0042, S-0043, S-0024; counts only).
  - The 10.0.6 footprint library holds `pad_prop_bga` 73 391 times, `pad_prop_heatsink` 6 375, `pad_prop_mechanical` 264 (connector shields) and `pad_prop_fiducial_loc` twice, in one QFN. No fiducial or test-point footprint carries a mark. The 9.0.9 library has the same pattern.
  - `Fiducial.pretty`: 10 footprints `(attr smd exclude_from_bom)`; `Fiducial_1mm_Mask2mm` is one unnumbered SMD pad of 1 mm on `F.Cu` and `F.Mask` with `(solder_mask_margin 0.5)` and `(clearance 0.6)`. `TestPoint.pretty`: 30 bare pads `(attr exclude_from_pos_files exclude_from_bom)`, 25 `through_hole`, 2 `smd`. `Panelization.pretty`: 31 mouse bites and break lines `(attr [smd] board_only exclude_from_pos_files exclude_from_bom dnp)`.
  - Symbols: `Mechanical:Fiducial` has no pin, `in_bom no`, reference `FID`; `Connector:TestPoint` has one passive pin, `in_bom yes`, reference `TP`.
  - Of the 16 demo boards of 10.0.6, 4 hold fiducial or test-point footprints (3 fiducials, 24 test points); no pad carries a fiducial or test-point mark.
- **Measured on 2026-10-05**, with `kicad-cli` 10.0.6 (macOS) and 9.0.9 (the pinned image), on projects built by the review branch (`27ef3ad7`) through `fenolite build` and edited by token or through the model API where a feature is missing; identical on both majors unless said. Outputs with the options of `exports.plan` and `pcb drc --format json --severity-all`.
  1. *Library parts build today.* Three `Fiducial_1mm_Mask2mm` (one on the bottom), three `TestPoint_Pad_D1.5mm`, one `TestPoint_THTPad_D1.0mm_Drill0.5mm` with `Mechanical:Fiducial` and `Connector:TestPoint` build with exit 0 and no issue.
  2. *The mark in the outputs.* Marks added by token edit (`fiducial_glob`, `fiducial_loc`, `testpoint`): the copper Gerbers flash those pads with `%TA.AperFunction,FiducialPad,Global*%`, `FiducialPad,Local` and `TestPad` instead of `SMDPad,CuDef` or `ComponentPad`. `pcb export pos --format csv`, `pcb export ipcd356` and the mask Gerbers are unchanged; so are the Gerber position file, `pcb export ipc2581`, `odb`, `gencad` and `stats` on 10.0.6, dates aside. The other marks: `bga` → `BGAPad,CuDef`, `heatsink` → `HeatsinkPad`, `castellated` → `CastellatedPad`, `mechanical` on an SMD pad → `SMDPad,CuDef`, `pressfit` on a through-hole pad → `ComponentPad`. `castellated` and `mechanical` on an SMD pad give `padstack` ("… are normally PTH"). 10.0.6's `pcb upgrade --force` keeps all eight; 9.0.9 drops `pressfit`.
  3. *Library mismatch.* A mark on a placed copy of a library footprint gives one `lib_footprint_mismatch` per footprint (6 of 6). An authored footprint whose vendored `.kicad_mod` carries the same mark gives none (2 of 2).
  4. *Position file.* Fiducials (`smd`, no `exclude_from_pos_files`) are listed, test points are not; an authored footprint is listed with an empty `Ref` and `Val`.
  5. *IPC-D-356.* A top SMD test pad on `F.Cu` and `F.Mask`: `327`, `A01`, `S2`; a bottom one: `A02`, `S1`; a through-hole one: `317`, `A00`, `S0`; an SMD copper pad without a mask layer: `S3`. Fiducial pads are `327N/C` records.
  6. *A generated fiducial.* An unnumbered 1 mm SMD pad on `F.Cu` and `F.Mask` with the mark, and an unnumbered 2 mm SMD pad on `F.Mask` only: no violation of its own; a 2 mm flash on `F.Mask`; `327N/C … S2`. With the copper pad on `F.Cu` only, IPC-D-356 says `S3`.
  7. *Clear area: the pad's own clearance* (10.0.6). `Fiducial_1mm_Mask2mm` under a GND pour, with a 0.2 mm SIG track 0.4 mm from its 1 mm pad: the refilled pour stays 0.6005 mm from the pad; DRC reports `clearance` ("pad clearance 0.6000 mm") and `solder_mask_bridge`; with a board-wide or a net rule of 0.2 mm the pad's 0.6 mm is still reported, so a custom rule does not replace it. Fenolite's copper check reports nothing.
  8. *Clear area: a rule by reference* (10.0.6). `rule("fid", "clearance", where=select.ref("FIDB"), min=mm(0.6))` on an authored fiducial writes `A.memberOfFootprint('FIDB')`, which matches nothing: the footprint has no Reference. With a Reference added by token edit, the refill keeps 0.6005 mm and the copper check reports 0.4 mm; KiCad's DRC reports the rule only when the other fiducial is moved off the same track, one clearance violation per track item in this run. The mask aperture pad's opening over the track gives no `solder_mask_bridge`.
  9. *Clear area: a keep-out* (10.0.6). A model `Keepout` written by `write_board`, an octagon of apothem 1.1 mm around the authored fiducial on `F.Cu`, forbidding tracks, vias and pours: the refilled pour stays 1.1000 mm from the centre; DRC reports `items_not_allowed` for the track, nothing for the fiducial's pads. The copper check reports nothing until c0103's `copper.keepout`.
  10. *Panels.* `kicad-cli` 10.0.6 has no panel command (`pcb`: `drc`, `export`, `import`, `render`, `upgrade`).

  None of these probes is committed. They were taken on the review branch and not repeated on `dev`; they are facts of `kicad-cli` and of KiCad's public libraries, and each becomes a recorded probe of task group 1 before code leans on it.
- **Constraints.** Stdlib only. `dsl` imports `core` and `model` only. Integers in nanometres. No value shipped (plan D6): pad sizes, mask openings, clear areas, coverage targets, probe pitches and fiducial counts are the user's.

## Goals / Non-Goals

**Goals**
- A script places fiducials, test points and tooling holes that KiCad loads clean and labels in its outputs, with no library needed.
- The marks survive a round trip through KiCad, so any reader of the board finds them.
- One read-only command lists test points, fiducials and holes, says which nets have a test point, and judges the user's targets.

**Non-Goals**
- Everything under "Non-goals" in the proposal, with the destinations named there.
- A panel (Open Questions).

## Decisions

1. **The mark is KiCad's pad property, modelled as `Pad.fab_property`.** Values `bga`, `fiducial_global`, `fiducial_local`, `test_point`, `heatsink`, `castellated`, `mechanical` and `press_fit`, `None` for no mark. All eight are modelled, so a read board keeps every mark it has and c0110 may read `bga`.
   - Rejected: a footprint property `fenolite.role`, which KiCad's outputs ignore; c0113 rejected the same for heights. Rejected: a field of `.fenolite/` only, which a board read without it loses.
2. **Reading and writing follow `zone_connect`.** `_fpmap` maps the child both ways for board and `.kicad_mod` pads; an unknown or repeated child stays opaque with `kicad.board.kept-opaque` or `kicad.lib.kept-opaque`, and a model value that differs from it gives `kicad.board.projection-read-only`. A created pad writes it after `drill` (or `size`) and before `layers`, where KiCad's files hold it. `press_fit` written for target 9 is a modelled token newer than the target: `LossyWriteError`, not droppable ("Lossy writes are refused unless allowed").
   - Rejected: dropping `press_fit` for target 9 with a warning. 9.0.9 would lose it silently on load; the script asked for it.
3. **Generated definitions in `Fenolite_Assembly`.** `dsl/assembly.py` builds the footprints and symbols from model types, as c0102's `dsl/holes.py` does, and registers each once per lib id. The build needs no step of its own.
   - Rejected: KiCad's library parts. They carry no mark, marking a copy gives a mismatch (measurement 3), they need the fetched libraries, and their clear area is a pad clearance the copper check ignores (measurement 7). Rejected: leaving the geometry to each script.
4. **A fiducial is two unnumbered pads and a courtyard.** The copper pad (`circle`, `copper`, on `F.Cu` and `F.Mask`) carries `fiducial_global` or `fiducial_local`; an aperture pad (`circle`, `mask`, on `F.Mask` only) opens the mask; a courtyard circle of the clear diameter sits on `F.CrtYd`. Kind `smd`, flag `exclude_from_bom`: listed in the position file, absent from the BOM, as KiCad's library fiducials (measurements 4 and 6).
   - Rejected: a mask margin on the copper pad, the form of KiCad's library: the model has no such field, and the roadmap line `authored-pad-options` owns it. Rejected: the copper pad on `F.Cu` only, which IPC-D-356 reports as covered (`S3`).
5. **The clear area is a keep-out, made by c0103's `rule_area`.** The maintainer decided on 2026-10-07 (decision 2) that `rule_area` is the one script call for a keep-out and that c0096's `Design.keepout(key, …)` adapts to it, so there is one id (`area:<name>`), one rebuild rule and one predicate for a part inside a keep-out (c0113's `place.keepout`). `fiducial()` calls `rule_area(f"clear_{ref}", outline, layers=(<copper layer of the side>,), forbid=("tracks", "vias", "pours"))`; `tooling_hole(clear=…)` does the same on every copper layer. Pads stay allowed, so the fiducial's own pads are not reported (measurement 9).
   - *Outline.* Model outlines hold points only (c0103). The octagon has the apothem `a = ⌈clear / 2⌉` and the corner offset `b = ⌈√(2a²)⌉ − a`, computed with `math.isqrt`, with vertices `(x ± a, y ± b)` and `(x ± b, y ± a)`. It contains the circle of diameter `clear` and has about 5.5 % more area.
   - *Locked.* A keep-out stays where the script drew it, so fiducials and tooling holes are always locked; neither call takes `locked`.
   - Rejected: the pad's own clearance (measurement 7): the copper check ignores it. Rejected: a clearance rule by reference (measurement 8): it matches nothing until c0077, and a class minimum of priority 1 written after it would govern instead (`H-K-DRU-ORDER`).
6. **A test point is one marked pad.** Pad `1`, `circle` or `rect`, SMD on `F.Cu` and `F.Mask` or plated through-hole on `*.Cu` and `*.Mask`, `test_point` mark; courtyard of the pad size or of `courtyard`, on both sides for a through-hole pad. Kind `unspecified`, flags `exclude_from_pos_files` and `exclude_from_bom`, as KiCad's bare test points. The symbol has one passive pin, reference prefix `TP`, `in_bom` false. `test_point()` connects pin 1 to its net; it is unlocked by default.
   - Rejected: `in_bom` true, as KiCad's `Connector:TestPoint`. A bare pad is never bought, and the symbol and the footprint flag then agree.
7. **A tooling hole is c0102's hole under its own library name.** By the same decision, `design.hole()` is c0102's locked part with a generated footprint, and c0096's neutral `Hole` and `MechanicalIntent` adapt to it. c0096 also reports duplicate drill intents and records reservations on existing drills: a tooling hole is one part with one drill, declared once, and task 3.4 proves that c0096's check does not report it. One unnumbered `np_thru_hole` pad, courtyards on both sides and the two exclusion flags, as `design.hole()` makes, but named `Fenolite_Assembly:ToolingHole_<d>mm`, with `_Clear<c>mm` when `clear` is given. The symbol is c0102's `Fenolite_Holes:Hole`. The library name is the tooling mark: KiCad has no pad mark for it.
   - Rejected: `pad_prop_mechanical`, which KiCad's library uses for connector shields. Rejected: `hole()` with a flag that no file keeps.
8. **Authored pads take `fab_property=`.** `castellated` and `mechanical` are refused on a pad that is not `thru_hole`, the two cases KiCad's DRC flags (measurement 2).
   - Rejected: accepting them, which gives a `padstack` warning on every `check`.
9. **The report reads the board file, as `pnp` does.** `exports.testpoints.report(design, pads, *, side)`:
   - *Test points.* Every pad marked `test_point`. Its access is the set of sides where the pad has both the copper layer and the mask layer: `top`, `bottom`, `both` or `none`. That is IPC-D-356's side code reduced by its mask code (measurement 5).
   - *Fiducials.* Every footprint with a pad marked `fiducial_*`. *Holes.* Every `np_thru_hole` pad; `tooling` is true for `Fenolite_Assembly:ToolingHole_*`.
   - *Coverage.* A net with at least two pads is eligible; it is covered when a test point on it has the asked side in its access.
   - *Findings.* Without values: `testpoint.covered` and `testpoint.no-net` (warnings), `testpoint.none` (info). With the user's values: `testpoint.coverage-low`, `testpoint.too-close` and `fiducial.too-few` (errors, exit 5).
   - Rejected: a `check` stage, whose gates would all need values. Rejected: finding unmarked test points by footprint name; the `testpoint.none` hint names the two ways to mark them.
10. **The CSV uses the template's placement frame.** Fixed columns `kind,ref,pad,net,x,y,side,access,width,height,drill`, in the origin, Y axis, units, decimals and side names of the template's `[placement]` table, so test points and parts share one frame.
    - Rejected: a `[testpoints]` table in c0064's template, a schema change for columns nobody asked for.
11. **Fiducial rows in the placement table.** `PlacementRow.fiducial`, the column field `fiducial` (`yes` or empty) and the key `fiducials` (default `true`) in `[placement]`. The default keeps KiCad's own file (`H-K-POS-ROWS`).
    - Rejected: dropping fiducials by default, or a mount value `fiducial`, which would change `smd_only`.
12. **The IPC-D-356 reader keeps the mask code.** `Ipcd356Record.covered` from the `S` field: `S0` none, `S1` top, `S2` bottom, `S3` both. The oracle compares it and the side with the report's access.
    - Rejected: a second parser in the oracle test, which could disagree with the reader that `check` uses.
13. **Altium: test points are written, fiducials and tooling holes are left out.** `dev` writes the PCB library and document (c0085) and the schematic (c0086) through one lowering (c0126), so each of the three parts was checked against `pcblib.check_footprint` (Context):
    - A test point is one numbered pad with copper and a symbol with one pin: it is written like any authored part, and its pad is on its net in the PCB document. Leaving it out would give the Altium board one pad fewer on that net than the KiCad board of the same script.
    - A fiducial holds two unnumbered pads, one of them without copper; a tooling hole holds one unnumbered pad. Both footprints are refused, and a refused footprint withholds the whole PCB document. They are therefore left out before the check, in the schematic too (a fiducial symbol has no pin, a hole symbol none), with one `altium.not-lowered` info of the kind `assembly features`.
    - The mark is written nowhere: no public source read for Fenolite says where an Altium pad record holds a test-point or fiducial flag, and the format rule forbids a guess. Every written footprint with a marked pad is named by one `altium.not-lowered` info of the kind `pad properties`. No row of the Altium rule table (c0084) is concerned: this change adds no rule kind and no selector.
    - The keep-outs of fiducials and tooling holes are board keep-outs; the living "PCB document output" already reports a board's keep-outs as not lowered, and c0103 says what its `rule_area` does in an Altium build. This change adds nothing to that.
    - If c0102's final text writes its hole parts into the PCB document, a tooling hole takes the same path; task 0.1 reads c0102's living requirement and corrects this decision and its requirement before task 3.5.
    - Rejected: leaving test points out as well (the text before 2026-10-07, written when no PCB document was planned): it drops a net pad for no format reason. Rejected: writing the fiducial as a numbered pad without its mask aperture: it would be another footprint than the KiCad one under the same name.
14. **Other changes that hold the same requirements or names** (checked 2026-10-07 on `origin/dev` at `9aba2dff`, and against the review of the 26 proposals of v0.4).
    - c0102 and c0103 land first (Prerequisites); c0064, c0065 and c0066 are archived, so the fiducial rows are ADDED to the living `assembly-outputs`, `testpoints --manifest` and `paged` are written unconditionally, and the "if archived" branches are gone.
    - "IPC-D-356 parsing" (`kicad-file-backend`): the living text is the text the delta was written on, and no open change on `dev` holds a delta of it.
    - "Artefact states" (`manufacturing-exports`): modified here (the derived kind `testpoints`), and by c0116, c0117 and c0105. **Order: c0116, c0117, c0118, c0105.** The delta is the living text of `9aba2dff` with only `testpoints`; task 0.1 regenerates it from the living text of the day, keeping the kinds of c0116 and c0117.
    - "Manifest option of producing commands" (`cli-contract`): modified here (`testpoints` beside `bom` and `pnp`) and by c0116 (the `layer`, `from` and evidence of document kinds). c0116 first; task 0.1 regenerates.
    - `altium-build`: nine open changes on `dev` hold deltas of the capability (c0084 to c0088, c0090, c0092, c0121, c0126), none of a requirement named here. The requirement of this change leans on "PCB document output" and "PCB issue codes" as they are on `dev`; c0102 modifies "PCB document output", and task 0.1 re-reads the requirement on its text.
    - `schemas/fenolite.model.v0/board.json` is regenerated by this change (`fab_property`) and by c0096, c0099, c0108, c0112, c0114, c0121 and c0126: additive keys that do not clash; the order of landing decides who regenerates last. c0126 and this change both edit `_fpmap` and `embed.place_footprint`, in different functions.
    - c0077 is not required: until it lands, KiCad's own position file and Gerber attributes show generated parts without a reference, and the oracle pairs rows by position. c0110 may read the `bga` mark; c0113 owns local fiducials near a part.
    - Rejected: waiting for c0077. It changes only what KiCad's own outputs print for the generated parts.
15. **Guide line.** If c0080 is archived first, the three calls and `testpoints` get one tested line each on its guide page (task 7.2).
    - Rejected: writing the lines now, before the page and its test exist.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/board.py` | `PadFabProperty`; `Pad.fab_property: PadFabProperty \| None = None` |
| `schemas/fenolite.model.v0/*.json` | regenerated |
| `src/fenolite/backends/kicad/_fpmap.py`, `pcb.py`, `mod.py`, `embed.py` | `FAB_PROPERTY_TOKENS`; read, emit and place the mark; `CANONICAL_ORDER["pad"]`, `PAD_CANONICAL` |
| `src/fenolite/backends/kicad/ipcd356.py` | `Ipcd356Record.covered` |
| `src/fenolite/dsl/footprint.py` | `Footprint.pad(…, fab_property=None)` |
| `src/fenolite/dsl/assembly.py` (new) | `ASSEMBLY_LIBRARY`, `fiducial_footprint`, `test_point_footprint`, `tooling_hole_footprint`, `fiducial_symbol`, `test_point_symbol`, `clear_outline(x, y, diameter)` |
| `src/fenolite/dsl/design.py` | `Design.fiducial`, `Design.test_point`, `Design.tooling_hole` |
| `src/fenolite/exports/testpoints.py` (new) | `TestPointRow`, `FiducialRow`, `HoleRow`, `Coverage`, `Report`, `report`, `findings`, `csv_table`, `TOOLING_PREFIX`, `EVIDENCE` |
| `src/fenolite/exports/placement.py`, `assembly.py`, `codes.py` | `PlacementRow.fiducial`, `PlacedRow.fiducial`, `PlacementTemplate.fiducials`, the field `fiducial`; the six codes |
| `src/fenolite/cli/cmd_testpoints.py` (new) | `fenolite testpoints` (`paged="test_points"`, `--manifest`) |
| `src/fenolite/exports/states.py` | `testpoints` in `DERIVED` |
| `src/fenolite/cli/data/explain.toml` | one entry per new code |
| `src/fenolite/lens/altium.py`, `backends/altium/lower.py` | fiducial and tooling-hole parts left out before the footprint check; the two not-lowered kinds |
| tests | `tests/unit/model/test_pad_fab_property.py`; `tests/unit/backends/kicad/test_pad_fab_property.py`, `test_ipcd356.py`; `tests/unit/dsl/test_assembly_features.py`, `test_footprint_fab_property.py`; `tests/unit/exports/test_testpoints.py`, `test_placement.py`; `tests/unit/cli/test_testpoints_cmd.py`; `tests/unit/lens/test_build_assembly.py`; `tests/kicad/assembly/_featurebench.py`, `test_pad_properties.py`, `test_features_oracle.py`, `test_testpoints_d356.py` |
| docs | `docs/dsl.md` ("Assembly and test features"), `docs/assembly.md` (the report, fiducial rows), `docs/cli-contract.md`, `docs/formats/kicad/board.md` and `libraries.md` (the facts of measurements 2 to 9) |

Public names a script sees: `Design.fiducial`, `Design.test_point`, `Design.tooling_hole`, `Footprint.pad(fab_property=)`. CLI: `fenolite testpoints PATH [--side top|bottom|both] [--template FILE] [--min-coverage PERCENT] [--min-pitch LENGTH] [--min-fiducials N] [-o FILE] [--manifest]`. Model field: `Pad.fab_property`. Issue codes: `testpoint.covered`, `testpoint.no-net`, `testpoint.none`, `testpoint.coverage-low`, `testpoint.too-close`, `fiducial.too-few`. Manifest kind: `testpoints`.

## Sources registered by this change

None. The KiCad facts rest on S-0020 and S-0029 (the two oracles), the library counts on S-0018, S-0042 and S-0043, the corpus on S-0024. The panel tool named in Open Questions is registered by the change that takes that option.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-PAD-FABPROP | A pad's `(property pad_prop_<x>)` loads on 9.0.9 and 10.0.6 for `bga`, `fiducial_glob`, `fiducial_loc`, `testpoint`, `heatsink`, `castellated` and `mechanical`, and on 10.0.6 for `pressfit`, which 9.0.9 drops; 10.0.6's re-save keeps it; the copper Gerber function is `BGAPad,CuDef`, `FiducialPad,Global`, `FiducialPad,Local`, `TestPad`, `HeatsinkPad`, `CastellatedPad`, `SMDPad,CuDef` (mechanical, SMD) and `ComponentPad` (press-fit, through-hole); `pos` and `ipcd356` are equal with and without it; `castellated` and `mechanical` on an SMD pad give `padstack` (S-0020, S-0029) | `tests/kicad/assembly/test_pad_properties.py` | probes `pad-fabprop-<value>`, `pad-fabprop-outputs` and `pad-fabprop-padstack` `equal` on both majors |
| H-K-PAD-FABPROP-LIB | A board pad whose mark differs from its library pad gives one `lib_footprint_mismatch` for the footprint; a footprint whose library copy carries the same mark gives none (S-0020, S-0029) | `tests/kicad/assembly/test_pad_properties.py -k lib` | `pad-fabprop-lib-mismatch` `present`, `pad-fabprop-lib-same` `absent`, on both majors |
| H-K-FIDUCIAL-FORM | The fiducial of Decision 4, on either side, loads with no violation of its own, flashes the mask diameter on its mask layer, and gives one `327N/C` IPC-D-356 record with `S2` on the top and `S1` on the bottom (S-0020, S-0029) | `tests/kicad/assembly/test_features_oracle.py -k fiducial` | `asm-fiducial-drc` `absent`, `asm-fiducial-mask` and `asm-fiducial-d356` `equal`, on both majors |
| H-K-FIDUCIAL-KEEPOUT | The keep-out of Decision 5 gives `items_not_allowed` for a track through it and nothing for the fiducial's pads; a refill on 10.0.6 leaves no fill closer to the centre than the apothem (S-0020, S-0029) | `tests/kicad/assembly/test_features_oracle.py -k keepout` | `asm-keepout-track` `present` on both majors; `asm-keepout-fill` `equal` on 10.0.6 |
| H-K-TESTPOINT-D356 | Each pad marked `testpoint` has one IPC-D-356 record with its net and position; the side code is `A01` for an SMD pad on `F.Cu`, `A02` on `B.Cu`, `A00` through-hole; the mask code is `S2`, `S1` and `S0` when the pad's own mask layers open it, and `S3` for a top SMD pad without one (S-0020, S-0029) | `tests/kicad/assembly/test_testpoints_d356.py` | probe `asm-testpoint-d356` `equal` on both majors for the four cases; the report's rows agree |

All five start `INFERRED`, with the measurements of "Context" as their first record. Ids used without changing their level: `H-K-PCB-POS`, `H-K-POS-ROWS`, `H-K-NET-IPC`, `H-K-DRU-ORDER`, and the two that c0103 and c0102 register before this change lands, `H-K-AREA-KEEPOUT` and `H-K-HOLE-FOOTPRINT` (task 0.1 checks that both rows exist under these names). The inventory rows `pad-property-mechanical` and `pad-property-pressfit` keep their labels.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| marks read and written, Gerber functions, outputs unchanged | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-PAD-FABPROP` |
| no mismatch for generated definitions | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-PAD-FABPROP-LIB` |
| fiducial form | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-FIDUCIAL-FORM` |
| keep-out | KICAD-VERIFIED (9.0.x, 10.0.x) for the track, (10.0.x) for the refill | `H-K-FIDUCIAL-KEEPOUT` |
| test-point rows and access | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-TESTPOINT-D356` |
| script calls, coverage, findings, CSV | mechanical | unit tests |

`exports.testpoints.EVIDENCE` starts `INFERRED` (`H-K-TESTPOINT-D356`, `H-K-PAD-FABPROP`) and rises to `KICAD-VERIFIED` when both hold on both majors.

## Risks / Trade-offs

- **Boards Fenolite did not build show no test points.** KiCad's library parts carry no mark (Context). Mitigation: `testpoint.none` names the two ways to mark a pad; marking a library copy in KiCad works, with the mismatch KiCad then reports.
- **A keep-out does not follow its part.** Fiducials and tooling holes are locked; a `place()` on their parts raises, as a second placement does.
- **The octagon takes more room than the circle**, up to 8.2 % further out at its corners. The value stays the user's; the shape is stated in `docs/dsl.md`.
- **KiCad's mask-bridge check misses the aperture pad's opening** (measurement 8). The keep-out is at least as wide as the opening (`clear` ≥ `mask` is enforced), so no other copper is inside it.
- **Area names.** `clear_<ref>` may collide with a user's area; c0103's uniqueness check names it.
- **c0077 later than this change.** KiCad's own files name generated parts with an empty reference; Fenolite's `pnp` and `testpoints` name them by path.
- **A new modelled child.** A read board's marks become modelled; a written board must stay tree-equal, which the corpus round trip proves (task 2.2).

## Migration Plan

- Additive. A script without the new calls builds the same bytes. Canonical JSON omits `fab_property` when `None`, so `.fenolite/` files of existing builds keep their bytes; the schema gains one optional key. A model document of 0.2.x or 0.3.0 loads as it is. The other direction does not hold: 0.2.x and 0.3.0 cannot read a document that carries `fab_property`, because their reader refuses an unknown key; `docs/design-model.md` and the changelog say so (task 2.1).
- An Altium build of a script that uses none of the three calls and no `fab_property=` writes the same files as before.
- Boards read before keep their bytes: marks move from opaque slots to modelled children with the same text.
- The default template gives the same placement rows; `fiducials = false` is opt-in.
- `Ipcd356Record.covered` has a default; existing callers are unchanged.
- Rollback: remove the calls, the command and the reader mapping; marks become opaque again.

## Budget (5.75 days)

| part | days |
|---|---|
| registers; probes of measurements 2 to 9 recorded on both majors | 1.0 |
| model field, reader and writers, version gate, schemas, corpus round trip | 0.75 |
| `Footprint.pad(fab_property=)` | 0.25 |
| `dsl/assembly.py`, the three calls and their keep-outs | 1.0 |
| `exports.testpoints`, `fenolite testpoints`, the CSV | 1.25 |
| IPC-D-356 mask code and the report oracle | 0.25 |
| fiducial rows in the placement table | 0.25 |
| Altium: test points written, fiducials and tooling holes left out, the two infos | 0.5 |
| documentation and closing | 0.5 |

Cut order: (1) fiducial rows in the placement table; (2) `tooling_hole()`, after which tooling holes are c0102's holes and appear as `hole` rows; (3) the CSV of `testpoints`; (4) `--min-pitch` and `--min-fiducials`; (5) `Footprint.pad(fab_property=)`. Never cut: the model field with its KiCad mapping and probes, `fiducial()` and `test_point()` with their oracle, and the report with coverage and its IPC-D-356 oracle.

## Open Questions

- **A panel.** Measured: `kicad-cli` 10.0.6 has no panel command; KiCad's library holds 31 panelization footprints (mouse bites, break lines). The options, not chosen here:
  1. *None.* The fabricator panelizes from the single-board data; the request (rails, panel fiducials, tooling holes) goes into the fabrication notes of c0117. No cost here; panel fiducials and rails are outside Fenolite's checks.
  2. *An own step,* `fenolite panel`: a new board with N copies of the routed board, new uuids and net names per copy, a frame with rails, tabs with mouse bites or V-cuts, panel fiducials and tooling holes, then `check`, `fill` and `export` on the panel. More than 10 design-days; it overlaps layout replication (roadmap v0.5b).
  3. *An external tool behind a process boundary.* KiKit states the MIT licence (https://github.com/yaqwsx/KiKit) and documents `kikit panelize -p <preset.json> input.kicad_pcb output.kicad_pcb`, with preset sections for framing, tabs, cuts, tooling and fiducials (https://yaqwsx.github.io/KiKit/latest/panelization/cli/). What it needs at run time and which KiCad versions it supports were not found on those pages; both need a probe on both majors. Fenolite would run it as a plugin under ADR-0006, as the routers, and then check and export the panel board. About 4 design-days with probes, plus a version to pin.
- **Should `clear` default to the mask diameter?** Default: yes, the smallest area that keeps other copper out of the opening.
- **Should unmarked test points be found by footprint name** (`TestPoint:*`)? Default: no; the `testpoint.none` hint says how to mark them.
- **Which nets count for coverage?** Default: every net with two pads or more; no option to leave nets out.
- **Should generated fiducials stay in the position file?** Default: yes, as KiCad's library fiducials; `fiducials = false` drops them from a template's table.
