## Context

- **Document pipeline** (`checks/documents.py`): `DOCUMENT_STAGES = model.validate, erc.lite, netlist.assignment_compare, roundtrip.rta0, roundtrip.rta1, roundtrip.rta2`. The KiCad pipeline (`checks/stages.py`) has `copper.clearance` and `parity`, which take a `DesignRulesSource`, a `BoardFrame` and a `ParityInputs` from the validator.
- **The copper check** (`checks/copper.py`, c0029, c0068): exact shorts and clearances on tracks, arcs, vias, pads and filled zones, with `copper.rules-incomplete` and `copper.item-unsupported` when it cannot judge.
- **The Altium import** gives tracks, arcs, vias, pads with padstacks, zones from polygons (with their poured regions when the document holds them), the outline and the rules that map.
- **c0072's design** says: "No Altium input yet (v0.3 adds an adapter for the same comparison)". No adapter was added; this change adds it.

## Found on 2026-10-06

The proposal was written from a survey. Reading the code and measuring the public corpus gave these
corrections; the spec, this design and the tasks follow them.

1. **The copper check judges no board-edge clearance.** `checks/copper.py` judges shorts, clearance and
   zone-outline overlaps; edge clearance is a placement rule (`placement.legality`). `BoardFrame` gives pads
   and courtyards, not the outline. "shorts, clearance, edge" became "shorts, clearance, zone overlaps", and
   decision 4 is void.
2. **The Altium backend had no board frame.** The KiCad frame reads KiCad's own tokens, and a backend may
   not import another (`package-layering`). `backends/altium/frame.py` is new: the pads of an imported board
   from the model alone. Before it, 383 pads of the third public document were left out of the check
   (c0122's measurement).
3. **A polygon has no clearance of its own** (S-0530). The import leaves the model's default zone clearance
   of 0.5 mm, which is no value of the document: c0122 measured 266 clearance findings against it on
   `altium-third-party-pcbdoc-03`. The rules source now gives every zone the clearance 0, so the Clearance
   rules alone decide. That document's three Clearance records are outside the rule table (two scoped by
   layer, one with a matrix key), so no clearance is in force there: the 266 are gone, the pour is counted in
   `summary.zones_unjudged`, 954 pairs are judged for shorts only, and the stage is `UNVERIFIED`. Task 2.3
   was added for this.
4. **Only Clearance records make the rules incomplete.** Every public document holds 28 to 37 rule kinds
   without a counterpart. Naming them all in `copper.rules-incomplete`, as the proposal said, would lower
   every native board for rules the copper check does not read. The stage counts the enabled Clearance
   records that stay opaque; the import already reports the other kinds.
5. **Internal planes are drawn in negative** (S-0531). The import keeps a plane as a copper layer and the
   lines drawn on it as tracks without a net. They cut the plane and are no copper: on two public documents
   they gave 71 false shorts and 48 false clearance findings. The rules source takes them out and reports the
   planes as copper that was not judged (`DesignRules.left_out`, a new field).
6. **The unit rounds.** The document counts in units of 2.54 nm, the model in nanometres. Copper at exactly
   its clearance reads 1 to 4 nm closer: 1 088 findings on the four public documents with a mapped rule.
   The rules source lowers a clearance rule by 5 nm (`UNIT_SLACK_NM`).
7. **`ParityInputs` does not fit a document backend.** It takes a `ProjectSet` and reads the schematic
   itself; the document pipeline already holds both readings, and the side needs the board (point 8). A new
   protocol `DocumentParity.parity_side(schematic, board)` serves it; `parity_stage` is KiCad's wrapper (it
   names `.kicad_sch`) and is not used, `checks.parity.compare` is.
8. **Two spellings differ in every project.** The schematic names a footprint's library by the model's
   file, the PCB document by where the part was placed from: 503 placed footprints of the five sets
   differ in the library alone. And the import does not give every net the name the PCB document holds: 139
   pads of the two hierarchical sets are on a net of another name with the same pads (measured again after
   c0083's channel names and pin-to-pad map; 332 of four sets and 189 before). The side is given in the
   board's spelling where the content agrees (`adapter/parity.py`); a split, joined or open net stays a
   finding, and every remaining net conflict of the sets is one that `netlist.assignment_compare` flags too.
9. **The guard cannot live in `lens`.** `lens` may not import `checks`; the KiCad guard is in
   `cli/cmd_build.py`, and so is the Altium one. It reads the planned bytes back, so it does not depend on
   how the build makes them (c0090 reroutes that).
10. **There is no `--no-copper-guard`.** The KiCad guard has `--copper-check refuse|warn` and no way to
    switch it off ("Copper guard before writing"). The Altium guard takes the same option, which was a usage
    error with that target.
11. **No record edit was needed.** The planted faults are in the design script and the build writes them
    (`tests/_altium_drc.py`); the scenarios say so instead of "by record edit".
12. **c0072 is not archived.** Its parity requirements are not in the living specs, so nothing of it is
    MODIFIED here; the parity codes are named by `checks.parity.PARITY_ISSUE_CODES`.

## Goals / Non-Goals

**Goals:**
- `fenolite check` on an Altium project fails on a short, a clearance violation and a board that disagrees with its schematic.
- The same board gives the same copper findings whichever backend read it.
- A stage never passes silently on copper or rules it did not judge.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Stage order for documents**: `model.validate`, `erc.lite`, `copper.clearance`, `parity`, `netlist.assignment_compare`, `roundtrip.rta0`, `roundtrip.rta1`, `roundtrip.rta2`. Both new stages are default stages and need no tool.
2. **Rules source.** `AltiumBackend.design_rules(design, project)` returns the import with what the copper check needs beyond the mapped rules: zones without a clearance of their own, clearance rules lowered by the unit's slack, the lines of internal planes taken out, and the count of enabled Clearance records that stayed opaque (read from `Rules6/Data` alone); the stage reports `copper.rules-incomplete` for them, as the KiCad stage does for rules it cannot lift.
3. **Polygons.** A polygon with poured regions is checked as a filled zone with those regions; an unpoured polygon is not copper and is counted in `summary.unpoured`; when any exists the stage adds `copper.item-unsupported` (warning) once with the count, and its evidence is `UNVERIFIED`, because the fabricated board will hold copper the check did not see. A filled zone that no clearance applies to is counted in `summary.zones_unjudged` with one `copper.rules-incomplete`: it is judged for shorts, never against a default.
4. **Frame.** `AltiumBackend.board_pads` and `placed_extents` (`BoardFrame`) give the pads and the hull of each footprint's pads. (The proposal's "outline for the edge clearance" is void: "Found on 2026-10-06", point 1.)
5. **Parity side.** `AltiumBackend.parity_side(schematic, board)` (`DocumentParity`) builds `SchematicSide` from the imported schematic: components by designator (after c0083's channels), value from the comment, footprint from the footprint model's name, pads from the pins and `Component.pin_pad_map` when the component holds one, nodes from the import's nets; a footprint's library and a net's name are given in the board's spelling where the content agrees. `fold` and `single_prefix` are empty: Altium has no escaped slash and no generated single-pin nets.
6. **Parity without a schematic or without a board** is skipped with `no-schematic` or `single-source`, the reasons the pipeline already has.
7. **Build guard.** Before it plans its writes, the build reads the planned PCB document back and judges it with the copper check and the rules that document holds, and refuses on `copper.short` (exit 5), as "Copper guard" does for KiCad; clearance findings are reported as warnings and do not refuse. `--copper-check warn` writes a board with a short.
8. **Cut order.** First the build guard, then the optional Part D, never the two stages.

## Files and public API

- `src/fenolite/checks/documents.py`: the two stages in `DOCUMENT_STAGES`; runners that call `copper_stage` and `parity_stage`.
- `src/fenolite/checks/documents.py` also holds `document_copper`, `unjudged_copper` and `project_of`.
- `src/fenolite/backends/base.py`: `DocumentParity`; `DesignRules.left_out`. `src/fenolite/checks/copper.py`: `rules_issues` reports `left_out`.
- `src/fenolite/backends/altium/backend.py`: `design_rules`, `rules_from_bytes`, `board_from_bytes`, `board_pads`, `placed_extents`, `parity_side`; `UNIT_SLACK_NM`.
- `src/fenolite/backends/altium/frame.py`: `board_pads`, `placed_extents`, `shape_entries`, `corner_radius`.
- `src/fenolite/backends/altium/read/pcb.py`: `read_rule_fields`.
- `src/fenolite/backends/altium/adapter/parity.py`: `side_of(schematic, board=None) -> SchematicSide`, `board_names`, `footprint_name`, `pads_of`.
- `src/fenolite/cli/cmd_build.py`: `altium_copper_guard`; `src/fenolite/cli/cmd_parity.py`: document input.
- Tests: `tests/unit/checks/test_document_copper.py`, `test_document_parity.py`, `tests/unit/backends/altium/test_frame.py`, `tests/unit/backends/altium/adapter/test_parity_side.py`, `tests/unit/cli/test_check_altium_copper.py`, `tests/unit/cli/test_build_altium_guard.py`, `tests/kicad/altium/test_copper_same.py`, `tests/corpus/test_altium_copper.py`; helpers `tests/_altium_drc.py`, `tests/_altium_sets.py`.

## Sources registered by this change

- No new record is read: the stages read what c0041, c0043 and c0084 read. Two facts about what the records mean were needed and are registered (block S-0530 to S-0539 of this change): S-0530, Altium's documentation page on polygons (a polygon's clearance is its rule's), and S-0531, the page on internal planes (a plane is drawn in negative). Both were read for facts on 2026-10-06; nothing is transcribed. The rows are in `docs/formats/altium/import.md`, "The copper check and the parity comparison".
- For Part D only: Altium's public documentation of the design rule check report (read for the names of the two violation kinds), to be registered when Part D runs.

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

### Session 2: the same copper in Altium's own check (required; added by change c0131 on 2026-10-07)

This is a step of the maintainer's second session of Altium work, and it is not optional: it settles whether the 25 clearance findings that are 8 to 20 nm short of their rule (c0131, "Decisions (2026-10-07)") are findings of the boards or of Fenolite's reading of a pad.

Document: the public row `altium-third-party-pcbdoc-03` of `tests/corpus/manifest.toml` (S-0172), chosen because it is the smallest document that shows the class and shows it most often: 6 fills, 383 pads, 604 tracks and 47 vias on two copper layers, with 7 findings; the other small candidate, `-01`, holds 2 findings among 40 fills, 735 pads, 1 346 tracks and 646 vias on four layers, two of them planes. Get it from `https://raw.githubusercontent.com/TobiasRothlin/AltiumPCBLibrary/fdff76666ffbfa4a1ba2e3d3fe5a52c090b45cb7/PCBLibrary/PCB1.PcbDoc` (commit `fdff76666ffbfa4a1ba2e3d3fe5a52c090b45cb7`, SHA-256 `567fd0dfdba54c04adbdd2cc19b427c894b7a94aa953aa361f3e0afc71db12b3`, Apache-2.0), or from the corpus cache; check the SHA-256 before opening. It is a public document, opened read-only: do not save it, and nothing that Altium writes comes back to the repository. The file is not copied into the repository. The locators below are quoted from the public document so that the place can be found.

What Fenolite reports: 7 `copper.clearance`, all between ONE pad and seven segments of ONE track net that runs around it on the `Bottom Layer`: pad `J2-1` (a square through-hole pad of 1.62 mm, net `NetJ2_1`) and the track of net `Net*_4`, 0.127 mm wide. The gaps are 126 991 nm (five segments) and 126 992 nm (two), against the rule `Clearance_2` (5 mil = 127 000 nm; the cell for the outer layers of the document's clearance matrix, priority 2). Places, in mm from the document's origin (which is at 0, 0): (150.929, 96.885), (150.040, 98.695), (149.463, 98.600), (149.491, 98.667), (149.491, 96.913); the first two are corners shared by two segments each.

4. D4: open the document, do not repour, and run Tools » Design Rule Check with only the Clearance rules enabled.
5. D5: report in one line: "Altium reports N violations of rule `Clearance_2` between pad `J2-1` and net `Net*_4`" (N from 0 to 7), the tool as `AD <major>.<minor>` and the date.
6. D6: select pad `J2-1` and report its X size and Y size as the properties panel shows them, in mil with every digit shown.

What follows. If Altium reports the pairs (N > 0): they are findings of the board, the 25 stay errors, and nothing changes. If Altium passes them (N = 0): Fenolite reads something of the pad wrong, and the follow-up is to find the pad-size fact that is read wrong, starting from D6 (Fenolite reads the pad as 637 795 units wide, 63.7795 mil, an odd number of units, which puts its edge on half a unit); no tolerance is added to the check in either case.

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

- `altium-verification`, "Check on Altium inputs" and "Altium check stage evidence": the scenarios and the evidence table grow (MODIFIED at task 0.1).
- `verification-loop`, "Document check pipeline": MODIFIED, because it spells the stage tuple and the stages (the proposal said "no delta").
- `backend-protocol`, "Design rules source": MODIFIED for `left_out`. `design-dsl`, "Copper guard before writing": MODIFIED, because it forbade the guard and the option with the Altium target.
- Archive order: after c0084; before c0091, whose kit compares its DRC step with this stage.

## Risks / Trade-offs

- [Many boards have unpoured polygons] → the stage says so and drops to `UNVERIFIED`; it still finds shorts between tracks, vias and pads.
- [The two readings of one board differ by rounding] → the criterion is 2 nm, the tolerance of the PCB unit; larger differences are import defects to fix, not to hide.
- [c0084 not archived] → the stage runs with three rule kinds and `copper.rules-incomplete` names the rest.

## Migration Plan

- `fenolite check` on Altium input runs two more stages by default and can exit 5 where it exited 0. The changelog says so, as a change of behaviour; `--stages` selects the old set. Confirmed by the maintainer on 2026-10-06: on by default.
- Rollback: remove the two names from `DOCUMENT_STAGES`.

## Open Questions

- **Should the build guard refuse on clearance findings too?** Default: no. (The KiCad guard does refuse a clearance error; the Altium guard reports it as a warning, as this change's requirement says.)
- **Should the import itself stop lowering the lines of an internal plane as tracks, and give a zone no default clearance?** Not decided here: this change corrects both in the view the copper check gets (`design_rules`), and leaves the import, its ids and its round trips as they are. A follow-up of c0043 would move the two corrections into the adapter.
- **Should more Clearance records map (a layer scope, a matrix that is uniform)?** That is c0084's table; until then three of the seven public documents have no clearance in force and are judged for shorts only.
- **Should `fenolite parity` take an Altium project?** Default: yes, through the same adapter; `--netlist` is then ignored with a usage error for `kicad`.
