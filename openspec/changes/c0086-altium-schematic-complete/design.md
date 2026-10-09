## Context

- **Today** (`docs/altium.md`, "Limits"): "One flat sheet by default, or one level of hierarchy with `--altium-sheets modules` (no repeated sheets, no deeper levels, no routed wires between sheet symbols, no port directions, no harness in the ASCII form, no nested harnesses); no buses, variants …; schematic libraries hold synthesised rectangles, not the symbols' graphics, and no alternate display modes; … text in 7-bit ASCII only." `altium-schematic-writer`, "Library symbols from KiCad symbols": "The symbol's own graphics are not in the model; each part gets a synthesised rectangle." That sentence is no longer true of the model.
- **The read side** (`altium-schematic-reader`): typed records for lines, rectangles, polylines, arcs, ellipses, labels, buses, bus entries, ports, sheet symbols and entries, with text decoding (code page plus UTF-8 companions) and the owner tree. So a written record of these kinds is proved by a reader that was proved on files Altium saved.
- **c0070** defines, for KiCad, one pinless sheet per module, file names, sheet references and a layout; its grammar and its naming are reused so that the two targets describe one tree.
- **Constraints.** Coordinates on the 10 mil grid as today; deterministic layout; unique ids stable across builds ("Stable component unique ids").

## Goals / Non-Goals

**Goals:**
- A person who opens the Altium schematic recognises each part by its symbol and can follow the hierarchy.
- Altium's compiler has directions to check, and reports no error on the examples.
- Nothing that worked before changes its nets: the netlist of every sample is the one it had.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Graphics.** `altsym.from_symbol_def` maps each `SymbolGraphic` of body style 1 to the record of its kind, in the symbol's frame, on the 10 mil grid where the record needs it; a coordinate off the grid is rounded to it and reported once per symbol with `altium.symbol-simplified`. A filled shape keeps its fill as a flag, not its colour. A symbol without graphics, or with a graphic kind without a record (a Bézier), keeps the synthesised rectangle for that part.
2. **The sheet tree.** One `.SchDoc` per module at any depth; the root holds a sheet symbol per child module; a child holds its components and the sheet symbols of its own children. File names and sheet names follow c0070's rule. `--altium-sheets modules` selects it; `flat` stays one sheet. Harnesses keep their one-level rule from c0037; a typed interface that crosses more than one level is drawn as ports (documented).
3. **Directions.** For a net that crosses a sheet boundary, the port or sheet entry gets: output when the sheet drives it (a pin of type output, tri-state, open collector, open emitter or power out inside and none outside the same sheet), input when only inputs or power inputs are inside, bidirectional when both or any bidirectional pin, unspecified when only passive pins. The table is in `docs/altium.md`. The two ends of one connection always get compatible types.
4. **Buses.** A `Bus` of the model whose members are named `NAME0…NAMEn` is drawn as a bus line with the label `NAME[0..n]`, bus entries, and the members' net labels; a bus with arbitrary member names is drawn as its nets (reported as info), because Altium's bus syntax needs a common stem.
5. **Text.** `text_problem` accepts any character that the chosen form can carry: in the binary form, any character of the code page of the document plus the UTF-8 companion field; in the ASCII form, the set that `docs/formats/altium/schematic-ascii.md` records as carried. `|` and line ends stay refused. The refusal names the character and the form that would carry it.
6. **Parameters.** Each property of a part other than those already written (comment, footprint link) becomes a hidden parameter record of its component, in name order.
7. **Cut order.** First parameters, then buses, then the ASCII form's wider text, never graphics, the tree and directions.

## Files and public API

- `src/fenolite/backends/altium/altsym.py`: graphics in `AltiumSymbol`; `GRAPHIC_KINDS`.
- `src/fenolite/backends/altium/hierarchy.py`: `sheet_tree(design)`, `direction(net, sheet)`, `DIRECTIONS`.
- `src/fenolite/backends/altium/ascii.py`, `binary.py`: `text_problem(text, *, form, parameter=False)`.
- Tests: `tests/unit/backends/altium/test_{symbol_graphics,sheet_tree,directions,bus_records,text_forms,parameters}.py`, `tests/unit/lens/test_altium_schematic_complete.py`, `tests/kicad/altium/test_schematic_complete_oracle.py`; a committed sample `tests/data/altium/tree/` (a design with two levels of modules, a bus, and catalog symbols).

## Sources registered by this change

- S-0130, S-0131, S-0133, S-0144, S-0150, S-0151 (registered): the schematic record kinds, the ASCII form, the library form.
- S-0185 (registered): hierarchy, ports, sheet entries and their I/O types; buses.
- The field facts of c0040 in `docs/formats/altium/schematic-records.md`.
- New: Altium's public documentation of port and sheet-entry I/O types and of the compiler's checks on them, of bus naming, and of the file encodings of the two schematic forms.

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-SCHX-READBACK | The sheets and libraries written with the records of this change read back to the symbols, modules, buses and texts they were written from | `tests/unit/lens/test_altium_schematic_complete.py::test_readback` | equal for `tree` and for every example script |
| H-A-SCHX-GRAPHICS | Altium draws the written graphics of a symbol as the KiCad symbol draws them, in the library editor and on the sheet | author report, Part Y steps Y2–Y3 | the four sample symbols match the reference pictures sent with the files |
| H-A-SCHX-TREE | A project of sheets nested two levels deep compiles, and the Navigator shows the module tree | author report, Part Y step Y4 | no compile error; the tree equals the list sent |
| H-A-SCHX-DIR | With the written I/O types, the compiler reports no port or sheet-entry direction error on the samples, and reports one for a planted contradiction | author report, Part Y step Y5 | no message on `tree`; one message on `tree-bad` |
| H-A-SCHX-BUS | A written bus with its label, entries and member labels gives the member nets the names of the model | author report, Part Y step Y6 (the KiCad oracle `test_schematic_complete_oracle.py::test_bus` was waived on 2026-10-09: `kicad-cli` reads no schematic document; task 5.2) | the nets of the bus in Altium's netlist equal the model's |
| H-A-SCHX-TEXT | A value with accented characters written in the binary form is shown unchanged; in the ASCII form it is shown unchanged or the build refused it | author report, Part Y step Y7 | the three sample strings read as written |
| H-A-SCHX-ECO | The change order from the complete schematic to an empty board has the components and nets of the model and no extra class, room or difference beyond those c0048 documents | author report, Part Y step Y8 | the counts equal the table sent |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Author report: Part Y, complete schematic

Files: the projects `tree` and `tree-bad` (the same with one contradicting direction) in the binary and the ASCII form, with reference pictures of four symbols and a table of counts.

The steps as built and handed over are in `docs/evidence/altium-schematic.md` ("Part Y"), with the SHA-256 of every file: they follow "Found on 2026-10-06" (Y7 reads a comment and a parameter; Y9, added by the maintainer's decision, opens the four regenerated samples). The list below is the proposal's.

1. Y1: open `tree` (binary). Expected: no repair prompt, no message.
2. Y2: open the schematic library and look at the four named symbols. Expected: the reference pictures (shape, pin places).
3. Y3: open the sheet that places them. Expected: the same graphics on the sheet.
4. Y4: compile the project and open the Navigator. Expected: no error; the sheet tree of the list.
5. Y5: read the Messages panel for port and sheet-entry messages; then compile `tree-bad`. Expected: none for `tree`, one for `tree-bad`.
6. Y6: in the Navigator, list the nets of the bus `D[0..3]`. Expected: `D0` to `D3`.
7. Y7: read the comment of `R1`, the net label and the parameter that hold accented characters. Expected: as written. Repeat with the ASCII project and report what is shown.
8. Y8: run Design » Update PCB Document into a new board and report the number of components, nets, classes and rooms the change order lists.

The maintainer reports one generic outcome per step (`as expected`, or what differed in one sentence), the tool as `AD <major>.<minor>` and the date. No file that Altium wrote is committed. A step that fails refutes the row it names: the row keeps its id and gets a registered successor (`verification-evidence`, "Refuted rows keep their id"). An author report never moves an operation out of `experimental` ("Author reports never promote an operation").

## Size (design-days)

| group | dd |
|---|---|
| entry, facts and sources | 0.75 |
| symbol graphics | 2 |
| sheet tree | 2 |
| directions | 1 |
| buses | 1 |
| text forms | 1 |
| parameters | 0.5 |
| sample, oracle, report, docs | 1 |
| closing | 0.25 |

Total: 9.5. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-schematic-writer`: "Generic component bodies", "Generic library symbols", "Library symbols from KiCad symbols", "Sheets of a hierarchical project", "Ports on module sheets", "Text the ASCII form cannot carry" are superseded in their limits; task 0.1 writes them as MODIFIED from the living text.
- `altium-build`: "Module sheets in an Altium build", "Hierarchy issue codes" (MODIFIED at task 0.1).
- Archive order: before c0090.

## Found on 2026-10-06

The proposal was written from a survey. The code and the public facts differ from it in these points; the spec deltas, this design and the tasks follow what was found.

1. **The model's symbol graphics are four kinds without a unit.** `SymbolGraphic.kind` is `line`, `circle`, `rect` or `polygon`; it names neither a unit nor a body style, and the KiCad reader keeps arcs, Bezier curves and texts only in the symbol's opaque library text. So there is no polyline, arc or text to map, a Bezier graphic cannot occur in the model, and the graphics of a symbol of several units or body styles cannot be given to a part. Decision 1 becomes: draw the graphics of a symbol of one unit and one body style whose graphics are all of the four kinds; keep the rectangle for a symbol of several units or body styles, for one without graphics, and for a KiCad symbol whose library text holds an arc, a Bezier curve or a text (`lens.altium.unmodelled_graphics`). The scenario "Symbol with a curve the writer lacks" uses a kind outside `GRAPHIC_KINDS`. Giving `SymbolGraphic` a unit, a body style and arcs is a model change of its own.
2. **Graphics need no 10-mil grid.** The catalog symbols are not drawn on a 50-mil grid: the resistor is eight lines with coordinates off the 10-mil grid, the inductor 64 short lines. The record pages already hold the `_FRAC` keys (1/100 000 unit, `H-A-RD-SCH-FRAC`), and saved components use them. So graphic coordinates are written exactly, to the 2.54 nm step, and nothing is rounded to 10 mil or reported for it. Pins keep the 10-mil grid.
3. **The catalog resistor is no rectangle.** The scenario "Resistor symbol" expects its eight lines.
4. **An Altium build did not take catalog or authored symbols.** `build_altium` resolved every KiCad lib id through the library resolver, and the command passed only footprints the script authored. The change adds `authored_symbols` to `build_altium` and passes the catalog and authored symbols and footprints, as the KiCad build does; without it no catalog symbol reaches the writer.
5. **The file naming keeps c0037's form.** c0070's rule puts child sheets in `sheets/` as `<module path with ".">.kicad_sch`. For Altium the tree, its order (depth first, siblings in natural order), the module-of-a-component rule and the sheet names are c0070's; the files stay beside the project as `<name>_<module path with ".">.SchDoc`. Reasons: a top-level module keeps the file name that Part H opened in Altium (`H-A-SCH-HIER-*`), and `docs/formats/altium/project.md` holds no fact about a document path with a folder. c0070 is not archived; its rule is read from its delta (`openspec/changes/c0070-schematic-hierarchy-layout/specs/kicad-schematic/spec.md`) and its code (`backends/kicad/schgen.py`), both in the base commit.
6. **The issue code is `altium.text-unwritable`.** The proposal names `altium.text-unsupported`, which does not exist. The existing code keeps its name; its message now names the form that carries the character.
7. **The ASCII form's wider text is cut** (third in the cut order), on the facts: the encoding of an ASCII schematic depends on the version that reads it (S-0133), so no set of characters past 7-bit ASCII is recorded as carried. The ASCII form stays 7-bit and the refusal names the binary form.
8. **Wider text is the comment and parameter values only.** Refs, net names, pin texts and library, symbol, footprint, module, harness, class and parameter names are also file names, storage names, binary pin strings or PCB net names, whose encodings this change does not touch. The PCB document's texts are 7-bit: a comment with another character is written there as the symbol name and reported. Step Y7 therefore reads a comment and a parameter, not a net label.
9. **The DSL has no bus.** `Circuit.buses` is filled only by readers. The bus records are written from the model and proved on a model with a bus; `tests/_altium_tree.py` adds the bus `D` to the tree sample's model, because its script cannot declare one. A bus in the DSL is a `design-dsl` change.
10. **A property never refuses a build.** A property that no parameter can hold (its name, its value in the chosen form, a name that repeats another in a different letter case) is kept in the model and reported with `altium.not-lowered`; otherwise a design with a property that an earlier build ignored would stop building.
11. **`kicad-cli` reads no schematic document.** `kicad-cli` 10.0.6 has three schematic subcommands, `sch erc`, `sch export` and `sch upgrade`, and no import. Tried on the written `tree.SchDoc` (binary), each with the message "Failed to load schematic" and exit 3: `kicad-cli sch export netlist --format kicadxml -o out.net tree.SchDoc`, `kicad-cli sch upgrade tree.SchDoc` and `kicad-cli sch erc -o erc.rpt tree.SchDoc` (S-0020; the page of Part A already says that only the GUI importer reads a `.SchDoc`). Task 5.2's oracle for the netlist, the sheet tree and the bus members cannot run. This is not true of schematic LIBRARIES: `kicad-cli sym upgrade X.SchLib -o Y.kicad_sym` converts them through KiCad's Altium importer (S-0153), which the existing oracle tests `tests/kicad/altium/test_schlib_oracle.py` and `test_schlib_read_oracle.py` use, and PCB documents go through `kicad-cli pcb` in the PCB oracles. So the oracle of this change uses `sym upgrade` and compares the graphics of 47 catalog symbols. It found that KiCad reads every circle as filled; the writer keeps the ellipse record and Part Y does not cover an open circle.
12. **No new source.** I/O types (S-0130, already a row of `schematic-ascii.md`), bus naming (S-0301) and the encodings of the two forms (S-0133) were registered. The reserved ids S-0480 to S-0489 are unused. The key orders of the new records are observations of the cached public corpus, counted by key name with Fenolite's reader; they are not a committed test, so their rows stay `INFERRED`.
13. **The link of a part two levels down.** The ids of both sheet symbols are a recorded fact (`connectivity.md`, "Component link"); the form of `SOURCEHIERARCHICALPATH` below the first level was not read from a saved file and is inferred (`H-A-SCHX-ECO`, step Y8).
14. **Symbol bodies are an option, and graphics is the default** (decision of the maintainer, 2026-10-06, see the proposal). `generic` gives the former bytes; the four regenerated samples keep their former bytes under `tests/data/altium/generic/`; step Y9 opens the regenerated ones.
16. **Rebased onto c0084, c0085, c0087 and c0089 (2026-10-06).** The drawing sheet of c0087 is made per planned sheet, so every sheet of the module tree gets the frame and its sheet parameters (`SheetNumber` 1 to n in tree order); a test builds the tree sample with one. `lens.build_altium` keeps c0087's defaults (no job, no drawing sheet), so the committed samples of this change did not change with the rebase. The sample `board6` of c0085 uses the blink symbols: its `board6.SchDoc` and `board6.SchLib` are regenerated in the graphics form (never reported on; no generic copy is kept, `--altium-symbols generic` rebuilds them). c0085's test of the old samples' bytes now excludes the nine regenerated files and compares their `generic` copies with the base commit instead. The handover files of Parts O and W of c0087 were built before this change, with rectangle bodies.
15. **A branch with code on the same topic was read, not used.** On the coordinator's request `symbol_graphics.py` of the local branch `codex/board-authoring-gaps` was read after the graphics of this change were written. Nothing was taken from it: it rests on a model with units and arcs in `SymbolGraphic`, which this change does not have. Its arc rule under a mirror, its writer claims on reader rows and its off-grid test were not copied.

## Risks / Trade-offs

- [Graphics off the 10 mil grid look wrong] → rounded and reported; the catalog symbols of c0075/c0076 are drawn on a 50 mil grid.
- [Directions cause compiler errors on real designs] → only unspecified is written when a net has only passive pins, and `--altium-directions off` writes all as unspecified.
- [Regenerated samples hide a regression] → the netlist of every sample is compared before and after (own readback and KiCad import).

## Migration Plan

- Builds draw other symbols; nets and designators are unchanged. A project whose `.SchDoc` was edited in Altium is refused as before.
- `--altium-sheets flat` keeps today's single sheet.

## Open Questions

- **Should colours of the KiCad symbol be written?** Default: no, Altium's defaults.
- **Should a module used twice be written as one sheet with two sheet symbols?** Default: no, two sheets, until multi-instance hierarchy (v0.5b).
