## Context

- **Document pipeline** (`checks/documents.py`): `DOCUMENT_STAGES = model.validate, erc.lite, netlist.assignment_compare, roundtrip.rta0, roundtrip.rta1, roundtrip.rta2`. The KiCad pipeline (`checks/stages.py`) has `copper.clearance` and `parity`, which take a `DesignRulesSource`, a `BoardFrame` and a `ParityInputs` from the validator.
- **The copper check** (`checks/copper.py`, c0029, c0068): exact shorts and clearances on tracks, arcs, vias, pads and filled zones, with `copper.rules-incomplete` and `copper.item-unsupported` when it cannot judge.
- **The Altium import** gives tracks, arcs, vias, pads with padstacks, zones from polygons (with their poured regions when the document holds them), the outline and the rules that map.
- **c0072's design** says: "No Altium input yet (v0.3 adds an adapter for the same comparison)". No adapter was added; this change adds it.

## Goals / Non-Goals

**Goals:**
- `fenolite check` on an Altium project fails on a short, a clearance violation and a board that disagrees with its schematic.
- The same board gives the same copper findings whichever backend read it.
- A stage never passes silently on copper or rules it did not judge.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Stage order for documents**: `model.validate`, `erc.lite`, `copper.clearance`, `parity`, `netlist.assignment_compare`, `roundtrip.rta0`, `roundtrip.rta1`, `roundtrip.rta2`. Both new stages are default stages and need no tool.
2. **Rules source.** `AltiumBackend.design_rules(project)` returns the neutral rules of the PCB document (the mapped kinds of `rulemap`, c0084) and the list of kinds that stayed opaque; the stage reports `copper.rules-incomplete` with that list, as the KiCad stage does for a rules file it cannot read fully.
3. **Polygons.** A polygon with poured regions is checked as a filled zone with those regions; an unpoured polygon is not copper and is counted in `summary.unpoured`; when any exists the stage adds `copper.item-unsupported` (warning) once with the count, and its evidence is `UNVERIFIED`, because the fabricated board will hold copper the check did not see.
4. **Frame.** `AltiumBackend.board_frame` gives the outline for the edge clearance; a board without a closed outline is reported as on KiCad.
5. **Parity side.** `AltiumBackend.schematic_side(documents)` builds `SchematicSide` from the imported schematic: components by designator (after c0083's channels), value from the comment, footprint from the footprint model's name, pins from the symbol and the pin-to-pad map, nodes from the import's nets. `fold` and `single_prefix` are empty: Altium has no escaped slash and no generated single-pin nets.
6. **Parity without a schematic or without a board** is skipped with `no-schematic` or `single-source`, the reasons the pipeline already has.
7. **Build guard.** After writing, the build checks the design it wrote with the copper check and the design's rules, and refuses on `copper.short` (exit 5), as "Copper guard" does for KiCad; clearance findings are reported and do not refuse.
8. **Cut order.** First the build guard, then the optional Part D, never the two stages.

## Files and public API

- `src/fenolite/checks/documents.py`: the two stages in `DOCUMENT_STAGES`; runners that call `copper_stage` and `parity_stage`.
- `src/fenolite/backends/altium/backend.py`: `design_rules`, `board_frame`, `schematic_side`.
- `src/fenolite/backends/altium/adapter/parity.py`: `side_of(project_import) -> SchematicSide`.
- Tests: `tests/unit/checks/test_document_copper.py`, `test_document_parity.py`, `tests/unit/backends/altium/adapter/test_parity_side.py`, `tests/unit/cli/test_check_altium_copper.py`, `tests/kicad/altium/test_copper_same.py`, `tests/corpus/test_altium_copper.py`.

## Sources registered by this change

- No new format fact: the stages read what c0041, c0043 and c0084 read.
- For Part D only: Altium's public documentation of the design rule check report (read for the names of the two violation kinds).

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-DRC-SAME | For a board that Fenolite reads through both backends, `copper.clearance` reports the same shorts and clearance findings, by kind, net pair and place within 2 nm | `tests/kicad/altium/test_copper_same.py` (samples built for both targets) and `tests/corpus/test_altium_copper.py` (corpus documents that KiCad imports) | equal on every sample and on every corpus document listed in the page; differences are listed with their cause |
| H-A-DRC-PARITY | On the corpus project sets, the parity findings of the Altium reading are those that `netlist.assignment_compare` and the component comparison of `equivalent` level 1 imply, and a planted edit gives the finding of its kind | `tests/corpus/test_altium_copper.py::test_parity` and `tests/unit/checks/test_document_parity.py` | no finding without a cause on the five sets; each of the six planted edits of c0072 gives its code |
| H-A-DRC-ALTIUM | Altium's design rule check reports the two planted violations that `copper.clearance` reports on the sample, and no other clearance or short | author report, Part D | two violations of the kinds named, at the places named |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Author report: Part D, the same two violations (optional)

Files: the project `rules` of c0084's Part U (it holds a narrow track and two pads closer than the clearance).

1. D1: open the PCB document, repour all polygons, and run Tools » Design Rule Check with the default report.
2. D2: report the clearance and short-circuit violations: for each, the two nets and the layer. Expected: the one clearance violation that `fenolite check` reports, and no short.
3. D3: report whether Altium lists a violation of a kind that Fenolite's table says it judges and that Fenolite did not report.

The maintainer reports one generic outcome per step (`as expected`, or what differed in one sentence), the tool as `AD <major>.<minor>` and the date. No file that Altium wrote is committed. A step that fails refutes the row it names: the row keeps its id and gets a registered successor (`verification-evidence`, "Refuted rows keep their id"). An author report never moves an operation out of `experimental` ("Author reports never promote an operation").

## Size (design-days)

| group | dd |
|---|---|
| entry | 0.25 |
| rules source and frame | 0.75 |
| copper stage on documents | 1 |
| parity side and stage | 1.25 |
| build guard | 0.5 |
| agreement runs and evidence | 0.75 |
| docs and report | 0.25 |
| closing | 0.25 |

Total: 5. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-verification`, "Check on Altium inputs" and "Altium check stage evidence": the stage list and the evidence table grow (MODIFIED at task 0.1).
- `verification-loop`: no delta; the stages are those of that capability, run by the document pipeline.
- Archive order: after c0084; before c0091, whose kit compares its DRC step with this stage.

## Risks / Trade-offs

- [Many boards have unpoured polygons] → the stage says so and drops to `UNVERIFIED`; it still finds shorts between tracks, vias and pads.
- [The two readings of one board differ by rounding] → the criterion is 2 nm, the tolerance of the PCB unit; larger differences are import defects to fix, not to hide.
- [c0084 not archived] → the stage runs with three rule kinds and `copper.rules-incomplete` names the rest.

## Migration Plan

- `fenolite check` on Altium input runs two more stages by default and can exit 5 where it exited 0. The changelog says so, as a change of behaviour; `--stages` selects the old set. Confirmed by the maintainer on 2026-10-06: on by default.
- Rollback: remove the two names from `DOCUMENT_STAGES`.

## Open Questions

- **Should the build guard refuse on clearance findings too?** Default: no, as on KiCad.
- **Should `fenolite parity` take an Altium project?** Default: yes, through the same adapter; `--netlist` is then ignored with a usage error for `kicad`.
