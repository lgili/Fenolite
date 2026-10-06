## Why

A footprint instance of the model holds pads, text fields and bodies. It holds no line, no arc and no free text, and a rounded pad holds no corner value. Two things of v0.4 stop there.

- **A rewritten Altium board has no silkscreen of its footprints.** The import counts every line, arc, fill, region and text of a component as a record without a model entity: 271 to 9 763 per public document, 16 647 on the eight documents of the RT-A3 table, the largest count of that table (`docs/evidence/altium-roundtrip.md`). The write of a model (c0090) then has nothing to write but pads.
- **The Altium build has two paths.** c0090 could not send the build through its lowering `lower.from_design`, because a model could not give the graphics and the corner ratios that the build takes from library definitions and from KiCad's own data. Its task 2.2 stayed open.

The maintainer decided on 2026-10-06 that the model holds these before v0.4 closes, and that this change closes task 2.2. It is implemented on top of c0123, which changes the model first, and it is the last change of the model in v0.4. The maintainer's answers to the questions of this proposal are in the design, "Decisions of the maintainer (2026-10-06)": none is open.

## What Changes

- **The model.** `FootprintInstance` gains `graphics` (the board's `Graphic` entity) and `texts` (the board's `Text` entity), both in the footprint's own frame, the frame of its pads. `Pad` gains `corner_ratio`, the corner radius of a rounded rectangle in parts per million of the pad's shorter side. Three fields, each with a default; no new class and no new model version.
- **The library of a footprint needs no field.** `lib_ref` already names library and footprint in both imports. What the build needs beyond the instance, the definitions of its PCB library and the name of that file, it hands to the lowering as options.
- **Old model documents.** A `board.json` of 0.2.0 has none of the keys and loads as it is; every consumer then does what it does today. **0.2.0 cannot read a model document that carries the new keys**, as after every earlier additive change; the changelog and `docs/design-model.md` say so. A `board.json` that the code of the tag `v0.2.0` wrote is committed as a fixture and must load unchanged and serialise to its own bytes.
- **KiCad: nothing moves.** No reader and no writer of the KiCad backend fills or reads the new fields. A projection on request (`backends.kicad.fpitems.with_footprint_items`) gives them for a board that was read, as read-only copies of the file's own children; the write of a KiCad design as Altium documents asks for it. Every KiCad output of 0.2.0 stays byte-equal, `.fenolite/board.json` included: no file is named as changing.
- **Altium import.** The tracks, arcs, fills and regions of a component become the graphics of its footprint; its designator and comment become the fields `Reference` and `Value`, with their place and visibility; its other texts become texts of the footprint; a rounded pad gets its ratio.
- **Altium write.** A component is written with the lines and arcs of its instance, on the overlay and on the mechanical layers 1 to 16 (the maintainer decided that Mechanical 1 to 12 are in and are not to be cut), and with its designator and comment where the fields say. Two groups that can be cut add free texts, and fills and regions. Copper lines inside a footprint are not written and are counted as a loss.
- **The two build paths are compared first.** The first implementation task, before any change of the model, compares the specification of the build with the one of the lowering field by field and writes the table into the design. A field that cannot come from the model plus options stops the switch of the build, and the implementer reports to the coordinator; the model is not bent to hide it.
- **One lowering.** `fenolite build --target altium` places its footprints into the model and calls `lower.from_design` with its options; `lens.altium.pcb_document` is removed. **No file under `tests/data/altium/` changes a byte**: that is the acceptance test. The one file of a build that changes is `.fenolite/board.json`, which gains the graphics and the ratios; the ten pinned digests of c0123 that hold it are moved with that reason, after the files outside `.fenolite/` are shown unchanged.
- **Comparisons.** `diff` compares footprint graphics and texts as kinds of their own; RT-A2 and RT-A3 compare footprint graphics and corner ratios; no level of `equivalent` changes.
- **Measured.** The RT-A3 table is measured again: the count of footprint records without a model entity goes to 0, and what a rewrite still leaves out is listed by reason.

Size: 13.75 design-days (a size, not time), 11.5 without the three groups of the cut order (the KiCad projection, free texts, fills and regions).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-model`: ADDED "Graphics and texts of a footprint instance", "Corner ratio of a rounded-rectangle pad", "Models without footprint items".
- `kicad-file-backend`: ADDED "Footprint items projected on request".
- `altium-import`: MODIFIED "Footprint instances and pads"; ADDED "Graphics, fields and texts of a component".
- `altium-pcb-writer`: MODIFIED "Imported boards are written from the model"; ADDED "Footprint items of a written component".
- `backend-protocol`: MODIFIED "Altium write of a model".
- `altium-build`: MODIFIED "Stored board of an Altium build"; ADDED "Altium build through the lowering".
- `altium-verification`: MODIFIED "Round-trip level RT-A3"; ADDED "Footprint graphics in the Altium round trips".
- `verification-loop`: ADDED "Footprint items in the model difference".

## Non-goals

- No component body (3D): c0085 cut the body record, and the sibling proposal c0121 owns bodies.
- No change of any KiCad output, and no edit of a footprint's graphics written to a KiCad board: the KiCad writer keeps writing the file's own children, and an edited projection is refused.
- No PCB library derived from the instances of a model that was read (v0.5a, with `convert`), and no per-layer corner ratio of a pad stack.
- No level of `equivalent` reads a footprint's drawing.
- No claim that Altium shows a rewritten board's graphics: the author report Part G is the maintainer's.
- No further field of the model in v0.4. If the build's specification needs one, the switch of the build stops and the design says which.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` or `docs/formats/kicad/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- The model change holds no format fact: `INFERRED` under `H-G-FPGFX-ADD` and `H-G-CORNER-PPM`, settled by unit tests.
- "No KiCad output changes" is `H-K-PCB-FPGFX-BYTES`, `INFERRED`, settled by the untouched RT1 and RT2 tests and the pinned builds of c0123. The projection is `H-K-PCB-FPGFX`, `INFERRED`, against the library reader.
- That a primitive with a component index belongs to its footprint: `CORPUS-VERIFIED` under `H-A-IMP-FPGFX` when the census is conserved on every listed public document.
- The written items read back: `INFERRED` (`H-A-PCBX-FPGFX`, `H-A-PCBX-FPTEXT`, `H-A-PCBX-MECH`, `H-A-VER-RTA2-GFX`, `H-A-VER-RTA3-GFX`): Fenolite reads what Fenolite wrote.
- KiCad's importer on the rewrites: `ORACLE-VERIFIED(kicad-cli 10.0.x)` under `H-A-PCBX-FPGFX-KICAD`.
- The build's bytes: `INFERRED` under `H-A-PCBX-BUILD-LOWER`, settled by the golden tests without an edit.
- Altium itself: `ALTIUM-VERIFIED(author-report)` under `H-A-PCBX-FPGFX-AD` only after Part G is recorded.

## Impact

- Changed: `model/board.py`, `model/design.py`, `schemas/fenolite.model.v0/board.json` and `library.json` (generated), `checks/diff.py`, `checks/rta2.py`, `backends/kicad/pcb.py` (the projection check of the writer), `backends/altium/adapter/board.py`, `adapter/copper.py`, `adapter/pads.py`, `backends/altium/lower.py`, `pcbdoc.py`, `libboard.py`, `roundtrip.py`, `backend.py`, `lens/altium.py`, `cli/data/explain.toml`; new `backends/kicad/fpitems.py`.
- Pages: `docs/design-model.md`, `docs/altium.md` ("Round trips", "Written scope"), `docs/formats/altium/import.md`, `docs/formats/kicad/board.md`, `docs/evidence/altium-roundtrip.md`, `docs/evidence/altium-pcb.md` (Part G), `docs/hypotheses.md`, `docs/evidence/matrix.md` (generated), `docs/cli-contract.md` (`model.corner-ratio`).
- Behaviour that changes: `altium.import.unmapped` no longer lists `footprint-graphics` for a normal document; `board.json` of an imported Altium board grows by about 43 % on the public corpus; `.fenolite/board.json` of an Altium build changes; `AltiumBackend().write` writes footprint graphics and may refuse a model with copper lines inside a footprint unless `allow_lossy` is given.
- New test data: `tests/data/model/v0.2.0/blink_2layer.board.json` with its entry in `tests/data/MANIFEST.toml`. Source ids: the block S-0580 … S-0589 is reserved for this change.
- Depends on: c0090 (the lowering and the round-trip levels), c0123 (this change is implemented on top of it: it changes the model first, and pads take their nets through its map), c0085 (text and region records), c0043 (the import). c0127 decides how the points of an arc are compared. c0092 follows.
