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

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

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
- `altium-build`: "Copper issue codes" and "PCB issue codes" lose the codes of items that are now written (MODIFIED at task 0.1).
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
