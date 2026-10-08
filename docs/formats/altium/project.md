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
| The minimal project file that Fenolite writes for the board example (top sheet, `driver`, `led`, PCB document, PCB library, schematic library; no other key) is accepted by Altium Designer 26.5: on a fresh copy, after "Project » Validate PCB Project" alone, both module sheets are under the top sheet, and "Design » Update PCB Document" then runs on the compiled project (maintainer's third report of Part H, 2026-10-03) | S-0134 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HIER-PRJ |

## The project file as Altium saves it

Change c0042 reads project files (`fenolite.backends.altium.read.project`). The rows below state what
the reader relies on, measured on the three public project files of the corpus (S-0187, S-0188,
S-0297; rows `altium-third-party-prjpcb-01` to `-03`) and on the sources named. The writer's rows above
stay as they are. The reader keeps every byte (`read.textfile`, `read.ini`) and types only what the
import (c0043) needs; every other section and key stays reachable through `ProjectFile.ini`.

| fact | source | label | hypothesis |
|---|---|---|---|
| A saved project file is INI text: a line `[<name>]` opens a section, each `<key>=<value>` line belongs to the section above it, and empty lines separate the sections. No line outside these three forms, no line before the first section and no repeated key was seen | S-0132, S-0187, S-0188, S-0297 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-INI |
| The file starts with `[Design]`, whose first two keys are `Version=1.0` and `HierarchyMode` | S-0187, S-0188, S-0297 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-INI |
| After `[Design]` come some thirty to fifty more design keys, then `[Preferences]`, the numbered sections `[Document<n>]`, `[GeneratedDocument<n>]`, `[Configuration<n>]` and `[OutputGroup<n>]`, and option sections whose names hold spaces (`[Electrical Rules Check]`, `[Comparison Options]`, …). One file adds `[ProjectVariant<n>]` and `[Parameter<n>]`, and another adds `[ProjectVariant<n>]` alone | S-0187, S-0188, S-0297 | INFERRED | H-A-RD-PRJ-INI |
| A section `[Document<n>]` lists one document: `DocumentPath` first, then fourteen keys of annotation, library update and class generation, the last one `DocumentUniqueId`. The numbers run from 1 without a gap | S-0132, S-0187, S-0188, S-0297 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-DOCS |
| `DocumentPath` is relative to the folder of the project file, with `\` between folders; a path can leave that folder through `..`. No saved path is absolute or starts with a drive letter | S-0132, S-0187, S-0297 | INFERRED | H-A-RD-PRJ-DOCS |
| The documents listed are schematic sheets, PCB documents, schematic, PCB and integrated libraries, harness definition files, output jobs, a bill-of-materials document, draftsman documents and an annotation file: every extension is one of `DOCUMENT_KINDS` | S-0187, S-0188, S-0297 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-DOCS |
| The spelling of an extension's case varies between documents of one file (`.SchLib` and `.SCHLIB`) | S-0187 | INFERRED | H-A-RD-PRJ-DOCS |
| A listed document can be absent from the published folder: a project lists an output job that its repository does not hold | S-0187 | INFERRED | H-A-RD-PRJ-DOCS |
| A section `[GeneratedDocument<n>]` lists a file that an output wrote (reports, Gerber and drill files), with `DocumentPath` and a revision key | S-0187, S-0188 | INFERRED | H-A-RD-PRJ-DOCS |
| A project parameter is a section `[Parameter<n>]` with the keys `Name` and `Value` | S-0187 | INFERRED | H-A-RD-PRJ-PARAM |
| `[Design]` holds the net-naming options `AllowPortNetNames`, `AllowSheetEntryNetNames`, `AppendSheetNumberToLocalNets` and `PowerPortNamesTakePriority`, each `0` or `1`, and `OutputPath`; that they are the options of the same names in the project options is read from their names | S-0185, S-0187, S-0188, S-0297 | INFERRED | H-A-SCH-HIER-NAMES |
| In all six corpus project files `[Design]` holds, after `Version` and `HierarchyMode`, the channel keys in the order `ChannelRoomNamingStyle`, `ReleasesFolder`, `ChannelDesignatorFormatString`, `ChannelRoomLevelSeperator`, and later, in this order, `AllowPortNetNames=0`, `AllowSheetEntryNetNames` (`1` in five), `AppendSheetNumberToLocalNets` (`0` in five), `NetlistSinglePinNets=0`, `ReorderDocumentsOnCompile=1`, `NameNetsHierarchically=0` and `PowerPortNamesTakePriority` (`0` in five), with other keys between them; `NewIndexingOfSheetSymbols` is in three files only. What Altium assumes for an absent key is not documented; the two-channel sample writes these seven with the majority value (c0151) | S-0706 | INFERRED | H-A-SCHRPT-ATTACH |
| Altium documents five net identifier scopes (Automatic, Flat, Hierarchical, Strict Hierarchical, Global) and stores the project options in the project file. `HierarchyMode` is `0` in two saved files and `2` in the third; no permitted source gives the number of each scope | S-0138, S-0187, S-0188, S-0297 | INFERRED | H-A-RD-PRJ-HIER |
| Encodings and line ends vary: one file is UTF-8 with a byte-order mark and LF line ends; one is 7-bit ASCII with CR LF; one has CR LF and no byte-order mark and holds single bytes above `7F` that are not UTF-8 (such as a degree sign, in values of a variant section). Which code page those bytes are in is not stated (`H-A-RD-PRJ-ENC`, refuted: not every file is ASCII or UTF-8) | S-0187, S-0188, S-0297 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-ENC-2 |

### Document kinds

`project.DOCUMENT_KINDS`: the kind of a document comes from its extension, compared without case, as
KiCad's project importer does (S-0132). Any other extension is `other`.

| extension | kind |
|---|---|
| `.SchDoc` | `schematic` |
| `.PcbDoc` | `pcb` |
| `.SchLib` | `schematic-library` |
| `.PcbLib` | `pcb-library` |
| `.IntLib` | `integrated-library` |
| `.OutJob` | `output-job` |
| `.RUL` | `rules` |
| `.stackup` | `stackup` |
| `.Harness` | `harness` |
| `.SchDot` | `sheet-template` |
| `.BomDoc` | `bom` |
| `.PCBDwf` | `draftsman` |
| `.Annotation` | `annotation` |

### Hierarchy modes

`project.HIERARCHY_MODES` holds only the numbers this page states (`H-A-RD-PRJ-HIER`). The other four
scopes get a row when the maintainer's author report names their numbers
(`docs/evidence/altium-project-read.md`); until then a project with another number reads with
`net_scope = None` and the warning `altium.project.hierarchy-mode-unknown`.

| HierarchyMode | net scope |
|---|---|
| `0` | `automatic` |

### Fenolite's choices (reader)

- The bytes are the source of truth: `ProjectFile.to_bytes()` gives the input back, with its byte-order
  mark, line ends, unknown sections, key order and repeated keys.
- The typed text is UTF-8 when the file has a byte-order mark or its bytes decode as UTF-8, else Latin-1
  with the warning `altium.text.encoding-assumed`: Latin-1 maps every byte, so reading never fails on
  an encoding, and only the typed text of the affected values can be wrong.
- Section and key names are matched exactly as written. Numbered sections are taken by name, not by
  position; their numbers need not be consecutive.
- Typed: the documents and generated documents, the parameters and seven `[Design]` options
  (`HierarchyMode`, `OutputPath` and the four net-naming options above; `raw` keeps every entry).
  Variants, configurations, output groups, error reporting, class generation and every other section
  stay raw.
- `load_project` opens only the text companions (output jobs, rule files, stack-up files) that lie
  inside the project folder; a path that leaves it is not opened and its issue names the document
  index, not the path. A missing companion is a warning, and a companion that is not readable is a
  warning too: the project still loads.

## Class generation

Change c0048 writes the options that decide which classes and rooms "Design » Update PCB Document" derives
from the schematic.

| fact | source | label | hypothesis |
|---|---|---|---|
| The tab "Class Generation" of the project options holds, per schematic sheet, a tick "Component Classes", a tick "Generate Rooms" and a net class scope (None, Local Nets Only, All Nets), and, for the project, the ticks "Generate Component Classes" and "Generate Net Classes" under "User-Defined Classes" | S-0310 | INFERRED | H-A-ECO-PRJ-KEYS |
| A sheet's component class is named after its sheet symbol, and its room, a Room Definition rule scoped `InComponentClass('<name>')`, has the same name; no room is made for a sheet without components | S-0310 | INFERRED | H-A-ECO-ROOMS |
| Saved project files hold, in every `[Document<n>]` section, `ClassGenCCAutoEnabled`, `ClassGenCCAutoRoomEnabled` (0 or 1) and `ClassGenNCAutoScope` (`None` in every section read), in this order among the other keys; that the first two are the ticks "Component Classes" and "Generate Rooms" and the third the net class scope is read from their names | S-0187, S-0188, S-0313 | INFERRED | H-A-ECO-PRJ-KEYS |
| Saved project files hold a section `[PrjClassGen]` after the document sections, with seven keys in this order: `CompClassManualEnabled`, `CompClassManualRoomEnabled`, `NetClassAutoBusEnabled`, `NetClassAutoCompEnabled`, `NetClassAutoNamedHarnessEnabled`, `NetClassManualEnabled` and `NetClassSeparateForBusSections`. The two public projects hold the values 0, 0, 1, 0, 0, 1, 0; one of them declares net classes by directives (`schematic-ascii.md`, "Net class directive"). That `NetClassManualEnabled` is the tick "Generate Net Classes" is read from its name | S-0187, S-0188 | INFERRED | H-A-ECO-PRJ-KEYS |
| The project file that Altium Designer 26.5 saved from Fenolite's minimal file of the board example holds the same seven keys with `NetClassManualEnabled=0`, and, in all six document sections, `ClassGenCCAutoEnabled=1`, `ClassGenCCAutoRoomEnabled=0` and `ClassGenNCAutoScope=None`; its `[Design]` section holds `ConstraintManagerFlow=0`. Whether these are the defaults Altium takes for missing keys, or settings changed in that session, is not recorded | S-0313 | INFERRED | H-A-ECO-PRJ-KEYS |
| On the board example built before change c0048, "Design » Update PCB Document" of Altium Designer 26.5 matched every component and net and proposed four groups: remove the net class `PWR`; add the component classes `driver` and `led`; add a room for each, scoped by its component class; add two "Supply Nets" rules with a voltage of 0. Which project file that session used, Fenolite's minimal one or the saved one with the room key at 0, is not recorded, so that the key stops the rooms is a hypothesis (maintainer's report of 2026-10-03) | S-0313, S-0310 | INFERRED | H-A-ECO-ROOMS |
| With the three class keys in every schematic section and `[PrjClassGen]`, Altium Designer 26.5 opens the project of the board example, matches every component of both module sheets, keeps the net class and proposes no component class and no room: its change order lists only two "Supply Nets" rules. The flat routed sample of the same session, whose project file held `[PrjClassGen]` and no class key, kept its net class and was offered the component class `routed`, the room `routed` scoped by that class, and two "Supply Nets" rules. The two samples differ in the key and in the component class of the board, so the report does not isolate which of the two stops the room; the documentation ties the room to the option "Generate Rooms" (maintainer's report of 2026-10-04) | S-0310, S-0313 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-04; no artefact) | H-A-ECO-ROOMS |

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
- Class generation (change c0048). A project with module sheets or with a PCB document holds three more lines
  after `DocumentPath` in the section of every schematic document, the single or top sheet and each module
  sheet: `ClassGenCCAutoEnabled=1`,
  `ClassGenCCAutoRoomEnabled=0` and `ClassGenNCAutoScope=None`. So Altium derives the component class of each
  sheet, which the PCB document holds (`pcb-copper.md`), and no room (`H-A-ECO-ROOMS`): Fenolite writes no room,
  because no permitted source holds a room rule's record. The sections of the other documents hold
  `DocumentPath` alone. A flat project with a PCB document holds the keys too: without them its change order
  proposed a room for the single sheet, and with them, and the sheet's class in the PCB document, it proposes none (reports of Part E, 2026-10-04; `H-A-ECO-SHEETCLASS`). Only a project
  without module sheets and without a PCB document holds none.
- A design with a net class ends its project file with an empty line, `[PrjClassGen]` and the seven keys with
  the values of the public saved projects: `CompClassManualEnabled=0`, `CompClassManualRoomEnabled=0`,
  `NetClassAutoBusEnabled=1`, `NetClassAutoCompEnabled=0`, `NetClassAutoNamedHarnessEnabled=0`,
  `NetClassManualEnabled=1` and `NetClassSeparateForBusSections=0`. The whole section is written, not the one
  key, because no file read holds a partial section and the defaults of missing keys are not known. A design
  without a net class, without module sheets and without a PCB document keeps the minimal bytes
  (`H-A-ECO-PRJ-KEYS`).
- No key of the comparator or of the change-order options is written: the saved files number those options
  without naming them, so their meaning is in no permitted source.

## Output job in the project (change c0087)

| fact | source | label | hypothesis |
|---|---|---|---|
| A saved project lists its output job as a document: a section `[Document<n>]` whose `DocumentPath` is the job's file name, among the sections of the other documents | S-0187, S-0188 | INFERRED | H-A-OUTJOB-OPEN |

- The written project file lists `<name>.OutJob`, when the build writes one, in the section after the PCB
  document and before the libraries, with `DocumentPath` alone. A project without a job keeps its bytes.
- A project file that exists is kept (the rule above): when it does not list the job, the build reports
  `altium.outjob-not-listed` and the user adds the job in Altium.
