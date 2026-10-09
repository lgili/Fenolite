## Why

The via writer of the Altium PCB document refuses a via whose drill is not below its diameter, a rule that change c0038 pins ("Via records": `write_pcbdoc` raises `ValueError`). For a board that a script designs the rule is right: a via without an annular ring is a mistake of the script.

A document that Altium saved can hold such vias. The public document `altium-third-party-pcbdoc-02` holds 242 via records, and in 48 of them the hole equals the diameter. The import reads them into the model as they are. When the model is written back (change c0090, RT-A3), `lower.from_design` leaves the 48 vias out and counts them: the rewrite of that board has 48 vias fewer than the board.

The maintainer decided on 2026-10-06 (design of c0090, "Decisions of the maintainer", 3): the rule is relaxed for the rewrite of an imported document only; a build from a script keeps refusing.

## What Changes

- **`AltiumBackend.write(design, …, rewrite=False)`** and `lower.write_design` / `lower.from_design` take one more argument. `rewrite=True` is the caller's statement that the design is the reading of an Altium document and that the write gives the document back. It is explicit: the write does not infer it from the design.
- **In a rewrite, a via whose drill equals its diameter is written**, with the hole equal to the diameter, as the document held it. A drill above the diameter, and a drill of 0 or less, is refused as before.
- **`AltiumBackend.model_roundtrip` passes `rewrite=True`**, so the stage `roundtrip.rta3` and `fenolite roundtrip PATH --level rta3` write such vias. **This changes the counts that those two report on a document with such vias** (`written.via` rises and `unwritten.via` falls); no verdict changes.
- **Nothing else passes it.** `fenolite build --target altium`, `lens.altium.write_model` (a KiCad design written as Altium documents) and a plain `AltiumBackend().write(design)` refuse or leave out such a via exactly as today. `rewrite=True` for a board that was not read from an Altium document raises `ValueError`.
- **One format fact**, read from the public document with Fenolite's own reader: what a via record with a hole equal to its diameter looks like.

Size: 0.75 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-pcb-writer`: MODIFIED "Via records" (`PcbDocSpec.allow_full_drill`), "Imported boards are written from the model" (`rewrite`) and "Writer options for a model that was read" (the option).
- `backend-protocol`: MODIFIED "Altium write of a model" (the argument `rewrite`).
- `altium-verification`: MODIFIED "Round-trip level RT-A3" (the trip is a rewrite).

Every one of these requirements is modified or added by a change that is implemented and not archived (c0085, c0090, c0127); the design says from which delta each text starts.

## Non-goals

- No change of a build from a script: `lens/altium.py` and `lens/altium_copper.py` are not edited, `altium.copper-invalid` keeps its meaning, and the committed samples under `tests/data/altium/` keep their bytes.
- No relaxation for a drill above the diameter: no public document read holds one.
- No other rule of the writers is relaxed. The design lists what else a rewrite leaves out on the same document and why each is another matter.
- No inference of "imported" from the design alone.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- That a saved document holds via records with a hole equal to the diameter, and their form: `CORPUS-VERIFIED` under `H-A-PCBX-VIA-FULL`, read from the public document itself (S-0176, read again as S-0565) by Fenolite's reader and pinned by a corpus test.
- That KiCad's importer reads the rewrite with these vias as Fenolite does: the existing row `H-A-VER-RTA3-KICAD`, whose test rewrites the same document; it stays `INFERRED` by its own rule.
- Nothing is claimed about Altium Designer opening a rewrite.

## Impact

- Changed: `backends/altium/pcbdoc.py` (`PcbDocSpec.allow_full_drill`, `via_records`), `backends/altium/lower.py` (`rewrite`), `backends/altium/backend.py` (`write`, `model_roundtrip`).
- Pages: `docs/formats/altium/pcb-copper.md` (one row), `pcb-document.md` ("A model that was read"), `docs/altium.md` ("Written scope"), `docs/evidence/altium-roundtrip.md` ("RT-A3"), `docs/evidence/sources.md` (S-0565), `docs/hypotheses.md` (one row), `docs/evidence/matrix.md` (generated).
- Depends on: c0090 and c0127 (implemented, not archived); this change is written on top of c0127 and is archived after it.
