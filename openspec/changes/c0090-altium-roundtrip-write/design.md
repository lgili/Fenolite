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

1. **One lowering.** `lower.from_design(design) -> AltiumInputs` produces what the writers take today from the build (sheets, symbols, footprints, placements, copper, zones, rules, stack, classes) from a `Design` alone. The build is changed to go through it, so there is one path: script → model with board → `from_design` → writers. The built model then holds the footprints and copper that are written, and RT-A2 can compare them.
2. **RT-A2, widened.** With the built model holding the board, `RT_A2_SCOPE` is compared in full: footprint position, rotation and side; pad number, net, position and size; tracks, arcs, vias, zones; rules of the `exact` kinds. The successor row replaces the bounded `H-A-VER-RTA2-2`.
3. **RT-A3.** `rt_a3(documents)`: import → write to a temporary folder → import; compare the two models with `checks.diff` inside `RT_A3_SCOPE` (the written scope) within 2 nm; outside the scope, count the records of the first reading per kind (`unwritten`). The level holds when the comparison is equal; the count is reported, never part of the verdict, and the stage's evidence names it.
4. **Schematic side.** RT-A3 covers the PCB document and the circuit. The schematic's presentation (where symbols and wires are) is not kept by a rewrite: the schematic is generated from the circuit, and the stage says `presentation: regenerated`. Keeping an Altium schematic's drawing is not in v0.4.
5. **Corpus list.** The run uses the PCB documents and project sets of c0041's and c0044's lists that are not marked heavy. A document that cannot pass for a reason outside this change (an import defect) is listed with its cause and an issue reference, and does not block the row when at least the listed minimum passes; the minimum is three repositories, as `H-A-VER-RTA0` requires.
6. **Claims.** `roundtrip_exact` is set for `altium_pcbdoc` and `altium_prjpcb` only if RT-A3 holds with an empty `unwritten` on the corpus list, which is not expected; otherwise the cell stays empty and a new matrix column note says `RT-A3 inside the written scope`. No cell is set from Fenolite's own files alone.
7. **Cut order.** First `fenolite roundtrip` on Altium input, then the KiCad oracle on rewritten corpus files, never `from_design`, the widened RT-A2 and RT-A3.

## Files and public API

- `src/fenolite/backends/altium/lower.py`: `AltiumInputs`, `from_design(design, *, issues) -> AltiumInputs`.
- `src/fenolite/backends/altium/roundtrip.py`: `RT_A3_SCOPE`, `rt_a3(documents) -> RtA3(equal, differences, unwritten)`, `EVIDENCE_RT_A3`.
- `src/fenolite/checks/documents.py`: the stage `roundtrip.rta3` (opt-in, like `roundtrip.rt2`).
- Tests: `tests/unit/backends/altium/test_lower.py`, `tests/unit/checks/test_rta3.py`, `tests/unit/lens/test_altium_rta2.py` (widened), `tests/corpus/test_altium_rta3.py`, `tests/kicad/altium/test_rta3_oracle.py`.

## Sources registered by this change

- No new format fact: the change composes the readers and writers of the other changes.

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-VER-RTA2-3 | For a project built from a script, the built model equals the reading of the written documents for every kind of `RT_A2_SCOPE`, footprints, pads and copper included, within 2 nm | `tests/unit/lens/test_altium_rta2.py` | equal for every example script and the committed samples, with no kind only counted |
| H-A-VER-RTA3 | A PCB document that Altium saved, imported, written by Fenolite and imported again gives an equal model inside `RT_A3_SCOPE` | `tests/corpus/test_altium_rta3.py` | equal on every listed corpus document, from at least three repositories; the unwritten counts are recorded per kind |
| H-A-VER-RTA3-PRJ | A corpus project set (schematics and PCB document), imported, written and imported again gives an equal circuit and board inside the scope, and `parity` and `netlist.assignment_compare` report on the rewrite what they reported on the original | `tests/corpus/test_altium_rta3.py::test_sets` | equal on the five sets; the findings of the two checks are equal by code and count |
| H-A-VER-RTA3-KICAD | KiCad's import of the original document and of the rewritten one are equal at level 5 of `equivalent` within the profile's tolerances | `tests/kicad/altium/test_rta3_oracle.py` | probe `altium-rta3-kicad` `equal` on the listed documents that KiCad imports; exclusions listed by rule |

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

- `altium-verification`, "Round-trip level RT-A2": the bullets "What the built model holds" and "RT-A2 is not judged for a file that Altium saved" are superseded; "Check on Altium inputs" gains the opt-in stage. Task 0.1 writes them as MODIFIED from the living text.
- `altium-build`, "Altium build outputs": `.fenolite/` holds the board that was written (MODIFIED at task 0.1).
- Archive order: after c0084, c0085, c0086 and c0089; before c0092.

## Risks / Trade-offs

- [The build changes its `.fenolite/` model] → it gains the board items; `fenolite check` on old built projects still reads them (the model schema is additive), and RT-A2 on an old project is skipped with a reason.
- [RT-A3 fails on most corpus boards because of items outside the scope] → that is the measurement; items outside the scope are counted, not compared; a failure inside the scope is a writer or reader defect to fix in this change.
- [Ids do not survive a rewrite] → the comparison matches as `equivalent` does, by reference and geometry, when unique ids differ.

## Migration Plan

- The build writes the same documents as before (a regression test over the committed samples) and a larger `.fenolite/board.json`.
- `roundtrip.rta3` is opt-in; default checks do not change.

## Open Questions

- **Should a rewrite keep the unique ids of components?** Default: yes, the writer takes them from the model's native ids when present, so that Altium's component links survive.
- **Should the unwritten count fail the stage above a threshold?** Default: no; it is evidence, and c0092 decides what leaves `experimental`.
