## Context

**Scope.** Milestone v0.5a, the first item ("conversion between KiCad and the second backend, with a report of what is kept or lost"), direction KiCad to Altium. c0159 builds the command and reports every loss of today's writers; this change closes the losses that a public format fact and an existing reader allow to close, and leaves the rest reported. It also takes the two items that the maintainer put in v0.5a "with `convert`" on 2026-10-06: the tolerant schematic write for circuits that were read (`docs/evidence/altium-roundtrip.md`, "Project sets"; `H-A-VER-RTA3-PRJ`) and the PCB library derived from a model (design of c0126, item 7).

**What exists** (checked on `origin/dev` at `f802b60`, 2026-10-09):

| where | what |
|---|---|
| `src/fenolite/backends/altium/cfb.py:65` | `CompoundTooLarge` when the FAT needs more than `MAX_FAT_SECTORS` (109), the entries the header holds |
| `docs/formats/altium/compound-file.md:27` | the DIFAT row (S-0145, `INFERRED`): a FAT of more than 109 sectors needs DIFAT sectors; never exercised by a written or read sample |
| `src/fenolite/backends/altium/pcblib.py:164` | a pad with a per-layer stack is refused ("has a per-layer padstack") |
| `docs/formats/altium/import.md:43`–`48` | the read rows of pad shapes, stack modes 0, 1 and 2 (Simple, Top-Middle-Bottom, Full Stack), hole shapes and offsets (S-0160, S-0302, `INFERRED`, `H-A-IMP-PADSTACK`) |
| `lower.py:641` `_pad_problem` | a free pad may lack a number; a footprint's pad may not |
| `lower.py:84` `MORE_KINDS`; `pcbdoc.py` | footprint graphics and texts on Mechanical 1 to 16 and the overlays (c0126); a KiCad layer with no Altium layer is not written |
| `src/fenolite/backends/altium/project.py:432` `generic_symbols`; `--altium-symbols graphics` (c0086); `--altium-sheets modules` (c0037) | the schematic writer: generic rectangles or a symbol's own graphics, one sheet or one per module |
| `docs/formats/altium/schematic-records.md:40`–`41` | `%UTF8%` twins of non-ASCII values (S-0130, S-0187, S-0188, S-0279; `CORPUS-VERIFIED`, 22 rows) |
| `docs/formats/altium/schematic-ascii.md:83` | a parameter text that starts with `=` names another parameter of its owner (S-0130, `INFERRED`) |
| `lower.py:1440` `write_design` | the schematic and project file are not written when the schematic writer refuses the circuit (one `altium.not-lowered` info, `where` `schematic`) |
| `docs/evidence/altium-roundtrip.md`, "Project sets" | three of five public project sets not judged: a comment that starts with `=`, one pin on two nets in the import, a comment outside Windows-1252 |

**Measured on 2026-10-09**: the table of c0159's design ("Context"). The losses this change addresses, by board count among the 16 written (first reason per kind, which is all `lower` keeps before c0159): `pad` on 13 boards (per-layer padstack on 2, connector pad on 2, a pad without a number on 6, a custom shape on 1, the others not named by the first reason); drawings on `Dwgs.User`, `Cmts.User` and `User.N` (`graphic`, `footprint-graphic`, `footprint-text`) on 12; texts on `F.Cu` and `B.Cu` on 6; `CompoundTooLarge` on 2 (119 and 181 FAT sectors). Task 1.1 counts them again per reason with c0159's report, which is the baseline of this change.

## Goals / Non-Goals

**Goals**
- Every KiCad 10.0.6 demo board is written.
- Each loss of the baseline is either closed, with a public fact row, or stays reported with its reason.
- A converted project opens in Altium Designer with its library and its schematic (Part T).

**Non-Goals**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **DIFAT sectors.** `cfb.write_compound` writes the FAT sectors past the 109th into DIFAT sectors, each holding 127 FAT sector numbers and the number of the next DIFAT sector (ENDOFCHAIN in the last), with the header's first DIFAT sector and count set (`compound-file.md`, rows of the header and the DIFAT; S-0145). The DIFAT sectors are marked `DIFSECT` in the FAT. `CompoundTooLarge` remains for a file beyond what a version-3 file holds. The reader (`read/cfb.py`) gains the DIFAT chain if it lacks it (task 1.2 checks). Rejected: a version-4 file with 4096-byte sectors: no saved Altium file of the corpus is version 4.
2. **Full-stack pads.** A pad whose per-layer stack gives each copper layer a plain shape (circle, oval, rectangle, rounded rectangle with a ratio) is written with stack mode 2 and the sixth subrecord's tables, by the read rows of `import.md` turned into write rows of `pcb-library.md` with the same sources. A layer with a custom shape keeps the pad a loss. A stack of three distinct shapes (top, inner, bottom) uses mode 1. Rejected: the largest shape on every layer: it adds copper.
3. **Connector and free pads.** A KiCad pad of kind `connect` (copper without a hole, paste or mask) is a surface pad with the paste and mask expansions that remove both (the expansion rows of `import.md:48` turned into write rows); a pad without a number inside a footprint is written as a pad of that footprint with an empty designator when a public source states that Altium accepts one (task 1.3), else as a free pad at its board position and counted `changed`. Rejected: a numbered placeholder (`?1`): it invents a pin.
4. **The layer map.** `lower.KICAD_MECHANICAL` maps `User.1` to `User.8` to Mechanical 1 to 8, `Dwgs.User` to Mechanical 9, `Cmts.User` to Mechanical 10, `Eco1.User` and `Eco2.User` to Mechanical 11 and 12, and keeps `F.Fab`, `B.Fab`, `F.CrtYd` and `B.CrtYd` on Mechanical 13 to 16, where `pcbrecords.LAYER_MAP` puts them since c0126; a layer outside the map (`User.9` and above, `Margin`) stays a loss. The map is one table, documented in `docs/conversion.md`, and the written document names each mechanical layer after its KiCad name. Rejected: user configuration of the map in this change (open question 2, decided by the maintainer on 2026-10-09: not in v0.5a). A text on a copper layer is a copper text record of that layer.
5. **The derived library.** `<name>.PcbLib` holds one footprint per distinct footprint name of the board (the part of `lib_ref` after `:`), built from the first instance by reference order in the footprint's own frame (pads, graphics, texts, bodies as c0126 and c0121 write them for a build). Every component links it. An instance whose pads or graphics differ from that definition (a footprint edited on the board) is counted `changed` with the reason "differs from the library footprint"; the document keeps the instance as it is. Rejected: one library footprint per instance (`R1`, `R2`): the library then means nothing to a user.
6. **The schematic of a KiCad source.** When the source project has a schematic, the converted schematic takes the circuit from it (c0158's schematic side: components, values, nets) and the symbol graphics from the schematic's own `lib_symbols`, written with `--altium-symbols graphics` and one Altium sheet per KiCad sheet (`--altium-sheets modules`, a KiCad sheet path as the module). Symbol positions come from the writer's layout, not from KiCad: the report row `schematic` is `changed` with "positions and wires are not converted". Without a schematic, today's generic sheet stays. Rejected: converting wires, labels and positions: a schematic editor's presentation is after 1.0 (Open decisions row 3, "schematic editing that keeps presentation").
7. **Tolerant texts and nets.** For a circuit that was read (a converted source or an RT-A3 rewrite):
   - a comment that starts with `=` and comes from an Altium read is written as read: in that document it names a parameter (`schematic-ascii.md:83`), and the rewrite gives the reference back. From a KiCad source it is written with a leading space and counted `changed`;
   - a text outside Windows-1252 is written in the binary form with its `%UTF8%` twin holding the text and a plain value with `?` for each character outside the code page (`schematic-records.md:40`–`41`); the ASCII form refuses it as today;
   - a pin on two nets in the import is written on the net that holds more pins (ties by name) and counted lost under `pin-net`.
   With these three rules the three sets of `H-A-VER-RTA3-PRJ` are judged; task 5.3 measures them.
8. **What stays reported.** Custom pad shapes, the fitted flag, net ties, dimensions, a keep-out without a restriction that the record carries, the arcs of an outline written as edges, the stack-up values without a key. Each keeps its reason in the report.
9. **Part T of the maintainer's Altium work.** Three converted demo projects (one with DIFAT sectors, one with full-stack pads, one with a converted schematic), handed in `~/fenolite-altium-checks/session-3/T-convert/` with their SHA-256: T1 open the project; T2 compile the schematic (no error, the messages counted); T3 open the PCB document and repour; T4 run the design rule check with the document's rules (count of violations per rule); T5 update the PCB from the schematic and say whether the update proposes changes; T6 open the PCB library and place one footprint. The report is recorded as an author report (tool `AD <major>.<minor>`, date, one generic outcome per step, no artefact). It does not make any write leave `experimental`.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/altium/cfb.py`, `read/cfb.py` | DIFAT sectors written; read if missing |
| `src/fenolite/backends/altium/pcbrecords.py`, `pcblib.py` | stack modes 1 and 2; connector pads; pads without a number |
| `src/fenolite/backends/altium/lower.py` | `KICAD_MECHANICAL`; copper texts; the derived library; `changed` reasons |
| `src/fenolite/backends/altium/project.py`, `schdoc.py` | the schematic from a source's symbols and sheets; tolerant texts and nets |
| `src/fenolite/convert/to_altium.py` | the KiCad schematic as circuit and symbols; the derived library in the files |
| `docs/formats/altium/compound-file.md`, `pcb-library.md`, `pcb-document.md`, `schematic-records.md` | the write rows |
| `docs/evidence/altium-pcb.md`, `docs/evidence/altium-schematic.md` | Part T and its report |
| `tests/unit/backends/altium/test_cfb_difat.py`, `test_pcblib_stacks.py`, `test_lower_layers.py`, `test_derived_library.py`, `test_schematic_tolerant.py` (new) | the scenarios |
| `tests/corpus/test_convert_census.py` (c0159) | the baseline and the counts after each group |
| `tests/kicad/convert/test_triangle_large.py` (new) | KiCad's importer on a DIFAT document and on full-stack pads |

## Sources registered by this change

From the block S-0740 to S-0759 (reserved for v0.5a): S-0740 for a public page that states whether a footprint pad may have an empty designator (task 1.3), and S-0741 for a public statement of the paste and mask expansion fields of a pad record if S-0302 does not hold them for writing. Neither is certain; each task writes whether it was needed. The maintainer's report of Part T is registered as the next free source id when it is given.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-CONV-DIFAT | A compound file whose FAT needs more than 109 sectors, written with DIFAT sectors as S-0145 states, is read by Fenolite's reader and by `kicad-cli pcb import` 10.0.6, and Altium Designer opens it (S-0145, S-0029) | `tests/unit/backends/altium/test_cfb_difat.py`; `tests/kicad/convert/test_triangle_large.py`; Part T, step T1 | the reads equal; probe `convert-difat` `equal`; T1 reported as expected |
| H-A-CONV-PADSTACK | A pad written with stack mode 1 or 2 and the tables of the read rows is read back by Fenolite and by `kicad-cli pcb import` 10.0.6 with the shape and size per layer of the model, and Altium Designer shows the stack (S-0160, S-0302, S-0029) | `tests/unit/backends/altium/test_pcblib_stacks.py`; `test_triangle_large.py`; Part T, step T6 | read-back equal per layer; probe `convert-padstack` `equal`; T6 as expected |
| H-A-CONV-LIBRARY | The derived `.PcbLib` opens in Altium Designer, and "Update PCB from schematic" of the converted project proposes no change of footprint (Part T, steps T5 and T6) | Part T | T5 and T6 reported as expected |
| H-A-CONV-SCHEMATIC | The converted schematic of a KiCad project compiles in Altium Designer without error, and its netlist (level 2 of `equivalent`, read by Fenolite) equals the KiCad schematic's (Part T, step T2) | `tests/unit/convert/test_to_altium_schematic.py`; Part T, step T2 | level 2 equal; T2 as expected |

All four start `INFERRED`. Ids used without changing their level unless the change measures them: `H-A-SCHBIN-CFB`, `H-A-IMP-PADSTACK`, `H-A-VER-RTA3-PRJ` (task 5.3 measures it again), `H-A-RD-SCH-TEXT-2`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| DIFAT sectors | `INFERRED` (S-0145, own reader), `ORACLE-VERIFIED(kicad-cli)` for the import | `test_cfb_difat.py`, `test_triangle_large.py` |
| full-stack, connector and free pads | `INFERRED`, `ORACLE-VERIFIED(kicad-cli)` for the import | `test_pcblib_stacks.py`, `test_triangle_large.py` |
| layer map, copper texts | `INFERRED` (read-back) | `test_lower_layers.py` |
| derived library | `INFERRED` (read-back); `ALTIUM-VERIFIED(author-report)` after Part T, not required to merge | `test_derived_library.py`; Part T |
| schematic of a KiCad source; tolerant texts and nets | `INFERRED`; level 2 equal by Fenolite's reader | `test_to_altium_schematic.py`, `test_schematic_tolerant.py` |
| the census | `CORPUS-VERIFIED`: every demo board written, every difference explained | `test_convert_census.py` |

The author report never promotes a write kind out of `experimental` (c0092's rule).

## Risks / Trade-offs

- **DIFAT is untested by any saved file in the corpus.** The two files that need it are Fenolite's own; KiCad's importer is the independent reader, Altium Designer the second (Part T). Until both, the row stays `INFERRED`.
- **The layer map is a choice.** Two users may want `Dwgs.User` elsewhere. It is documented and closed; a configurable map is not in v0.5a (open question 2, decided by the maintainer on 2026-10-09), and comes later if a user asks.
- **The derived library hides edited instances.** Counted `changed` per instance, so the report says which.
- **The schematic from KiCad symbols draws what KiCad drew, at other positions.** The report says it, and the netlist is checked at level 2.
- **The tolerant write changes the bytes of RT-A3 rewrites** of the three public sets that were not judged; no committed sample changes.

## Migration Plan

- Builds from scripts give the same bytes; every committed Altium sample and pinned build is asserted unchanged.
- `fenolite convert --to altium` writes boards it refused and loses fewer items; the census of `docs/evidence/conversion.md` is regenerated.
- RT-A3 judges the three public project sets that it left out.

## Budget (9.5 days)

| part | days |
|---|---|
| entry check, baseline per reason, sources, hypotheses | 0.75 |
| DIFAT sectors, read and write, oracle | 1.0 |
| full-stack pads, connector and free pads, oracle | 2.0 |
| layer map and copper texts | 0.75 |
| derived library | 1.25 |
| schematic from the source's symbols and sheets | 1.5 |
| tolerant texts and nets, RT-A3 sets | 1.0 |
| Part T files and steps; the report when given | 0.5 |
| documentation, census, closing | 0.75 |
| **total** | **9.5** |

Cut order: (1) the schematic from the source's symbols (the generic sheet stays, reported `changed`); (2) connector and free pads (reported); (3) the layer map beyond the fabrication layers. Not cut: DIFAT, full-stack pads, the derived library, the tolerant write (a decision of the maintainer).

## Open questions

All answered on 2026-10-09: the maintainer accepted every recommended answer (`docs/roadmap.md`, Open decisions row 40).

1. **Is the derived library one footprint per name, from the first instance?** Recommended: yes, with edited instances counted `changed`. Decided by the maintainer on 2026-10-09: yes; one footprint per name, from the first instance, with edited instances counted `changed`.
2. **A user map of KiCad layers to mechanical layers (`--altium-layer-map FILE`)?** Recommended: not in v0.5a; the closed map first, a file later if a user asks. Decided by the maintainer on 2026-10-09: not in v0.5a; the closed map first, a file later if a user asks.
3. **Write the converted schematic's symbol positions from KiCad's sheet?** Recommended: no; presentation is after 1.0, and the report says so. Decided by the maintainer on 2026-10-09: no; presentation is after 1.0, and the report says so.
4. **When will the maintainer run Part T?** Recommended: in the same session as the kit run that c0091 still owes, so one Altium session settles both. Every other task can close before; the change is archived after the report, as c0121 waited for step X8. Decided by the maintainer on 2026-10-09: in the same session as the kit run that c0091 still owes; every other task may close before, and the change is archived after the report.
