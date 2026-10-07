## MODIFIED Requirements

### Requirement: Output job read
`fenolite.backends.altium.read.outjob.read_outjob(data, *, file="")` SHALL return an `OutJobFile(ini, version, groups, issues)` whose `to_bytes()` equals `data`.
- `version` MUST be the `Version` value of `[OutputJobFile]`. Data without that section MUST raise `FormatError`.
- `groups` MUST hold one `OutputGroup(index, name, description, variant_name, media, outputs)` per section `OutputGroup<n>`, in file order, from the keys `Name`, `Description` and `VariantName`.
- `media` MUST hold one `OutputMedium(index, name, type)` per key `OutputMedium<j>`, with `type` from `OutputMedium<j>_Type` (`""` when absent).
- `outputs` MUST hold one `JobOutput(index, type, name, category, document_path, variant_name, enabled, enabled_media, settings=())` per index `i` for which any of the keys `OutputType<i>`, `OutputName<i>`, `OutputCategory<i>`, `OutputDocumentPath<i>`, `OutputVariantName<i>` or `OutputEnabled<i>` exists, in ascending `i`. `enabled` is true only for the value `1`; `enabled_media` holds each `j` for which `OutputEnabled<i>_OutputMedium<j>` is not `0`.
- `settings` MUST hold one `OutputSetting(index, name, item)` per `k` for which `Configuration<i>_Name<k>` or `Configuration<i>_Item<k>` exists, in ascending `k`, with `name` and `item` the two values as they stand in the file (`""` for an absent one). An output without such a key MUST have `settings == ()`.
- `record_fields(item)` MUST return the fields of a settings record as `(name, value)` pairs in the order of the text: the text split at each `|`, each part split at its first `=`. A name that occurs twice MUST be returned twice, a value MUST keep its spaces, and a part without `=` MUST be returned with the value `""`. An empty text MUST give `()`. The function MUST NOT judge which fields a record holds.
- An index without `OutputType<i>` MUST add the warning `altium.outjob.output-incomplete` and MUST still be listed, with `type == ""`.
- The sections `PublishSettings`, `GeneratedFilesSettings` and any other, and the keys `PageOptions<i>` and `OutputDefault<i>`, MUST stay reachable through `ini` and MUST NOT be typed. The `Configuration<i>_…` keys MUST stay reachable through `ini` as well. The reader MUST NOT run an output.

#### Scenario: Outputs of one group
- **GIVEN** the authored fixture `tests/data/altium/read/jobs.OutJob` with one group, the media `Print Job` (`Printer`) and `PDF` (`Publish`), and two outputs: `Schematic Print` (category `Documentation`, enabled, medium 2 set to `1`) and `Gerber` (category `Fabrication`, `OutputEnabled2=0`)
- **WHEN** `read_outjob` is called
- **THEN** `groups[0].outputs` are `(1, "Schematic Print", …, enabled=True, enabled_media=(2,))` and `(2, "Gerber", …, enabled=False, enabled_media=())`, and `to_bytes()` equals the fixture

#### Scenario: Not an output job
- **GIVEN** the bytes of a project file
- **WHEN** `read_outjob` is called
- **THEN** `FormatError` is raised naming the missing section `OutputJobFile`

#### Scenario: Settings of an output
- **GIVEN** the same fixture, whose Gerber output holds `Configuration2_Name1=OutputConfigurationParameter1` and `Configuration2_Item1=Record=GerberView|Units=Imperial`, and whose print holds no configuration key
- **WHEN** `read_outjob` is called
- **THEN** the settings of the Gerber output are one `OutputSetting(1, "OutputConfigurationParameter1", "Record=GerberView|Units=Imperial")`, `record_fields` of its item is `(("Record", "GerberView"), ("Units", "Imperial"))`, and the settings of the print are `()`

#### Scenario: A field written twice
- **WHEN** `record_fields("A=1|A=1|B= |C")` is called
- **THEN** it returns `(("A", "1"), ("A", "1"), ("B", " "), ("C", ""))`

### Requirement: Output job written
`fenolite.backends.altium.outjob.write_outjob(groups)` SHALL return the bytes of an Altium output job that holds the given groups, media and outputs, in the form that `read_outjob` reads, and `read_outjob(write_outjob(groups)).groups` MUST equal `groups`.
- `OUTPUT_KINDS` MUST be the closed table of the output kinds the writer knows, in this order: `gerbers` (Gerber), `drill` (NC drill), `pos` (pick and place), `bom` (bill of materials), `schematic_print` and `pcb_print`, each with the type, name and category that `docs/formats/altium/output-job.md` records with a source and a label.
- Only keys recorded on that page MUST be written: `Version` of `[OutputJobFile]`; `Name`, `Description` and `VariantName` of a group; `OutputMedium<j>` and `OutputMedium<j>_Type`; per output `OutputType<i>`, `OutputName<i>`, `OutputCategory<i>`, `OutputDocumentPath<i>`, `OutputVariantName<i>`, `OutputEnabled<i>`, one `OutputEnabled<i>_OutputMedium<j>` per container and then `OutputDefault<i>`; and, for an output of the type `Gerber` only, `Configuration<i>_Name1` and `Configuration<i>_Item1` after `OutputDefault<i>`. No `PageOptions<i>` and no key of `[PublishSettings]` or `[GeneratedFilesSettings]` MUST be written; the two sections MUST be present and empty.
- **A Gerber output always carries the complete record.** `GERBER_FIELDS` MUST be the table of the 44 fields of the Gerber record in their order, with the rule of each (`constant` and its value, `layers`, `unit`, `decimals`), equal to the field table of `docs/formats/altium/output-job.md`; the seven names that a saved record holds twice MUST stand in it twice, one after the other. `write_outjob` MUST raise `ValueError` for an output of the type `Gerber` whose settings are not exactly one `OutputSetting(1, "OutputConfigurationParameter1", item)` with the field names of `record_fields(item)` equal to those of `GERBER_FIELDS` in order, and for a value that holds `|` or a character outside printable 7-bit ASCII. A record with a part of the fields MUST never be written, and `DocumentPath` MUST NOT be a field.
- **No other output kind carries a record.** `write_outjob` MUST raise `ValueError` for a setting on an output whose type is not `Gerber`.
- **Every output carries `OutputDefault<i>=0`**, directly after its last `OutputEnabled<i>_OutputMedium<j>`, whatever its type and whether it is enabled or not. Against the writer of change c0087, the text of a job MUST differ by exactly that one line per output and, for each output of the type `Gerber`, by its two configuration lines after it, and by nothing else. `read_outjob` of the written bytes MUST hold the key in its `ini` view for every output, and its `to_bytes()` MUST equal the written bytes.
- `gerber_record(layers, *, decimals)` MUST return the record: each `constant` field with its value, `GerberUnit` as `Metric` in both places, `NumberOfDecimals` as `decimals` in both places, `Mirror.Set` and `AddToAllPlots.Set` as the head `SerializeLayerHash.Version~2,ClassName~TLayerToBoolean`, and `Plot.Set` as that head followed by `,<long id>~1` for each layer of `layers` in the order given. `decimals` other than 4, 5 or 6, an empty `layers` and a repeated layer MUST raise `ValueError`.
- `plot_layers(copper)` MUST return the long ids of the plotted layers of a board whose copper layers have the Altium ids `copper`, from top to bottom: Top Overlay, Top Paste, Top Solder; each layer of `copper` by `libboard.long_id`, a signal layer and an internal plane alike; Bottom Solder, Bottom Paste, Bottom Overlay; then Mechanical 13, 14, 15 and 16 (`libboard.ENABLED_MECHANICAL`). A `copper` that `libboard.valid_stack` refuses MUST raise `ValueError`.
- `OutputEnabled<i>_OutputMedium<j>` MUST be `0` for a container the output is not sent to, and otherwise the position of the output among the outputs of that container, counted from 1 in output order.
- The text MUST be 7-bit ASCII without a byte-order mark, with LF line ends and one empty line after each section. A text that such a line cannot hold, an index that is not positive or is repeated, and a container an output names but the group does not hold MUST raise `ValueError`.
- `from_preset(preset, *, name, copper, disabled=())` MUST return one group named `<name>.OutJob` with the variant name `[No Variations]`, the container `fab` of type `GeneratedFiles` and the container `doc` of type `Publish`, and one output per kind of `OUTPUT_KINDS`: `gerbers`, `drill` and `pos` bound to `<name>.PcbDoc` and sent to `fab`, `bom` bound to the project (an empty document path) and sent to `fab`, `schematic_print` bound to the project and sent to `doc`, `pcb_print` bound to `<name>.PcbDoc` and sent to `doc`. The Gerber output MUST hold the setting of `gerber_record(plot_layers(copper), decimals=d)`, where `d` is the preset's `gerbers.precision` when the preset sets it and 4 otherwise, whether the kind is disabled or not. A kind of `disabled` MUST be present with `enabled` false and no container; an unknown kind MUST raise `ValueError`.
- `MAPPED_OPTIONS` MUST be `{"gerbers.precision"}`, and `unmapped(preset)` MUST return, sorted, `table.key` for every other option the preset sets.
- The module MUST declare `EVIDENCE` as `INFERRED` with `H-A-OUTJOB-READBACK`, `H-A-OUTJOB-OPEN`, `H-A-OUTJOB-RUN-2`, `H-A-OUTJOB-GERBER-RECORD`, `H-A-OUTJOB-GERBER-ACCEPT` and `H-A-OUTJOB-GERBER-LAYERS`.

#### Scenario: Default preset
- **WHEN** `write_outjob(from_preset(Preset(), name="blink", copper=(1, 32)))` is read back
- **THEN** one group with two media and six outputs is read, equal to the groups written, the Gerber output is bound to `blink.PcbDoc` and enabled for the folder medium, and it is the only output with a setting

#### Scenario: A disabled kind
- **WHEN** the job of `from_preset(Preset(), name="blink", copper=(1, 32), disabled=("pos",))` is written and read back
- **THEN** the pick-and-place output is listed with `enabled` false and no container, and the bill of materials is the third output of the folder medium: the file holds `OutputEnabled4_OutputMedium1=3`

#### Scenario: Text that a line cannot hold
- **WHEN** `write_outjob` is given a group whose name holds a line feed
- **THEN** `ValueError` is raised

#### Scenario: The record of a two-layer board
- **WHEN** the Gerber setting of `from_preset(Preset(), name="blink", copper=(1, 32))` is split with `record_fields`
- **THEN** it holds 44 fields with the names of `GERBER_FIELDS` in order, `GerberUnit` is `Metric` twice, `NumberOfDecimals` is `4` twice, and `Plot.Set` is the head followed by the twelve entries `16973830~1`, `16973832~1`, `16973834~1`, `16777217~1`, `16842751~1`, `16973835~1`, `16973833~1`, `16973831~1`, `16908301~1`, `16908302~1`, `16908303~1` and `16908304~1`

#### Scenario: A plane among the copper layers
- **WHEN** `plot_layers((1, 2, 39, 4, 5, 32))` is called
- **THEN** it returns sixteen ids whose fourth to ninth are `16777217`, `16777218`, `16842753`, `16777220`, `16777221` and `16842751`

#### Scenario: Decimals of the preset
- **GIVEN** a preset with `[gerbers]` `precision = 6` and `[drill]` `units = "in"`
- **WHEN** the job of `from_preset(preset, name="blink", copper=(1, 32))` is written
- **THEN** both `NumberOfDecimals` fields are `6`, and `unmapped(preset)` is `("drill.units",)`

#### Scenario: A partial record is refused
- **GIVEN** the groups of the default preset with the field `Plot.Set` removed from the Gerber record
- **WHEN** `write_outjob` is called
- **THEN** `ValueError` is raised, and so it is for a Gerber output without a setting and for a setting on the NC drill output

#### Scenario: One key per output
- **GIVEN** an authored group with one container, an NC drill output and a schematic print
- **WHEN** `write_outjob` is called
- **THEN** the text holds `OutputDefault1=0` directly after `OutputEnabled1_OutputMedium1` and `OutputDefault2=0` directly after `OutputEnabled2_OutputMedium1`, it holds no `Configuration` key, and without those two lines it has the SHA-256 that the test pins from the writer of change c0087

#### Scenario: The keys of the Gerber output
- **WHEN** the job of `from_preset(Preset(), name="blink", copper=(1, 32))` is written
- **THEN** the lines after `OutputEnabled1_OutputMedium2=0` are `OutputDefault1=0`, `Configuration1_Name1=OutputConfigurationParameter1` and the line of `Configuration1_Item1`, in that order, each of the six outputs holds its `OutputDefault<i>=0`, and `read_outjob` of the bytes gives the groups written and the same bytes back

#### Scenario: The key in the public jobs
- **GIVEN** the corpus rows `altium-third-party-outjob-01`, `-02` and `-03` in the cache
- **WHEN** each is read with `read_outjob`
- **THEN** all 24 outputs (12, 3 and 9) hold `OutputDefault<i>` with the value `0`, directly after the last `OutputEnabled<i>_OutputMedium<j>` of the output

#### Scenario: Constant fields equal the public jobs
- **GIVEN** the corpus rows `altium-third-party-outjob-01` and `altium-third-party-outjob-03` in the cache
- **WHEN** the record of each Gerber output is split with `record_fields`
- **THEN** the names of its first 44 fields equal those of `GERBER_FIELDS`, every field whose rule is `constant` holds the value that `GERBER_FIELDS` gives, at 31 positions, and only row 01 holds a 45th field
