# Altium output job (`.OutJob`)

This page states, in Fenolite's own words, what the output-job reader
`fenolite.backends.altium.read.outjob` (change c0042) relies on. The sources are Altium's public
documentation (S-0293) and three public output jobs saved by Altium Designer (S-0187, S-0297, S-0299;
corpus rows `altium-third-party-outjob-01` to `-03`), fetched to the corpus cache and never committed.
No parser code of another project was read. The reader lists the outputs of a job; it runs none.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| An output job is an ASCII file of the project that holds the outputs to generate, the output containers (media) they go to, and hard copy settings; each output names its source document, its variant and whether it is enabled for a container | S-0293 | INFERRED | H-A-RD-PRJ-OUTJOB |
| A saved output job is INI text with LF line ends, 7-bit ASCII without a byte-order mark, and ends with an empty line | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-INI |
| It holds the sections `[OutputJobFile]`, `[OutputGroup1]`, `[PublishSettings]` and `[GeneratedFilesSettings]`; the order of the sections differs between files | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| `[OutputJobFile]` holds `Version=1.0` | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| Newer files add to `[OutputJobFile]` a caption, a description and vault keys | S-0187, S-0299 | INFERRED | H-A-RD-PRJ-OUTJOB |
| A group section holds `Name`, `Description`, `TargetOutputMedium`, `VariantName`, `VariantScope`, `CurrentConfigurationName`, `TargetPrinter` and `PrinterOptions` | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| A container (medium) `j` of a group is the key `OutputMedium<j>` (its name) with `OutputMedium<j>_Type` (`Printer`, `Publish`, `GeneratedFiles` or `Multimedia` in the files read); a printer adds `OutputMedium<j>_Printer` and `OutputMedium<j>_PrinterOptions` | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| An output `i` of a group is the set of keys `OutputType<i>`, `OutputName<i>`, `OutputCategory<i>`, `OutputDocumentPath<i>`, `OutputVariantName<i>`, `OutputEnabled<i>` and `OutputDefault<i>`, numbered from 1; outputs can add `PageOptions<i>` and `Configuration<i>_Name<k>` / `Configuration<i>_Item<k>` | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| `OutputEnabled<i>_OutputMedium<j>` is written for every output `i` and every container `j` of the group; it is `0` for most pairs and `1`, `2` or `3` for the others | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| That a value of `OutputEnabled<i>_OutputMedium<j>` other than `0` means the output is sent to that container is inferred from the documentation's enabled state per container | S-0293 | INFERRED | H-A-RD-PRJ-OUTJOB |
| `[PublishSettings]` and `[GeneratedFilesSettings]` hold one numbered set of keys per container (paths, file names, open and reload options) | S-0187, S-0297, S-0299 | INFERRED | H-A-RD-PRJ-OUTJOB |

## Fenolite's choices

- `OutJobFile.to_bytes()` gives the input back. The section `OutputJobFile` is required: without it the
  data is not an output job and `FormatError` is raised.
- An output is listed for each index `i` that has any of the six keys `OutputType<i>`, `OutputName<i>`,
  `OutputCategory<i>`, `OutputDocumentPath<i>`, `OutputVariantName<i>` or `OutputEnabled<i>`, in
  ascending `i`. One without `OutputType<i>` is still listed, with an empty type and the warning
  `altium.outjob.output-incomplete`.
- `enabled` is true only for `OutputEnabled<i>=1`; `enabled_media` holds each `j` whose
  `OutputEnabled<i>_OutputMedium<j>` is not `0`.
- `[PublishSettings]`, `[GeneratedFilesSettings]`, `PageOptions<i>`, `Configuration<i>_…` and every
  other key stay in `OutJobFile.ini` and are not typed.

## Outputs and containers as saved (change c0087)

What the output-job writer `fenolite.backends.altium.outjob` (change c0087) relies on, read with
`read_outjob` from the three public rows on 2026-10-06. Names of keys, of output types and of categories
are recorded; no path, printer name or column list of a row is.

| fact | source | label | hypothesis |
|---|---|---|---|
| Every section, the last one included, is followed by one empty line | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-06; 3 rows, 3 repositories) | H-A-OUTJOB-READBACK |
| In a group, the keys of an output come in the order `OutputType<i>`, `OutputName<i>`, `OutputCategory<i>`, `OutputDocumentPath<i>`, `OutputVariantName<i>`, `OutputEnabled<i>`, then one `OutputEnabled<i>_OutputMedium<j>` per container in ascending `j`; the group's own keys and the container keys come before the outputs | S-0187, S-0297, S-0299 | INFERRED | H-A-OUTJOB-OPEN |
| For each container, the values of `OutputEnabled<i>_OutputMedium<j>` that are not `0` are the numbers 1 to n, each once: the value is the position of the output among the outputs of that container | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-06; 3 rows, 3 repositories) | H-A-OUTJOB-OPEN |
| `OutputEnabled<i>` is `0` or `1` and does not follow the containers: in two rows most outputs that a container holds have `0` and one has `1`, and in the third every output has `1`. What Altium does with the value is not stated by a source | S-0187, S-0297, S-0299 | INFERRED | H-A-OUTJOB-OPEN |
| A Gerber output has the type `Gerber` and the category `Fabrication`; it is named `Gerber Files` in one row | S-0187, S-0299 | INFERRED | H-A-OUTJOB-OPEN |
| An NC drill output has the type `NC Drill` and the category `Fabrication`; it is named `NC Drill Files` in one row | S-0187, S-0299 | INFERRED | H-A-OUTJOB-OPEN |
| A pick-and-place output has the type `Pick Place`, the name `Pick and Place` and the category `Assembly` | S-0187 | INFERRED | H-A-OUTJOB-OPEN |
| A bill of materials has the type `BOM_PartType` and the category `Report`; it is named `Bill of Materials` in one row | S-0187, S-0297 | INFERRED | H-A-OUTJOB-OPEN |
| A schematic print has the type `Schematic Print` and the category `Documentation`; it is named `Schematic Prints` in one row | S-0187, S-0297 | INFERRED | H-A-OUTJOB-OPEN |
| A PCB print has the type `PCB Print` and the category `Documentation`; it is named `PCB Prints` in one row | S-0297, S-0299 | INFERRED | H-A-OUTJOB-OPEN |
| No row holds an output type for an assembly drawing: the two outputs named as drawings have the type `PCBDrawing` and name a drawing document of their own | S-0187, S-0299 | INFERRED | H-A-OUTJOB-OPEN |
| `OutputDocumentPath<i>` is empty for most outputs; it is the bare file name of a PCB document for one PCB print, and a bracketed name for one schematic print and one bill of materials. That an empty path leaves the choice of the document to the project is inferred from the documentation's source-document setting | S-0187, S-0293, S-0297 | INFERRED | H-A-OUTJOB-OPEN |
| A container of the type `Publish` is named as a PDF in every row, and one of the type `GeneratedFiles` as a folder or a set of files: the two types are the PDF container and the folder-structure container of the documentation | S-0187, S-0293, S-0297, S-0299 | INFERRED | H-A-OUTJOB-RUN |
| A group's `Name` is the job's file name in two rows and empty in one; its `VariantName` is `[No Variations]` in two rows; an output's `OutputVariantName<i>` is empty for all but one output | S-0187, S-0297, S-0299 | INFERRED | H-A-OUTJOB-OPEN |
| The settings of an output are `Configuration<i>_Name<k>` / `Configuration<i>_Item<k>` pairs whose item is a record of `Key=Value` fields joined by a vertical bar. The Gerber record holds a unit, a zero mode and the plotted layers, the NC drill record a unit, digit counts, a zero mode and an origin, the pick-and-place record a unit and the file formats. No source says what Altium does with a record that holds some of its fields only | S-0187, S-0297 | INFERRED | H-A-OUTJOB-OPTIONS |

## The writer's choices (change c0087)

- The writer writes `Version=1.0`, and per group `Name`, `Description`, `VariantName`, the container keys
  `OutputMedium<j>` and `OutputMedium<j>_Type`, and per output the six keys of the reader and one
  `OutputEnabled<i>_OutputMedium<j>` per container, in the order of the saved files. It writes no other
  key: `TargetOutputMedium`, `VariantScope`, `CurrentConfigurationName`, the printer keys,
  `OutputDefault<i>`, `PageOptions<i>` and the keys of `[PublishSettings]` and `[GeneratedFilesSettings]`
  have no recorded meaning. The two sections are written empty, because every saved file holds them.
- **No output setting is written.** A configuration record with some of its fields is a guess about what
  the missing fields become (a Gerber record without its layer list could plot nothing), so the writer
  writes no `Configuration<i>_…` key and every output keeps Altium's defaults. `outjob.MAPPED_OPTIONS` is
  empty, and the build lists the options a preset sets in `result.outjob.defaults`
  (`H-A-OUTJOB-OPTIONS` stays open).
- `OutputEnabled<i>` is written `1` for an output that a container holds and `0` otherwise, which is the
  reader's `enabled`.
- The job of a build has the containers `fab` (`GeneratedFiles`) and `doc` (`Publish`). Gerber, NC drill
  and pick and place name `<name>.PcbDoc`; the bill of materials and the schematic print have an empty
  document path; the sixth output is a PCB print of `<name>.PcbDoc`, since no public file gives the type
  of an assembly drawing.
- Whether Altium opens such a job, lists the outputs and generates them is not known until Part O of
  `docs/evidence/altium-schematic.md` is reported.
