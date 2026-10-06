## ADDED Requirements

### Requirement: Output job written
`fenolite.backends.altium.outjob.write_outjob(groups)` SHALL return the bytes of an Altium output job that holds the given groups, media and outputs, in the form that `read_outjob` reads, and `read_outjob(write_outjob(groups))` MUST return equal groups.
- `OUTPUT_KINDS` MUST be the closed table of the output kinds the writer knows (Gerber, NC drill, pick and place, bill of materials, schematic print, assembly drawing), each with the type and category names that `docs/formats/altium/output-job.md` records with a source and a label.
- Only keys recorded on that page MUST be written. The text MUST use the encoding and line ends the page records.
- `from_preset(preset, *, name, layers)` MUST return one group with a folder medium and a PDF medium and one output per kind, enabled as the preset selects, each bound to its source document; a kind the preset disables MUST be present and disabled.

#### Scenario: Default preset
- **WHEN** `write_outjob(from_preset(DEFAULT, name="blink", layers=2))` is read back
- **THEN** one group with two media and six outputs is read, the Gerber output is bound to `blink.PcbDoc` and enabled for the folder medium

#### Scenario: A disabled kind
- **GIVEN** a preset that turns pick and place off
- **WHEN** the job is written and read back
- **THEN** the pick-and-place output is listed with `enabled` false
