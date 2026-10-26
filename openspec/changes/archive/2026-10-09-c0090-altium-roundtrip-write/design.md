## Context

- **Today.** The Altium build takes a script: the schematic comes from the circuit, the PCB from placements, library footprints and a copper source (script copper or a routed KiCad board). `backend.write` exists for libraries and for what the build passes; a `Design` with a full board is not an input. RT-A2 (`checks/rta2.py`, `roundtrip.RT_A2_SCOPE`) is skipped with `native-input` on files Altium saved, and on built projects it counts footprint, pad, track, arc, via and zone without comparing them.
- **The import is lossless below the model.** The readers keep every record and field (RT-A1 holds over the corpus); the adapter builds the model and counts what it does not map ("Unmapped records are counted"). So the loss of a rewrite is measurable per record kind.
- **Constraints.** A rewrite is new documents in a new folder, never over the input. Ids: the model's native ids let the second import be matched to the first by unique id where the writer keeps them, else by reference and geometry as `equivalent` does.

## Goals / Non-Goals

**Goals:**
- A model with a board can be written to Altium documents without a script.
- The loss of a rewrite is a number per record kind, on public boards, in the evidence page.
- The matrix states round-trip levels for Altium kinds that a test supports.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **One lowering of a model, beside the build.** `lower.from_design(design, *, issues, corner_ratios=None) -> AltiumInputs` produces the writers' inputs from a `Design` alone, and `lower.write_design` writes them. The build did not go through it when this change landed (see "Found on 2026-10-06", 1): it kept its own path, and stores the board it wrote (`lower.stored_board`), so the built model holds the footprints and copper that are written and RT-A2 can compare them. Corrected on 2026-10-08: since change c0126 the build goes through it (`lower.from_design` with `lower.LowerOptions`, after `lens.altium.place_footprints`), and the committed samples keep their bytes.
2. **RT-A2, widened.** With the built model holding the board, `RT_A2_SCOPE` is compared in full: footprint position, rotation and side; pad number, net, position and size; tracks, arcs, vias, zones. Rules stay outside the scope ("Found", 4). The successor row replaces the bounded `H-A-VER-RTA2-2`.
3. **RT-A3.** `AltiumBackend.model_roundtrip(path, compare=…)`: import → write to a temporary folder → import; `rta3.rt_a3` judges the two models with the comparison that the caller hands in (`checks.diff.diff_designs`) inside `RT_A3_SCOPE` (the written scope) within 2 nm, after the entities that the write reports as not written are taken out of the first model; `unwritten` counts them per kind, with the records of the first reading that the import maps to no model entity. The level holds when the comparison is equal; the count is reported, never part of the verdict.
4. **Schematic side.** RT-A3 covers the PCB document and the circuit. The schematic's presentation (where symbols and wires are) is not kept by a rewrite: the schematic is generated from the circuit, and the stage says `presentation: regenerated`. Keeping an Altium schematic's drawing is not in v0.3.
5. **Corpus list.** The run uses the PCB documents and project sets of c0041's and c0044's lists that are not marked heavy. A document that cannot pass for a reason outside this change (an import defect) is listed with its cause and an issue reference, and does not block the row when at least the listed minimum passes; the minimum is three repositories, as `H-A-VER-RTA0` requires.
6. **Claims.** `roundtrip_exact` is set for `altium_pcbdoc` and `altium_prjpcb` only if RT-A3 holds with an empty `unwritten` on the corpus list, which is not expected; otherwise the cell stays empty and a new matrix column note says `RT-A3 inside the written scope`. No cell is set from Fenolite's own files alone.
7. **Cut order.** First `fenolite roundtrip` on Altium input, then the KiCad oracle on rewritten corpus files, never `from_design`, the widened RT-A2 and RT-A3.

## Files and public API

- `src/fenolite/backends/altium/lower.py`: `AltiumInputs`, `ProjectWrite`, `LossyWriteError`, `from_design(design, *, issues, corner_ratios=None)`, `write_design`, `stored_board`, `in_frame_of`, `schematic_design`.
- `src/fenolite/backends/altium/roundtrip.py`: `RT_A3_SCOPE`, `EVIDENCE_RT_A3`, `RECORD_PREFIX`; `src/fenolite/backends/altium/rta3.py`: `rt_a3(first, written, second, *, compare, census, from_board) -> ModelRoundTrip`, `without_unwritten`.
- `src/fenolite/backends/altium/backend.py`: `write`, `in_model_frame`, `model_roundtrip`; `src/fenolite/backends/base.py`: `ModelRoundTrip`, `ModelCompare`, `ModelWriter`.
- `src/fenolite/backends/altium/pcbdoc.py`: `Frame.document()`, `FreePad`, `PcbDocSpec.frame`, `.origin`, `.free_pads`, `PlacedComponent.record_unique_id`, `.nets_by_pad`; `project.native_unique_id`.
- `src/fenolite/lens/altium.py`: the stored board of a build, `corner_ratios`, `write_model`.
- `src/fenolite/checks/rta2.py` (`predates_board`), `checks/rta3.py`, `checks/documents.py` (`OPT_IN_DOCUMENT_STAGES`, the stage `roundtrip.rta3`), `cli/cmd_roundtrip.py` (the Altium levels).
- Tests: `tests/unit/backends/altium/test_lower.py`, `test_claims_notes.py`, `tests/unit/checks/test_rta3.py`, `tests/unit/checks/test_rta2.py` and `tests/unit/lens/test_altium_rta2.py` (widened), `tests/unit/cli/test_roundtrip_cmd.py`, `tests/corpus/test_altium_rta3.py`, `tests/kicad/altium/test_rta3_oracle.py` with `tests/kicad/_rta3oracle.py`, and the shared `tests/_altium_sets.py`.

## Sources registered by this change

- No new format fact: the change composes the readers and writers of the other changes.

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-VER-RTA2-3 | For a project built from a script, the built model equals the reading of the written documents for every kind of `RT_A2_SCOPE`, footprints, pads and copper included, within 2 nm | `tests/unit/lens/test_altium_rta2.py` | equal for every example script and the committed samples, with no kind only counted |
| H-A-VER-RTA3 | A PCB document that Altium saved, imported, written by Fenolite and imported again gives an equal model inside `RT_A3_SCOPE` | `tests/corpus/test_altium_rta3.py` | equal on every listed corpus document, from at least three repositories; the unwritten counts are recorded per kind |
| H-A-VER-RTA3-PRJ | A corpus project set (schematics and PCB document), imported, written and imported again gives an equal circuit and board inside the scope, and `parity` and `netlist.assignment_compare` report on the rewrite what they reported on the original | `tests/corpus/test_altium_rta3.py::test_sets` | equal on the five sets; the findings of the two checks are equal by code and count |
| H-A-VER-RTA3-KICAD | KiCad's importer reads the rewrite as Fenolite's reader does: the two reads of the rewrite are equal at the levels 1 to 5 of `equivalent` within the profile's tolerances ("Found", 9) | `tests/kicad/altium/test_rta3_oracle.py` | probe `altium-rta3-kicad` `equal` on the listed documents that KiCad imports; exclusions listed by rule |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Size (design-days)

| group | dd |
|---|---|
| entry and registers | 0.5 |
| lowering from the model | 2 |
| build through the lowering, RT-A2 widened | 1.25 |
| RT-A3 and its stage | 1.25 |
| corpus run and KiCad oracle | 1 |
| claims, roundtrip command, docs | 0.75 |
| closing | 0.25 |

Total: 7. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-verification`: MODIFIED "Round-trip level RT-A2" (the bullets "What the built model holds", "RT-A2 is not judged for a file that Altium saved" and the evidence bullet; the scenario "Built blink holds RT-A2"), copied from the living text; MODIFIED "Check on Altium inputs" (the opt-in stage) and MODIFIED "Altium check stage evidence" (the rows of `roundtrip.rta2` and `roundtrip.rta3`), see below.
- `verification-loop`, MODIFIED "Document check pipeline": the bullet of `roundtrip.rta2` (every kind compared, no `not_in_model`, the two skips) and a new bullet of `roundtrip.rta3`. Since the rebase onto `f7984380` the text is copied from the delta of c0088 (implemented, not archived), which holds the stages `copper.clearance` and `parity`: every bullet and scenario of c0088 is in this delta, so either archive order loses nothing of c0088; if this change is archived first, c0088's delta must not be applied over it without the two bullets of this change.
- `altium-verification`, MODIFIED "Check on Altium inputs" and "Altium check stage evidence": likewise copied from c0088's delta since the rebase (its rows of `copper.clearance` and `parity` are kept).
- `altium-import`, MODIFIED "Altium backend": the sentence "The backend MUST NOT offer `write`" is replaced; copied from the living text.
- `altium-build`, MODIFIED "Altium build outputs": the bullet of the layer texts. The text is copied from the delta of c0087, which is implemented and not archived and holds the newest text of that requirement: c0087 must be archived before this change.
- Archive order: after c0084, c0085, c0086, c0087, c0088 and c0089; before c0092.

## Risks / Trade-offs

- [The build changes its `.fenolite/` model] → it gains the board items; `fenolite check` on old built projects still reads them (the model schema is additive), and RT-A2 on an old project is skipped with a reason.
- [RT-A3 fails on most corpus boards because of items outside the scope] → that is the measurement; items outside the scope are counted, not compared; a failure inside the scope is a writer or reader defect to fix in this change.
- [Ids do not survive a rewrite] → the comparison matches as `equivalent` does, by reference and geometry, when unique ids differ.

## Migration Plan

- The build writes the same documents as before (a regression test over the committed samples) and a larger `.fenolite/board.json`.
- `roundtrip.rta3` is opt-in; default checks do not change.

## Open Questions

- **Should a rewrite keep the unique ids of components?** Default: yes, the writer takes them from the model's native ids when present, so that Altium's component links survive. Implemented; an id that two components share (the instances of a repeated sheet) is not reused.
- **Should the unwritten count fail the stage above a threshold?** Default: no; it is evidence, and c0092 decides what leaves `experimental`.

## Found on 2026-10-06

The proposal was written from a survey. What the code and the corpus showed, and what was changed for it:

1. **The build cannot go through `from_design` and keep its bytes.** What `lens.altium.build_altium` takes from outside the model today, and whether a model with a board can give it:

   | input of the build | from where today | can a model with a board give it? |
   |---|---|---|
   | placements | the script's `PlacementRequest`s, or a copper source | yes: `FootprintInstance.position`, `rotation`, `side`, `locked` |
   | pads of a footprint | the library `FootprintDef` (authored, or resolved by `LibraryResolver`) | yes: `FootprintInstance.pads` |
   | graphics and texts of a footprint | the library `FootprintDef.graphics`, `footprint_texts` | **no**: a `FootprintInstance` holds pads, fields and bodies, and no graphic |
   | corner ratio, pad settings that are dropped or refused | `lens.altium.pad_extras`, from KiCad's opaque pad children | **no**: the model has no field; only KiCad's bag holds them |
   | the PCB library file | the library definitions | **no**: a model holds instances, not definitions |
   | copper | `design.board`, or a `CopperSource` (script copper, a routed KiCad board) checked by `match_source` | yes, once it is in the board |
   | copper layer count and planes | `copper=` and `planes=` of the script | partly: layers from `Board.layers`; a plane only when the layer carries the import's `plane_net` |
   | symbols | resolved KiCad symbols or authored ones | no: generic symbols only |
   | sheets mode, form, directions, drawing sheet, output job | options of the command | no: they are options, not model |

   A lowering from the model alone would drop the footprint graphics and the PCB library of every committed sample, so the scenario "Build and write agree" (byte for byte) cannot hold. Chosen: `from_design` and `write` are a path of their own that shares the writers; the build keeps its path and stores the board it wrote (`BuildOutput.layout`, `.fenolite/board.json`); the scenario is corrected to what is proved: the stored model, written, gives a PCB document that reads to the same model as the build's. `BuildOutput.design` stays the script's model (a test rebuilds the document from it).
2. **`AltiumBackend.write` did not exist**, and the living `altium-import` "Altium backend" forbade it ("The backend MUST NOT offer `write`"), with two tests. The requirement is MODIFIED: the backend has `write`, and its capability report still names no write kind and no `write` operation until c0092 decides what leaves `experimental`.
3. **`roundtrip.py` touches no file by a pinned rule of c0044** (`test_roundtrip_module_works_on_bytes_only`). `rt_a3` is therefore a judge without I/O in a module of its own (`rta3.py`), and the backend's `model_roundtrip` reads and writes. A backend imports no check, so the comparison is handed in (`ModelCompare`).
4. **Rules are not compared by RT-A2.** The PCB document also holds the rules that the writer derives from net classes and defaults, which are no rule of the model; the two lists have no equal state. The read-back of lowered rules is c0084's (`rulemap.lift`, `same_rules`).
5. **The model holds no corner ratio of a rounded rectangle.** A pad read from an Altium document carries its percentage in the `altium` bag; a pad read from KiCad keeps it in KiCad's bag, which a backend must not read (import graph). `lens.altium.write_model` reads it and is the write of a KiCad design; `AltiumBackend.write` refuses such pads instead of guessing. The scenario "A KiCad board written as Altium documents" names the lens.
6. **A written document lies in its own frame.** A build moves the outline to (1000 mil, 1000 mil), so the stored model and the reading differ by a translation: `ModelWriter.in_model_frame` moves the reading back by the outline's corner, exactly. A board that was read from Altium is written without a move (`Frame.document()`), or RT-A3 could not hold.
7. **A zone on two layers is two polygons**, and a hole is a free pad that reads as a footprint: the stored board holds one zone per polygon, and `in_model_frame` leaves the hole pads out.
8. **`roundtrip_exact` has no note column in the matrix.** The notes are `claims.ROUND_TRIP_NOTES`; no cell is set.
9. **The KiCad oracle compares the two reads of the rewrite**, not KiCad's import of the original with KiCad's import of the rewrite: the original holds items that the rewrite does not (counted by RT-A3), and the two imports cannot be paired on them.
10. **Measured limits.** (a) An arc's points can come back more than 2 nm away: the record holds centre, radius and angles, each rounded to a unit, and the model three points; 7 of 517 arcs of the heavy public document, none of the examples. (b) The schematic writer of the build refuses three of five project sets (a comment that starts with `=`, one pin on two nets in the import, a comment outside Windows-1252), so those sets give a PCB document and no project. (c) The via writer refuses a drill that equals the diameter (a rule that c0038 pins): 48 vias of one document are not written. (d) On a rewrite, pins of pads that were not written give one `netlist.uncovered` info. None was worked around; each is in the evidence page.
11. **The "Own sample" scenario said `result.unwritten` is empty.** It is not: board6 holds texts and graphics on a mechanical layer, and the lines of its library footprints are records without a model entity. The scenario states the counts.
12. **`codex/board-authoring-gaps` was read as input** (`docs/board-authoring-withdrawn-requirements.md`, the requirement "Altium board operations"). Nothing was reused: no file, code or text of that branch is in this change.

13. **Rebase onto `0e1a6f4e` (c0083 rest, c0088, c0091).** Both sides are kept in every file. The MODIFIED deltas of "Document check pipeline", "Check on Altium inputs" and "Altium check stage evidence" now start from the text of c0088's delta, so every bullet, row and scenario of c0088 is in them. What c0083 added to an imported circuit is counted by the write as not written (`pin-pad-map`, `module`, `channel`); no number of the RT-A3 tables moved. `AltiumBackend.write` runs no copper guard: the guard of c0088 belongs to the build command. The kit of c0091 builds through the build path, and its tests pass with the stored board.

## Decisions of the maintainer (2026-10-06)

1. **Task 2.2 stays open** and is closed by a later change, c0126: footprint instance graphics, corner ratio and library in the model, so that the build goes through `from_design` and a rewritten board keeps its footprint silkscreen. c0090 lands with the two paths as implemented.
2. **Arcs.** The record's own centre, radius and angles are kept for an arc that was read, by follow-up change c0127; it closes the difference of `altium-third-party-pcbdoc-08`. Until it lands the 2 nm claim excludes arcs.
3. **Vias with a drill equal to the diameter** are relaxed for the rewrite of an imported document only, by follow-up change c0128; a build from a script keeps refusing.
4. **A tolerant schematic write for imported circuits** belongs to v0.5a, with `convert`; v0.3 records the sets 01, 02 and 04 as not judged in the project round trip.
