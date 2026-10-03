## Context

The Altium build (c0032 to c0036) writes one schematic sheet, its libraries, a project file and a PCB
document. The maintainer opened and compiled these files in Altium Designer 26.5. The next design
needs several sheets and signal harnesses.

Facts, all from public sources, recorded with their source and confidence in the research note of
this change and, at implementation, in `docs/formats/altium/`:

- **Sheet symbol and entries.** Record 15 is a box whose location is its top-left corner. Records 16
  are its sheet entries, placed by side and by a distance from the top in steps of 100 mil. Records 32
  and 33 are its name and its file name; the file name is a bare name beside the project (S-0130,
  S-0131, S-0185, S-0187, S-0188).
- **Port.** Record 18 extends `WIDTH` to the right of its location and joins a wire at either end
  (S-0130, S-0187, S-0188).
- **Harness.** Records 215 (connector), 216 (entry), 217 (type) and 218 (line) are not in
  `FileHeader`. They are in the stream `Additional`, which has its own header record and record
  count. Their `OWNERINDEX` counts inside `Additional`; an index of 0 is omitted. A port or sheet
  entry that carries a harness holds `HARNESSTYPE` (S-0130, S-0131, S-0187, S-0188).
- **Harness definitions.** A `.Harness` text file holds `<type>=<entry>,<entry>` lines. Altium
  generates one per sheet that has connectors and lists each in the project file (S-0186, S-0187,
  S-0188).
- **Project.** Every sheet is a `[Document<n>]` section; saved, full project files hold them in no
  particular order. The top sheet is the one no sheet symbol names (S-0132, S-0185, S-0187, S-0188).
  For Fenolite's minimal file the order matters (decision 16, after the second report of step H7).
- **Net scope.** With the default scope, "Automatic", Altium uses the hierarchical scope when the top
  sheet has sheet entries: net labels are local to a sheet, a port joins the sheet entry of the same
  name, and power ports are global (S-0185).
- **Unique ids.** A sheet symbol has a unique id. A PCB component from a module sheet holds
  `SOURCEUNIQUEID=\<sheet symbol id>\<component id>` and
  `SOURCEHIERARCHICALPATH=<top sheet stem>\<sheet name>` (S-0139, S-0164, S-0188).
- **Other sources.** AltiumSharp version 1 (S-0150) holds no sheet symbol, port or harness record,
  so it gives nothing here. Version 2 was not opened.

Two sets of Altium-saved files were downloaded to a scratch folder, with the maintainer's leave, from
repositories whose licences permit the use: S-0187 (MIT) and S-0188 (LGPL-3.0). They were read with
`tests/_cfb_read.py`. Their keys agree with S-0130 and add the keys of records 215 to 217, which no
documentation lists. No file, name, value or coordinate from them enters the repository.

There is no oracle. KiCad's GUI imports hierarchical Altium projects, but `kicad-cli` has no schematic
import. Evidence is Fenolite's readback plus the maintainer's author reports.

## Goals / Non-Goals

**Goals**

- One sheet per top-level module, a top sheet with sheet symbols, matching ports and sheet entries.
- Harnesses from a small DSL surface, drawn with Altium's own harness objects.
- The verified single-sheet output stays byte for byte, and the change order keeps matching.
- An early sample for the maintainer: a top sheet, two module sheets, one harness.

**Non-Goals**

- Repeated sheets, deeper hierarchy, buses, nested harnesses, routed wires, port directions.
- Harnesses in the ASCII form. Reading Altium files. Hierarchy in the KiCad build.

## Decisions

1. **The hierarchy is opt-in: `--altium-sheets flat|modules`, default `flat`.** The sample of c0032
   has modules and one sheet, and its bytes are verified. A default of `modules` would rewrite every
   golden file and five requirements before Altium has opened one hierarchical sheet.
   - Rejected: `modules` by default. It discards verified evidence. Open Question 1 revisits it after
     Part H.
   - Rejected: a DSL call (`design.sheets(...)`). The sheet split is a property of the Altium output,
     like `--altium-format`, not of the design.
2. **One sheet per top-level module; deeper modules are flattened.** A component's sheet is the first
   segment of its component path. This needs only the path, so it works on any model.
   - Rejected: one sheet per module at any depth. It needs sheet symbols on module sheets and
     three-id PCB links, which no report covers yet.
3. **File names: `<design>.SchDoc` and `<design>_<module>.SchDoc`.** The top sheet keeps today's
   name, so the project file's first document does not change. Module names match
   `[A-Za-z0-9_.+-]+`, so every name is a valid file name. Two module names that differ only in
   letter case are refused (`altium.sheet-name-collision`).
   - Rejected: `<module>.SchDoc`. Two designs built into one folder would collide.
   - Rejected: a subfolder. Every Fenolite file sits beside the project (c0032).
4. **A net crosses a module when it has pins on that module's sheet and on another sheet.** The model
   already holds this: no new DSL marking. Each crossing gives a port on the module sheet and a sheet
   entry with the same name on the sheet symbol.
   - Rejected: explicit `module.port(net)` calls. The script would repeat what the connections say,
     and a forgotten call would split a net silently.
5. **Nets of a `power` interface never cross.** Their pins already get power ports, which Altium
   treats as global in the hierarchical scope (S-0185). A power port wired to a port would become
   local, so no port is drawn for them.
   - Rejected: ports for power nets too. It doubles the entries and changes the scope of power nets.
6. **No routed wire. Every port, sheet entry and harness entry gets a short wire and a net label.**
   This is the construct c0032 uses for pins, which Altium already compiles. Labels join everything
   on a sheet, so the top sheet needs no wire between two sheet symbols, for any number of sheets.
   - Rejected: wires from entry to entry on the top sheet. It needs a router, junctions for nets on
     three sheets, and a rule for crossings.
7. **One name per net on every sheet.** The port, the sheet entry and every label of a net carry the
   net's name. Altium then has one candidate name, so the netlist and the change order keep the names
   of the single-sheet build (`H-A-SCH-HIER-NAMES`).
8. **`Harness(name, members)` is a subclass of `Interface` with kind `harness`.** `interfaces.py`
   already has `Interface(name, kind, members)`, `Power` and `DiffPair`; the model's `Interface`
   stores any kind. So the DSL gains one class and the model nothing. The name is the harness type
   name and is required: `<a>/<b>` defaults make no sense for more than two nets.
   - Rejected: reuse `Interface(name, "harness", …)` only. It works, but a named class documents the
     intent and validates an empty group.
   - Rejected: typed classes (`Spi`, `I2c`). They fix entry names the design may not use.
   - Entry order: the model stores a mapping, and canonical JSON sorts keys, so the writer sorts
     entry names. The order then survives a round trip through `.fenolite/`.
9. **A harness is drawn as a block beside its port, and on the top sheet as a line between two sheet
   entries when that is possible.** On a module sheet: port, harness line, connector, entries,
   labelled wires; the block is the construct Altium saves on child sheets (S-0187). On the top sheet
   (changed after the report of 2026-10-03, see "Changes after the maintainer's report"): one straight
   signal harness line from the entry on the right side of one sheet symbol to the entry on the left
   side of the next, as the reference top sheets draw them (S-0187, S-0188), when the harness joins
   exactly two neighbouring modules and no other sheet holds a pin of its nets. Otherwise the top
   sheet keeps the block beside each sheet entry, and its labels join the blocks.
   - First form, replaced: the same block on both sides in every case. Altium Designer 26.5 compiled
     it, but warned that each member net had multiple names (step H3).
   - Rejected: routed harness lines between any two sheet entries. It needs a router, and whether
     crossing harness lines join is not documented. The line is drawn only where it is straight.
   - Rejected: no harness objects, only nets. It does not give the maintainer harnesses.
10. **Every block of a type holds all its entries; an entry is wired only when its net crosses that
    module.** All drawn definitions of a type are then equal, so no "conflicting definition" can
    arise. Wiring an entry whose net is local to another sheet would create a second net with the
    same name, so such entries stay bare on both sides (`H-A-SCH-HARN-UNUSED`).
    - Rejected: blocks with only the used entries. Two blocks of one type would differ.
11. **Harness records go to `Additional`; a sheet without a harness gets no `Additional` stream.**
    The verified binary sheets have none, so their bytes do not change.
    - Rejected: always write an empty `Additional`, as Altium does. It changes verified files for no
      gain.
12. **The ASCII form writes the hierarchy but no harness.** The place of records 215 to 218 in the
    ASCII form is not documented, and no ASCII file with a harness was found. The member nets cross
    as plain nets, with an `altium.not-lowered` info.
    - Rejected: refuse `modules` with `ascii`. The hierarchy records are ordinary records and work.
13. **One `.Harness` file per sheet that holds a block, listed in the project file.** This is what
    Altium generates (S-0187, S-0188). If the file were missing, Altium would create it and mark the
    project as changed.
    - Rejected: one `<design>.Harness`. It differs from what Altium writes next to each sheet.
    - Rejected: no file. Altium would generate them on first compile, which edits the output folder.
14. **Unique ids.** Components keep `unique_id(<component id>)` in both modes. A sheet symbol gets
    `unique_id("sheet:<module>")`, because the PCB link names it. A port gets
    `unique_id("port:<module>:<name>")`, because every saved port has one. Sheet entries, harness
    records, wires and labels get none, as the older saved files and Fenolite's verified sheets.
15. **PCB link.** `PlacedComponent.sheet` is `(sheet symbol id, module name)` or `None`. With it the
    writer emits the two-id path and `SOURCEHIERARCHICALPATH=<design>\<module>`. A top-sheet part
    keeps today's one-id path and empty hierarchical path, the form verified for a flat sheet; no
    saved file shows a part on a hierarchical top sheet (`H-A-SCH-HIER-ECO`).
16. **Project file order: top sheet, module sheets, PCB document, libraries, harness files.** Every
    schematic document precedes every other document. The first build appended the module sheets
    after the libraries, to keep `[Document2]` the PCB document as in c0035; with that order Altium
    Designer 26.5 took only the first module sheet into the hierarchy (second report of step H7,
    `H-A-SCH-HIER-ORDER`). The bytes without module sheets do not change: there `[Document1]` is the
    schematic and `[Document2]` the PCB document.
17. **Layout.** Sheet symbols and ports are cells of the existing packing, before the component
    cells. Constants in `layout.py`:
    - `ENTRY_PITCH = 100` mil (one `DISTANCEFROMTOP` step); `SYMBOL_MIN_WIDTH = 1500`;
      `CONNECTOR_MIN_WIDTH = 500`; `HARNESS_GAP = 200` (the harness line).
    - Text width estimate `100 · ⌈(70 · L + 150) / 100⌉` mil, as for labels.
    - A sheet symbol's entries are on its right side. Slots start at 1. A net entry takes one slot.
      A harness entry of `m` members takes `m + 2` slots: its connector is `(m + 1) · 100` mil high,
      with `PRIMARYCONNECTIONPOSITION = 10 · ⌊(m + 1) / 2⌋` units, and the entry sits at that height.
      The symbol's height is `(slots + 1) · 100` mil.
    - A port cell: the port, then its stub and label, or the harness line and the block.
18. **Readback is extended, not replaced.** `tests/_altium_read.py` gains a project reader that
    applies the hierarchical scope and follows harness blocks. It shares no code with the writer.

## Files and public API

| File | Change | Public API |
|---|---|---|
| `src/fenolite/dsl/interfaces.py` | class | `Harness(name, members)` |
| `src/fenolite/dsl/__init__.py` | re-export | `Harness` |
| `src/fenolite/backends/altium/hierarchy.py` | new | `SheetFile`, `ProjectSheets`, `plan_sheets(design, *, name, sheets, form, symbols=None) -> ProjectSheets`, `sheet_of(component) -> str \| None`, `crossings(design, *, form) -> dict[str, tuple[Crossing, ...]]`, `write_harness(types) -> bytes` |
| `src/fenolite/backends/altium/layout.py` | plan | `Crossing`, `HarnessBlock`, `SymbolSpec`, `PlacedSymbol`, `PlacedPort`; `layout_sheet(parts, *, symbols=(), ports=())`; `SheetPlan.symbols`, `.ports`, `.harnesses` |
| `src/fenolite/backends/altium/schdoc.py` | records | records 15, 16, 18, 32, 33 in `schdoc_records(plan)`; `additional_records(plan)`; `write_schdoc` refuses a harness block |
| `src/fenolite/backends/altium/binary.py` | stream | `additional_stream(records)`; `write_schdoc_binary` adds `Additional` when needed; the padding added after the first report (`padded_records`) was removed after the second |
| `src/fenolite/backends/altium/prjpcb.py` | arguments | `write_prjpcb(*, schematic, pcb=None, libraries=(), sheets=(), harnesses=())` |
| `src/fenolite/backends/altium/project.py` | mode | `SheetMode`, `DEFAULT_SHEETS`, `HARNESS_KIND`; `write_project(..., sheets=DEFAULT_SHEETS)`; `WRITE_KINDS` gains `altium_harness` |
| `src/fenolite/backends/altium/pcbdoc.py` | link | `PlacedComponent.sheet: tuple[str, str] \| None = None`; after the report: `channel_offsets(components)` |
| `src/fenolite/lens/altium.py` | build | `build_altium(..., sheets=DEFAULT_SHEETS)`; five issue codes; summary keys; nine hypotheses in `ALTIUM_BUILD_EVIDENCE` |
| `src/fenolite/cli/cmd_build.py` | option | `--altium-sheets flat\|modules` |
| `examples/altium_hier/design.py`, `partial.py` | new | designs `altium_hier`, `altium_hier_partial` |
| `examples/altium_hier_board/design.py`, `sym-lib-table`, `fp-lib-table` | new | design `altium_hier_board` |
| `tests/data/altium/hier/` | new | seven golden files (eight before the report of 2026-10-03) |
| `tests/_altium_read.py` | reader | `nets_from_project(sheets, top)`; after the report: `project_documents`, `component_links`, `board_link_problems` |
| `tests/unit/backends/altium/test_hierarchy.py`, `tests/unit/lens/test_altium_hier.py`, `tests/unit/lens/test_altium_hier_golden.py`, `tests/unit/dsl/test_harness.py` | new | tests |
| `tests/unit/backends/altium/test_layout.py`, `test_schdoc.py`, `test_binary.py`, `test_prjpcb.py`, `test_pcbdoc.py`, `test_readback.py`, `tests/unit/lens/test_altium_issues.py`, `test_altium_determinism.py`, `tests/unit/cli/test_build_altium.py`, `test_capabilities_experimental.py`, `tests/unit/test_altium_rows.py` | extended | — |
| `docs/altium.md`, `docs/dsl.md`, `docs/cli-contract.md` | sections | — |
| `docs/formats/altium/schematic-ascii.md`, `schematic-binary.md`, `project.md`, `pcb-document.md`, `src/fenolite/backends/altium/PROVENANCE.md`, `LEGAL-ANNEX.md` | fact rows | — |
| `docs/evidence/altium-schematic.md`, `docs/hypotheses.md`, `docs/evidence/sources.md` | Part H, rows | — |

`backends.altium` imports only `model`, `core` and itself; `dsl` imports only `model` and `core`. No
entry of `tests/unit/test_import_graph.py` changes.

## Sources registered by this change

| id | URL | licence | used for |
|---|---|---|---|
| S-0185 | https://www.altium.com/documentation/altium-designer/schematic/creating-circuit-connectivity and https://www.altium.com/documentation/altium-designer/schematic/multi-sheet-hierarchical-designs | Altium documentation, all rights reserved (read for facts) | net identifier scope and how "Automatic" chooses; ports join sheet entries of the same name; net labels local, power ports global; the sheet symbol's file name |
| S-0186 | https://www.altium.com/documentation/altium-designer/sch-obj-signalharnesssignal-harness-ad and https://techdocs.altium.com/node/296805 | Altium documentation, all rights reserved (read for facts) | signal harness, harness connector, harness entry, harness type; harness definition files and their generation |
| S-0187 | https://github.com/luxonis/oak-hardware at commit `7d569e3ccdff30014a498dc6c64a2e0dcad6964c`, folder `DM3370_RAE/PCB/`: one top sheet, five module sheets, their `.Harness` files and the project file (SHA-256 of each in the research note) | MIT (`LICENSE`); files saved by Altium Designer, downloaded to a scratch folder and never committed | hierarchy and harness records as a recent Altium saves them; the `Additional` stream; one `.Harness` file per sheet, listed in the project |
| S-0188 | https://github.com/raphaelchang/battman-hardware at commit `db5ae48d09e9ec9523387e2190fd14671a0646ca`, folder `BMS/`: the top sheet, five module sheets, their `.Harness` files, the project file and the PCB document (SHA-256 of each in the research note) | LGPL-3.0 (`LICENSE`; data files read for facts, nothing copied); files saved by Altium Designer, downloaded to a scratch folder and never committed | the same records from an older Altium; the two-id `SOURCEUNIQUEID` and `SOURCEHIERARCHICALPATH` of a part on a module sheet |

Cited, already registered: S-0130 (records 15, 16, 18, 32, 33, 215 to 218), S-0131 (the keys a second
reader needs; `Additional`), S-0132 (project sections), S-0139 (sheet symbol unique ids), S-0150
(nothing found), S-0164 (component links). Task 1.1 widens their "used for" cells. S-0189 to S-0194
stay unused.

## Hypotheses registered by this change

All rows: backend `altium`, level `INFERRED`, result `pending (author report)`.

| id | statement | test | criterion |
|---|---|---|---|
| `H-A-SCH-HIER-OPEN` | Altium Designer opens a top sheet with records 15, 16, 32 and 33 and module sheets with record 18, written with Fenolite's keys, without `INDEXINSHEET` and with `UNIQUEID` on sheet symbols and ports only | Part H, H1 | no prompt or repair offer; two sheet symbols with five entries; five ports |
| `H-A-SCH-HIER-PRJ` | A project file that lists the top sheet, then the module sheets, then the PCB document, the libraries and the harness files, with no other key, is accepted (restated after the second report of step H7; it first read "the module sheets and harness files after the libraries"), and Altium takes the sheet no symbol names as the top | Part H, H1 and H3 | the Projects panel shows the top sheet with two children |
| `H-A-SCH-HIER-COMPILE` | Without a scope key, compilation uses the hierarchical scope and matches each port with its sheet entry | Part H, H3 | no message about ports, sheet entries or duplicate net names |
| `H-A-SCH-HIER-NAMES` | Each net keeps the name of its labels on every sheet, and power ports join across sheets | Part H, H4 | exactly the nine net names of the sample, each with the model's pins |
| `H-A-SCH-HIER-ECO` | The change order matches components by `\<sheet symbol id>\<component id>` for module-sheet parts and `\<component id>` for top-sheet parts, and nets by name | Part H, H5 and H7 | H5: six components and nine nets added, validated; H7: no component or net change proposed |
| `H-A-SCH-HARN-OPEN` | Altium Designer opens a binary sheet whose `Additional` stream holds records 215 to 218 with Fenolite's keys, and draws the block | Part H, H2 | each connector shows four entries and the type `SPI`; a harness line joins it to its port or sheet entry |
| `H-A-SCH-HARN-FILE` | Listed `.Harness` files with Fenolite's lines are accepted and match the drawn connectors | Part H, H2 and H3 | no "conflicting harness definition" message; the files are not rewritten with other content |
| `H-A-SCH-HARN-NETS` | A net on a harness entry keeps the name of its label and joins the same entry on the other side of the port and sheet entry | Part H, H4 | each `SPI_*` net has one pin on each module sheet |
| `H-A-SCH-HARN-UNUSED` | A harness entry without a wire gives at most a warning and breaks no net | Part H, H6 | no error names `HOLD`; the nets equal the model's |

## Evidence level per behaviour (before merge)

| Behaviour | Level | Basis |
|---|---|---|
| `Harness` in the DSL and model | Fenolite's own rule | unit tests |
| Sheet split, crossings, names | Fenolite's own rule | unit tests |
| Records 15, 16, 18, 32, 33: keys and geometry | `INFERRED` (S-0130, S-0131, S-0187, S-0188), then author report per row | Part H, H1 |
| Records 215 to 218 and the `Additional` stream | `INFERRED` (S-0130, S-0131, S-0187, S-0188), then author report | Part H, H2 |
| `.Harness` file and its listing | `INFERRED` (S-0186, S-0187, S-0188), then author report | Part H, H2 and H3 |
| Net scope and net names | `INFERRED` (S-0185), then author report | Part H, H3 and H4 |
| PCB link of a module-sheet part | `INFERRED` (S-0164, S-0188), then author report | Part H, H5 and H7 |
| Written sheets join the model's nets, both forms | Fenolite's own readback | raises no label |
| `flat` output unchanged | byte comparison with the committed golden files | unit tests |
| Altium build envelope | `INFERRED`, experimental | an author report never promotes an operation |

## Size (design-days)

| work | design-days |
|---|---|
| 1. sources, hypotheses, fact rows, provenance | 0.5 |
| 2. `Harness` in the DSL | 0.25 |
| 3. sheet split, layout cells, hierarchy records, project file | 1.75 |
| 4. harness blocks, `Additional`, `.Harness` files | 1.0 |
| 5. build option, issue codes, CLI | 0.75 |
| 6. readback, sample, golden files, Part H | 1.0 |
| 7. PCB link and the board example | 0.5 |
| 8. documentation, the maintainer's report and fixes | 0.75 |
| 9. closing | 0.5 |
| **total** | **7.0** |

A size, not calendar time. The early sample (groups 1 to 6) is 5.25 design-days.

## Overlaps with other active changes

- **c0032 → c0033 → c0034 → c0035 → c0036.** This change MODIFIES four requirements, each copied
  from the latest change that holds it:
  - `altium-schematic-writer` "Binary schematic form": ADDED by c0033, not modified since.
  - `altium-schematic-writer` "Stable component unique ids": ADDED by c0032, not modified since.
  - `altium-pcb-writer` "PCB document links and nets": ADDED by c0035, not modified since.
  - `altium-build` "Altium build outputs": MODIFIED by c0035 (c0036 does not modify it).

  `openspec archive` applies a MODIFIED delta only to a requirement that exists, so the archive order
  is c0032, c0033, c0034, c0035, c0036, then c0037.
- **Extended without a MODIFIED delta.** "Project file", "Deterministic sheet layout", "Connectivity
  on the sheet", "Altium schematic format option" and "Altium build issue codes" keep their text. The
  ADDED requirements of this change extend them and only add keyword arguments with defaults, rows
  and records, as c0033 and c0035 extended c0032. c0036's `summary["no_connects"]` and its record 22
  are untouched; directives stay on the sheet of their pin.
- **c0038 (PCB copper, being proposed).** It uses sources from S-0195 and `H-A-PCB-CU-*` rows; no id
  collides. If it modifies "PCB document links and nets" or "Altium build outputs", it bases its text
  on this change's and archives after it.
- **c0020, c0021, c0028 to c0031.** None touches an Altium requirement or "Interfaces in the DSL".

## Risks / Trade-offs

- **Altium may want keys Fenolite omits** (`INDEXINSHEET`, `UNIQUEID` on entries, a document unique
  id). Mitigation: the saved files give the full key lists; a refuted row names the key, the fact
  page is corrected first, and a regression test follows.
- **The `Additional` stream is new to the writer.** A fault there may stop the sheet from opening.
  Mitigation: the early sample is checked first; the `flat` mode and plain-net crossings do not
  depend on it.
- **A bare harness entry may be an error** (`H-A-SCH-HARN-UNUSED`). Mitigation: the main sample has
  none; `partial.py` isolates the case. Fallback: wire it to a No ERC directive (c0036).
- **Switching the mode after the PCB exists in Altium changes the links of module-sheet parts.**
  Altium then offers to match by designator (S-0164). The default stays `flat`, and the Altium page
  says so.
- **Drawing quality.** Labelled stubs are correct but busy. Routed lines are Open Question 3.
- **Stale sheets.** A renamed module leaves its old sheet in the folder; it is no longer listed.

## Changes after the maintainer's report (2026-10-03, AD 26.5)

The report of Part H is in `docs/evidence/altium-schematic.md`, "Reports". It changed three things.

- **H3: harness on the top sheet.** Decision 9 above. Requirement "Harness lines between sheet
  symbols" is added; "Sheet symbols and sheet entries", "Harness records", "Harness definition files",
  "Hierarchical sheet layout", "Hierarchy read back" and the scenarios that count the records, labels
  and files of the sample are edited in place (the change is not archived). The sample now has seven
  golden files: the top sheet holds no connector, so it gets no `.Harness` file. `layout.SymbolSpec`
  gains `line_to` and `line_from`, `layout.PlacedEntry` gains `side`, `layout.SheetPlan` gains `lines`,
  and `hierarchy.harness_lines` and `layout.SplitLine` are new.
- **H6: bare harness entries.** A warning, not an error. Open Question 5 is closed.
- **H7: the board example.** Altium Designer left the sheet of the module `led` outside the hierarchy,
  so `D1` was missing from the compiled schematic and the comparison reported it as extra on the
  board. The built files were read again with the test readers: the top sheet holds the sheet symbol
  `led`, its file-name record equals the name the project file lists, the project file lists the sheet,
  and the board's link of `D1` is `\<id of that sheet symbol>\<id of D1>`. The maintainer then opened
  "Synchronize Sheet Entries and Ports" on the symbol `led`: it showed the file, one link `LED_A` and
  nothing unmatched, and after it was closed without a change the sheet was a child. So the content is
  consistent for Altium, and its first pass over the project skips that sheet. **The cause is not
  proven.** The one thing that sets the sheet `led` apart from every sheet Altium has taken as a child
  is its size: its `FileHeader` stream is 2303 bytes and so lies in the compound file's mini stream,
  while every child so far, and every sheet Altium saved, holds 4096 bytes or more (`H-A-SCHBIN-MINI`).
  What was done:
  - the supposed cause was removed: the binary form padded a sheet under 4096 bytes with one hidden
    sheet parameter. The second report refuted the guess, and the padding is withdrawn (below);
  - one difference from a saved board was found and corrected: `CHANNELOFFSET` restarts at 0 on every
    sheet (S-0188), and Fenolite wrote the index over the whole board, which gave `D1` the offset 2
    on a sheet of one part. Nothing shows that this explains H7;
  - the readback `component_links` and `board_link_problems` (`tests/_altium_read.py`) now checks, for
    the board example, what the report asked for: every board link resolves to a schematic component
    through an existing sheet symbol whose file the project lists, and every module sheet is reachable
    from the top sheet, also for a module without a crossing. It passes on the files the maintainer
    opened, so it would not have caught H7; it catches a missing symbol, a wrong file name and an
    unlisted sheet;
  - `H-A-SCH-HIER-ECO` and `H-A-SCH-HIER-PRJ` stay pending with the observation, `H-A-SCHBIN-MINI` is
    registered, and step H7 is re-opened on the rebuilt example. Seven variants tell the possible
    causes apart: a structure file, document ids in the project file, the padded sheets alone, the
    small module sheet moved to the other module, the order of the sheet symbols and documents, the
    PCB document, and the ports and sheet entries;
  - **no project structure file and no document ids are written.** After the dialog and "Save All",
    Altium wrote `<project>.PrjPcbStructure` and a full project file with a `DocumentUniqueId` per
    document (empty for `driver`, which was a child all the same). Both are results of Altium's own
    passes: the structure file is derived from the sheets, and an id appears when a document is loaded
    in full. Writing them would be a second output to keep in step with the sheets (and to keep when
    Altium rewrites it, as the project file), and a written tree could hide a sheet that the compiler
    still does not read. So the default stays as c0032 decided, and variants a and b measure whether
    either file changes anything before the question is opened again (Open Question 7).

- **H7, second report (2026-10-03, AD 26.5): the cause is the order of the documents.** Each test used a
  fresh copy and "Validate PCB Project" alone. The padded example and variant c still had the second
  module sheet outside the hierarchy, variant d failed as well, and so did variants a, b, f and g. In
  variant e, where the sheet of `D1` is listed first, that sheet was a child and `driver` was outside:
  only the first module sheet listed joins. The project file that Altium saved in full works in the
  first order, alone, with its structure file, and with its document sections cut down to
  `DocumentPath` (variants h, j and n). Fenolite's minimal file works when its documents are in the
  order top sheet, `driver`, `led`, PCB document, PCB library, schematic library (variant l), and was
  not reported as working with Altium's `[Design]` section or with `HierarchyMode=0` (variants k and
  m). What was done:
  - **decision 16 is changed**: `write_prjpcb` lists the top sheet, the module sheets, the PCB
    document, the libraries and the harness files. For the board example it gives the bytes of
    variant l. A flat build keeps its bytes. The rule that an existing project file is kept stays, so
    a folder with a project file of the first build needs it deleted;
  - **the padding is removed**: `MINI_CUTOFF`, `note_record`, `padded_records` and the `FenoliteNote`
    parameter, with their tests. `H-A-SCHBIN-MINI` is refuted and superseded by `H-A-SCH-HIER-ORDER`,
    which variant l confirms. The sheets of the board example are again the bytes of the first build;
  - **`CHANNELOFFSET` per sheet stays**: it follows a saved board (S-0188), not the refuted guess;
  - why the full project file is accepted in the other order is not known and not needed. The
    hierarchy sample also had both module sheets as children; its built project file held the
    schematic library between the top sheet and the module sheets, and no PCB document or PCB
    library, so which documents in between stop the second sheet is not settled. Listing the
    schematic documents first makes the question moot;
  - a regression test checks, on the board example, that every schematic document precedes every
    other document of the project file, with the top sheet first;
  - open for the next report: the change order of H7 on the rebuilt example, and steps H3 to H5.

## Migration Plan

- No migration. Without the option every Altium output is unchanged, byte for byte.
- A design that adds a `Harness` and stays `flat` gets one more `altium.not-lowered` info.
- Rollback: drop the option or the `Harness` call; no stored file needs repair.

## Open Questions

1. Should `modules` become the default once Part H is confirmed? Default: no, until the maintainer
   asks; it would rewrite the sample's golden files.
2. Should the sheet name be `U_<module>`, Altium's default, instead of `<module>`? Default:
   `<module>`. It is the DSL's name and it is what the PCB's hierarchical path then shows.
3. Should the top sheet join two sheet entries of one harness by a direct harness line when exactly
   two modules share it? Answered by step H3 of the report of 2026-10-03: yes. The blocks gave four
   "multiple names" warnings; the line is now drawn when the two symbols are neighbours.
4. Should a port carry a direction (`IOTYPE`) from pin types? Default: no; unspecified.
5. Should an entry whose net does not cross be left out instead of drawn bare? Answered by step H6 of
   the report of 2026-10-03: it stays drawn bare. Altium Designer 26.5 reports "Unconnected Harness
   Entry" as a warning, once per connector, and compiles the project without an error.
6. Should Part H include an import of the project in KiCad's GUI as a third reading? Default: no; it
   is not an oracle and adds a manual step.
7. Should the build write `<name>.PrjPcbStructure` (from the sheet symbols, written once and then
   kept, as the project file) and `DocumentUniqueId` keys? Default: no, until variants a and b of step
   H7 show that Altium needs either to show or to compile the hierarchy.
