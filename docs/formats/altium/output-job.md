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

## The Gerber settings record (change c0138)

What the Gerber record of the output-job writer relies on. Measured on 2026-10-07 with `read_outjob` and
`record_fields` on the three public rows; `tests/corpus/test_altium_text.py` (`test_output_default`,
`test_gerber_records`, `test_gerber_constants`) repeats the measurement on the corpus cache. Two of the three
public jobs hold a Gerber output (rows 01 and 03: S-0187, S-0299), so every row of the record is `INFERRED`:
two rows of two repositories. Altium's documentation of the Gerber setup (S-0605) names options; it ties no
option to a field name. No path, printer name, column list or file name of a row is recorded here.

**Amends the sections of change c0087 (2026-10-07).** The row "The settings of an output are …" of "Outputs
and containers as saved" described the Gerber record as a unit, a zero mode and the plotted layers: the
whole record is the table below. The choice "No output setting is written" holds since change c0138 for
every output kind but Gerber, whose output carries the complete record; and the key `OutputDefault<i>`,
which the list of keys that are not written names, is written on every output. The reason is the behaviour
row at the end of this section.

### Where the record stands

| fact | source | label | hypothesis |
|---|---|---|---|
| Every output `i` holds `OutputDefault<i>` with the value `0`, directly after its last `OutputEnabled<i>_OutputMedium<j>`: all 24 outputs of the three jobs (12, 3 and 9). It is followed by `PageOptions<i>` in 14 outputs and by `Configuration<i>_Name1` in 10 | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-07; 3 rows, 3 repositories, 24 outputs) | H-A-OUTJOB-GERBER-RECORD |
| What Altium does with the value of `OutputDefault<i>` is not stated by a source; the writer writes `0` because no saved output shows another value | S-0187, S-0293, S-0297, S-0299 | INFERRED | H-A-OUTJOB-GERBER-ACCEPT |
| A Gerber output holds one setting, after `OutputDefault<i>`: `Configuration<i>_Name1` with the value `OutputConfigurationParameter1` and `Configuration<i>_Item1` with the record. Its `OutputDocumentPath<i>` and `OutputVariantName<i>` are empty in both jobs, and the record is printable 7-bit ASCII | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| The record is `Name=Value` fields joined by a vertical bar. Its first 44 fields have the same names in the same order in both jobs, and that order is the order of the names by code point; 37 names are distinct, and seven are written twice, one after the other, with equal values. 31 positions (28 names) hold one value in both jobs; 13 positions (9 names) differ | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| One of the two jobs adds a 45th field, `DocumentPath`, outside the name order; its value is an absolute path of the machine that saved the job. The writer does not write it: a build writes no absolute path, and the output's own `OutputDocumentPath<i>` names the PCB document | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-ACCEPT |

### The fields of the record

One row per name, in the order of the record; a name that stands twice has one row that says so. "The head"
is the text `SerializeLayerHash.Version~2,ClassName~TLayerToBoolean`. The rule says where the written value
comes from: `constant` (both jobs hold it), `choice` (the two jobs differ and the writer takes the one that
fits what it writes), `unit`, `decimals`, `layers`. Every row has the sources S-0187 and S-0299 (and S-0605
where the documentation names an option that reads like the field), the label `INFERRED` and a hypothesis.
No source states what a field means or the unit of a number (unknown U1): the rows record name, position
and value.

| # | field | row 01 | row 03 | Fenolite writes | rule | source | label | hypothesis |
|---|---|---|---|---|---|---|---|---|
| 1 | `AddToAllLayerClasses.Set` | one space | one space | one space | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 2 | `AddToAllPlots.Set` | the head, no entry | the head, no entry | the head, no entry | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 3 | `CentrePlots` | `False` | `False` | `False` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 4 | `DrillDrawingSymbol` | `GraphicsSymbol` | `GraphicsSymbol` | `GraphicsSymbol` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 5 | `DrillDrawingSymbolSize` | `200000` | `200000` | `200000` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 6 | `EmbeddedApertures` | `True` | `True` | `True` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 7 | `FilmBorderSize` | `10000000` | `10000000` | `10000000` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 8 | `FilmXSize` | `200000000` | `200000000` | `200000000` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 9 | `FilmYSize` | `160000000` | `160000000` | `160000000` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 10 | `FlashAllFills` | `False` | `False` | `False` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 11 | `FlashPadShapes` | `True` | `True` | `True` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 12 | `G54OnApertureChange` | `False` | `False` | `False` | constant | S-0187, S-0299, S-0605 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 13, 14 | `GenerateDRCRulesFile` (written twice) | `True` | `True` | `True` | constant | S-0187, S-0299, S-0605 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 15 | `GenerateReliefShapes` | `True` | `True` | `True` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 16, 17 | `GerberUnit` (written twice) | `Metric` | `Imperial` | `Metric` | unit | S-0187, S-0299, S-0605 | INFERRED | H-A-OUTJOB-GERBER-DECIMALS |
| 18 | `IncludeUnconnectedMidLayerPads` | `False` | `False` | `False` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 19 | `LayerClassesMirror.Set` | one space | one space | one space | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 20 | `LayerClassesPlot.Set` | four quoted class names | one space | one space | choice | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 21 | `LeadingAndTrailingZeroesMode` | `SuppressLeadingZeroes` | `SuppressLeadingZeroes` | `SuppressLeadingZeroes` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 22 | `MaxApertureSize` | `2500000` | `2500000` | `2500000` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 23, 24 | `MinusApertureTolerance` (written twice) | `39` | `50` | `39` | choice | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 25 | `Mirror.Set` | the head, no entry | the head, no entry | the head, no entry | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 26 | `MirrorDrillDrawingPlots` | `False` | `False` | `False` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 27 | `MirrorDrillGuidePlots` | `False` | `False` | `False` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 28 | `NoRegularPolygons` | `False` | `False` | `False` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 29, 30 | `NumberOfDecimals` (written twice) | `4` | `5` | the decimals | decimals | S-0187, S-0299, S-0605 | INFERRED | H-A-OUTJOB-GERBER-DECIMALS |
| 31, 32 | `OptimizeChangeLocationCommands` (written twice) | `True` | `True` | `True` | constant | S-0187, S-0299, S-0605 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 33 | `OriginPosition` | `Relative` | `Relative` | `Relative` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 34 | `Panelize` | `False` | `False` | `False` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 35 | `Plot.Set` | the head and 22 entries | the head and 12 entries | the head and the board's layers | layers | S-0187, S-0299, S-0605 | INFERRED | H-A-OUTJOB-GERBER-LAYERS |
| 36 | `PlotPositivePlaneLayers` | `False` | `False` | `False` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 37 | `PlotUsedDrillDrawingLayerPairs` | `True` | `False` | `False` | choice | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 38 | `PlotUsedDrillGuideLayerPairs` | `True` | `False` | `False` | choice | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 39, 40 | `PlusApertureTolerance` (written twice) | `39` | `50` | `39` | choice | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 41 | `Record` | `GerberView` | `GerberView` | `GerberView` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 42 | `SoftwareArcs` | `True` | `False` | `False` | choice | S-0187, S-0299, S-0605 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| 43, 44 | `Sorted` (written twice) | `False` | `False` | `False` | constant | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |

How the values that are not constant are chosen:

- `GerberUnit` is `Metric`: Fenolite's lengths are metric, the export preset has no Gerber unit, and row 01
  holds the value.
- `NumberOfDecimals` is `gerbers.precision` of the export preset (5 or 6, the two values the preset allows)
  when the preset sets it, and `4` otherwise. `Metric` with `4` is the one pair a public job holds; `5` stands
  beside `Imperial`, and `6` in no public job. The writer writes what the preset asks for and clamps nothing;
  whether Altium takes `5` or `6` beside `Metric` is unknown U6, and the row is `INFERRED` for that reason too.
- `MinusApertureTolerance` and `PlusApertureTolerance` are `39`, the value of the metric row.
- `LayerClassesPlot.Set` is one space, `PlotUsedDrillDrawingLayerPairs` and `PlotUsedDrillGuideLayerPairs`
  are `False`, and `SoftwareArcs` is `False`, the values of row 03: the layers are named one by one in
  `Plot.Set`, and no drill drawing or drill guide is asked for. The documentation names an option for
  software arcs (S-0605) and does not say which value of the field is which state.

### The layer sets

| fact | source | label | hypothesis |
|---|---|---|---|
| `Plot.Set`, `Mirror.Set` and `AddToAllPlots.Set` start with the head `SerializeLayerHash.Version~2,ClassName~TLayerToBoolean`; `Mirror.Set` and `AddToAllPlots.Set` hold nothing else in both jobs | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-RECORD |
| `Plot.Set` holds after the head one entry `,<long layer id>~1` per plotted layer, the id in decimal as `pcb-library.md`, "Long layer ids", gives it; no entry of either job holds a value other than `1`. That an entry plots its layer is inferred from the documentation's plot switch per layer | S-0187, S-0299, S-0605 | INFERRED | H-A-OUTJOB-GERBER-LAYERS |
| Both jobs list their layers in one order: Top Overlay, Top Paste, Top Solder; the copper from top to bottom (Top Layer, Mid-Layer 1, Mid-Layer 2, Bottom Layer in both); Bottom Solder, Bottom Paste, Bottom Overlay; the mechanical layers in ascending number (1, 3, 5, 6, 13, 14, 15, 31, 32 in row 01; 1, 2 in row 03); then, in row 01 only, Keep-Out Layer, Top Pad Master and Bottom Pad Master. The first ten entries are equal in both | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-LAYERS |
| No entry of either job names an internal plane. The writer puts the long id of a plane at its place among the copper layers, from top to bottom; that this plots the plane is inferred from the order of the signal layers (unknown U4) | S-0187, S-0299 | INFERRED | H-A-OUTJOB-GERBER-PLANE |
| No entry of either job names a drill layer or the board outline: every entry is explained by the long-id rows. The documentation lists a board outline as the first layer of the setup's list (S-0605); how a saved job names it is not shown (unknown U5), and the writer writes no entry for it | S-0187, S-0299, S-0605 | INFERRED | H-A-OUTJOB-GERBER-LAYERS |

The writer's `Plot.Set` (`outjob.plot_layers`) holds the layers of the board and no other: Top Overlay, Top
Paste, Top Solder; the copper layers of the written document from top to bottom, a plane at its place;
Bottom Solder, Bottom Paste, Bottom Overlay; Mechanical 13, 14, 15 and 16, the four that every written
document enables. The six overlay, paste and solder layers are always listed. **The board outline is not
plotted** (`outjob.OUTLINE_REASON`).

### Behaviour without a record

| fact | source | label | hypothesis |
|---|---|---|---|
| In Altium Designer 26 a Gerber output without a configuration record plots no layer and gives no error: the job of change c0087 produced NC drill, pick and place, the bill of materials and the prints, and no Gerber layer file (`docs/evidence/altium-pcb.md`, "Returned folders of 2026-10-07"; the minor version is not stated) | S-0606 | INFERRED | H-A-OUTJOB-GERBER-EMPTY |

The label of this row rises to the author-report level only when the maintainer states the outcome with his
minor version (the register's rule on author-report rows). Until then it is an observation read from
returned files.

### Not known

- **U1.** The meaning of the fields that never vary, and the unit of their numbers (`FilmXSize`,
  `MaxApertureSize`, the tolerances).
- **U2.** Whether Altium Designer 26 accepts a record that a third party wrote, without `DocumentPath`, in
  a job that holds no other key that Altium saves.
- **U3.** What Altium does with the id of a layer the board lacks. Not tested: only the board's layers are
  written.
- **U4.** Where an internal plane stands in the list, and whether its entry plots it.
- **U5.** How a saved job names the board outline among its plotted layers. The Gerber set of a written job
  has no outline file.
- **U6.** Which decimals Altium takes beside `Metric` other than 4.
- **U7.** What the drill drawing, drill guide and pad master plots give, and what the drill symbol fields do.
- **U8.** What a plotted layer without an object gives: an empty file, or none.
