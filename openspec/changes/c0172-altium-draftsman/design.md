## Context

- **Request.** The maintainer, 2026-10-16: he will soon need Draftsman documents in the library. Asked to choose, he chose "a real .PCBDwf document", not only PDF drawings, for release 0.5.0.
- **What exists** (`release-0.5.0` at `03440f4`, read 2026-10-16):
  - `backends/altium/read/project.py` maps `.PCBDwf` to the kind `draftsman`, and the reader stops there. `docs/evidence/altium-project-read.md` counts two draftsman documents in the project of S-0187.
  - c0117: `exports/drawing_spec.py` (`fenolite.drawing-spec.v0`, closed key set), `drawing_tables.py` (board, stack-up, drill and notes blocks from the model, `drill_rows`), `drawing_layout.py` (pure `place` and `choose_paper` at 1:1) and `drawings.py` (KiCad plot copies). `fenolite export` refuses Altium inputs (`docs/drawings.md`).
  - c0087/c0138: `outjob.py` writes six outputs. c0087 found that public jobs bind drawings through an output of the type `PCBDrawing` that names a drawing document, and left Draftsman out (`docs/formats/altium/output-job.md`).
  - `prjpcb.py` writes no `[Parameter<n>]`. The reader knows the form (`H-A-RD-PRJ-PARAM`, S-0187).
  - `backends.altium` may import neither `exports` nor `templates` (`tests/unit/test_import_graph.py`). The lens composes them.
- **Public pages** (registered S-0772 to S-0781, read 2026-10-16):
  - Files: drawings are `*.PCBDwf`, sheet templates `*.DwsDot`, document templates `*.DwfDot` (S-0772, S-0774). Draftsman is "based on a dedicated file format" (S-0773); no page describes it.
  - Binding: a document is created for a project and a PCB source document of that project, and "draws data" from it. Tools » Import Changes From `<name>.PcbDoc` refreshes it (S-0772, S-0773).
  - Templates: a document template keeps the current PCB's data as a "shell", and a new document from it gets "the project's current PCB data" loaded into the shell (S-0774).
  - Objects: Board Assembly View, Board Fabrication View, Drill Drawing View, Layer Stack Legend, Bill Of Materials, Drill Table, Table, Note, Text, Linear Dimension (S-0775 to S-0781).
  - Parameters: project, system (`SheetNumber`, `SheetTotal`, `CurrentDate`, …), PCB and custom document parameters (S-0772).
  - Outputs: print, Output Job, Export to PDF and DXF (S-0773). In public jobs the drawing output has the type `PCBDrawing`, the category `Documentation` and the bare file name as its document path (S-0786, S-0187).
- **Public samples** (first look on 2026-10-16, counts only, with a script of this session; files in a scratch folder, never committed):

  | sample | source | licence | bytes |
  |---|---|---|---|
  | `DM3370_RAE/PCB/Assembly_Drawing.PCBDwf` | S-0785 (luxonis/oak-hardware, the repository of S-0187) | MIT | 4455680 |
  | `DM3370_RAE/PCB/Fabrication_Drawing.PCBDwf` | S-0785 | MIT | 4903885 |
  | `PiDP11IOExpander_Assembly.PCBDwf` (Git LFS) | S-0786 (sstallion/PCB-PiDP11IOExpander, the repository of S-0174) | BSD-2-Clause | 458794 |
  | `PiDP11IOExpander_Fabrication.PCBDwf` (Git LFS) | S-0786 | BSD-2-Clause | 328671 |

  All four start with `01 80 80 40`, then four bytes that differ per file, then `<Document xmlns="http://schemas.datacontract.org/2004/07/Altium.Designer.PcbDrawing.DataSerialization.V1"`. That is the default namespace a .NET data contract gets from its CLR namespace (S-0782). After the opening, element names appear in runs cut by short binary sequences, as in a compressed stream that keeps literal runs. Python's `zlib` (raw, zlib, gzip), `lzma` and `bz2` decode no part at offsets 0 to 8. The visible names include pads, polygons, silkscreen, board holes, designators and a model hash: **a document holds a copy of the board data**, consistent with Import Changes and the template shell.
  - Usable for the corpus: all four. Both licences are permissive, both repositories are already corpus sources, and the rows are fetched, `embeddable = false`, read for facts only. Not usable: no other public `.PCBDwf` was found by a web search on 2026-10-16. One public project that lists the extension in its README is a third-party parser and is not read.
- **Microsoft's public pages on data contracts** (S-0782 to S-0784, read for facts): members serialize base type first, then alphabetically, then by `Order`. On reading, an unknown element is ignored and a missing member keeps its default unless it is `IsRequired`. If Altium reads documents with that serializer (`H-A-DWF-MINIMAL`), a document that holds only the members Fenolite needs may open. Whether it does is a kit question.
- **Constraint.** No fact comes from Altium's program code: no decompilation, no reflection over or inspection of its installed assemblies, no schema exported from the program. No third-party Draftsman or Altium parser is read. Only the public pages above, the public samples, publicly specified compression formats and the maintainer's saved files are used. A file Altium wrote is never committed.

## Goals / Non-Goals

**Goals**
- An Altium build can write a native Draftsman document that Altium Designer 26.5 opens, fills from the PCB, prints and outputs, made from the same drawing specification as the KiCad drawings.
- Nothing is claimed for Altium before the kit has shown it. When the format cannot be established, the change says so early and ships the fallback.

**Non-Goals**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Measure before writing (Phase 1, gate G1).**
   - Census of the samples with a measuring script: header bytes, sizes, where text runs start, run lengths.
   - Candidate algorithms with a public specification only, each tried on the samples at every offset up to the first `<`: RFC 1950/1951/1952, LZMA/XZ, bzip2 (all in the standard library), LZ4 block and frame (public format description), Snappy (public format description), Zstandard (RFC 8878), Brotli (RFC 7932), and the Plain LZ77, LZ77+Huffman and LZNT1 forms of Microsoft's Open Specification MS-XCA. A codec missing from the standard library is run in a scratch environment as a measuring tool, never as a dependency. Each is registered as a source when it is used.
   - If none decodes the stream, the stream itself is observed: the maintainer's observation files F0 (Decision 8) differ by one edit each. The pairs show where literals, back-references and the second header field change. A decoder written from that observation is Fenolite's own.
   - **G1 passes** when `read_draftsman` decodes the four samples and every F0 file into XML that `xml.etree.ElementTree` parses, and the second header field is explained: a length, a known checksum or a field that Altium ignores (`H-A-DWF-FIELD`).
   - **G1 fails** after 2 design-days of Phase 1. Then the writer phases stop and the fallback ships (Decision 9). G1 cannot be passed by copying bytes the format was not understood from.

2. **Reader and census (Phase 2).** `read_draftsman(data) -> DraftsmanFile(header, root)` and `summary(file) -> DraftsmanSummary` (sheets with paper; views with kind, side, scale and place; tables with kind; notes with texts; parameters). Census of the four samples into `docs/evidence/altium-draftsman.md`: element counts, the sheet, view and table forms, counts only. The fact rows of `docs/formats/altium/draftsman.md` follow it, labelled `CORPUS-VERIFIED` on 2 repositories or `INFERRED` on one. The project loader keeps the kind `draftsman`. Reading a document into the model is a non-goal.

3. **What a first document holds.** The minimal useful set, from c0117's pages:

   | sheet | content | from the drawing specification |
   |---|---|---|
   | 1 fabrication | Drill Drawing View (top, layer pair Top–Bottom); Drill Table; Layer Stack Legend (default columns, total footer); generic Table "board" with c0117's board rows; Note with `[fab].notes`; two Linear Dimensions of the outline when `dimensions` is true | `[fab]` title, tables, dimensions, notes, at |
   | 2 assembly top | Board Assembly View, side Top, designator captions, values hidden unless `values`; Bill Of Materials table filtered to that view; Note with `[assembly].notes` | `[assembly]` title_top, values, designators, notes |
   | 3 assembly bottom | Board Assembly View, side Bottom; Bill Of Materials table filtered to that view | `[assembly]` title_bottom; left out when no part is on the bottom or `sides` omits it |
   | every sheet | a title block of Texts in the bottom-right corner holding the parameters `Title`, `Revision`, `Date`, `SheetNumber` and `SheetTotal`, and the sheet's title | `design.title_block(...)`, `[fab].title`, `[assembly].title_*` |

   - The BOM table is always on the assembly sheets. Its rows are Altium's (ActiveBOM or source documents, S-0778), not written by Fenolite. The specification gets no new key (open question 4).
   - Paper and places: c0117's `choose_paper` and `place`, at 1:1 around the board box. Draftsman tables are sized by Altium, so block sizes are Fenolite's estimates from the glyph bound. The kit checks overlaps (F2).
   - `dnp` cannot be drawn: the Altium build writes no variant. A do-not-populate part gives one `altium.not-lowered` info naming the refs (open question 6). `pads` and `designator_size` are reported the same way when they differ from the defaults.
   - The `drawing_sheet` frame of a `.sheet.toml` is not drawn in this change (cut item 2). The title block is plain Texts.

4. **Views as shells (open question 1).** Fenolite writes each view's own members: kind, side, place, scale, title and the source document. It writes no board copy. Altium fills the views by Import Changes, as it does for a template's shell (S-0772, S-0774). Probe FP4 settles this (`H-A-DWF-IMPORT`). If it fails, the board copy would be Fenolite's serialisation of the whole board in Altium's drawing data. That is a large, separately measured work and a later change, and this change takes the template route of Decision 9.

5. **The writer.** `write_draftsman(spec: DraftsmanSpec) -> bytes` writes the header and the stream in the form G1 established. If the format allows literal-only output, Fenolite needs no compressor, and the census says whether Altium writes such runs. Elements are written only from fact rows, in data-contract order (S-0783), with only the members a row names. Everything else is left to its default (S-0784, `H-A-DWF-MINIMAL`). `written_scope(root) -> DraftsmanSummary` is the summary of Decision 2. A unit test writes, reads and compares it (`H-A-DWF-READBACK`).
   - Unique ids that a document needs are derived from the design name and the object's path by SHA-256, as the other Altium writers do. There is no date and no random value.
   - `draftsman.NATIVE_WRITE: Final = False`. Probes FP1 to FP4 flip it in task 6.3 and acceptance F1 to F8 confirms it. As in c0168, it is a constant and not an option (open question 3).

6. **Build integration.**
   - `fenolite build --target altium --altium-draftsman {off,on}` (default `off`, open question 2) and `--drawing-spec FILE` (the c0117 file, read by `exports.drawing_spec.read_spec` in the command; errors exit 3 `FEN-3004`). Both are usage errors (exit 2, `FEN-2001`) with `--target kicad`. `--drawing-spec` without `--altium-draftsman on` is a usage error too.
   - The lens builds the `DraftsmanSpec` from the stored model, the specification and the layout, and passes plain values to `backends.altium`. The import graph stays as it is.
   - With `on`, a written PCB document and `NATIVE_WRITE`, the build plans `<name>.PCBDwf` (kind `altium_draftsman`). The project file lists it after the output job. The job gains one `PCBDrawing` output (category `Documentation`, document path `<name>.PCBDwf`, enabled for the PDF container; S-0786, S-0187). The project file gains `[Parameter<n>]` sections for the non-empty title-block fields, in the order of `title_block`.
   - Otherwise there is one `altium.draftsman-not-written` info. Its reason is the gate, no PCB document, or the option being off. No document is planned.
   - The edited-output rule (`FEN-7001`, `--discard-layout`, `.bak`) and the kept project file rule apply as for the job (c0138). A kept project file that does not list the document gives `altium.draftsman-not-listed` (info).
   - `result.draftsman`: `file`, `sheets` (per sheet its title, paper and objects), `not_lowered` and `spec` (the path as given and its SHA-256). It is `null` without a document.
   - With `--altium-draftsman off`, every file holds the bytes it held before this change.

7. **Verification.**
   - **RT-D1**, own read-back: `written_scope(read_draftsman(write_draftsman(spec)).root)` equals the spec's scope, and two writes give equal bytes.
   - **RT-D2**, Altium's re-save (kit F8): Fenolite reads the document the maintainer saved after Import Changes. It must hold the written sheets, views, tables and notes. When the census shows that a saved Drill Table holds its rows, their counts per diameter are compared with c0117's `drill_rows(design)`.
   - The corpus census (Decision 2) runs under `FENOLITE_HEAVY=1` with the corpus cached.
   - KiCad has no importer for Draftsman, so no `kicad-cli` oracle exists. The levels above `INFERRED` come from the samples (`CORPUS-VERIFIED`) and the kit only.

8. **The maintainer's kit, Part F** (Altium Designer 26.5, in the form of the native acceptance inventory: date, version, case, file hash, step, expected and observed outcome, level). Files are built outside the repository into `~/fenolite-altium-checks/session-5/F-draftsman/`, and every file Altium saves stays there.
   - **F0, observation (before any writer code).** On `f0/blink.PrjPcb`, a routed two-layer project that Fenolite builds for this round from `examples/blink_2layer/design.py`, the maintainer creates and saves, each as its own file:
     - F0.1 a new Draftsman document `[Default]` with no object;
     - F0.2 F0.1 saved again unchanged;
     - F0.3 F0.1 with one Text `FENOLITE-1`;
     - F0.4 F0.3 with the text changed to `FENOLITE-22`;
     - F0.5 F0.1 with a Board Assembly View, top;
     - F0.6 F0.5 with a second view, bottom;
     - F0.7 F0.1 with a Drill Drawing View and a Drill Table;
     - F0.8 F0.1 with a Layer Stack Legend;
     - F0.9 F0.5 with a Bill Of Materials table;
     - F0.10 F0.1 with a Note of two entries and a Linear Dimension on the outline in F0.7's view;
     - F0.11 F0.1 with a second sheet;
     - F0.12 F0.5 after moving `R1` in the PCB and running Import Changes;
     - F0.13 F0.10 saved as a document template `.DwfDot`;
     - F0.14 an Export to PDF of F0.10.

     He sends the folder, and `fenolite kit verify`'s path scan is run on it first. Only counts and element names derived from these files enter the repository.
   - **FP, probes (decide G2 and G3).** Candidate files written by Fenolite, opened in Altium:
     - FP1 F0.3 decoded and encoded again by Fenolite (the container);
     - FP2 F0.3 with the text changed by Fenolite (an edited member);
     - FP3 a document written from scratch with one sheet and one Text (`H-A-DWF-MINIMAL`);
     - FP4 FP3 with a Board Assembly View as a shell, then Import Changes (`H-A-DWF-IMPORT`);
     - FP5 a written `.DwfDot` used by File » New » Draftsman Document (`H-A-DWF-TEMPLATE`).

     For each he reports whether it opens without a message and what it shows.
   - **F1 to F8, acceptance** of a build of the routed blink with a drawing specification of two notes per page:
     - F1 the project lists `blink.PCBDwf`, which opens without a message;
     - F2 three sheets with their papers, titles, title-block parameters, and no overlapping objects;
     - F3 Import Changes fills every view;
     - F4 designators on both assembly views, the bottom one seen from the bottom;
     - F5 drill symbols and Drill Table counts equal `expected.md`;
     - F6 the Layer Stack Legend rows equal the stack-up of `expected.md`, and the BOM table lists the parts;
     - F7 the notes, numbered in order;
     - F8 File » Export to PDF and the job's `PCBDrawing` output give a PDF; the document saved as `saved.PCBDwf` passes `FENOLITE_ALTIUM_F8=<file> uv run pytest tests/unit/backends/altium/test_part_f.py -k f8` (RT-D2).

9. **Stop rules and the fallback.**
   - **G1**, Decision 1, after Phase 1: stream not decoded. Phases 3 to 6 stop. Ship **route P**: `[Parameter<n>]` title-block parameters in the project file (Decision 6, without the document; a build option `--altium-title-parameters on` is then the one new public name, with its guide line), no reader, and a procedure in `docs/altium.md`: create the document in Altium from a template, whose title block reads the parameters, and build the same script for KiCad to get c0117's PDFs. `--altium-draftsman` is not added. The tasks of the cut phases are closed as cut, with the reason.
   - **G2**, after probes FP1 to FP3: Altium refuses FP1 (the container) or FP3 (a minimal document) after one round of corrections. If FP5 opens, ship **route T**: the build writes `<name>.DwfDot` with the content of Decision 3, `result.draftsman.route` is `template`, and the procedure says File » New » Draftsman Document with it, which loads the current PCB data (S-0774). If FP5 also fails, ship route P.
   - **G3**, after FP4: a shell view is not filled by Import Changes. Then the views go through route T while the native document keeps only sheets, title block, notes and tables. The kit says whether the tables are filled without views. The board copy is a later change.
   - The maintainer is told which route ships as soon as each gate is settled, and before the 0.5.0 cut. If no gate has passed by the release cut, 0.5.0 ships route P and the writer moves to a 0.5.x release (open question 5).

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/altium/read/draftsman.py` | `read_draftsman`, `DraftsmanFile`, `summary`, `DraftsmanSummary` |
| `src/fenolite/backends/altium/draftsman.py` | `DraftsmanSpec` and its parts, `write_draftsman`, `written_scope`, `NATIVE_WRITE`, `DRAFTSMAN_KIND`, `EVIDENCE` |
| `src/fenolite/lens/altium_draftsman.py` | `draftsman_spec(model, spec, layout) -> (DraftsmanSpec, issues)` |
| `src/fenolite/lens/altium.py`, `backends/altium/project.py`, `prjpcb.py`, `outjob.py` | the planned document, the listing, the `PCBDrawing` output, `[Parameter<n>]` |
| `src/fenolite/cli/cmd_build.py` | `--altium-draftsman`, `--drawing-spec` |
| `docs/formats/altium/draftsman.md`, `docs/evidence/altium-draftsman.md`, `docs/evidence/sources.md`, `PROVENANCE.md`, `LEGAL-ANNEX.md` | facts, census, Part F, sources, provenance |
| tests | `tests/unit/backends/altium/test_draftsman_read.py`, `test_draftsman_write.py`, `test_part_f.py`, `tests/unit/lens/test_altium_draftsman.py`, `tests/unit/cli/test_build_draftsman.py`, `tests/corpus/test_altium_draftsman_census.py` |
| docs | `docs/altium.md` ("Draftsman document"), `docs/drawings.md` (the Altium sentence), agent guide `commands.md` and `altium.md` |

## Sources registered by this change

- S-0772 to S-0781: Altium's Draftsman pages (setting up, overview, templates, assembly and fabrication views, additional views, tables, annotations, dimensions, the object list), read 2026-10-16 for facts.
- S-0782 to S-0784: Microsoft's data contract pages (names, member order, versioning), CC-BY-4.0, read for facts.
- S-0785, S-0786: the four public samples and the jobs of S-0786, first look 2026-10-16.
- To be registered when used (task 1.2): the specifications of the compression formats tried, and the maintainer's reports of F0, FP and F1 to F8.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-DWF-CONTAINER | Every public sample and every F0 file is an 8-byte header starting `01 80 80 40` and a stream that Fenolite's reader decodes into one well-formed XML document of the namespace `…/Altium.Designer.PcbDrawing.DataSerialization.V1` (S-0782, S-0785, S-0786) | `tests/corpus/test_altium_draftsman_census.py` with the corpus cached; F0 files by the maintainer's run | 4 of 4 samples and every F0 file |
| H-A-DWF-FIELD | The four bytes after `01 80 80 40` are explained (a length, a checksum of a public algorithm, or ignored by Altium) | F0.1 against F0.2, F0.3 against F0.4; FP1 | the rule predicts the field of every sample and F0 file, or FP1 opens with it zeroed |
| H-A-DWF-READBACK | A written document reads back to its written scope, and two writes give equal bytes | `tests/unit/backends/altium/test_draftsman_write.py::test_readback` | equal for the routed blink and two authored specifications |
| H-A-DWF-MINIMAL | Altium Designer 26.5 opens a document that holds only the members Fenolite writes (S-0784) | probe FP3 | opens without a message and shows the text |
| H-A-DWF-IMPORT | Import Changes fills the views of a written shell with the board of the project (S-0772, S-0774) | probe FP4, case F3 | every view shows the outline and the components |
| H-A-DWF-TEMPLATE | A written `.DwfDot` is offered by File » New » Draftsman Document and gives a document with the project's current PCB data (S-0774) | probe FP5 | the new document shows the board in its views |
| H-A-DWF-OUTJOB | A `PCBDrawing` output bound to the written document generates a PDF from the output job (S-0786, S-0187) | case F8 | a PDF of three pages |
| H-A-DWF-PARAMS | Project parameters written as `[Parameter<n>]` show in the title-block texts of the document (S-0772, S-0187) | case F2 | the values of `title_block` on every sheet |
| H-A-DWF-KIT | Cases F1 to F8 of Part F hold their expected outcomes in Altium Designer | maintainer's report | one outcome per case |

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| container facts and the reader on public files | CORPUS-VERIFIED (2 repositories) | `H-A-DWF-CONTAINER` |
| written document and its read-back | INFERRED (mechanical) | `H-A-DWF-READBACK` |
| `NATIVE_WRITE = True` | ALTIUM-VERIFIED(author-report) of probes FP1 to FP4 | `H-A-DWF-MINIMAL`, `H-A-DWF-IMPORT` |
| the build's document as shipped | ALTIUM-VERIFIED(kit) | `H-A-DWF-KIT` F1 to F8 |
| route T or P when a gate fails | the probe that decides it; the procedure is documentation | FP5 |

## Risks / Trade-offs

- **The format may not yield to observation.** That is the main risk, and G1 bounds it to 2 design-days. The fallback ships something useful and says what it is not.
- **Altium may require members that Fenolite does not write.** FP3 shows it early. Each refusal message is recorded, and one round of corrections is allowed before G2.
- **A shell may be refused or left empty** (G3). Route T is the documented way Altium itself fills a shell.
- **Table sizes are Altium's.** Places use estimates, and F2 checks overlaps. A fixed corner (`at`) stays the user's tool.
- **Three maintainer rounds** (F0, FP, F1 to F8) for the 0.5.0 date. F0 is small and comes first. FP and F1 to F8 can be one session when FP passes.
- **Facts from files Altium saved.** Only element names and counts are recorded. The files stay in the maintainer's folder, and their path scan comes first.

## Migration Plan

- No model change and no schema change of the drawing specification.
- Builds without `--altium-draftsman on` keep their bytes, including the committed Altium samples.

## Budget (10 design-days)

| phase | content | days | depends on |
|---|---|---|---|
| 0 | entry, facts from the pages, corpus rows, the family | 0.75 | none |
| 1 | container measurement and F0 (gate G1) | 2.0 | 0; the maintainer's F0 |
| 2 | reader, census, fact rows | 1.0 | G1 |
| 3 | writer of sheets, Texts, parameters and Notes, the gate; probes FP1 to FP5 (gates G2, G3) | 2.0 | 2; the maintainer's FP |
| 4 | views as shells, Drill Table, Layer Stack Legend, BOM, board Table, dimensions, layout | 1.25 | 3 |
| 5 | build, CLI, project file, output job, issue codes, agent guide | 1.25 | 4 |
| 6 | Part F kit, the maintainer's run, the gate | 1.0 | 5 |
| 7 | docs and closing | 0.75 | 6 |

Cut order (first cut first):
1. Linear Dimensions.
2. The `.sheet.toml` frame; plain Texts stay.
3. The bottom assembly sheet.
4. The board Table.
5. The Layer Stack Legend.
6. The native `.PCBDwf`, replaced by route T.
7. Route T, replaced by route P.

Never cut: facts before writer code, the stop rules, the gate, the read-back, the maintainer's report before any `ALTIUM-VERIFIED`, and the project parameters.

## Open questions

1. **Views as shells filled by Import Changes, or Fenolite writing the board copy?** Recommended: shells (Decision 4). The copy is most of a document's bytes and would need its own measurement and kit. FP4 decides.
2. **Default of `--altium-draftsman`?** Recommended: `off` in 0.5.0, so builds keep their bytes and the document stays opt-in while experimental. Turn it on by default after a second kit run on another board.
3. **Gate as a constant rather than a build option?** Recommended: a constant flipped once by the kit, as c0168 decided for cut-out regions. An option would let a user write an unconfirmed form.
4. **New keys in the drawing specification for Draftsman (BOM on or off, view scale, sheet template)?** Recommended: none in 0.5.0. The BOM table is always on the assembly sheets, the scale is 1:1 as in c0117, and the schema id stays `v0`.
5. **If no gate has passed by the 0.5.0 cut?** Recommended: ship route P in 0.5.0 (project parameters and the procedure, which are useful on their own) and the document in a 0.5.x release. Do not hold the release.
6. **Do-not-populate parts on the assembly sheets?** Recommended: report them with `altium.not-lowered` and draw them as fitted, because the Altium build writes no variant. Variants and their not-fitted display are a later change.
7. **Commit the public samples?** Recommended: no. Manifest rows `altium-third-party-pcbdwf-01` to `-04`, fetched, `embeddable = false`, as the other Altium rows.
