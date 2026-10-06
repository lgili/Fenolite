## Why

No Altium file is read and written back. `claims.py` says so in its first sentence, and every round-trip cell of the Altium kinds in the evidence matrix is empty. Fenolite writes Altium documents only from a design script, and reads them only into the model. The two halves never meet: "Writing an imported model is not available before v0.4" (`altium-verification`).

Two things follow. The level RT-A2 is judged only on built projects, and there only on the circuit and the net-class names, because the built model holds no footprint and no copper (`H-A-VER-RTA2` was refuted for that reason). And the conversion of v0.5a has no base: KiCad to Altium works through a script only. This change joins the halves: a model that was imported, from Altium or from KiCad, can be written as Altium documents, and what comes back is compared.

## What Changes

- **`AltiumBackend.write(design)`**: writes a neutral design that holds a board (footprints, pads, copper, zones, rules, stack) and a circuit as a PCB document, a schematic and a project, with the writers of c0084 to c0086. It is the write of a model, not of a script: placements and copper come from the model.
- **RT-A2 on what was written from a model**: the level compares footprints, pads, tracks, arcs, vias, zones and rules, which a model has, and not only the circuit.
- **A new level, RT-A3**: a document that Altium saved is imported, written back and imported again; the two imports are equal inside the written scope, and what the write left out is listed by record kind. It is run over the public corpus.
- **The first round-trip cells** of the Altium kinds in `claims.py`, at the level the corpus run supports.
- **`fenolite roundtrip`** accepts Altium input for the levels RT-A0 to RT-A3.

Size: 7 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-verification`: ADDED "Round-trip level RT-A3", "RT-A2 on a written model", "Round-trip claims of the Altium kinds"; MODIFIED "Round-trip level RT-A2", "Check on Altium inputs", "Altium check stage evidence".
- `backend-protocol`: ADDED "Altium write of a model", "Model writers".
- `altium-pcb-writer`: ADDED "Imported boards are written from the model", "Writer options for a model that was read".
- `altium-build`: ADDED "Stored board of an Altium build"; MODIFIED "Altium build outputs".
- `altium-import`: MODIFIED "Altium backend" (the backend offers `write`).
- `verification-loop`: MODIFIED "Document check pipeline" (`roundtrip.rta2` compares every kind; the opt-in `roundtrip.rta3`).

## Non-goals

- No byte-preserving edit of an Altium document (changing one record of a file Altium saved and keeping the rest): RT-A0 and RT-A1 prove the container and the record codecs, and that is as far as preservation goes in v0.4.
- No conversion command and no loss report for users (v0.5a): this change gives the write and the measurement; `convert` builds on them.
- No claim that Altium opens a rewritten corpus file: the kit of c0091 checks Fenolite's own samples, and a rewritten third-party board is checked by Fenolite's readers and by KiCad's importer only.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- RT-A3 over the corpus: `CORPUS-VERIFIED` for `H-A-VER-RTA3` when every listed document passes inside the written scope.
- The written scope itself (what the writers carry) is a table in `docs/altium.md`; what is outside it is counted per record kind in the stage summary and never called equal.
- KiCad's importer on the rewritten documents, at level 5 of `equivalent`: `ORACLE-VERIFIED(kicad-cli 10.0.x)` for `H-A-VER-RTA3-KICAD`.
- `roundtrip_modified` cells stay empty: no edit path exists.

## Impact

- Changed: `backends/altium/backend.py` (`write`, `in_model_frame`, `model_roundtrip`), `roundtrip.py` (scopes), `pcbdoc.py` and `project.py` (options with defaults that keep every build's bytes), `claims.py`, `backends/base.py`, `lens/altium.py`, `checks/rta2.py`, `checks/documents.py`, `cli/cmd_roundtrip.py`, `cli/cmd_check.py`; new `backends/altium/lower.py` (model → writer inputs), `backends/altium/rta3.py`, `checks/rta3.py`. The design's "Found on 2026-10-06" says where the proposal was corrected.
- Pages: `docs/altium.md` ("Round trips", "Written scope"), `docs/evidence/altium-roundtrip.md`, `docs/evidence/matrix.md` (generated).
- Depends on: c0084, c0085, c0086 (the writers must carry what a model holds), c0089 (level 5 for the KiCad oracle), c0083 (so that the corpus project with repeated sheets has a correct circuit); c0043 and c0044.
