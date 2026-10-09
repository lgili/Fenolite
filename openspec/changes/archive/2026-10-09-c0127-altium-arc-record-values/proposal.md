## Why

The level RT-A3 (change c0090) reads an Altium document, writes its model as new documents and reads those again; the two models must be equal inside the written scope within 2 nm. On the heavy public document `altium-third-party-pcbdoc-08` they are not: 7 of its 517 written arcs come back with a point 3 nm or more away, and 12 more arcs are not written at all.

The cause is the form of an arc. An arc record holds a centre, a radius and two angles, each rounded to the file's unit; the model's arc holds three points in whole nanometres. The import converts the record to points, the writer derives a record from the points, and that record is not the first one: for a short arc the centre can move by hundreds of units, and three points that fall on one line give no record at all. Record → points → record → points does not close.

The maintainer decided on 2026-10-06 (design of c0090, "Decisions of the maintainer", 2): an arc that was read keeps the record's own centre, radius and angles, and the writer gives them back.

## What Changes

- **The import keeps the record.** An `Arc`, and a graphic of kind `arc`, that is read from an arc record holds one more pair in its `altium` bag: `arc`, the record's centre, radius and two angles. **The canonical JSON of an imported Altium design gains this pair on every such arc**; no id changes, and a design read from KiCad never holds it.
- **The write of a model uses it when it is still true.** `lower.from_design` writes an arc with the kept centre, radius and angles when they still give the arc's three points within 2 nm. An arc that was moved or reshaped in the model has a stale pair: it is ignored without an issue, and the arc is written from its points as before. An arc without the pair is written as before.
- **An arc with a kept record is no longer refused for three points on one line.** The 12 arcs of the heavy document that were counted as not written are written.
- **Measured.** `altium-third-party-pcbdoc-08` is equal inside the scope and leaves the list of documents that differ; `H-A-VER-RTA3` is judged again by its criterion.

Size: 1 design-day (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-import`: MODIFIED "Extension bags" (the pair `arc`).
- `altium-verification`: MODIFIED "Round-trip level RT-A3" and "Altium check stage evidence" (the level of `EVIDENCE_RT_A3`). Both come from c0090's delta.
- `altium-pcb-writer`: MODIFIED "Imported boards are written from the model" (an arc is written from its kept record when the record still says its points) and "Writer options for a model that was read" (`PcbDocSpec.arc_records`). Both are requirements that c0090 adds; the text starts from c0090's delta.

## Non-goals

- No change of the model: `Arc` keeps its three points and gains no field. The record's values are in the backend's bag, as other import-side values are.
- No change of a build from a script: `lens/altium.py` passes no kept record, a script's arc holds no `altium` bag, and the committed samples under `tests/data/altium/` keep their bytes.
- No change of the arcs of a footprint in a PCB document: they are records without a model entity (`record:footprint-graphics`), which change c0126 gives a place in the model.
- No change of the arcs of a library footprint, of the arc vertices of a board outline or of a zone outline, and no change of the 2 nm of the scope. The design lists each place that holds an arc.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- No format fact is added: the layout of an arc record is a row of `docs/formats/altium/pcb-read.md` (c0041) and of `pcb-copper.md` (c0038). The pair is a row of "Extension-bag keys" in `import.md`.
- `H-A-VER-RTA3` is judged again by its own criterion (equal on every listed corpus document, from at least three repositories). When the run with the heavy document passes, the row is confirmed and `CORPUS-VERIFIED`, as the proposal of c0090 states and by the maintainer's decision of 2026-10-07. The level says that Fenolite reads its own rewrite of a public Altium PCB document back to an equal model inside the written scope; it says nothing about Altium opening a written file, which stays `INFERRED` until the kit run (c0091, c0092). The two requirements of c0090 that name the level of `roundtrip.EVIDENCE_RT_A3` are MODIFIED; a stage and a verdict stay `INFERRED`, because the import's evidence is.

## Impact

- Changed: `backends/altium/adapter/copper.py` and `adapter/ids.py` (the pair), `backends/altium/lower.py` (`kept_arc`, `ARC_TOLERANCE`), `backends/altium/pcbdoc.py` (`PcbDocSpec.arc_records`, `graphic_problem(…, arc_known=…)`; defaults keep every build's bytes).
- Pages: `docs/formats/altium/import.md` (one key), `pcb-document.md` ("A model that was read"), `docs/altium.md` ("Written scope"), `docs/evidence/altium-roundtrip.md` ("RT-A3"), `docs/hypotheses.md` (the result of `H-A-VER-RTA3`), `docs/evidence/matrix.md` (generated).
- The content of an imported Altium board with arcs changes (one more pair per arc). A rewrite of such a board holds the arcs' own records.
- Depends on: c0090 (implemented, not archived), which must be archived first. c0128 is written on top of this change.
