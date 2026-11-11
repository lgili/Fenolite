# Proposal: c0483-altium-project-layout-kept

## Problem
An Altium project converted to KiCad and back (`convert --to kicad`, then `convert --to altium`), or
imported to Python and built for Altium (`import --to python`, then `build --target altium`, which since
c0480 goes through the same conversion writer), comes back with a layout of Fenolite's own:
- the drawn sheets are named `<name>.SchDoc` and `<name>_drawn_<id>.SchDoc`, not as the source names them;
- every document is written beside the project file, while the source lists them in folders (`SCH\…`,
  `PCB\…`, `LIB\…`);
- the documents Fenolite does not model are gone: output jobs, Draftsman documents, harness definition files
  that the drawing does not write, a second PCB document (`altium.import.extra-board`), integrated libraries,
  and the `.PrjPcbStructure` file beside the project. c0479 carries every section of the project file but
  the document list.

On the maintainer's board (private, codes and counts only) the source lists 22 documents; the projects
written by F2 and F5 list 14, the 8 sheets under other names, and none of the 11 listed documents
Fenolite does not model.

## Scope
- Carry the source's document list in the root sheet's `Fenolite.Altium.Sheet` carrier, beside the settings
  of c0479 (field `DOCUMENTS`), each schematic document with the key of its drawn sheet.
- Write each drawn sheet with its source file name, when it is written once and the name is a valid and
  unique `.SchDoc` name; the sheet symbols that point at it name it so.
- Carry the bytes of the documents Fenolite does not model, and the `.PrjPcbStructure`, in a folder
  `altium-carried/` beside the KiCad project (conversion) or the Python script (import), at their project
  paths. The Altium build of such a script hands the folder to its conversion.
- On the way back to Altium, write every document at its source path, add the carried documents, and list
  them in the project file in the source's order, then the written documents the source lacks.

Out of scope: a source document that is listed but missing on disk, or whose path leaves the project
folder, is not carried. A KiCad build of the script (`build` without `--target altium`) does not copy the
folder.
