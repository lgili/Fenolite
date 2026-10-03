# Altium project file (`.PrjPcb`)

This page states, in Fenolite's own words, what the experimental writer `fenolite.backends.altium`
(change c0032) relies on to write an Altium Designer PCB project file. The schematic itself is
described in `schematic-ascii.md`, with the same rules: sources in `docs/evidence/sources.md`, code
written from these pages only, GPL sources (S-0132) read for facts only, every fact `INFERRED` until
the maintainer's author report (`docs/evidence/altium-schematic.md`). `kicad-cli` reads no Altium
schematic (S-0132, S-0020), so nothing here is `ORACLE-VERIFIED`.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| A PCB project file (`.PrjPcb`) is an ASCII file that lists the project's documents and its project-level settings | S-0134 | INFERRED | H-A-PRJ-OPEN |
| The layout is INI-like: a line `[<section>]` starts a section, and `<key>=<value>` lines follow | S-0132, S-0143 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PRJ-OPEN |
| Each document is a numbered section `[Document1]`, `[Document2]`, … holding `DocumentPath=<path>`; readers take every section whose name starts with `Document` and tell document kinds by extension (`.SchDoc`, `.PcbDoc`, `.SchLib`, `.PcbLib`) | S-0132, S-0143 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PRJ-OPEN |
| `DocumentPath` is relative to the project folder: a bare file name names a document beside the project file | S-0132 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PRJ-OPEN |
| A project file has a `[Design]` section. That it holds `Version=1.0` and that its other keys and the per-document keys are optional is a hypothesis: no permitted source states it | S-0143 (the `[Design]` section); `Version` and the optional keys: no permitted source (S-0142 removed by the audit of 2026-10-02; S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) does not give it) | INFERRED | H-A-PRJ-OPEN |
| An open-source writer writes `[Design]` and `[DocumentN]` with CR LF line ends; no permitted source states the line end Altium writes | S-0143 | INFERRED | H-A-PRJ-OPEN |
| No permitted source says that Altium needs a UTF-8 byte-order mark; the file is read as plain 7-bit ASCII | no permitted source (S-0142 removed by the audit of 2026-10-02; S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) does not give it) | INFERRED | H-A-PRJ-OPEN |
| KiCad's developer page sketches one `[Design]` section with repeated `DocumentPath=` lines, a layout that KiCad's own project importer does not read; numbered `[DocumentN]` sections are used instead | S-0002, S-0132 | INFERRED | H-A-PRJ-OPEN |
| Altium rewrites the project file when the user adds a document, such as a new PCB document, and saves the project; keys it adds are expected | S-0134 | INFERRED | H-A-PRJ-KEEP |
| "Design » Update PCB Document" opens the engineering change order of a compiled project: "Validate Changes" fills its check column, "Execute Changes" its done column, and a change that cannot be made is marked with a red cross and a message | S-0141 | INFERRED | H-A-SCH-ECO |
| A multi-sheet project lists every document in its own `[Document<n>]` section: each schematic sheet, the PCB document, the libraries and the harness definition files. The saved projects read, which are full project files, hold them in no particular order, and their top sheet need not be first; for Fenolite's minimal file the order matters (`H-A-SCH-HIER-ORDER`, below) | S-0132, S-0187, S-0188 | INFERRED | H-A-SCH-HIER-PRJ |
| The top sheet is found from the structure, as the sheet that no sheet symbol names, not from the order of the sections | S-0185, S-0187, S-0188 | INFERRED | H-A-SCH-HIER-PRJ |
| Saved project files hold scope and net-naming keys under `[Design]` and a unique id per document section; Fenolite's verified project file holds none of them and relies on Altium's defaults | S-0187, S-0188 | INFERRED | H-A-SCH-HIER-PRJ |
| The project option "Net Identifier Scope" has the values Automatic, Flat, Hierarchical, Strict Hierarchical and Global. Automatic picks Hierarchical when the top sheet has sheet entries, Flat when there are ports but no sheet entry, and Global otherwise | S-0185 | INFERRED | H-A-SCH-HIER-COMPILE |
| In the hierarchical scope a net label is local to its sheet, and a port connects only upwards, to the sheet entry of the same name on the symbol of its sheet; ports of the same name on other sheets do not join | S-0185 | INFERRED | H-A-SCH-HIER-COMPILE |
| Power ports are global: the same name joins on every sheet. A power port wired to a port becomes local to its sheet, and the strict hierarchical scope makes every power net local | S-0185 | INFERRED | H-A-SCH-HIER-NAMES |
| Net naming has project options (ports or sheet entries may name nets, higher-level names or power-port names may take priority). With one name on every label, port and sheet entry of a net, the net has one candidate name; that Altium then uses it is inferred | S-0185 | INFERRED | H-A-SCH-HIER-NAMES |
| Harness definitions are text files with the extension `.Harness`; each line is `<type>=<entry>,<entry>,…`. Type names may hold spaces. Line ends are CR LF in the older saved project and LF in the recent one, and the types appear in name order | S-0186, S-0187, S-0188 | INFERRED | H-A-SCH-HARN-FILE |
| Altium generates a definition when a connector with entries is built and updates it when the connector changes, unless the line starts with `Locked;`. A locked definition that differs from the drawn connector is reported as a conflicting harness definition | S-0186 | INFERRED | H-A-SCH-HARN-FILE |
| Saved projects hold one `.Harness` file per sheet that has connectors, named after that sheet, and the project file lists each one as a document | S-0187, S-0188 | INFERRED | H-A-SCH-HARN-FILE |
| A `.PrjPcbStructure` file beside a saved project lists the top document and each sheet symbol; Altium writes it | S-0188 | INFERRED | H-A-SCH-HIER-PRJ |
| Altium Designer 26.5 writes `<project>.PrjPcbStructure` on "Save All" once it holds the whole hierarchy; Fenolite's files had none and Altium did not ask for one. Its lines end with CR LF: first `Record=TopLevelDocument`, `FileName=<top sheet>` and `SheetNumber=` followed by one space; then, per sheet symbol, `Record=SheetSymbol`, `SourceDocument=<sheet that holds the symbol>`, `Designator` and `SchDesignator` (the symbol's name), `FileName` and `RawFileName` (the child's file name), `SymbolType=Normal`, `ObjectKind=Sheet Symbol`, and the keys `SheetNumber`, `DesignItemId`, `SourceLibraryName`, `RevisionGUID`, `ItemGUID` and `VaultGUID`, each with one space as its value (maintainer's report of step H7, 2026-10-03) | S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HIER-PRJ |
| Altium Designer 26.5 saves the project file in UTF-8 with a byte-order mark and CR LF lines. It keeps `[Design]` and `Version=1.0`, adds `HierarchyMode=0` and some forty more keys there, keeps the `[Document<n>]` sections in the written order and adds 14 keys to each, the last one `DocumentUniqueId`, and adds sections for preferences, a configuration, output groups, rule checks, annotation, class generation and comparison (maintainer's report of step H7, 2026-10-03) | S-0134 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PRJ-KEEP |
| In that saved project `DocumentUniqueId` held eight letters for the top sheet, for the PCB document and for the module sheet that a dialog had just loaded, and was empty for the two libraries and for the other module sheet, which was a child all the same. The save changed no schematic file, and none of the ids is one that Fenolite writes. So Altium gives a document an id when it loads it in full, and a sheet can be a child without one (maintainer's report of step H7, 2026-10-03) | S-0134 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HIER-PRJ |
| With a minimal project file (`[Design]`, `Version=1.0` and one `DocumentPath` per section), Altium Designer 26.5 builds the whole hierarchy when the schematic documents are listed together: the top sheet, then the module sheets, then the PCB document and the libraries. Both module sheets are then under the top sheet after "Project » Validate PCB Project" on a fresh copy, with no dialog (variant l of step H7, 2026-10-03) | S-0134 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HIER-ORDER |
| With the same minimal file in the order top sheet, PCB document, PCB library, schematic library, module sheets, Altium Designer 26.5 takes only the first module sheet listed as a child: the second one stays outside the hierarchy, whatever its size, and "Validate PCB Project" does not bring it in. With the module sheets listed in the other order, the other sheet is the child (variant e). Neither a `.PrjPcbStructure` file with Altium's lines, nor a `DocumentUniqueId` in every section, nor leaving out the PCB document, nor a design without ports changed that (variants a, b, f and g), and the minimal file with Altium's full `[Design]` section or with `HierarchyMode=0` alone was not reported as working (variants k and m) (maintainer's second report of step H7, 2026-10-03) | S-0134 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HIER-ORDER |
| The project file that Altium Designer 26.5 saved in full is accepted in that first order: with it, alone, with its structure file, or with every `[Document<n>]` section cut down to `DocumentPath`, both module sheets are children (variants h, j and n of step H7, 2026-10-03). Which of its other sections makes the difference is not known, and Fenolite does not need it | S-0134 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HIER-ORDER |
| In the hierarchy sample both module sheets are under the top sheet in Altium Designer 26.5 (maintainer's report, 2026-10-03). The maintainer's note gives its documents as top sheet, `flash`, `mcu`, schematic library; the project file built for that session held the schematic library as its second document, between the top sheet and the two module sheets, and no PCB document or PCB library. So one schematic library in between may not be what stops the second sheet; which of the documents in between does is not known, and the order written now avoids the question | S-0134 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HIER-PRJ |

## Fenolite's choices

- The written project file is exactly `[Design]`, `Version=1.0`, an empty line, `[Document1]` and
  `DocumentPath=<name>.SchDoc`, each line ending with CR LF, in 7-bit ASCII and without a byte-order
  mark.
- It is written once: an existing `<name>.PrjPcb` in the output folder is kept, because Altium rewrites
  it when the PCB document is added (capability `altium-build`, "Edited Altium outputs are not
  overwritten").
- Change c0037 (`--altium-sheets modules`) lists the documents in this order: the top sheet as
  `[Document1]`, one section per module sheet in module-name order, the PCB document when there is one,
  the libraries in the MS-CFB order of their names, and one section per harness definition file in the
  MS-CFB order of the names. Every schematic document so precedes every other document, the top sheet
  first (`H-A-SCH-HIER-ORDER`). The first build listed the module sheets after the libraries, and Altium
  Designer then took only the first module sheet into the hierarchy. Without module sheets the bytes do
  not change: `[Document1]` is the schematic and `[Document2]` the PCB document when there is one.
- No key names the top sheet or the net scope, and no project structure file is written
  (`H-A-SCH-HIER-PRJ`, `H-A-SCH-HIER-COMPILE`). Altium derives the structure file from the sheets and
  writes it itself; a written copy, or document ids in the project file, did not bring a skipped sheet
  into the hierarchy (variants a and b of step H7).
- The order holds for a project file that Fenolite writes. An existing `<name>.PrjPcb` is kept as it
  is, so a project file of the first build has to be deleted, or its sections reordered, before the
  build is repeated.
- A harness definition file is `<sheet file stem>.Harness`, one per sheet that holds a harness block
  (a harness connector). A top sheet that only joins two sheet entries by a signal harness line holds no
  connector and gets no file, as the saved top sheets. The file holds
  one line `<type>=<entry>,<entry>,…` per type, types and entries in code-point order, each line ending
  with CR LF, in 7-bit ASCII without a byte-order mark. A name that holds `=`, `,` or `;` is refused
  (`H-A-SCH-HARN-FILE`).
