## ADDED Requirements

### Requirement: Output job written
`fenolite.backends.altium.outjob.write_outjob(groups)` SHALL return the bytes of an Altium output job that holds the given groups, media and outputs, in the form that `read_outjob` reads, and `read_outjob(write_outjob(groups)).groups` MUST equal `groups`.
- `OUTPUT_KINDS` MUST be the closed table of the output kinds the writer knows, in this order: `gerbers` (Gerber), `drill` (NC drill), `pos` (pick and place), `bom` (bill of materials), `schematic_print` and `pcb_print`, each with the type, name and category that `docs/formats/altium/output-job.md` records with a source and a label.
- Only keys recorded on that page MUST be written: `Version` of `[OutputJobFile]`; `Name`, `Description` and `VariantName` of a group; `OutputMedium<j>` and `OutputMedium<j>_Type`; and per output `OutputType<i>`, `OutputName<i>`, `OutputCategory<i>`, `OutputDocumentPath<i>`, `OutputVariantName<i>`, `OutputEnabled<i>` and one `OutputEnabled<i>_OutputMedium<j>` per container. No `Configuration<i>_…` key, no `PageOptions<i>` and no key of `[PublishSettings]` or `[GeneratedFilesSettings]` MUST be written; the two sections MUST be present and empty.
- `OutputEnabled<i>_OutputMedium<j>` MUST be `0` for a container the output is not sent to, and otherwise the position of the output among the outputs of that container, counted from 1 in output order.
- The text MUST be 7-bit ASCII without a byte-order mark, with LF line ends and one empty line after each section. A text that such a line cannot hold, an index that is not positive or is repeated, and a container an output names but the group does not hold MUST raise `ValueError`.
- `from_preset(preset, *, name, disabled=())` MUST return one group named `<name>.OutJob` with the variant name `[No Variations]`, the container `fab` of type `GeneratedFiles` and the container `doc` of type `Publish`, and one output per kind of `OUTPUT_KINDS`: `gerbers`, `drill` and `pos` bound to `<name>.PcbDoc` and sent to `fab`, `bom` bound to the project (an empty document path) and sent to `fab`, `schematic_print` bound to the project and sent to `doc`, `pcb_print` bound to `<name>.PcbDoc` and sent to `doc`. A kind of `disabled` MUST be present with `enabled` false and no container; an unknown kind MUST raise `ValueError`.
- `unmapped(preset)` MUST return, sorted, `table.key` for every option the preset sets, since the writer maps no option of the preset to a key (`MAPPED_OPTIONS` is empty).
- The module MUST declare `EVIDENCE` as `INFERRED` with `H-A-OUTJOB-READBACK`, `H-A-OUTJOB-OPEN` and `H-A-OUTJOB-RUN`.

#### Scenario: Default preset
- **WHEN** `write_outjob(from_preset(Preset(), name="blink"))` is read back
- **THEN** one group with two media and six outputs is read, equal to the groups written, and the Gerber output is bound to `blink.PcbDoc` and enabled for the folder medium

#### Scenario: A disabled kind
- **WHEN** the job of `from_preset(Preset(), name="blink", disabled=("pos",))` is written and read back
- **THEN** the pick-and-place output is listed with `enabled` false and no container, and the bill of materials is the third output of the folder medium: the file holds `OutputEnabled4_OutputMedium1=3`

#### Scenario: Text that a line cannot hold
- **WHEN** `write_outjob` is given a group whose name holds a line feed
- **THEN** `ValueError` is raised
