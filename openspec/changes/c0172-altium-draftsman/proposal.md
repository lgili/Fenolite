## Why

The maintainer will soon need Draftsman documents from Fenolite's Altium builds. Asked on 2026-10-16 to choose between PDF drawings and a native document, he chose "a real .PCBDwf document", for release 0.5.0.

Today Fenolite only recognises `.PCBDwf` in a project file (`backends/altium/read/project.py`, kind `draftsman`). KiCad boards get fabrication and assembly PDFs from a drawing specification (c0117). An Altium build gets an output job (c0087, c0138) and no drawing. `fenolite export` refuses Altium inputs.

What is public (design, "Context"):

- **Altium's documentation** (S-0772 to S-0781) gives the objects, not the bytes. A document belongs to a project and a PCB document. It is multi-sheet and holds views, tables, notes, dimensions and parameters. It is refreshed by Import Changes From `<name>.PcbDoc`. A document template (`.DwfDot`) is a "shell" into which a new document loads the project's current PCB data. An output job binds a document to a `PCBDrawing` output.
- **Four public samples** in two repositories already in the corpus (S-0785, MIT; S-0786, BSD-2-Clause). A first look, counts only, found an 8-byte header, then a .NET data-contract XML document (namespace `…/Altium.Designer.PcbDrawing.DataSerialization.V1`, S-0782) in a stream that looks compressed. Python's standard decompressors do not decode it.
- **Not public:** the stream's algorithm, the meaning of the header's second field, the element tree, and what Altium requires in it.

So the format must be measured before anything is written. Altium's code is never decompiled, its installed assemblies are never inspected and no third-party parser is read. The measurement uses the public samples and files that the maintainer saves in Altium Designer 26.5 from inputs authored for Fenolite. The change has hard stop rules and a documented fallback.

## What Changes

- **Facts first.** A new page `docs/formats/altium/draftsman.md` records every fact with a source and a label. Corpus rows are added for the four samples (fetched, never committed). The family `H-A-DWF-*` is registered.
- **Measure the container (gate G1).** Fenolite's reader must decode the four samples and the maintainer's observation files into well-formed XML, using only publicly specified algorithms. If it cannot within 2 design-days, the native writer stops and the fallback ships.
- **Reader.** `backends/altium/read/draftsman.py` decodes a document into its header and XML tree and gives a summary: sheets, views, tables and notes. The census of the samples feeds the fact rows.
- **Writer behind a gate.** `backends/altium/draftsman.py` writes a document from a `DraftsmanSpec`: sheets with a title block of parameter texts; a fabrication sheet with a drill drawing view, drill table, layer stack legend, board table and notes; assembly sheets for the top and the bottom with assembly views, a BOM table and notes. Views are written as a shell that Altium fills by Import Changes. `draftsman.NATIVE_WRITE` stays false until the maintainer's kit has opened a written document.
- **Driven by c0117's drawing specification.** The same `fenolite.drawing-spec.v0` file drives the document. Its paper, titles, tables, notes, assembly options and layout are reused, and the file's schema does not change.
- **Build.** The new option `build --target altium --altium-draftsman on` and `--drawing-spec FILE` plan `<name>.PCBDwf`. The document is listed in the project file and bound to a `PCBDrawing` output of the output job. The title-block values are written as project parameters. While the gate is off, an info names the reason and no document is planned.
- **Verification.** Own read-back of the written scope. The kit's Part F has three rounds: F0, observation files saved by the maintainer; FP, probe documents that decide the gates; F1 to F8, acceptance.
- **Fallback when a gate fails.** First a written document template `<name>.DwfDot` (the shell route of S-0774). If that is refused too, project parameters and a documented procedure (design, "Fallback"). The maintainer is told which route ships before the 0.5.0 cut.

Size: 10 design-days; cut order and stop rules in the design.

## Capabilities

### New Capabilities
- `altium-draftsman`: reading and writing Draftsman documents, their facts, the write gate and the content made from a drawing specification.

### Modified Capabilities
- `altium-build`: ADDED "Draftsman document in an Altium build", "Draftsman output in the output job", "Title-block parameters in the project file".
- `cli-contract`: ADDED "Draftsman options of the build command".
- `altium-verification`: ADDED "Kit cases for Draftsman documents", "Draftsman scope round trip".

## Non-goals

- Fenolite never runs Altium and never renders a Draftsman page. The PDF comes from Altium, through File » Export to PDF or the output job.
- The board snapshot inside a document (pads, polygons, component graphics) is not written. Views are shells that Altium fills. If Altium refuses that, writing the snapshot is a later change.
- Section, detail, isometric, realistic, region, component, counter-hole, via-type, harness and multi-board views. Callouts, datums, feature control frames, surface finish marks, and transmission-line and harness tables.
- Variants. Do-not-populate parts are reported, not drawn as not fitted (open question 6).
- Draftsman sheet templates (`.DwsDot`) as standalone files, and Workspace templates.
- Reading a document into the design model, and converting a document to or from KiCad.
- Anything taken from decompiled Altium code, its installed assemblies, a third-party Draftsman parser (one public project lists the extension; it is not read) or any employer or private project.

## Evidence level required

- Fact rows from the public pages: `INFERRED`. Container facts from the public samples: `CORPUS-VERIFIED` (2 repositories, 4 files). Facts from the maintainer's saved files: `ALTIUM-VERIFIED(author-report; AD 26.5; <date>)`.
- Written documents: `INFERRED` until Part F's probes and acceptance cases pass. No `ALTIUM-VERIFIED(kit)` before the kit runs, and `NATIVE_WRITE` stays false before that.

## Impact

- New: `backends/altium/read/draftsman.py`, `backends/altium/draftsman.py`, `lens/altium_draftsman.py`, `docs/formats/altium/draftsman.md`, `docs/evidence/altium-draftsman.md`, tests and corpus rows.
- Changed: `lens/altium.py`, `backends/altium/project.py`, `prjpcb.py`, `outjob.py`, `cli/cmd_build.py`, `PROVENANCE.md`, `docs/altium.md`, `docs/drawings.md`, the agent guide's `commands.md` and `altium.md`, `CHANGELOG.md`.
- A build without `--altium-draftsman on` writes the bytes it wrote before.
- Depends on c0087/c0138 (output job), c0117 (drawing specification and layout) and c0101 (stack-up). Nothing open blocks it.
