## Context

- **Today.** `docs/altium.md`: "a board's keep-outs, texts, graphics and holes are" not lowered; "no blind, buried or micro vias"; "Texts, properties and 3D model links are not written"; `footprint.bodies`: "the writer does not write it"; a model stack-up that does not fit two or four layers "falls back to defaults with `altium.not-lowered`"; zones are written "without poured copper".
- **The read side is ahead.** `altium-pcb-reader` reads text records and wide strings, regions and polygons, fills, pads with padstacks, the board record with its layer stack and component bodies, losslessly, with a field evidence table over the public corpus. `docs/formats/altium/pcb-records.md` and `pcb-bodies.md` hold the field facts. The writer can therefore be proved by reading its output with a reader that was proved on files Altium saved.
- **Record forms not written today** (`altium-pcb-writer`): the 252-byte text form and the 49/60-byte track and arc forms. This change writes one form per record kind, the one the facts page marks as the current one, and says so.
- **Constraints.** Stdlib only; integer nanometres in, the PCB unit out, within 2 nm; no record field is written whose meaning the facts pages do not record.

## Goals / Non-Goals

**Goals:**
- Every board item the model holds is written or counted as not lowered with a reason.
- Each new record kind is proved by the product reader and, where KiCad imports it, by KiCad.
- One Altium session by the maintainer confirms that the document opens and shows the items.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Stack from the model.** `Board.stackup` gives the copper layers in order, each `signal` or `plane`, and the dielectrics between them with thickness, material name and permittivity. The layer map assigns Altium's mid layers and internal planes in order. A stack-up that is absent gives the two- or four-layer default of c0038. An odd copper count, more than 16 signal layers or more than 16 planes gives `altium.not-lowered` with `where` `stackup` and the default stack: no partial stack is written.
2. **Via spans.** A via whose span is two copper layers of the stack is written with its start and end layer, and the board record gets one drill pair per distinct span. A micro via (a span of adjacent layers with the micro flag) gives `altium.via-unsupported`.
3. **Texts.** Stroke texts with height, width, rotation, mirror, layer and justification; the string is written in the form(s) the reader requires for the text to survive non-ASCII characters. Barcode and TrueType texts are not written (`value-unsupported`), because their rendering depends on fonts.
4. **Graphics and keep-outs.** Lines and arcs as track and arc records without a net on their layer; filled shapes as region records; a keep-out as a region or track with the keep-out flag and the restriction set that the facts page records. A restriction the record cannot carry is reported per keep-out.
5. **Holes.** A non-plated round hole is a free pad with no copper and a hole; a slot uses the slot fields of the pad record. A hole shape outside those gives `altium.not-lowered` per hole.
6. **Bodies.** One component body record per `ComponentBody` with its outline, standoff height and overall height, on the mechanical layer pair that the layer map gives 3D bodies; no model file.
7. **Polygons stay unpoured.** A zone is a polygon with its net, layer, outline, clearance-relevant properties, thermal settings, island removal and priority; the pour state is unpoured. Reason: a pour is the result of Altium's rules and Altium's algorithm, and a fill computed elsewhere would be shown as poured while disagreeing with what a repour gives.
8. **Accounting.** The build counts model items and written records per kind and fails with an internal error when an item is neither written nor reported.
9. **Cut order.** First bodies, then keep-out restrictions beyond the basic ones, then slots, never the stack, the vias and the texts.

## Files and public API

- `src/fenolite/backends/altium/pcbrecords.py`: `text_record`, `region_record`, `body_record`, `free_pad_record`, via span fields, drill pairs.
- `src/fenolite/backends/altium/layout.py` / `docboard.py`: the layer map for up to 16 + 16 layers; stack record.
- `src/fenolite/lens/altium_copper.py`: `stack_for(design)`, the accounting.
- Tests: `tests/unit/backends/altium/test_pcb_{stack,vias,text,graphics,holes,bodies}.py`, `tests/unit/lens/test_altium_pcb_complete.py`, `tests/kicad/altium/test_pcb_complete_oracle.py`; a committed sample `tests/data/altium/board6/` (a six-layer authored design with one item of every kind).

## Sources registered by this change

- S-0160, S-0161, S-0162 (registered; facts only): record fields as the KiCad importer reads them.
- S-0197, S-0198 (registered): blind and buried vias, the layer stack.
- S-0195, S-0196 (registered): unpoured polygons and the polygon manager.
- The field evidence table of c0041 over the public corpus (`docs/formats/altium/pcb-records.md`).
- New: Altium's public documentation of drill pairs, keep-out restrictions, free pads as holes and component bodies, where the registered sources do not cover a field.

Each new source gets a number of the block reserved for this change, S-0470 to S-0479 (registered: S-0470), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-PCBX-READBACK | A PCB document written with the records of this change reads back to the model it was written from, inside the written scope and within 2 nm | `tests/unit/lens/test_altium_pcb_complete.py::test_readback` | equal for `board6` and for every example script |
| H-A-PCBX-STACK | Altium shows the written layer stack (layer order, kinds, thicknesses, materials) in the Layer Stack Manager, for 6 and 8 copper layers | author report, Part X steps X2–X3 | the manager's table equals the table sent with the files |
| H-A-PCBX-VIASPAN | A via written with a start and an end layer and a matching drill pair is shown as a blind or buried via of that span | author report, Part X step X4 | the properties of the three sample vias show the spans written |
| H-A-PCBX-TEXT | A text record written in the chosen form shows its string, non-ASCII characters included, at the written place, size and rotation | author report, Part X step X5 | the four sample texts read as in the table |
| H-A-PCBX-KEEPOUT | A region with the keep-out flag and a restriction set is listed as a keep-out with those restrictions | author report, Part X step X6 | the properties show the restrictions written |
| H-A-PCBX-HOLE | A free pad without copper and with a hole is drilled as a non-plated hole, and a slot as a slot | author report, Part X step X7 | the drill table or the pad properties show plated off, and the slot length |
| H-A-PCBX-BODY | A component body record gives the component its height in the 3D view and in the component clearance check | author report, Part X step X8 | the two sample bodies show the heights written |
| H-A-PCBX-REPOUR | Every written polygon is listed as unpoured and "Repour all" pours it without an error | author report, Part X step X9 | the polygon manager lists all as unpoured before, poured after, with no message |
| H-A-PCBX-KICAD | KiCad's importer reads the written stack, via spans, texts, graphics and keep-outs as the model holds them | `tests/kicad/altium/test_pcb_complete_oracle.py` | probe `altium-pcbx-<kind>` `equal` for each kind KiCad imports; the kinds it does not import are listed |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Author report: Part X, complete board

Files: the project `board6` (six copper layers, one blind and one buried via, texts on four layers, a keep-out, a non-plated hole, a slot, two bodies, two polygons) built outside the repository, with a table of the values to compare.

1. X1: open the project and the PCB document. Expected: no repair prompt and no message in the Messages panel.
2. X2: open Design » Layer Stack Manager. Expected: six copper layers in the order and with the kinds of the table.
3. X3: read thickness and material of each dielectric. Expected: the table's values.
4. X4: select each of the three sample vias and read its start and end layer. Expected: through, blind (top to mid 1), buried (mid 1 to mid 2).
5. X5: read the four sample texts (one with accented characters), their layers, heights and rotations. Expected: the table.
6. X6: select the keep-out and read its restrictions. Expected: the table.
7. X7: select the non-plated hole and the slot; read plated, hole size and slot length. Expected: the table.
8. X8: switch to the 3D view and read the height of the two bodies in their properties. Expected: the table.
9. X9: open Tools » Polygon Pours » Polygon Manager; note the state of the two polygons; run Repour All; note the state and any message. Expected: unpoured, then poured, no message.
10. X10: save the document under another name and send only its size and whether Altium asked anything on save.

The maintainer reports one generic outcome per step (`as expected`, or what differed in one sentence), the tool as `AD <major>.<minor>` and the date. No file that Altium wrote is committed. A step that fails refutes the row it names: the row keeps its id and gets a registered successor (`verification-evidence`, "Refuted rows keep their id"). An author report never moves an operation out of `experimental` ("Author reports never promote an operation").

## Found on 2026-10-06

The proposal was written from a survey. Implementing it showed these differences from the code, the model
and the public sources; the spec, this design and the tasks were corrected in the same commit.

1. **The model's stack-up has no signal or plane kind.** `StackLayer.kind` is `copper` or `dielectric`
   (Decision 1 said "each `signal` or `plane`"). A plane is what the build declares (`planes`, layer name →
   net name), as since c0038. The spec says so; `board6` is built with `In2.Cu` as a plane on `GND`.
2. **The DSL has two or four copper layers.** `design.board(..., copper=…)` is not changed by this change
   (it names nothing of the DSL). A stack of more layers comes from a model whose board names its copper
   layers (an imported design, or `board6`, which is authored as a model in `tests/_altium_board6.py`),
   built with `copper` equal to their count.
3. **The layer map is by position, not by name.** The k-th inner copper layer is Mid-Layer k, the p-th
   plane Internal Plane p. For `F.Cu, In1.Cu, In2.Cu, B.Cu` this is the map of c0038, so its bytes hold.
4. **"At most 16 signal layers" with "from 2 to 32".** The spec's limits are implemented as written: an
   even count up to 32, at most 16 signal layers and 16 planes. The proposal's "from 2 to 16" is the case
   without planes.
5. **The default stack of a refused count** is the stack of the two outer layers, since a five-layer
   board has no four-layer default.
6. **The model's `Text` has no mirror, no justification and no font kind.** Decision 3 and the Open
   Question about TrueType texts name fields the model does not hold. Written: string, layer, position,
   height, stroke width, rotation; a text on a bottom-side layer is mirrored, as every free text of the
   public corpus on a bottom layer is. The position is written as the record's position; KiCad anchors an
   Altium text at its lower-left corner, and the model does not say where its anchor is, so the anchor is
   a step of Part X and listed as not compared by the oracle.
7. **The model's `Hole` is round and has no slot.** "Slots" (Decision 5, third item of the cut order)
   cannot arise from a board hole; nothing is written and nothing is lost. A slotted pad of a footprint
   is the footprint writer's matter (c0035), unchanged. A plated board hole is written with its plated
   byte.
8. **Component bodies are cut** (first item of the cut order). The saved extruded bodies hold 35 keys, of
   which the fact page types seven; writing the others would need a row for each. Each body is reported
   with `altium.not-lowered` and `body/<id>`, so the accounting stays closed. `H-A-PCBX-BODY` and step X8
   are not registered and not run; the task 3.4 stays open with what is missing.
9. **Keep-out restrictions.** The saved documents hold the key `KEEPOUTRESTRICTIONS`; KiCad's parser reads
   `KEEPOUTRESTRIC`. The writer writes the key of the saved documents, so KiCad imports every keep-out with
   all restrictions; the bit meanings (1 vias, 2 tracks, 4 copper, 8 and 16 pads) were measured with
   KiCad's own key on a scratch document and are an oracle fact about KiCad, `INFERRED` for Altium until
   step X6. `no_footprints` has no bit (the cut "keep-out restrictions beyond the basic ones" was not
   needed otherwise). *Superseded on the same day by item 17: both keys are written.*
10. **Drill pairs and blind vias are not in any saved document read.** The second pair is composed from
    the keys of the first; KiCad reads no `LAYERPAIR` key, so only step X4 can settle it.
11. **Thermal settings are not keys of a polygon** (`pcb-copper.md`: clearance and connection come from
    rules). The polygon carries net, layer, outline, pour index and island removal (`REMOVEDEAD`).
12. **`altium.not-lowered` is an info**, not a warning, in the closed table and in `explain`; the new
    per-item issues keep that severity, since a second severity for one code is refused by the closed-set
    test and a warning on the old wheres would change the exit code of every build.
13. **"PCB issue codes" loses no code.** None of its rows is about an item that is now written; only
    "Copper issue codes" is MODIFIED.
14. **The import has no keep-out and no board hole.** The adapter of c0043 shows a keep-out region as a
    graphic on `Altium.KeepOut` and a free pad as a `board_only` footprint; the readback of these two kinds
    is therefore at record level and through those two forms, not as `Keepout` and `Hole` entities.
15. **An open question answered by the code as it is.** A plane with a zone of another net is an error
    (`altium.plane-copper`, c0038); it is not turned into a signal layer. Planes are declared by the
    build, so a plane with two nets cannot be declared.
16. **No new Altium documentation page was read.** The fields came from the registered sources, one
    summary of facts of KiCad's parser at the tag 10.0.6 (S-0470) and the seven PCB documents of the public
    corpus.
17. **Both keep-out keys (decision of the maintainer, 2026-10-06, after the first commit).** A keep-out
    record holds `KEEPOUTRESTRICTIONS` and, after it, `KEEPOUTRESTRIC` with the same value. Why: with the
    saved key alone KiCad imported every keep-out with all restrictions, so the one independent reader
    could not check the restrictions and a board taken through KiCad lost them. `KEEPOUTRESTRIC` is not a
    key Altium writes; that Altium opens a record with both and reads the first is `INFERRED` and is the
    new step X11 of Part X. The oracle now compares the restrictions (`altium-pcbx-keepouts`, same id,
    outcome still `equal`), and one more oracle test imports one keep-out per restriction.

## Size (design-days)

| group | dd |
|---|---|
| entry, facts and sources | 1 |
| stack and layer map | 1.75 |
| via spans and drill pairs | 1 |
| texts | 1.25 |
| graphics and keep-outs | 1.25 |
| holes and slots | 0.75 |
| bodies | 0.75 |
| polygons, accounting, build integration | 1 |
| sample, oracle, report, docs | 1 |
| closing | 0.25 |

Total: 10. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-pcb-writer`: "Four-layer stack", "Via records", "Polygon pour records", "Copper layer map" are superseded in their limits; task 0.1 writes them as MODIFIED from the living text.
- `altium-build`: "Copper issue codes" is MODIFIED (task 0.1); "PCB issue codes" names no such code and is not changed ("Found on 2026-10-06", 13).
- Archive order: before c0090.

## Risks / Trade-offs

- [A record form that reads back is not the one Altium wants] → the reader was proved on files Altium saved, so the form is one Altium writes; Part X confirms the opening.
- [Layer map beyond four layers collides with mechanical layer use] → the map is a table in the facts page, checked by a unit test for uniqueness.
- [Size] → the cut order drops bodies, keep-out restrictions and slots first; each is a requirement that can move to a follow-up without touching the others.

## Migration Plan

- Two- and four-layer builds without the new items are byte-equal to today's (a regression test over the committed samples).
- Rollback per kind: each record kind has its own switch in the accounting, so a kind that Altium rejects can be turned back to `not_lowered` in one line.

## Open Questions

- **Should a plane layer with more than one net be written as a signal layer with polygons?** Default: yes, with an info issue naming the layer.
- **Should TrueType texts be written as stroke texts of the same height?** Default: no, not written, reported per text.
