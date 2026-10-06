## Why

The Altium import reads a repeated sheet once. A sheet symbol whose designator is a `Repeat(…)` statement stands for several channels of one child sheet, and Altium gives each channel's components their own designators on the board. Fenolite reports `altium.import.repeated-sheet` and keeps the designators that the child sheet holds, so every channel but one is missing from the circuit.

On the public project `altium-set:02` (`docs/evidence/altium-roundtrip.md`, 2026-10-05) this gives `model.duplicate-ref` in `model.validate`, 26 elements that only the schematic covers and 217 that only the PCB document covers in `netlist.assignment_compare`. The page blames the missing pin-to-pad map for these counts; most of them are the channels that were never instantiated. The import is the read side of the second backend, but v0.4 cannot round-trip that project honestly while its circuit is wrong, so this change comes first and stands alone.

## What Changes

- **Channels of a repeated sheet.** The import instantiates a child sheet once per channel of a `Repeat(name, first, last)` sheet symbol, and once per sheet symbol that names the same file.
- **Channel designators.** Each component of a channel gets the designator Altium gives it. The source, in this order: the board's component of the same unique-id path (`project.link`), the project's annotation file, and the project's naming format applied to the channel index. The source used is reported.
- **Channel nets.** A net that is local to the child sheet becomes one net per channel; a repeated sheet entry `Repeat(NAME)` connects channel `i` to member `i` of the parent bus; a plain sheet entry is shared by all channels.
- **Annotation file.** `.Annotation` is read (today it is only classified), byte for byte like the other text files.
- **The pin-to-pad map of a footprint model**, when the sheet holds one, is applied to the elements of the assignment comparison, which the page already names as missing.
- **The evidence page is corrected**: the counts of `altium-set:02` are measured again and the note says what each cause contributes.

Size: 5.5 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-import`: ADDED "Repeated sheets as channels", "Channel designators", "Channel nets", "Pin-to-pad map of a footprint model"; these supersede the repeated-sheet clause of "Hierarchy as modules".
- `altium-project-reader`: ADDED "Annotation file read".
- `altium-verification`: ADDED "Repeated-sheet projects in the corpus run".

## Non-goals

- No writing of repeated sheets: `build --target altium` keeps one sheet per module (c0086 decides what the writer does with repeated modules).
- No multi-instance hierarchy in the model beyond what `Module` paths already carry (the roadmap has that in v0.5b): a channel is a module instance with its own path, nothing more.
- No reading of device sheets or of managed sheets.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- The channel count, the designators and the nets are `CORPUS-VERIFIED` on `altium-set:02` when the import's circuit agrees with the PCB document of the same project: the criterion of `H-A-IMP-RPT-BOARD`.
- The naming format without a board and without an annotation file is `INFERRED` (`H-A-IMP-RPT-FORMAT`) until the maintainer reports Part R.
- `adapter.IMPORT_EVIDENCE` keeps its level; the new rows are added to its hypotheses.

## Open decision for the maintainer

- **Question.** Does this change ship inside v0.4, or earlier as a v0.3 follow-up, since it repairs a read defect?
- **Default written here.** Inside v0.4, as its first change, with no dependency on any other v0.4 change, so it can be implemented and released before the rest.
- **Alternative.** A v0.3 follow-up released with v0.2/v0.3.
- **To switch.** Change the milestone cell of the roadmap row and of the `openspec/README.md` row; no requirement or task changes.

## Impact

- Changed: `backends/altium/adapter/{netlist,circuit,project,connectivity,pins}.py`, `backends/altium/read/project.py`; new `backends/altium/read/annotation.py`.
- Changed pages: `docs/altium.md` ("Hierarchy"), `docs/formats/altium/{connectivity,project}.md`, `docs/evidence/altium-roundtrip.md`.
- `altium.import.repeated-sheet` changes meaning: it is reported only for a repeat that cannot be instantiated (see the design).
- Depends on: c0043 (import), c0044 (check on Altium input); nothing of v0.4.
