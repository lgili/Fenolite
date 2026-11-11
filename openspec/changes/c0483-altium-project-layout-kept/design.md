# Design: c0483-altium-project-layout-kept

## D1: The document list rides with the settings
`convert.schematic.drawing_of` reads the source project's documents (`read_project(...).documents`, in
file order) and appends `<stem>.PrjPcbStructure` when that file is beside the project.
`prjpcb.documents_text` writes them one per line: the project path with `/`, a tab, and the key of the
drawn sheet the document is (`drawn_read.ROOT_DOCUMENT`, `/`, for the root sheet), else nothing. The text
goes to field `DOCUMENTS` (`drawn_read.DOCUMENTS_FIELD`) of the key `project` in the root sheet's carrier,
beside `PRJPCB` (c0479), and travels the same way: KiCad sheets, the `schematic.toml` footer of an import.
`drawn._styling_fields` leaves it out of the fields a sheet is styled with.

`prjpcb.documents_of` reads the lines back and leaves out a path that is absolute, holds a drive, or has
an empty, `.` or `..` part: the carrier is text a user can edit, and the paths become file names.

## D2: Sheet names
`drawn.lower_drawn` names the file of each drawn sheet from the list (`_source_names`): a `.SchDoc` name
that Altium can hold, for a sheet written once or a channel sheet (one document by design). When two sheets
would hold the same name without case, both keep the names of c0470. A generated module sheet keeps its
name. The sheet symbols take the name through the existing `files` map, so the hierarchy is unchanged.

## D3: Carried bytes
`prjpcb.carried_kind` names the documents Fenolite does not model: every listed document but `.SchDoc`,
`.SchLib`, `.PcbLib` and the first `.PcbDoc`. `convert.schematic.carried_documents` reads them (through
`read.project.locate`, without case) with the `.PrjPcbStructure`, and the KiCad conversion adds them as
`altium-carried/<project path>` when it writes the source's drawing. `import --to python` keeps those files
in its output beside `design.py`, as it keeps the model folders (c0409). `build --target altium` of an
imported script copies `altium-carried/` beside the script into the folder of its KiCad build before the
conversion (c0480, D3).

## D4: Layout of the written project
After `lower.write_design`, `to_altium._source_layout` reads the carried bytes from
`<KiCad project>/altium-carried/` and calls `prjpcb.laid_out`:
- a written document whose name (without case) a source path ends with moves to that path;
- the written `<name>.PcbDoc`, when the source's first PCB document has another name, takes its place and
  folder; the PCB document's bytes depend on its file name, so it is not renamed;
- a carried document is added at its path, unless a written one holds it; `.PrjPcbStructure` is written as
  `<name>.PrjPcbStructure` and not listed;
- `prjpcb.relisted` rewrites the `Document<n>` sections in the source's order (each keeping the keys the
  writer gave it, such as the class generation keys), then the written documents the source lacks in
  written order, numbered from 1 where the first document section stood. The encoding rule of the writer
  holds.

The read-back of the conversion follows the PCB document to its folder, and the schematic verification
lists the sheets at their paths (`relisted` on the project it writes).

Without a document list (a KiCad source, a source without sheets), the files keep their bytes.
