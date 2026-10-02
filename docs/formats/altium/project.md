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
| The layout is INI-like: a line `[<section>]` starts a section, and `<key>=<value>` lines follow | S-0132, S-0143 | INFERRED | H-A-PRJ-OPEN |
| Each document is a numbered section `[Document1]`, `[Document2]`, … holding `DocumentPath=<path>`; readers take every section whose name starts with `Document` and tell document kinds by extension (`.SchDoc`, `.PcbDoc`, `.SchLib`, `.PcbLib`) | S-0132, S-0143 | INFERRED | H-A-PRJ-OPEN |
| `DocumentPath` is relative to the project folder: a bare file name names a document beside the project file | S-0132 | INFERRED | H-A-PRJ-OPEN |
| A project file has a `[Design]` section. That it holds `Version=1.0` and that its other keys and the per-document keys are optional is a hypothesis: no permitted source states it | S-0143 (the `[Design]` section); `Version` and the optional keys: no permitted source (S-0142 removed by the audit of 2026-10-02; S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) does not give it) | INFERRED | H-A-PRJ-OPEN |
| An open-source writer writes `[Design]` and `[DocumentN]` with CR LF line ends; no permitted source states the line end Altium writes | S-0143 | INFERRED | H-A-PRJ-OPEN |
| No permitted source says that Altium needs a UTF-8 byte-order mark; the file is read as plain 7-bit ASCII | no permitted source (S-0142 removed by the audit of 2026-10-02; S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) does not give it) | INFERRED | H-A-PRJ-OPEN |
| KiCad's developer page sketches one `[Design]` section with repeated `DocumentPath=` lines, a layout that KiCad's own project importer does not read; numbered `[DocumentN]` sections are used instead | S-0002, S-0132 | INFERRED | H-A-PRJ-OPEN |
| Altium rewrites the project file when the user adds a document, such as a new PCB document, and saves the project; keys it adds are expected | S-0134 | INFERRED | H-A-PRJ-KEEP |
| "Design » Update PCB Document" opens the engineering change order of a compiled project: "Validate Changes" fills its check column, "Execute Changes" its done column, and a change that cannot be made is marked with a red cross and a message | S-0141 | INFERRED | H-A-SCH-ECO |

## Fenolite's choices

- The written project file is exactly `[Design]`, `Version=1.0`, an empty line, `[Document1]` and
  `DocumentPath=<name>.SchDoc`, each line ending with CR LF, in 7-bit ASCII and without a byte-order
  mark.
- It is written once: an existing `<name>.PrjPcb` in the output folder is kept, because Altium rewrites
  it when the PCB document is added (capability `altium-build`, "Edited Altium outputs are not
  overwritten").
