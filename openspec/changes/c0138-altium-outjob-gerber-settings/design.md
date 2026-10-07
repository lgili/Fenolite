## Context

- **The writer today.** `backends/altium/outjob.py` (change c0087) writes `Version`, the group keys, the containers and per output six keys and one `OutputEnabled<i>_OutputMedium<j>` per container. `MAPPED_OPTIONS` is empty; `from_preset(preset, *, name, disabled=())` ignores the preset; `unmapped(preset)` lists every option the preset sets, and the build shows them as `result.outjob.defaults`.
- **The reader today.** `read.outjob.read_outjob` types groups, containers and outputs; `Configuration<i>_…` keys stay in `OutJobFile.ini` and are not typed (living requirement "Output job read").
- **The finding.** `docs/evidence/altium-pcb.md`, "Returned folders of 2026-10-07": in Altium Designer 26 the written job produced five of its six kinds and no Gerber layer file, with no error. The rows `H-A-OUTJOB-RUN` and `H-A-OUTJOB-OPTIONS` of `docs/hypotheses.md` hold the observation and wait for the author's statement.
- **The public files.** Three public output jobs are corpus rows (`altium-third-party-outjob-01` to `-03`, sources S-0187, S-0297, S-0299), fetched to the corpus cache and never committed. `tests/corpus/test_altium_text.py` reads them with `read_outjob`.
- **The board.** `pcbdoc.PcbDocSpec.stack` (`libboard.StackSpec.copper`) holds the Altium ids of the copper layers from top to bottom: 1 the top, `k + 1` for Mid-Layer k, 39 onwards for internal planes, 32 the bottom. `pcbrecords.BOARD_LAYER_MAP` puts silkscreen, paste and solder mask on the ids 33 to 38, and `libboard.ENABLED_MECHANICAL` enables Mechanical 13 to 16 in every document (fabrication and courtyard drawings of both sides). `libboard.long_id` gives the long id of a numbered layer (`docs/formats/altium/pcb-library.md`, "Long layer ids").
- **The preset.** `exports/preset.py`, schema `fenolite.export-preset.v0`: `[gerbers]` holds `layers`, `precision` (5 or 6, no default: without it KiCad's own default applies) and nine switches. It holds no Gerber unit: KiCad's Gerber export has no unit option among the options of the preset.
- **Base of this proposal.** Branch `author-report-2`, commit `9845e020` (`origin/dev` `6f6227eb` and the docs commit that records the finding). `openspec list` there shows c0087 as implemented and not archived (10 of 12 tasks; its two open tasks are the author report and the full suite).

## Goals / Non-Goals

**Goals:**
- A written job produces the Gerber layer files of the board it stands beside.
- Every field of the record that is written has a fact row with a source, a label and a hypothesis, written before the code.
- The record is whole: the fields of the public files, in their order, with the doubled fields doubled.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Measured on 2026-10-07

Measured with two short scripts kept outside the repository, which read the three corpus files of the cache with `read_outjob` and split each `Configuration<i>_Item<k>` value at `|` and each field at its first `=`. No path, printer name, column list or file name of a row is recorded here.

### Where the record stands

In the three rows the keys of an output come in this order: the six keys of the reader, one `OutputEnabled<i>_OutputMedium<j>` per container, `OutputDefault<i>`, then `PageOptions<i>` for an output that prints, then the configuration keys `Configuration<i>_Name<k>` and `Configuration<i>_Item<k>`. `OutputDefault<i>` is `0` for all 24 outputs of the three files (12, 3 and 9), and in all 24 it stands directly after the output's last `OutputEnabled<i>_OutputMedium<j>`; it is followed by `PageOptions<i>` in 14 outputs and by `Configuration<i>_Name1` in 10. The Gerber output of rows 01 and 03 has one setting, named `OutputConfigurationParameter1`, an empty document path and an empty variant name; the item is printable 7-bit ASCII.

### The Gerber record

Row 01 holds 45 fields and row 03 holds 44. The first 44 have the same names in the same order in both, and that order is the order of the names by code point. 37 names are distinct; seven are written twice, one after the other, with equal values. Row 01 adds `DocumentPath` as its 45th field, outside the name order; its value is an absolute path of the machine that saved the job.

Of the 44 positions, 31 hold the same value in both rows (28 names) and 13 differ (9 names).

| # | field | row 01 | row 03 | Fenolite writes | rule |
|---|---|---|---|---|---|
| 1 | `AddToAllLayerClasses.Set` | one space | one space | one space | constant |
| 2 | `AddToAllPlots.Set` | the head, no entry | the head, no entry | the head, no entry | constant |
| 3 | `CentrePlots` | `False` | `False` | `False` | constant |
| 4 | `DrillDrawingSymbol` | `GraphicsSymbol` | `GraphicsSymbol` | `GraphicsSymbol` | constant |
| 5 | `DrillDrawingSymbolSize` | `200000` | `200000` | `200000` | constant |
| 6 | `EmbeddedApertures` | `True` | `True` | `True` | constant |
| 7 | `FilmBorderSize` | `10000000` | `10000000` | `10000000` | constant |
| 8 | `FilmXSize` | `200000000` | `200000000` | `200000000` | constant |
| 9 | `FilmYSize` | `160000000` | `160000000` | `160000000` | constant |
| 10 | `FlashAllFills` | `False` | `False` | `False` | constant |
| 11 | `FlashPadShapes` | `True` | `True` | `True` | constant |
| 12 | `G54OnApertureChange` | `False` | `False` | `False` | constant |
| 13, 14 | `GenerateDRCRulesFile` (twice) | `True` | `True` | `True`, twice | constant |
| 15 | `GenerateReliefShapes` | `True` | `True` | `True` | constant |
| 16, 17 | `GerberUnit` (twice) | `Metric` | `Imperial` | `Metric`, twice | choice (decision 3) |
| 18 | `IncludeUnconnectedMidLayerPads` | `False` | `False` | `False` | constant |
| 19 | `LayerClassesMirror.Set` | one space | one space | one space | constant |
| 20 | `LayerClassesPlot.Set` | four quoted class names | one space | one space | choice (decision 4) |
| 21 | `LeadingAndTrailingZeroesMode` | `SuppressLeadingZeroes` | `SuppressLeadingZeroes` | `SuppressLeadingZeroes` | constant |
| 22 | `MaxApertureSize` | `2500000` | `2500000` | `2500000` | constant |
| 23, 24 | `MinusApertureTolerance` (twice) | `39` | `50` | `39`, twice | choice (decision 4) |
| 25 | `Mirror.Set` | the head, no entry | the head, no entry | the head, no entry | constant |
| 26 | `MirrorDrillDrawingPlots` | `False` | `False` | `False` | constant |
| 27 | `MirrorDrillGuidePlots` | `False` | `False` | `False` | constant |
| 28 | `NoRegularPolygons` | `False` | `False` | `False` | constant |
| 29, 30 | `NumberOfDecimals` (twice) | `4` | `5` | the preset's `gerbers.precision`, else `4`; twice | from the preset (decision 3) |
| 31, 32 | `OptimizeChangeLocationCommands` (twice) | `True` | `True` | `True`, twice | constant |
| 33 | `OriginPosition` | `Relative` | `Relative` | `Relative` | constant |
| 34 | `Panelize` | `False` | `False` | `False` | constant |
| 35 | `Plot.Set` | the head and 22 entries | the head and 12 entries | the head and the board's layers | from the board (decision 2) |
| 36 | `PlotPositivePlaneLayers` | `False` | `False` | `False` | constant |
| 37 | `PlotUsedDrillDrawingLayerPairs` | `True` | `False` | `False` | choice (decision 4) |
| 38 | `PlotUsedDrillGuideLayerPairs` | `True` | `False` | `False` | choice (decision 4) |
| 39, 40 | `PlusApertureTolerance` (twice) | `39` | `50` | `39`, twice | choice (decision 4) |
| 41 | `Record` | `GerberView` | `GerberView` | `GerberView` | constant |
| 42 | `SoftwareArcs` | `True` | `False` | `False` | choice (decision 4) |
| 43, 44 | `Sorted` (twice) | `False` | `False` | `False`, twice | constant |
| 45 | `DocumentPath` | an absolute path | absent | not written | decision 5 |

"The head" is the text `SerializeLayerHash.Version~2,ClassName~TLayerToBoolean`.

### The layer list

`Plot.Set` is the head and then one `,<long layer id>~1` per plotted layer. No entry of either row holds a value other than `1`. With the long ids of `pcb-library.md`, both rows list their layers in one order:

| position | row 01 | row 03 |
|---|---|---|
| above the copper | Top Overlay, Top Paste, Top Solder | the same |
| copper, top to bottom | Top Layer, Mid-Layer 1, Mid-Layer 2, Bottom Layer | the same |
| below the copper | Bottom Solder, Bottom Paste, Bottom Overlay | the same |
| mechanical, ascending | 1, 3, 5, 6, 13, 14, 15, 31, 32 | 1, 2 |
| after the mechanical layers | Keep-Out Layer, Top Pad Master, Bottom Pad Master | none |

No entry names an internal plane, a drill layer or the board outline. Row 03 is a job of a template repository, kept beside no board.

### The other output kinds

Does a public job hold a record for its other outputs? Yes, for every output but one kind:

| output type | rows | settings of the output |
|---|---|---|
| `Gerber` | 01, 03 | one record, 45 and 44 fields |
| `NC Drill` | 01, 03 | one record, 13 and 12 fields (twelve names in name order; row 01 adds `DocumentPath`) |
| `Pick Place` | 01 | one record, 170 fields |
| `BOM_PartType` | 01, 02 | 10 and 6 named settings (general options, column and sort lists), and `PageOptions<i>` |
| `Schematic Print` | 01, 02 | one record, 20 and 18 fields, and `PageOptions<i>` |
| `PCB Print` | 02, 03 | 11 and 46 records (one per page and per layer of a page), `PageOptions<i>`, and in row 03 a preferences key |
| `Composite`, `PCB 3D Print`, `ExportSTEP`, `ComponentCrossReference`, `IPC2581`, `ODB`, `Board Stack Report`, `Copy Files` | 01, 03 | one or more records each |
| `PCBDrawing` | 01, 03 | no configuration key; `PageOptions<i>` only |

So Altium saves a record for nearly every output, and the job that Fenolite writes holds none. Of the records, this change adds the Gerber record only (decision 6); the key `OutputDefault<i>` it adds to every output (decision 7).

## Where the first analysis was wrong

The task that asked for this proposal carried a first analysis. Checked against the files:

- **"33 fields are equal in both."** 31 of the 44 positions are equal (28 names); 13 positions differ (9 names): the unit, the decimals, the two aperture tolerances, the two drill-plot switches, `SoftwareArcs`, `LayerClassesPlot.Set` and `Plot.Set`.
- **"Placed after the `OutputEnabled<i>_OutputMedium<j>` keys."** One key stands between: `OutputDefault<i>=0`, in every output of the three files. It is written (decision 7).
- **"Unit and decimals come from the export preset."** The preset has a Gerber precision and no Gerber unit. The unit is a stated choice (decision 3).
- **"The outline's layer."** The PCB writer puts the outline into the board record as the board's shape and draws it on no layer (`lens/altium_copper.py`: a graphic on `Edge.Cuts` is the outline and is not written as a graphic). There is no layer id to plot (unknown U5).
- **"Every sample that holds an `.OutJob`."** One committed file is a written job: `tests/data/altium/outjob/blink.OutJob`. The sample folders `blink`, `routed`, `board6` and the others hold no job, because the lens writes one only when asked. `tests/data/altium/read/jobs.OutJob` is an authored fixture of the reader and is not written by the writer.
- Confirmed as stated: 44 fields in the same order, 37 names, the seven doubled names, `DocumentPath` as the 45th field of row 01, the setting's name, the head of the three layer sets, `Mirror.Set` and `AddToAllPlots.Set` without an entry.

## Decisions

1. **The record is the 44 fields of the table above, in that order, joined by `|`, each as `Name=Value`.** It is written as `Configuration<i>_Name1=OutputConfigurationParameter1` and `Configuration<i>_Item1=<record>` after `OutputDefault<i>` of the Gerber output. The seven doubled names are written twice, one after the other, with the same value, as both files have them; their rows say so. `outjob.GERBER_FIELDS` is the table: 44 entries of name and rule, and a unit test compares it with the page.
   - *Rejected: each name once (37 fields).* No file shows a record of 37 fields. Whether Altium needs the second copy is not known, and writing what the files hold costs nothing.
   - *Rejected: only the fields whose meaning a source states.* That is the partial record that c0087 refused, and the coordinator's decision forbids it.
2. **`Plot.Set` comes from the board: `outjob.plot_layers(copper)`.** The entries, in the order of the public files: Top Overlay, Top Paste, Top Solder; the copper layers of `copper` from top to bottom, each by `libboard.long_id` (a signal layer or an internal plane at its place in the stack); Bottom Solder, Bottom Paste, Bottom Overlay; then Mechanical 13, 14, 15 and 16, the layers that `libboard.ENABLED_MECHANICAL` enables in every written document. Every entry is `<long id>~1`. The six overlay, paste and solder layers are always listed: every board has them, and both public files list all six.
   - A plane has no entry in either public file. Its long id is a recorded fact; that it belongs at its place in the copper run is inferred from the order of the signal layers (unknown U4, its own hypothesis).
   - *Rejected: the layers that hold an object.* The record would depend on a walk over every item of the board, and a board whose bottom silkscreen is empty would lose a file that a fabricator's checklist expects. An empty plot is a smaller fault than a missing one.
   - *Rejected: the layers of the preset's `gerbers.layers`.* The key holds KiCad layer names; `Edge.Cuts` and the user layers have no Altium id here. The key stays in `result.outjob.defaults` ("Decisions (2026-10-07)", 2).
   - *Rejected: a fixed list with Mid-Layer 1 and 2, as both files hold.* What Altium does with the id of a layer the board lacks is unknown (U3); the board's own layers avoid the question.
3. **Unit and decimals.** `GerberUnit` is `Metric`: Fenolite's lengths are metric, KiCad's Gerber export has no unit option in the preset, and row 01 holds the value. `NumberOfDecimals` is the preset's `gerbers.precision` (5 or 6) when it is set, so that both targets are asked for the same number of decimals of a millimetre; without the key it is `4`, the value that row 01 holds beside `Metric`, as the KiCad export without the key takes KiCad's own default. `outjob.MAPPED_OPTIONS` becomes `{"gerbers.precision"}`.
   - `Metric` with `4` is the one pair a public file holds. `5` occurs beside `Imperial`; `6` occurs in no file. Whether Altium Designer 26 takes `5` or `6` beside `Metric` is unknown (U6) and has its own hypothesis and its own file in Part O.
   - *Rejected: `6` without a preset, to equal KiCad's default.* The file the maintainer opens first would then rest on a value that no public file holds. The default of this change is the observed pair; the preset is the way to ask for more.
   - *Rejected: refuse a preset precision until it is proved.* The user asked for it; the value is written, reported in `result.outjob.gerber`, and its row says what is not known.
4. **The six names that differ and are neither layers nor unit: the value of the row that fits what is written.**
   - `MinusApertureTolerance` and `PlusApertureTolerance`: `39`, the value of the metric row. The unit of the number is not stated by a source (U1).
   - `LayerClassesPlot.Set`: one space, the value of row 03. The layers are named one by one in `Plot.Set`; row 01 names four layer classes besides.
   - `PlotUsedDrillDrawingLayerPairs` and `PlotUsedDrillGuideLayerPairs`: `False`, the value of row 03. The change asks for no drill drawing and no drill guide (U7).
   - `SoftwareArcs`: `False`, the value of row 03. Altium's documentation names an option for software arcs (S-0605) and does not say which value of the field is which state.
   - *Rejected: all nine differing names from row 01.* Row 01 turns on the two drill plots and the layer classes, which are outside the change.
5. **`DocumentPath` is not written.** One of the two files holds it, outside the name order, and its value is an absolute path of the saving machine; a build writes no absolute path (requirement "Altium build outputs"). The output's own `OutputDocumentPath<i>` names the PCB document.
6. **No other output kind gains a record.** The other five kinds ran in Altium Designer 26 without one, and their public records are larger and less regular than the Gerber record (170 fields for pick and place; column lists for the bill of materials; one record per page for a print). A record for them would be a change of what works, on fewer public files. `write_outjob` refuses a setting on an output whose type is not `Gerber`.
7. **`OutputDefault<i>=0` is written on every output**, directly after the output's last `OutputEnabled<i>_OutputMedium<j>` (decided on 2026-10-07; the first form of this proposal left it out). All 24 outputs of the three public jobs hold the key with the value `0` at that place, and the three jobs come from three repositories: by the rule of the page the presence, the value and the place are `CORPUS-VERIFIED` (3 rows, 3 repositories). What Altium does with the value is not stated by a source: the meaning stays `INFERRED`. **This changes the bytes of every written job and of every output kind, not only Gerber**: NC drill, pick and place, the bill of materials and the two prints each gain the line. They ran without it in Altium Designer 26; that they still run with it is part of the successor of the run row, settled by step O3.
   - *Rejected: the key on the Gerber output only.* No file shows an output without it; a job in which one output has the key and five do not is a form that no saved file has.
8. **The writer refuses a record that is not whole.** `write_outjob` raises `ValueError` for an output of type `Gerber` without exactly one setting named `OutputConfigurationParameter1` whose field names are those of `GERBER_FIELDS` in order. A job without a Gerber output gains the `OutputDefault<i>` lines and nothing else.
9. **The reader types the settings.** `JobOutput` gains `settings: tuple[OutputSetting, ...]` (default empty), one `OutputSetting(index, name, item)` per `k` of `Configuration<i>_Name<k>` / `Configuration<i>_Item<k>`, and `read.outjob.record_fields(item)` gives the `(name, value)` pairs of a record in order, doubles kept. The reader judges nothing: a record with two fields is read as two fields. So `read_outjob(write_outjob(groups)).groups == groups` keeps holding with the record inside, and the corpus test reads the public records with the same function.
   - *Rejected: leave the reader and parse the INI view in the tests.* The proof of the written record would then be a second parser that lives in a test.
10. **The build passes the stack and reports the record.** `from_preset(preset, *, name, copper, disabled=())`; the lens passes `StackSpec.copper` of the document it writes. `result.outjob.gerber` holds `unit`, `decimals` and `layers` (each with `id` and `name`), between `outputs` and `defaults`, and `outline`, an object with `plotted` (`false`) and `reason` (the text `outjob.OUTLINE_REASON`): a reader of the build result sees that the set is not complete without opening Altium.
11. **Cut order.** Nothing of the record, the fact rows or the tests can be cut. The one thing that can be cut is the text and the files of the session step ("Author report: Part O"): without them the change still ships, and its rows stay `INFERRED` and pending.

## What the two files do not show

Each is a named unknown. The proposal claims none of them, and no fact row states one as a fact.

- **U1. The meaning of the fields that never vary.** 28 names hold one value in both files. Their names read like options of Altium's Gerber setup (S-0605), but no source ties a name to an option or gives the unit of a number (`FilmXSize`, `MaxApertureSize`, the tolerances). The rows record name, position and value, and say that the meaning is not stated.
- **U2. Whether Altium Designer 26 accepts a record that a third party wrote**, without `DocumentPath`, and in a job that holds no other key that Altium saves. Hypothesis `H-A-OUTJOB-GERBER-ACCEPT`.
- **U3. What Altium does with the id of a layer the board lacks.** Not tested: decision 2 writes the board's layers only.
- **U4. Where an internal plane stands in the list, and whether its entry plots it.** Hypothesis `H-A-OUTJOB-GERBER-PLANE`.
- **U5. The board outline.** Altium's setup lists a board outline as the first layer (S-0605). Neither public file holds an entry that the long-id rows do not explain, so how a saved job names the board shape among its plotted layers is unknown, and the written document draws the outline on no layer. The Gerber set of this change has no outline file ("Decisions (2026-10-07)", 1). Step O6 asks the maintainer what Altium offers for the board shape in the Gerber setup.
- **U6. Which decimals Altium takes beside `Metric`** other than 4. Hypothesis `H-A-OUTJOB-GERBER-DECIMALS`.
- **U7. Drill drawing, drill guide and pad master plots.** Row 01 turns the two drill switches on and lists the two pad masters; what files follow, and what the drill symbol fields do, is not shown.
- **U8. What a plotted layer without an object gives**: an empty file, or none.

## Files and public API

- `src/fenolite/backends/altium/read/outjob.py`: `OutputSetting`, `JobOutput.settings`, `record_fields`.
- `src/fenolite/backends/altium/outjob.py`: `GERBER_TYPE`, `SETTING_NAME`, `LAYER_SET_HEAD`, `GERBER_FIELDS`, `GERBER_UNIT`, `DEFAULT_DECIMALS`, `plot_layers(copper)`, `gerber_record(layers, *, decimals)`, `from_preset(preset, *, name, copper, disabled=())`, `MAPPED_OPTIONS`, `EVIDENCE`.
- `src/fenolite/lens/altium.py`: the call of `from_preset` with the stack, and `outjob_summary` with `gerber`.
- `src/fenolite/verify/kit/steps.py`: one tuple and nothing else. At the base, line 412 of the file reads `        ("H-A-OUTJOB-RUN",),` inside step K7.2 (lines 406 to 415); it becomes `        ("H-A-OUTJOB-RUN", "H-A-OUTJOB-RUN-2"),`. Change c0139 edits the same file for the kit's own defects; no other line of it belongs to this change.
- Tests: `tests/unit/backends/altium/test_outjob_write.py`, `tests/unit/backends/altium/read/test_outjob.py`, `tests/unit/lens/test_altium_outjob.py`, `tests/unit/cli/test_build_altium.py`, `tests/unit/test_format_facts.py` (only if the page's new table needs it), `tests/corpus/test_altium_text.py`.

## Sources registered by this change

- S-0605 (new, of the block S-0605 to S-0609): Altium's documentation page "Preparing Fabrication Data" (`https://www.altium.com/documentation/altium-designer/preparing-for-manufacture/output-jobs/fabrication-data`, read 2026-10-07, all rights reserved, read for facts): the Gerber setup has units of inches or millimetres, a precision drop-down, a list of layers with a plot switch per layer, a board outline as the first layer of that list, a command that selects the used layers, and options for software arcs, optimised location commands, a G54 command and a rules export file. Nothing is transcribed.
- S-0187 and S-0299 (registered): the two public jobs with a Gerber output; S-0297 (registered): the third job, for the other output kinds.
- S-0606 to S-0609 stay unused unless the fact task needs one.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-OUTJOB-GERBER-EMPTY | In Altium Designer 26 a Gerber output without a configuration record plots no layer: generating its container gives no layer file and no error | the author's statement of the outcome of 2026-10-07 with his minor version (no new run) | the statement names the version and the outcome; then the row takes the author-report level |
| H-A-OUTJOB-GERBER-RECORD | A saved Gerber output holds one setting named `OutputConfigurationParameter1` whose record is 44 fields in name order, seven of them twice, after the output's own keys | `tests/corpus/test_altium_text.py::test_gerber_records`; a third public job with a Gerber output, from a third repository, would raise the rows to `CORPUS-VERIFIED` | the names and their order equal `GERBER_FIELDS` in every public job with a Gerber output |
| H-A-OUTJOB-GERBER-READBACK | A written Gerber record is read by `read_outjob` and `record_fields` to the fields it was written from, and its constant fields equal those of the two public jobs | `tests/unit/backends/altium/test_outjob_write.py::test_gerber_readback`; `tests/corpus/test_altium_text.py::test_gerber_constants` | equal for the three stacks of the design; 31 positions equal in the written record and both public records |
| H-A-OUTJOB-GERBER-ACCEPT | Altium Designer 26 opens a job whose Gerber output holds the written record, without `DocumentPath`, and shows the written values in the setup of the output | author report, Part O of session 2, steps O1 and O5 | no message; units, format and plotted layers as the table sent. When refuted, the next candidate is the field `DocumentPath`, which one of the two public records holds |
| H-A-OUTJOB-GERBER-LAYERS | An entry `<long layer id>~1` of `Plot.Set` plots that layer, so the job produces one Gerber file per entry | author report, Part O of session 2, step O3 | the count of layer files equals the count of entries; the list of extensions is reported |
| H-A-OUTJOB-GERBER-PLANE | The long id of an internal plane, at its place among the copper layers of `Plot.Set`, plots the plane | author report, Part O of session 2, step O7 (the six-layer job) | a file for the plane is among those produced |
| H-A-OUTJOB-GERBER-DECIMALS | `GerberUnit=Metric` shows as millimetres, and `NumberOfDecimals` of 4, 5 and 6 as that many decimals | author report, Part O of session 2, steps O5 and O8 (the job of a preset with precision 6) | the setup shows millimetres and the decimals written; a value Altium replaces is reported |
| H-A-OUTJOB-RUN-2 | Generating the container `fab` of a job whose Gerber output holds the record produces Gerber layer files, drill, pick-and-place and bill-of-materials files, and the container `doc` a PDF of the schematic and of the board | author report, Part O of session 2, step O3 | both containers generate without an error; the kinds of files are those of the table |
| H-A-OUTJOB-OPTIONS-2 | An output without a configuration record takes Altium's defaults, which are usable for NC drill, pick and place, the bill of materials and the prints and plot no layer for Gerber; a Gerber output with the complete record takes the record's values | author report, Part O of session 2, steps O4 and O5 | the NC drill setup shows defaults; the Gerber setup shows the written values |

All start `INFERRED`. None is in `docs/hypotheses.md` or in another active change (checked on 2026-10-07 at the base).

**How the two rows of c0087 are restated.** `H-A-OUTJOB-RUN` and `H-A-OUTJOB-OPTIONS` were written for the job without settings. Their statements are not edited. The fact task registers the two successors above and appends to the result of each old row, after its text, that change c0138 restates it in the successor. An old row becomes `refuted; superseded by <successor>` only when the run that refuted it has a level: when the maintainer states the outcome of 2026-10-07 with his minor version, by the living rules "Refuted rows keep their id" and "Author-report rows". Until then both keep `INFERRED` and their recorded observation. The second half of the old options row (a record with only the mapped fields) is dropped from the successor: no file will ever test it, because the writer writes no partial record.

## Tests

- **Read-back.** `test_gerber_readback`: for the three stacks below, `read_outjob(write_outjob(from_preset(...)))` gives equal groups, and `record_fields` of the Gerber setting gives 44 fields whose names equal `GERBER_FIELDS`.
- **Constants against the public files** (corpus test, runs when the cache holds the rows): for rows 01 and 03, the names of the first 44 fields equal `GERBER_FIELDS`, and every field whose rule is `constant` holds in both rows the value Fenolite writes. The test also counts: 31 equal positions, and one job with `DocumentPath`.
- **The page and the table.** A unit test reads the field table of `output-job.md` and compares names, order and written values with `GERBER_FIELDS`.
- **Refusals.** A Gerber output without a setting, with two settings, with a missing field, with a field out of order, and a setting on an NC drill output: each raises `ValueError`.
- **Every output gains exactly one key.** An authored group with an NC drill output and a print, written by this writer and by the writer at the base commit: the two texts differ by one inserted line per output, `OutputDefault<i>=0` after the output's last `OutputEnabled<i>_OutputMedium<j>`, and by nothing else. For a job with a Gerber output the difference is those lines and the two configuration lines.
- **`OutputDefault<i>` in the public files** (corpus test): all 24 outputs of the three rows hold the key with the value `0`, directly after the last `OutputEnabled<i>_OutputMedium<j>` of the output.
- **Read-back keeps the key.** `read_outjob` of a written job gives equal groups, `to_bytes()` gives the written bytes, and the INI view holds `OutputDefault<i>` for every output.
- **`Plot.Set` of the three committed boards**, read from `tests/data/altium/{blink,routed,board6}/<name>.PcbDoc` with `read_pcbdoc` (`board.copper_chain`), layer by layer:

| # | two layers (`blink`, chain 1, 32) | four layers (`routed`, chain 1, 2, 3, 32) | six layers (`board6`, chain 1, 2, 39, 4, 5, 32) |
|---|---|---|---|
| 1 | 16973830 Top Overlay | 16973830 Top Overlay | 16973830 Top Overlay |
| 2 | 16973832 Top Paste | 16973832 Top Paste | 16973832 Top Paste |
| 3 | 16973834 Top Solder | 16973834 Top Solder | 16973834 Top Solder |
| 4 | 16777217 Top Layer | 16777217 Top Layer | 16777217 Top Layer |
| 5 | 16842751 Bottom Layer | 16777218 Mid-Layer 1 | 16777218 Mid-Layer 1 |
| 6 | 16973835 Bottom Solder | 16777219 Mid-Layer 2 | 16842753 Internal Plane 1 |
| 7 | 16973833 Bottom Paste | 16842751 Bottom Layer | 16777220 Mid-Layer 3 |
| 8 | 16973831 Bottom Overlay | 16973835 Bottom Solder | 16777221 Mid-Layer 4 |
| 9 | 16908301 Mechanical 13 | 16973833 Bottom Paste | 16842751 Bottom Layer |
| 10 | 16908302 Mechanical 14 | 16973831 Bottom Overlay | 16973835 Bottom Solder |
| 11 | 16908303 Mechanical 15 | 16908301 Mechanical 13 | 16973833 Bottom Paste |
| 12 | 16908304 Mechanical 16 | 16908302 Mechanical 14 | 16973831 Bottom Overlay |
| 13 | | 16908303 Mechanical 15 | 16908301 Mechanical 13 |
| 14 | | 16908304 Mechanical 16 | 16908302 Mechanical 14 |
| 15 | | | 16908303 Mechanical 15 |
| 16 | | | 16908304 Mechanical 16 |

  The first ten entries of the four-layer list are the first ten entries of both public files.
- **Golden bytes.** One committed file changes: `tests/data/altium/outjob/blink.OutJob` (each of its six outputs gains `OutputDefault<i>=0`, and the Gerber output the two configuration lines after it: eight new lines; its manifest note says so). No other tracked file under `tests/data/` changes: the sample folders hold no job, the lens goldens are built without one, and `tests/data/altium/read/jobs.OutJob` is read, not written. The closing task proves it with `git status --short tests/data`. Outside the repository, the job of every build with a PCB document changes, and so does `routed.OutJob` of a fresh `fenolite kit build`.
- **The build.** `result.outjob.gerber` of the routed blink, with `outline.plotted` false and its reason; `defaults` empty for a preset that sets only `gerbers.precision`; the exact key order of `result.outjob`.

## Author report: Part O, session 2 (Altium Designer 26)

The files are built at implementation into `~/fenolite-altium-checks/session-2/O-outjob/`, never into the repository: `blink_routed/` (two layers, no preset), `board6/` (six layers with a plane) and `blink_routed_p6/` (a preset with `gerbers.precision = 6`). Their SHA-256 and the table of expected layers go to Part O of `docs/evidence/altium-schematic.md`. The steps are written from Altium's documentation (S-0293, S-0605); a menu path or a dialog name may read differently in version 26.

1. O1: open `blink_routed.PrjPcb` and then `blink_routed.OutJob`. Expected: no message.
2. O3: generate the container `fab`. Expected: no error. Report the extensions of the files that appear in the Gerber folder, as a list, and whether the report of the Gerber output now names layers.
3. O5: open the setup of the Gerber output (double-click it, or right-click and Configure) and read three things: the units, the format or decimals, and which layers have their plot switch on. Expected: millimetres, 4 decimals, and the twelve layers of the table sent.
4. O6: in the same setup, look at what Altium offers for the board shape: whether the layer list holds an entry for the board outline (the documentation names one as the first entry), what it is called, and whether its plot switch is on. Report that. Then turn it on if it exists, close with OK, save the job under another name in the same folder and generate `fab` again; report whether an outline file is then produced and its extension.
5. O7: open `board6.OutJob` and generate `fab`. Report the extensions, and whether one file is the internal plane.
6. O8: open `blink_routed_p6.OutJob`, read units and decimals in the Gerber setup, generate `fab`. Report what the setup shows and whether files appear.

To send back: the Altium version as `AD <major>.<minor>`, the date, one outcome per step (`as expected`, or what differed in one sentence), and the three lists of extensions. The job saved in O6 stays in the session folder; it is read outside the repository with `read_outjob`, and what its `Plot.Set` holds beside the written entries is recorded as an observation on the facts page. No file that Altium wrote is committed, and an author report never moves an operation out of `experimental`.

Steps O2 and O4 of c0087's Part O (the list of outputs; the defaults of the NC drill setup) are unchanged and still open; they are not repeated here.

## Size (design-days)

| group | dd |
|---|---|
| entry check, fact rows, source and register rows | 0.5 |
| reader: settings and `record_fields` | 0.25 |
| writer: the record, the layers, the refusals | 0.5 |
| build: the stack, `result.outjob.gerber`, the kit step's row | 0.25 |
| corpus test, sample, golden bytes | 0.25 |
| Part O files and text, user pages | 0.25 |
| closing | 0.25 |

Total: 2.25. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-project-reader`, "Output job read": MODIFIED from the **living spec** (`openspec/specs/altium-project-reader/spec.md`; change c0042 is archived). The change: `JobOutput.settings` and `record_fields`.
- `altium-project-reader`, "Output job written": MODIFIED from the **delta of c0087** (`openspec/changes/c0087-altium-outjob-sheet/specs/altium-project-reader/spec.md`), which adds the requirement and is not archived.
- `altium-build`, "Output job in an Altium build": MODIFIED from the **delta of c0087** (`…/specs/altium-build/spec.md`). No other active change holds a delta of these three requirements (checked with `grep` over `openspec/changes` at the base). "Altium build outputs" is not modified: the signature of `build_altium` does not change.
- **Archive order:** c0087 first, then this change, both before c0092. If c0087 is archived before this change is implemented, the entry task re-reads the two texts from the living spec and says so.
- **Dependencies:** c0087 (writer), c0042 (reader), c0085 (stack). Nothing of c0121 to c0134 is needed.

## Risks / Trade-offs

- [Altium still plots nothing with the record] → step O6 leaves a job that Altium saved from the written one, which shows every key and field Altium adds; the one candidate known in advance is the field `DocumentPath`.
- [`OutputDefault<i>` stops an output that ran without it] → the key and its value are in every output of three saved jobs; step O3 generates all six kinds again and says so.
- [A value outside what Altium takes (`6` decimals)] → it is written only when the user's preset asks for it, it has its own row and its own file, and the default pair is one a public file holds.
- [Four mechanical plots that a fabricator does not want] → listed in `result.outjob.gerber.layers`; the user turns them off in the setup ("Decisions (2026-10-07)", 2).
- [Two public files are a thin base] → every row is `INFERRED` and says "two rows, two repositories"; nothing is labelled `CORPUS-VERIFIED`.
- [The reader's new field changes equality of read jobs] → it has a default, both sides of every existing comparison are read by the same reader, and `to_bytes()` is untouched.

## Migration Plan

- A build with a PCB document writes a different `<name>.OutJob`: one more line per output and the Gerber record. A job of an earlier build that stands in the output folder differs from the new one and is refused as an edited output by the rule of every planned file; the user deletes it or builds into a clean folder. The changelog says so.
- Rollback: `from_preset` without the record is c0087's writer; the reader's field is additive.

## Decisions (2026-10-07)

The first form of this proposal ended with four open decisions and their defaults. The coordinator decided them on the maintainer's behalf on 2026-10-07; the specs and the tasks follow these.

1. **Board outline: no outline Gerber in this change.** The written PCB document holds the outline as the board shape and on no layer, and no public file shows how a saved job names the board shape among its plotted layers, so there is nothing sourced to write. The limit is said in bold in the changelog line and in `docs/altium.md`, and the build reports it: `result.outjob.gerber.outline` is `{"plotted": false, "reason": <outjob.OUTLINE_REASON>}`. Step O6 of Part O asks the maintainer what Altium offers for the board shape in the Gerber setup.
   - **Out of scope, with its reason:** drawing the outline on a mechanical layer in the PCB writer. It would give the Gerber set an outline through an entry whose form is known, but it changes every written PCB document and every committed sample of one, and which layer to use should follow what session 2 shows. It is its own proposal after session 2.
2. **The three defaults stand.** Mechanical 13 to 16 are plotted, the four layers the writer enables; the KiCad export plots none of them (it plots copper, mask, paste, silkscreen and the edge), so the two targets differ here, and the user pages say so. The preset's `gerbers.layers` does not choose the plotted layers and stays in `result.outjob.defaults`. Without a preset the decimals are 4, the one pair a public file holds beside `Metric`; KiCad's own default applies on the other target.
3. **`OutputDefault<i>=0` is written on every output** (decision 7; the default of the first form, not written, is reversed). The requirement of the first form, that a job without a Gerber output keeps its bytes, is removed: it is no longer true. What is true replaces it: every output gains exactly that key, and a Gerber output gains its record besides. The committed job file changes; read-back keeps the key. The key is no longer a fallback of the acceptance row; the candidate that remains is the field `DocumentPath`.
4. **The kit's step table.** This change edits one hypothesis id, at step K7.2 ("Files and public API" gives the line as it stands at the base). Everything else in `verify/kit/steps.py` is change c0139's.
