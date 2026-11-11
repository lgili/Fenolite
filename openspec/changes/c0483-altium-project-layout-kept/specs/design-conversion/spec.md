# Delta for design-conversion

## ADDED Requirements

### Requirement: The source's project layout is kept
A conversion that goes from an Altium project with sheets through KiCad and back to Altium, and an import of
such a project to Python built with `--target altium`, SHALL write the project in the source's layout
(change c0483).
- The conversion to KiCad MUST carry the source project's document list in the root sheet's carrier, field
  `DOCUMENTS` of the key `project`, each schematic document with the key of its drawn sheet.
- It MUST write the bytes of every listed document but the schematic sheets, the libraries and the first
  PCB document, and the `.PrjPcbStructure` beside the project, under `altium-carried/` at their project
  paths. A path that leaves the project folder MUST NOT be carried or written.
- An import to Python MUST keep `altium-carried/` beside the script, and its Altium build MUST write the
  documents back as the conversion does.
- The Altium writer MUST name each drawn sheet written once with its source file name when that name is a
  valid `.SchDoc` name no other written sheet holds, and every sheet symbol pointing at it MUST name it so.
- The written documents MUST stand at the source's paths; the written PCB document MUST take the folder and
  the place of the source's first one; the carried documents MUST be written back unchanged; the project
  file MUST list them in the source's order, then the written documents the source lacks.
- A conversion without a carried document list MUST keep the files it wrote before.

#### Scenario: A round trip through KiCad keeps the project layout
- **GIVEN** an authored Altium project with its sheets in `SCH\`, its board in `PCB\`, a second PCB
  document, a Draftsman document, a harness definition file, an integrated library, an output job and a
  `.PrjPcbStructure`
- **WHEN** it is converted to KiCad and back with `--name rt`
- **THEN** `altium-carried/` of the KiCad project holds the six documents Fenolite does not model
- **AND** the written `rt.PrjPcb` lists the source's document paths in the source's order, with
  `PCB\rt.PcbDoc` in place of the source's board
- **AND** the sheets keep their source names, no `_drawn_` sheet is written, and every carried document
  and `rt.PrjPcbStructure` are byte-equal to the source's

#### Scenario: An import built for Altium keeps the project layout
- **GIVEN** the same project imported with `import --to python`
- **WHEN** the script is built with `build --target altium`
- **THEN** the written project has the same layout and carried bytes as the round trip

#### Scenario: Unsafe document paths are not carried
- **GIVEN** a carried document list with `../x.OutJob` and `C:/y.IntLib`
- **WHEN** it is read back
- **THEN** both paths are left out
