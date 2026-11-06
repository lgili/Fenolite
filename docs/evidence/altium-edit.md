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
    from `J01-resave.PcbDoc` with the change of the matching case of phase A, and `shapes`, `create` and
    `set_outline` with the shapes of `expected-b.md` (`H-A-EDIT-SHAPE`, `H-A-EDIT-CREATE`); save it as
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
J13 of `H-A-EDIT-ADD`; J12 and J13 of `H-A-EDIT-IDS`; J23 of `H-A-EDIT-SHAPE` and `H-A-EDIT-CREATE`; J14 of `H-A-EDIT-LAYER`; J15 of `H-A-EDIT-RULE`; J18
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

### 2026-11-04, actual `AD 24.5.2.23`, phase A J1 to J22 (source S-1577)

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
| J4 | `J04-move-component.PcbDoc` `8eb8732e…` | P | `R1` moves with its pads and texts; tracks stay | `R1` is at (14, 20). `Components6` changes 2, `Tracks6` 20 and `Texts6` 4 records. Violation streams are added for clearance, component clearance, short circuit and silk-to-silk. Whether the free tracks stayed was not read. **This file does not hold the move described here**: read on 2026-11-05 (S-1609), it has `R1` at (26, 20) and `R2` at (26, 12) mm. J4's result is the panel redo of S-1610 below |
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

**Evening attempt to redo the scripted cases through the panel (source S-1582).** At the maintainer's
second request of 2026-11-04 the agent tried to redo J7, J9, J14, J18, J19 and J21 through the Properties
panel instead of a script, in the same Altium 24.5.2.23. J12 had already been done through the UI in the
run above. The attempt stopped before any case:

- The right dock showed the Components panel ("No Search Sources found"), left open by J13. The
  Properties tab lay outside the screen, at x 3112.
- Selecting or clicking that tab through UI Automation did not switch the dock to Properties.
- After the agent closed the Components panel, the dock was gone. View » Panels » Properties and F11
  did not bring back a Properties panel that UI Automation could see.

No case was redone, and nothing was saved. The six cases keep their scripted edits from the run above.
Every `H-A-EDIT-*` and `H-A-INTEG-*` row keeps its level.

### 2026-11-05, actual `AD 24.5.2.23`, J4 read and panel redo of six cases (source S-1609)

At the maintainer's delegation of 2026-11-04, relayed by the coordinator, a Claude agent read J4's free
tracks and redid J7, J9, J14, J18, J19 and J21 through the Properties panel. It worked on the phase A bytes
of the run above: the same kit folder, whose `edit.PcbDoc` `0f6301a5…`, `edit.SchDoc` `4940e6af…`,
`edit.PcbLib` `365b5ff3…` and `edit.PrjPcb` `21c386b7…` match `SHA256SUMS` before and after the run.
Phase A was not built again. The cases of the run above that are not named here keep their outcomes.

**Method.** An authored DelphiScript selected each object; it changed nothing else. The Properties panel was
brought back with View » Panels » Properties and opened from its side tab. The S-1582 blocker did not recur:
UI Automation reached every field. Each edit set a field of the panel: **P** in the table below. Each case
opened the kit's own document, was saved with File » Save As in a new folder, and was closed. Every save
showed only the Save As dialog, and no case raised a message. The diff column comes from
`fenolite diff A B --view records`. PCB cases are compared with `J01` and name only the streams beyond the
resave set of the run above. Schematic and library cases are compared with the kit's document.

| case | file (SHA-256) | way | expected | observed |
|---|---|---|---|---|
| J4 (read) | `J04-move-component.PcbDoc` `8eb8732e…` of the run above | read by script | the tracks stay where they were | the nine free tracks (eight on Top Layer for `GND`, `MID` and `VIN`, and one on Mechanical 13) have the same ends, widths and nets as in the kit's document. The same read gives `R1` at (26, 20) and `R2` at (26, 12) mm, against (12, 20) and (12, 12) in the kit's document; `D1` stays at (26, 15). Fenolite's reader gives the same positions. So that file does not hold `R1` at (14, 20), and `R2` moved too, while J4 asks for `R1` alone at X 14 mm |
| J7 | `J07-text.PcbDoc` `1f1013fe…` | P (Text) | the new text shows | the text reads `FENOLITE EDIT 2`. `WideStrings6` changes 1 record |
| J9 | `J09-flip.PcbDoc` `ba7edb2b…` | P (Layer combo, Top Layer to Bottom Layer) | `D1` on the bottom, mirrored, overlay on Bottom Overlay | `D1` is on the Bottom Layer at rotation 180, its origin reads (28.55, 15), and its designator and comment are on Bottom Overlay. `Components6` changes 1 record, `Arcs6` 3, `UniqueIDPrimitiveInformation` 2 and `WideStrings6` 5. One `Tracks6` record is replaced, and a clearance and a short-circuit violation are added. The origin and rotation are those of the scripted edit of the run above |
| J14 | `J14-layer.PcbDoc` `bbbf1fd3…` | P (Layer combo, both objects selected) | both on Mechanical 15 | the line and the region read Mechanical 15, and nothing is left on Mechanical 13. One `Tracks6` record is replaced, and `Regions6` and `ShapeBasedRegions6` each change 1 record, as with the scripted edit |
| J18 | `J18-sch-move.SchDoc` `3cf69fff…` | P (X, 60.96 mm to 70.96 mm) | `R1` moves; note the wires | the field reads 2793.7 mil, and `R1` is at (2794, 6300) mil. The six wires keep all their vertices, so they did not follow |
| J19 | `J19-sch-parameter.SchDoc` `b7224c00…` | P (Comment) | `R1` shows `2k2` | `R1`'s comment reads `2k2` |
| J21 | `J21-library.PcbLib` `6678cc7d…` | P (X of pad 1) | only pad 1 moves | the field reads -0.9 mm. Pad 1 is at (-0.9, 0) mm and pad 2 stays at (0.8, 0). Against the kit's library both footprints' records change, as in the run above |

The schematic files differ from the kit's document in their `FileHeader` (64 added, 31 removed and 14
changed records) and add one `Additional` record, as in the run above. The saved files stay outside the
repository.

Every `H-A-EDIT-*` row keeps its level: the run is an agent run on 24.5 under the approved scope. The J4
finding is the coordinator's to judge: the S-1574/S-1577 file does not show the move that J4 asks for.

**J4 redone through the panel (source S-1610).** On the coordinator's decision of 2026-11-05, the agent redid
J4 on the same phase A bytes (`edit.PcbDoc` `0f6301a5…` before and after). The J04 file of S-1577 did not
contain the move that J4 describes, so this redo is J4's result. Altium had closed at 16:11 with a .NET
runtime fault, after a "System Error. Code: 1158" (window-manager handles used up) while it opened
`edit.PcbDoc`. No crash report was sent. Altium was started again with the same build, and J4 ran in the new
session.

| case | file (SHA-256) | way | expected | observed |
|---|---|---|---|---|
| J4 (S-1610) | `J04-move-component.PcbDoc` `7c002de7…` | P (X of `R1`, 12 mm to 14 mm) | `R1` moves with its pads and texts; tracks stay | the field reads 551.181 mil (14 mm). A read-only script gives `R1` at (14, 20) and `R2` at (12, 12) mm, and Fenolite's reader gives the same. Against the kit's document, only the ten tracks of `R1`'s footprint differ, each moved by +2 mm in X. Every other track keeps its ends and width, including the free track that ends at `R1`'s old pad 1 at (11.2, 20). The save showed only the Save As dialog |

J4 passes. Every `H-A-EDIT-*` row keeps its level, because this is an agent run on 24.5 under the approved
scope.

### 2026-11-04 night, actual `AD 24.5.2.23`, phase B J23 to J33 (source S-1588)

A Claude agent ran phase B at the maintainer's request of 2026-11-04/05, in the Altium Designer installed in
the maintainer's Parallels Windows VM. The tool reports `Client.GetProductVersion` 24.5.2.23 (Trial). This
is not the maintainer's own review. The phase B kit was built at `aa49b069` (`origin/cac/lote-14`), which
holds the session of tasks 3.1 to 3.4. The build ran with `FENOLITE_ALTIUM_PART_J_SAVED` set to the agent's
phase A files of S-1577. Its `expected-b.md` is `354db907…`. Each document was opened on its own in a VM
copy, saved with File » Save As as `<name>-saved`, closed, and opened again. A read-only DelphiScript listed
the messages and objects at both openings. The written files are unchanged after the run. Fenolite's
read-back of each saved file, at `aa49b069`, gives the same record counts as the written file, except where
noted below.

| case | file | expected (`expected-b.md`) | observed in Altium | result |
|---|---|---|---|---|
| J23 move | `move` | GND track at (10, 6)–(20, 6) mm | as expected; no message; the same after save and reopen | pass |
| J23 rotate | `rotate` | R2 at 90° | as expected | pass |
| J23 flip | `flip` | D1 on the bottom | D1 on Bottom Layer at (26, 15) mm | pass |
| J23 set_property | `set_property` | R1 comment `2k2` | as expected | pass |
| J23 delete | `delete` | R2 gone | R2 absent; D1 and R1 remain | pass |
| J23 clone | `clone` | a GND track at (10, 8)–(20, 8) mm and a via at (20, 8) mm | both present; the original track and via remain | pass |
| J23 add_component | `add_component` | R9 at (32, 22) mm, 0°, `Mini_R_0603` | as expected | pass |
| J23 remap_layer | `remap_layer` | the track (2, 2)–(12, 2) mm and the filled region on Mechanical 15 | the region shows on Mechanical 15. The track still shows on Mechanical 13: its layer byte names Mechanical 15 (71), but the rest of its record still holds 13 | fail |
| J23 set_rule | `set_rule` | `Clearance` gap 9.8425 mil | Altium shows the gap as 0.2 mm (7.874 mil). The file's `GAP` is 9.8425 mil and its `GENERICCLEARANCE` is 7.874 mil; the saved file writes `GAP=7.874mil` back | fail |
| J24 | `sch-move`, `sch-parameter`, `sch-delete` | R1 moved; R1 comment `2k2`; R2 deleted with its wires kept | R1 at (2800, 6300) mil against 2400 in phase A; R1 `2k2`; R2 absent with 6 wires, as in phase A. No message. The project's net compile was not run, because the documents were opened on their own | pass, nets not compared |
| J25 | — | `edit-library.PcbLib` | not written (no library session) | dropped |
| J26 | `subpoly-gap` | report the opening, the messages, the save and the saved pieces | opens and saves with no message. Fenolite still reports `altium.integrity.subpoly-gap` on the saved file (pieces 0, 1, 3 of polygon `GND`), and reads 5 shape regions against 3 | observed |
| J27 | `pour-index-twice` | as J26, plus the Pour Index of each polygon | opens with no message. Altium shows Pour Index 2 for `GND` and 1 for `VIN`, against 0 and 0 in the file. The saved file gives no finding | observed |
| J28 | `unique-id-twice` | as J26 | opens and saves with no message. The saved file still has pads D1.1 and D1.2 sharing one unique id (`altium.integrity.unique-id-twice`) | observed |
| J29–J31 | — | parameter and model faults | not written (no parameter group in phase A; no embedded model) | dropped |
| J32 | `layer-fields` | as J26, plus the layer the region shows on | opens with no message. The region shows on Mechanical 15, the layer named by `V7_LAYER`, not by the layer byte (Mechanical 13). The saved file gives no finding | observed |
| J33 | — | path scan before reading | the saved files stay outside the repository in `c0241-JB-native/`; not zipped | not run |

The first Save As of `set_rule` lost the first letter of its typed name (`et_rule-saved.PcbDoc`). It was
saved again under the right name. No level is raised, because this was an agent run. `H-A-EDIT-KIT` and
the `H-A-INTEG-*` rows keep their levels, and every operation's gate stays off. Task 4.2 stays open.

### 2026-11-05, actual `AD 24.5.2.23`, phase B J23 to J33 run again (source S-1612)

A Claude agent ran phase B again on the coordinator's word, after the writer fix of task 4.2 (`af04e20f`).
It used the Altium Designer installed in the maintainer's Parallels Windows VM, which reports
`Client.GetProductVersion` 24.5.2.23 (Trial). This is not the maintainer's own review. The kit was built at
`d45e6533`, with `FENOLITE_ALTIUM_PART_J_SAVED` set to the same phase A files of S-1577 that S-1588 used.
Its `expected-b.md` is `354db907…`, the same as in S-1588. Against the kit of S-1588, four written files
differ:

- `set_rule` also writes `GENERICCLEARANCE` as 9.8425 mil;
- `remap_layer` and `flip` change the long layer id at the end of the moved track and arc records;
- `add_component` gives R9 another unique id.

Every other file is byte-identical to the kit of S-1588. Each document was opened on its own with File »
Open, then a read-only DelphiScript listed the messages since the opening and the objects. It was then
saved with File » Save As as `<name>-saved`, closed, opened again and listed again. No dialog showed at any
opening, save or close, and the Messages panel got no message. The written files are unchanged after the
run. For every case, the listing at the second opening equals the listing at the first.

| case | file | expected (`expected-b.md`) | observed in Altium | result |
|---|---|---|---|---|
| J23 move | `move` | GND track at (10, 6)–(20, 6) mm | as expected | pass |
| J23 rotate | `rotate` | R2 at 90° | as expected | pass |
| J23 flip | `flip` | D1 on the bottom | D1 on Bottom Layer at (26, 15) mm | pass |
| J23 set_property | `set_property` | R1 comment `2k2` | as expected | pass |
| J23 delete | `delete` | R2 gone | R2 absent; D1 and R1 remain | pass |
| J23 clone | `clone` | a GND track at (10, 8)–(20, 8) mm and a via at (20, 8) mm | both present; the original track and via remain | pass |
| J23 add_component | `add_component` | R9 at (32, 22) mm, 0°, `Mini_R_0603` | as expected | pass |
| J23 remap_layer | `remap_layer` | the track (2, 2)–(12, 2) mm and the filled region on Mechanical 15 | both on Mechanical 15 | pass |
| J23 set_rule | `set_rule` | `Clearance` gap 9.8425 mil | Altium reads the gap as 0.25 mm (9.8425 mil). The saved file keeps `GAP` and `GENERICCLEARANCE` at 9.8425 mil | pass |
| J24 | `sch-move`, `sch-parameter`, `sch-delete` | R1 moved; R1 comment `2k2`; R2 deleted with its wires kept | R1 at (2800, 6300) mil against 2400 in phase A; R1 `2k2`; R2 absent with 6 wires, as in phase A. The project's net compile was not run, because the documents were opened on their own | pass, nets not compared |
| J25 | — | `edit-library.PcbLib` | not written: no session edits a PCB library, and there is no sample | not executed |
| J26 | `subpoly-gap` | report the opening, the messages, the save and the saved pieces | opens and saves with no message. Fenolite still reports `altium.integrity.subpoly-gap` on the saved file, and reads 5 shape regions against 3 | observed, as in S-1588 |
| J27 | `pour-index-twice` | as J26, plus the Pour Index of each polygon | opens with no message. Altium reads Pour Index 2 for `GND` and 1 for `VIN`, against 0 and 0 in the file. The saved file gives no finding | observed, as in S-1588 |
| J28 | `unique-id-twice` | as J26 | opens and saves with no message. The saved file still has pads D1.1 and D1.2 sharing one unique id (`altium.integrity.unique-id-twice`) | observed, as in S-1588 |
| J29–J31 | — | parameter and model faults | not written: no file of phase A holds a parameter group, the kit board embeds no model, and there is no sample | not executed |
| J32 | `layer-fields` | as J26, plus the layer the region shows on | opens with no message. The region shows on Mechanical 15, the layer named by `V7_LAYER`, not by the layer byte. The saved file gives no finding | observed, as in S-1588 |
| J33 | — | path scan before reading | Altium was not closed and nothing was zipped. A scan of the saved files finds one absolute path in each saved PCB document: the `FILENAME` key of the board record, which holds the file's own save path in the VM. The saved schematic documents hold none. The saved files stay outside the repository | not run as written |

Fenolite reads back each saved PCB document with the same record counts as the written one, except
`subpoly-gap` (5 shape regions against 3). It gives no integrity finding on any saved written document. Each
saved schematic document holds 33 more parameter records (record 41) than the written one, and the same
components and wires, as in S-1588's saved files.

Both failures of S-1588 are gone: `remap_layer` and `set_rule` pass. Every J23 operation and J24 now
passes on 24.5. J25 and J29–J31 are not executed, and J33 was not run as written. No level is raised,
because this was an agent run. `H-A-EDIT-KIT` and the `H-A-INTEG-*` rows keep their levels, and every
operation's gate stays off. Task 4.2 stays open for the maintainer's decision.

### 2026-11-06, actual `AD 24.5.2.23`, c0452 shapes and creation (source S-2111)

A Claude agent ran the documents of c0452 on the coordinator's word, in the Altium Designer installed in the
maintainer's Parallels Windows VM (24.5.2.23). This is not the maintainer's own review. The edit session of
c0452 wrote each document from `J01-resave.PcbDoc` of S-1577: `shapes`, `create` and `set_outline` with the
changes of phase B, then `arc-moved` and `arc-deleted` from `create`. The kit board holds no fill, so the agent
placed one free fill on the Top Layer in Altium and saved it as the template. The session then wrote
`fill-added`, `fill-moved` and `fill-deleted` from that template. Each document was opened, its polygons
repoured, saved as `<name>-saved`, closed, opened again and read again. No dialog showed at any opening,
repour, save or close, and the Messages panel got no message. For every document, the geometry at the second
opening equals the geometry at the first.

| file | expected | observed in Altium | result |
|---|---|---|---|
| `shapes` | the Mechanical 13 region at (31, 24)–(37, 28) mm; `VIN` at (3, 22)–(9, 28) mm | as expected | pass |
| `create` | a free arc on Top Overlay, centre (30, 20) mm, radius 2 mm, 0° to 90°, 0.2 mm wide; a Mechanical 13 region (20, 20)–(24, 23) mm; polygon `AUX` on the Top Layer, net `MID`, (30, 4)–(38, 10) mm, pour index 2 | as expected; the repour gives `AUX` no region | pass |
| `set_outline` | `VIN` at (2, 21)–(10, 28) mm | as expected; the repour gives `VIN` one region | pass |
| `arc-moved` | the arc's centre at (31, 21) mm | as expected | pass |
| `arc-deleted` | no free arc | as expected | pass |
| `fill-added` | the template's fill and a new fill (2, 2)–(4, 3) mm on the Top Layer, no net | as expected | pass |
| `fill-moved` | the template's fill at (35, 2)–(37, 4) mm | as expected | pass |
| `fill-deleted` | no fill | as expected | pass |

`AUX` encloses no pad of `MID`, and its record holds `REMOVEDEAD=TRUE`, so a repour gives it no copper
(`pcb-pour.md`, I13). Fenolite reads each saved document strictly, with the same free arcs, fills, free
regions and polygons as the written one. No level is raised, because this was an agent run. `H-A-EDIT-SHAPE`
and `H-A-EDIT-CREATE` stay `INFERRED`, and the gates `move`, `delete`, `set_outline` and `create` stay off.

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
