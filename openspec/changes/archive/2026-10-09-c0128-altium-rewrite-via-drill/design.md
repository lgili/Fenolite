## Context

- **The rule.** `pcbdoc.via_records` raises `ValueError` unless `0 < drill < diameter` (c0038, "Via records"; `tests/unit/backends/altium/test_pcbdoc.py::test_via_refusals`). The build checks the same before it writes (`lens/altium_copper.py`, `altium.copper-invalid`), and `lower._copper` (c0090) leaves such a via out and counts it under `via` with the reason "the drill is not below the diameter".
- **The import does not have the rule.** `adapter/copper.vias` maps every via record with a diameter and a hole above 0. A via whose hole equals its diameter is a `Via` of the model with `drill == diameter`.
- **Measured on 2026-10-06** on the commit of c0127, with Fenolite's reader on the eight public PCB documents of the corpus (2 933 via records): 48 records hold a hole equal to the diameter, all in `altium-third-party-pcbdoc-02` (48 of its 242); no record holds a hole above its diameter. RT-A3 on that document: equal inside the scope, 194 vias written, 48 counted as not written.
- **Decision of the maintainer** (design of c0090, 2026-10-06, decision 3): relaxed for the rewrite of an imported document only; a build from a script keeps refusing.

## Goals / Non-Goals

**Goals:**
- The rewrite of a document that was read holds every via of the document that has a drill up to its diameter.
- A build, and every write that is not a rewrite, behaves as before, byte for byte.
- The caller says that a write is a rewrite.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **"Imported" is an argument, not a property that the write reads from the design.** A `Design` records where it came from in two places: each entity's `provenance.backend`, and the native ids (`"altium" in board.native_ids` is what `lower` already uses to choose the frame of the document). Both survive an edit: a design that was read, changed by a script and written is still marked as read, and a relaxation that hangs on the mark would silently reach it. An argument is the caller's word for one call: `AltiumBackend.write(design, rewrite=True)`. The trip of RT-A3 is by definition a rewrite and passes it.
2. **The mark is still required.** `rewrite=True` for a board whose `native_ids` hold no `altium` key raises `ValueError`: a KiCad design or a script's design cannot be written with the relaxed rule by passing the argument. So the relaxation needs both, the caller's word and a board that was read. A design without a board (a schematic alone) takes the argument without effect.
3. **Only equality.** `0 < drill <= diameter` in a rewrite. A drill above the diameter stays refused: no saved document read holds one, so there is no fact for it.
4. **The option of the writer.** `PcbDocSpec.allow_full_drill` (`False` by default), read by `via_records`. `lower.from_design` sets it from `rewrite`. The record needs no other value: `via_record` writes the hole at 25 and the diameter at 21 and in the thirty-two layer diameters, which is what the public records hold (see the fact).
5. **Name.** `rewrite`, not `imported` or `tolerant`: it says what the call does, and it is the word of the decision. It is one switch for "write it as it was read"; today one rule hangs on it.
6. **What the argument does not change.** The frame, the kept arc records of c0127, the unique ids and every count but `via` are the same with and without it; a test compares the two writes of a sample without such a via byte for byte.
7. **Callers.** `AltiumBackend.model_roundtrip` (so `checks/documents.py`, the stage `roundtrip.rta3`, and `fenolite roundtrip --level rta3`), and the two test helpers that write the rewrite of a document (`tests/kicad/_rta3oracle.py`, `tests/corpus/test_altium_rta3.py::test_sets`). Not: `lens.altium.write_model`, `lens/altium.py`, `fenolite build`.
8. **Cut order.** First the test helper of the KiCad oracle (decision 7), never the guard of decision 2.

## Files and public API

- `src/fenolite/backends/altium/pcbdoc.py`: `PcbDocSpec.allow_full_drill`; `via_records(vias, copper, *, allow_full_drill=False)`.
- `src/fenolite/backends/altium/lower.py`: `from_design(design, *, issues, corner_ratios=None, rewrite=False)`, `write_design(design, *, allow_lossy=False, corner_ratios=None, rewrite=False)`.
- `src/fenolite/backends/altium/backend.py`: `write(design, *, target=None, allow_lossy=False, rewrite=False)`; `model_roundtrip` passes `rewrite=True`.
- Tests: `tests/unit/backends/altium/test_pcbdoc.py`, `test_lower.py`, `tests/unit/checks/test_rta3.py`, `tests/corpus/test_altium_rta3.py`, `tests/kicad/_rta3oracle.py`.
- Pages: `docs/formats/altium/pcb-copper.md`, `pcb-document.md`, `docs/altium.md`, `docs/evidence/altium-roundtrip.md`.

## The fact (2026-10-06)

Read with `fenolite.backends.altium.read.pcb.read_pcbdoc` from the corpus cache; counts and structure only.

| what | `altium-third-party-pcbdoc-02` (S-0176) |
|---|---|
| via records | 242 |
| hole (32-bit at 25) equal to the diameter (32-bit at 21) | 48 |
| hole above the diameter | 0 |
| subrecord length of the 48 | 351 bytes each (the 321-byte form with one polygon-connect entry) |
| start and end layer of the 48 | 1 and 32 (through) |
| net of the 48 | each on a net |
| diameter stack mode (byte at 74) of the 48 | 0 |
| the thirty-two layer diameters (from 75) of the 48 | all equal to the diameter |
| distinct sizes among the 48 | 1 |
| the other 194 via records | 160 of 321 bytes and 34 of 351 bytes, hole below the diameter |

The other seven public PCB documents (2 691 via records) hold no via with a hole equal to or above its diameter. So such a record is the ordinary via record with two equal values; no field marks it.

## Measured (2026-10-06, macOS, local corpus cache)

Counts only. Before: the commit of c0127. After: this change. `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_rta3.py -q`, run on 2026-10-07.

| `altium-third-party-pcbdoc-02` | before | after |
|---|---|---|
| verdict inside the scope | equal | equal |
| vias of the model | 242 | 242 |
| vias written by the trip of RT-A3 | 194 | 242 |
| `via` in "model items not written" | 48 | 0 |
| vias written by a write that is not a rewrite (`write_design(…, allow_lossy=True)`) | 194 | 194 |
| vias that such a write leaves out, with the reason "the drill is not below the diameter" | 48 | 48 |
| tracks not written (on the internal plane `In2.Cu`) | 43 | 43 |

- **The test run**: 15 passed before, 16 passed after (the new `test_vias_with_a_full_drill`). Compared line by line with the run before: only `via` of `altium-third-party-pcbdoc-02` and of the project set that holds it (`altium-set:04`, not judged for its schematic) moved, from 194 written and 48 unwritten to 242 written and none unwritten. No verdict and no other count of the eight documents and five sets moved.
- **KiCad's importer on the rewrites** (`uv run pytest tests/kicad/altium/test_rta3_oracle.py tests/kicad/test_probe_results.py -q`, `kicad-cli` 10.0.6, 2026-10-07): 11 passed. The helper now writes each rewrite with `rewrite=True`, so the rewrite of `altium-third-party-pcbdoc-02` holds the 48 vias. KiCad's read of it equals Fenolite's at the levels 1 to 5 with no difference and no exclusion, and with the counts of before (41 components, 141 pad nets, 141 pads, 41 placements, 32 routed nets): level 5 compares the vias per layer pair of each net. The probe `altium-rta3-kicad` stays `equal`, and its recorded file did not change.
- **A build**: `uv run pytest tests/unit/lens -k altium -q` passes; every committed sample under `tests/data/altium/` keeps its bytes, and `test_via_refusals` of c0038 passes unchanged.

## Out of scope

What else the rewrite of `altium-third-party-pcbdoc-02` leaves out, measured with `lower.from_design` on its reading, and why none is the matter of this change:

| count | reason given by the write | why it is not relaxed here |
|---|---|---|
| track 43 | "In2.Cu is an internal plane, which holds no primitive" | not an analogous refusal: the 43 tracks lie on a layer that the document declares as an internal plane with a net (the board holds two, `In1.Cu` and `In2.Cu`). A plane is written in negative and the writer puts no primitive on it (c0038, "Internal planes"; S-0531 says what an object on a plane layer is: a void in the copper). Writing them needs the form of a line on a plane, which sibling change c0124 reads in the import; it is no rule about a value that could be relaxed |
| zone 2 | the model holds no outline (an outline with an arc) | a limit of the model's zone outline |
| pad 2 | a custom shape | no exact Altium form in the writer |
| text 1, graphic 16, copper-shape 17, body 42, outline 8, zone-fill 9 | layers without a layer in the written document, shapes on copper, bodies, arcs of the outline, poured fills | counted by c0090 and c0085; c0126 and later changes |

Also out of scope: a via with a drill above its diameter (no document holds one); letting `fenolite build` take such a via behind an option (the decision says a build keeps refusing); a `convert` command that would pass `rewrite` (v0.5a).

## Sources registered by this change

- S-0565: the public document of S-0176 (`altium-third-party-pcbdoc-02` of the corpus manifest), read again on 2026-10-06 with Fenolite's own reader for the via records whose hole equals their diameter; Apache-2.0; fetched by the corpus manifest, never committed. The ids S-0566 to S-0569 stay unused.

Each new source is a row of `docs/evidence/sources.md` with its licence and what was read. Nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-PCBX-VIA-FULL | A document that Altium saved can hold a through via whose hole equals its diameter: the ordinary via record with equal 32-bit values at 21 and 25, the stack mode 0 and the thirty-two layer diameters equal to the diameter | `tests/corpus/test_altium_rta3.py::test_vias_with_a_full_drill` | the public document holds such records, each of that form; its rewrite holds every one of them and is equal inside the scope |

It starts `INFERRED` and becomes `CORPUS-VERIFIED` when the test passes on the public document. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Size (design-days)

| group | dd |
|---|---|
| entry, measurement, the fact | 0.25 |
| the option, the argument, their tests | 0.25 |
| corpus run, oracle, pages, closing | 0.25 |

Total: 0.75. This is a size, not a calendar estimate.

## Spec deltas and archive order

Every MODIFIED requirement is the whole text of the newest delta that holds it, with the edit applied; a script asserts each sentence it replaces.

- `altium-pcb-writer`, "Via records": the living spec holds the text of c0038; c0085 (implemented, not archived) modifies it for blind and buried vias. The text here starts from **c0085's delta**; one sentence is added to the bullet of `write_pcbdoc` and one scenario.
- `altium-pcb-writer`, "Imported boards are written from the model" and "Writer options for a model that was read": ADDED by c0090 and MODIFIED by c0127. The text here starts from **c0127's delta**: the signature gains `rewrite`, one bullet and one scenario are added to the first, one clause of its list of items that are not lowered is changed, and one bullet is added to the second.
- `backend-protocol`, "Altium write of a model": ADDED by c0090; the text starts from **c0090's delta**: the signature, one bullet and one scenario.
- `altium-verification`, "Round-trip level RT-A3": ADDED by c0090 and MODIFIED by c0127 (the level of its evidence); the text starts from **c0127's delta**: the call of `write_design` and one scenario.
- Archive order: after c0085, c0090 and c0127; before c0092. If c0126 or another change modifies one of these requirements first, its text is the base and the edits of this change are applied again.

## Risks / Trade-offs

- [A caller passes `rewrite=True` for a design that it edited after reading] → the argument is the caller's word; the only effect is that a via with `drill == diameter` is written as the model holds it.
- [KiCad's importer reads such a via differently] → the oracle test rewrites the same public document with `rewrite=True` and compares the two reads.
- [The counts of `roundtrip.rta3` change on documents with such vias] → said in the changelog; the verdict does not depend on the counts.
- [A second relaxed rule later] → it hangs on the same argument and gets its own fact row.

## Migration Plan

- None: the new argument defaults to the behaviour of before. A script that calls `AltiumBackend().write(design)` gets the same files.
- Rollback: `model_roundtrip` stops passing `rewrite=True`.

## Open Questions

- **Should `rewrite=True` on a board that was not read be ignored instead of refused?** Default: refused with `ValueError`; a silent no-op would hide a caller's mistake.
