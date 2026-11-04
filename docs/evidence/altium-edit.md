# Altium edit sessions: the maintainer's check

This page is the protocol by which the maintainer shows Fenolite what Altium Designer does to its own
documents when one object is edited, and later checks the documents that Fenolite's edit session writes
(change c0241, package 12 of c0175; capability `altium-edit`). Nothing on this page is verified yet.

- Results are recorded in the form of the native acceptance inventory (date, version, case, file hash, step,
  expected and observed outcome) under "Reports", and the rows `H-A-EDIT-*` and `H-A-INTEG-*` of
  `docs/hypotheses.md` change only from a recorded report.
- **Licence rule.** Part J needs Altium Designer under a licence the maintainer may use for Fenolite
  (`LEGAL.md`, block A, P3 and P4). A result obtained with any other licence is **not recorded**.
- **Observation only.** The documents are authored for Fenolite and built by Fenolite. Fenolite reads what
  Altium saved with its own readers (`fenolite diff A B --view records`, `fenolite inspect`); no vendor
  software is decompiled or traced, and no third-party parser is read for code.
- Every file Altium saves stays in the maintainer's folder. Only counts, record kinds, key names, digests
  and sizes derived from them enter the repository, after `fenolite kit verify`'s path scan has run on the
  folder (`docs/altium-kit.md`, "What a saved file may contain").

## Part J: edit sessions

Change c0241; pending, no Altium verification is claimed. Fenolite reads Altium documents losslessly and
writes compound files, but it has no edit session yet: no write code of the session exists until phase A is
reported (task 1.2 of c0241). Phase A (task 1.1 builds it, task 1.2 is the maintainer's run) observes what
Altium Designer changes in a document when it makes one edit: each case makes one change to the kit's own
document and saves it under its own name, and Fenolite compares the saved file with the plain resave of J1,
so that what a save rewrites anyway is kept apart from what the edit changed. Phase B (task 4.2) asks Altium
to open what Fenolite's session writes, and to open copies with one planted fault each. Every operation of
the session stays behind its own gate, off by default, until its phase B case passes (c0092's graduation
rule), and the integrity rules report `warning`, not `error`, until their cases pass.

**Files of phase A.** Built outside the repository by `FENOLITE_ALTIUM_PART_J=~/fenolite-altium-checks/session-7/J-edit
uv run pytest tests/unit/backends/altium/test_part_j.py -k phase_a`: `board/`, the fixture
`tests/data/altium_edit/edit.py` built with `--target altium --altium-pour outline` (`edit.PrjPcb`,
`edit.PcbDoc`, `edit.PcbLib`, `edit.SchDoc`, `edit.SchLib` and `edit.OutJob`), a two-layer 40 × 30 mm
rectangle authored for Fenolite; `expected.md`, every item the cases name, read back from
`board/edit.PcbDoc` with Fenolite's reader; `README.md`, these steps in Brazilian Portuguese; `PART-J.md`,
this text; and `SHA256SUMS`. Coordinates are millimetres from the board's lower-left corner, which is the
document's origin, Y up. **Files of phase B** (task 4.1): `written/`, `faults/` and `expected-b.md`.

| item | where | what it is |
|---|---|---|
| `R1`, `R2` | (12, 20) and (12, 12) | resistors `Mini_R_0603` on the top, Comment `1k` |
| `D1` | (26, 15) | through-hole LED `Mini_LED_THT_3mm` on the top |
| track `probe` | (10, 5) to (20, 5), Top Layer | 0.25 mm on `GND`, ending on a `GND` via at (20, 5) |
| polygon `GND` | Bottom Layer, (1, 1) to (39, 29) | pour index 0, written without poured copper |
| polygon `VIN` | Top Layer, (2, 22) to (8, 28) | pour index 1, fed by a `VIN` via at (5, 25) |
| text `FENOLITE EDIT` | (30, 4), Top Overlay | a free text |
| line and filled region | Mechanical 13 | a line from (2, 2) to (12, 2) and a region (30, 24) to (36, 28) |
| rule `Clearance` | | the clearance rule, 0.2 mm |

Work on a copy of the folder. Each case from J3 on starts from `board/edit.PcbDoc` as the kit wrote it
(J17 from the file of J16, J18 to J20 from `board/edit.SchDoc`, J21 from `board/edit.PcbLib`): open it
again with **File » Open**, make only the change of the case, and save it with **File » Save As** into
`board/` under the name given. Never save the kit's own documents in place. When Altium asks whether to save
`edit.PrjPcb` or another document, answer No. For each case report `as expected` or what differed, in one
sentence, and any message Altium showed.

*Phase A, observation:*

1. **J1** Open `board/edit.PrjPcb` and `board/edit.PcbDoc`. Save it unchanged with **File » Save As** as
   `J01-resave.PcbDoc`. Expected: the document opens with no repair message and saves without a message.
2. **J2** Close `J01-resave.PcbDoc`, open it again and save it unchanged as `J02-resave.PcbDoc`. Expected:
   it opens and saves without a message.
3. **J3** Select the track `probe` and set Start Y and End Y to 6 mm in Properties (a move of 1 mm up). Save
   as `J03-move-track.PcbDoc`. Expected: only the track moves; the via stays at (20, 5).
4. **J4** Select `R1` and set its X to 14 mm. Save as `J04-move-component.PcbDoc`. Expected: `R1` moves with
   its pads and texts; the tracks stay where they were.
5. **J5** Set the Width of the track `probe` to 0.3 mm. Save as `J05-width.PcbDoc`. Expected: only the width
   changes.
6. **J6** Set the Comment of `R1` to `2k2`. Save as `J06-comment.PcbDoc`. Expected: the comment text of `R1`
   reads `2k2`.
7. **J7** Change the free text `FENOLITE EDIT` to `FENOLITE EDIT 2`. Save as `J07-text.PcbDoc`. Expected:
   the new text shows.
8. **J8** Set the Rotation of `R2` to 90. Save as `J08-rotate.PcbDoc`. Expected: `R2` turns about its
   origin with its pads and texts.
9. **J9** Set the Layer of `D1` to Bottom Layer in Properties (flip). Save as `J09-flip.PcbDoc`. Expected:
   `D1` lies on the bottom side, mirrored, its overlay on Bottom Overlay.
10. **J10** Delete the track `probe`. Save as `J10-delete-track.PcbDoc`. Expected: the via stays.
11. **J11** Delete `R2`. Save as `J11-delete-component.PcbDoc`. Expected: `R2` goes with its pads and texts;
    the tracks that ended on it stay.
12. **J12** Select the track `probe` and its via, **Edit » Copy** with the via as reference point, **Edit »
    Paste** and click 3 mm above the via, clear of other copper. Save as `J12-copy.PcbDoc`. Expected: a
    second track and via; note the net the copies show.
13. **J13** **Place » Component**: in the Components panel choose `edit.PcbLib` (if it is not listed, add it
    from `board/` as a file-based library) and its footprint `Mini_R_0603`; place it near (32, 22) and note
    the designator Altium gives. Save as `J13-place-component.PcbDoc`. Expected: one more component with
    two pads.
14. **J14** Select the line and the filled region on Mechanical 13 and set their Layer to Mechanical 15.
    Save as `J14-layer.PcbDoc`. Expected: both show on Mechanical 15.
15. **J15** **Design » Rules**, rule `Clearance`: set the minimum clearance to 0.25 mm. Save as
    `J15-rule.PcbDoc`. Expected: the rule shows 0.25 mm when the editor is opened again.
16. **J16** **Tools » Polygon Pours » Repour All**. Save as `J16-repour.PcbDoc`. Expected: both polygons pour
    without a message.
17. **J17** Open `J16-repour.PcbDoc`, delete the polygon `VIN` (with its copper). Save as
    `J17-delete-polygon.PcbDoc`. Expected: `GND` keeps its copper; note the Pour Index that the Polygon
    Manager (**Tools » Polygon Pours » Polygon Manager**) shows for `GND`.
18. **J18** Open `board/edit.SchDoc`, select `R1` and set its X 10 mm further right in Properties. Save as
    `J18-sch-move.SchDoc`. Expected: `R1` moves; note whether its wires followed.
19. **J19** In `board/edit.SchDoc` change the text `1k` of `R1` (its Comment or Value, the one that shows
    `1k`) to `2k2`. Save as `J19-sch-parameter.SchDoc`. Expected: `R1` shows `2k2`.
20. **J20** In `board/edit.SchDoc` delete `R2`. Save as `J20-sch-delete.SchDoc`. Expected: `R2` goes; its
    wires stay.
21. **J21** Open `board/edit.PcbLib`, footprint `Mini_R_0603`: set the X of pad 1 to -0.9 mm. Save as
    `J21-library.PcbLib`. Expected: only that pad moves.
22. **J22** Close Altium, zip the folder without the `History` and `Project Outputs` folders, and send it.
    Expected: Fenolite runs `fenolite kit verify`'s path scan before anything is read.

*Phase B, confirmation (files written by Fenolite after tasks 3.1 to 3.4, each operation's gate forced on
for the kit only; the planted faults of `faults/` are written by the same session with the integrity check
off):*

23. **J23** Open each PCB document of `written/`, one per operation of the session (`move`, `rotate`,
    `flip`, `set_property`, `delete`, `clone`, `add_component`, `remap_layer`, `set_rule`), each written
    from `J01-resave.PcbDoc` with the change of the matching case of phase A; save it as
    `<name>-saved.PcbDoc`, close it and open the saved file. Expected: no repair message at either opening;
    the object shows as `expected-b.md` says; Fenolite's read-back of the saved file equals the written file
    outside the records that a resave rewrites (`H-A-RD-RESAVE`).
24. **J24** The same for the schematic documents of `written/` (`move`, `set_property`, `delete`).
    Expected: as J23, and Altium's compile of the project lists the same nets as before the edit.
25. **J25** The same for `written/edit-library.PcbLib` (`move` of one pad). Expected: as J23.
26. **J26** Open `faults/subpoly-gap.PcbDoc`, in which one polygon's pieces are numbered 0, 1, 3. Save it as
    `subpoly-gap-saved.PcbDoc`. Expected: report whether it opens, any message, whether the save completes,
    and the numbers the saved pieces hold. Note: 8 of the 81 polygons of the public documents hold numbers
    with gaps (`docs/formats/altium/pcb-pour.md`), so a clean opening is a possible outcome.
27. **J27** The same with `faults/pour-index-twice.PcbDoc`, in which both polygons hold Pour Index 0.
    Expected: report as J26, and the Pour Index each polygon shows in the Polygon Manager.
28. **J28** The same with `faults/unique-id-twice.PcbDoc`, in which two pads share one unique id. Expected:
    report as J26.
29. **J29** The same with `faults/parameter-count.PcbDoc`, in which a parameter group counts one record
    more than it holds. Expected: report as J26. Dropped when no file of phase A holds a parameter group.
30. **J30** The same with `faults/parameter-orphan.PcbDoc`, which keeps the parameter records of a deleted
    component. Expected: report as J26. Dropped when no file of phase A holds a parameter group.
31. **J31** The same with `faults/model-unused.PcbDoc` (a model-store entry that no body names) and
    `faults/model-missing.PcbDoc` (a body that names a model the store does not hold). Expected: report as
    J26 for each.
32. **J32** The same with `faults/layer-fields.PcbDoc`, in which the filled region's layer byte names
    Mechanical 13 and its `V7_LAYER` names Mechanical 15. Expected: report as J26, and the layer on which the
    region shows.
33. **J33** Close Altium, zip the folder without the `History` and `Project Outputs` folders, and send it.
    Expected: Fenolite runs `fenolite kit verify`'s path scan before anything is read.

Send the Altium Designer version (`AD <major>.<minor>`, from **Help » About**), the date, the SHA-256 of
each file sent (the kit's own are in `SHA256SUMS`), and one outcome per case, in the form of the native
acceptance inventory (date, version, case, file hash, step, expected and observed outcome). J1 and J2 settle
the observation of `H-A-EDIT-RESAVE`; J3 and J4 of `H-A-EDIT-MOVE`; J5 to J7 of `H-A-EDIT-PROPERTY`; J8 of
`H-A-EDIT-ROTATE`; J9 of `H-A-EDIT-FLIP`; J10, J11 and J17 of `H-A-EDIT-DELETE`; J12 of `H-A-EDIT-CLONE`;
J13 of `H-A-EDIT-ADD`; J12 and J13 of `H-A-EDIT-IDS`; J14 of `H-A-EDIT-LAYER`; J15 of `H-A-EDIT-RULE`; J18
to J20 of `H-A-EDIT-SCH`; J21 of `H-A-EDIT-LIBRARY`. J23 to J25 settle `H-A-EDIT-KIT` and decide each
operation's gate. The integrity rows are observed in phase A and settled in phase B: `H-A-INTEG-SUBPOLY` by
J16 and J26, `H-A-INTEG-POURINDEX` by J17 and J27, `H-A-INTEG-ID` by J12, J13 and J28,
`H-A-INTEG-PARAMCOUNT` by J1, J6 and J29, `H-A-INTEG-PARAMORPHAN` by J11 and J30, `H-A-INTEG-MODEL` by J31
and `H-A-INTEG-LAYER` by J14 and J32. Saved native files stay outside the repository; only measured facts,
digests and sizes are committed.

## What Fenolite does with the files

1. `fenolite kit verify`'s path scan on the returned folder; its list is read before anything else.
2. The SHA-256 of each kit file against `SHA256SUMS`: a kit document that differs was saved in place, and
   the cases that start from it are repeated.
3. `fenolite diff board/edit.PcbDoc board/J01-resave.PcbDoc --view records` gives what a plain save
   rewrites (J1), and J2 against J1 what a second save rewrites. Each case from J3 is then compared with
   J1 (`fenolite diff board/J01-resave.PcbDoc board/J03-move-track.PcbDoc --view records`, and the
   schematic and library cases with the kit's own documents saved alike), so that each record and each
   index table that the edit changed is listed apart from the resave.
4. The integrity invariants of the rows `H-A-INTEG-*` are counted on every saved file (sub-indices of each
   polygon, pour indices, unique ids, parameter groups, model-store entries, the two layer fields of each
   region).
5. What was measured is written into the result cells of the rows, with the report's date and source id,
   and the rows stay `INFERRED` until phase B passes.

## Reports

No report of Part J has been received from the maintainer. The agent run below is not an author report.

### 2026-11-04, actual `AD 24.5.2.23`, phase A J1 to J22 (source S-1316)

A Claude agent ran phase A at the maintainer's request of 2026-11-04, in the Altium Designer installed in
the maintainer's Parallels Windows VM. This is not the maintainer's own review. `X2.exe` is 24.5.2.23
(Trial licence). The kit was built at `7074a68e` into the agent's folder
`~/fenolite-altium-checks/claude-2026-11-04/c0241-J` (2 passed). The agent worked on a copy of `board/`
and used File » Open and File » Save As for every case. Each kit document still matches `SHA256SUMS` after
the run: `edit.PcbDoc` `0f6301a5…`, `edit.SchDoc` `4940e6af…`, `edit.PcbLib` `365b5ff3…`, `edit.PrjPcb`
`21c386b7…`. The project file was never saved.

**Method.** An authored DelphiScript selected each object, and the selection was cleared before every
save. The edit itself was made in one of four ways:

- **P**: the Properties panel, with its fields set through UI Automation.
- **M**: a menu command.
- **UI**: an interactive command; the pointer was placed with Edit » Jump » Location and Enter.
- **S**: an authored DelphiScript through the public PCB, schematic or library interface.

S was used where the Properties field could not be reached: the panel was re-docked narrow after a
restart, and the field lookups timed out. S is a weaker observation than an edit in the panel.

Altium closed with an unhandled exception (`0xeedfade`, then `0xc000041d`) at 10:25 while a selection
script was being started from File » Run Script, between J2 and the repeat of J3. No crash report was
sent. Altium was started again with the same build. The first J3 file had kept a script selection, so it
was deleted and the case repeated. A first J12 paste landed off position and a first J21 edit was lost
before its save; both were discarded unsaved.

The diff column comes from `fenolite diff A B --view records`. It lists the streams whose record counts
change. Each PCB case is compared with `J01`. J2 against J1 shows what a second save rewrites anyway:
`Board6` 1, `FileHeaderSix` 1, `Pads6` 6, `Rules6` 32, `Texts` 1, `Texts6` 7 and `Vias6` 3 records
changed. The cases from J3 also change `Classes6` 14, `PrimitiveGuids` 1 and, after a move, `Connections6`
1 against J1. Only streams beyond that resave set are named below.

| case | file (SHA-256) | way | expected | observed |
|---|---|---|---|---|
| J1 | `J01-resave.PcbDoc` `8e025db3…` | M | opens with no repair message, saves without a message | as expected. Against the kit's document, the save adds 14 `Classes6`, 32 `Rules6` and one record each in `BoardRegions`, `EmbeddedFonts6`, `FileVersionInfo`, `PrimitiveGuids`, `Texts` and `UnionNames`, and changes 33 `Tracks6`, 6 `Pads6`, 3 `Vias6`, 3 `Arcs6` and 3 `Components6` records |
| J2 | `J02-resave.PcbDoc` `fa2c9147…` | M | opens and saves without a message | opens and saves without a message. The second save still changes the records listed above |
| J3 | `J03-move-track.PcbDoc` `b012fac6…` | P | only the track moves; the via stays at (20, 5) | as expected: the track runs (10, 6)–(20, 6), and the via stays at (20, 5). `Tracks6` changes 1 record |
| J4 | `J04-move-component.PcbDoc` `8eb8732e…` | P | `R1` moves with its pads and texts; tracks stay | `R1` is at (14, 20). `Components6` changes 2, `Tracks6` 20 and `Texts6` 4 records. Violation streams are added for clearance, component clearance, short circuit and silk-to-silk. Whether the free tracks stayed was not read |
| J5 | `J05-width.PcbDoc` `6d41066d…` | P | only the width changes | `Tracks6` changes 1 record, and a `TMaxWidthTrackViolation` record is added |
| J6 | `J06-comment.PcbDoc` `fb814f35…` | P | the comment reads `2k2` | the Comment field reads `2k2`. `WideStrings6` changes 1 record |
| J7 | `J07-text.PcbDoc` `d4234eec…` | S | the new text shows | the text reads `FENOLITE EDIT 2`. `Texts6` changes 1 record and `WideStrings6` 1 |
| J8 | `J08-rotate.PcbDoc` `aced1e3e…` | P | `R2` turns about its origin | `R2` is at rotation 90 at (12, 12). `Components6` changes 1 record and `Tracks6` 10 |
| J9 | `J09-flip.PcbDoc` `7412c97b…` | S (Layer set to Bottom) | `D1` on the bottom, mirrored, overlay on Bottom Overlay | `D1` is on the Bottom Layer at rotation 180, and its origin reads (28.55, 15), not (26, 15). One `Tracks6` record is replaced. `UniqueIDPrimitiveInformation` changes 2 records and `WideStrings6` 5. Clearance and short-circuit violations are added. The overlay layer was not read |
| J10 | `J10-delete-track.PcbDoc` `d45f8291…` | M (Edit » Delete) | the via stays | as expected: 1 `Tracks6` record is removed, and all three vias remain |
| J11 | `J11-delete-component.PcbDoc` `b4660ee2…` | M (Edit » Delete) | `R2` goes with its pads and texts; its tracks stay | `R2` is removed with 2 pads, 2 texts and 10 tracks. The count of 10 equals the tracks that one placed `Mini_R_0603` adds in J13, so the free tracks appear to stay |
| J12 | `J12-copy.PcbDoc` `f4d97b62…` | UI (copy with reference at the via, paste at (20, 8)) | a second track and via; note the net | one track (10, 8)–(20, 8) and one via at (20, 8) are added, on `GND`. That place touches the `GND` via at (16, 8). The discarded first paste, at a clear place near (16.1, 29.9), showed the copies with no net |
| J13 | `J13-place-component.PcbDoc` `7896eb7a…` | UI | one more component with two pads; note the designator | the Components panel had no library installed. With `edit.PrjPcb` open it listed the project's `Mini_R`, whose footprint is `Mini_R_0603`. Place MiniR at (32, 22) adds one component `Designator1` with 2 pads, 2 texts and 10 tracks. The file grows to 747520 bytes |
| J14 | `J14-layer.PcbDoc` `a1fbaf46…` | S | both on Mechanical 15 | the line and the region read Mechanical 15. One `Tracks6` record is replaced, and `Regions6` and `ShapeBasedRegions6` each change 1 record |
| J15 | `J15-rule.PcbDoc` `65c5d0f0…` | UI (rules editor) | the rule shows 0.25 mm when reopened | the saved rule holds `GAP=9.8425mil` (0.25 mm), where the kit has `7.874mil`. The reopened editor's list showed only the rule name |
| J16 | `J16-repour.PcbDoc` `941bc082…` | M | both polygons pour without a message | as expected: 2 `Regions6` and 2 `ShapeBasedRegions6` records are added |
| J17 | `J17-delete-polygon.PcbDoc` `1d2fc7c2…` | M (Edit » Delete, from J16) | `GND` keeps its copper; note its Pour Index | as expected: 1 polygon, 1 region and 1 shape-based region are removed. A read-only script gives `GND` Pour Index 0. The Polygon Manager grid did not expose the index |
| J18 | `J18-sch-move.SchDoc` `88b608b8…` | S (move by 10 mm) | `R1` moves; note the wires | `R1` is at (2794, 6300) mil, from (2400, 6300). The wires' first vertices are unchanged |
| J19 | `J19-sch-parameter.SchDoc` `18354348…` | S | `R1` shows `2k2` | as expected: `R1`'s comment reads `2k2` |
| J20 | `J20-sch-delete.SchDoc` `53264a3e…` | M (Edit » Delete) | `R2` goes; its wires stay | as expected: no message, and the six wires remain |
| J21 | `J21-library.PcbLib` `b558bb8d…` | S | only pad 1 moves | pad 1 is at (-0.9, 0) mm, from (-0.8, 0), and pad 2 stays at (0.8, 0). Against the kit's library, both footprints' records change. There is no plain library resave to separate them |
| J22 | the 21 files above | copy without `History` | path scan before reading | `fenolite kit verify` refuses the folder with `FEN-3001` (no `kit.json`). Called directly, the kit privacy scan finds no home folder or login name. Each PCB document and the library hold their own VM path in the file header. `J13` also has one false match inside binary data. The folder cannot be published as it is |

The schematic cases are compared with the kit's `edit.SchDoc`. Each schematic file differs in its
`FileHeader` (64 added, 31 removed and 14 changed records for J18). No plain schematic resave was made,
so the edit cannot be separated from the save there. The saved files stay in `c0241-J/saved/board/`,
outside the repository.

Every `H-A-EDIT-*` and `H-A-INTEG-*` row keeps its level. The run is on 24.5 under the approved scope, by an
agent, and six cases used a scripted edit, so task 1.2 stays open.

## Approved pending-native scope — 2026-11-03

The maintainer explicitly authorized the pending Altium validations on the
available Altium Designer 24.5.2.23: "tenho so o24.5, mas eu autorizo as
validacoes serem no24, nao precisa ser na26". This replaces the version
prerequisite of pending runs only. Record the actual tool/build, input hashes
and each observed outcome. It does not complete a case, open a write gate,
raise evidence, prove26.5 equivalence or replace any historical26.5 report.
Do not combine different versions/input digests into one fictional kit run.
All existing acceptance criteria, facts-before-code rules and final CI remain.
The kit form keeps its existing AD major.minor dialect: use AD 24.5; keep full
build 24.5.2.23 in the separate native observation report, not a new form key.
