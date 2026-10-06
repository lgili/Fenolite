## ADDED Requirements

### Requirement: Output job in an Altium build
`fenolite build --target altium` SHALL write `<name>.OutJob` from the export preset of the project (the default preset without one) when the build writes a PCB document, and SHALL list it in the project file it writes.
- `--altium-outjob on|off` (default `on`) MUST select it. An output job that exists and differs from the one the build would write MUST be refused as an edited output.
- When the project file exists and does not list the job, the build MUST report `altium.outjob-not-listed` (info) and MUST NOT rewrite the project file.
- `result.outjob` MUST hold the file name, the outputs with their kind and enabled state, and `defaults`: the preset options without a mapped key.

#### Scenario: Job beside the board
- **WHEN** the routed blink is built for Altium into an empty folder
- **THEN** `blink.OutJob` is written, `blink.PrjPcb` lists it, and `result.outjob.outputs` holds six entries

#### Scenario: Turned off
- **WHEN** the same build runs with `--altium-outjob off`
- **THEN** no output job is written and `result.outjob` is `null`

### Requirement: Drawing sheet in an Altium build
When the script names a drawing sheet with `design.sheet(drawing_sheet=…)`, `fenolite build --target altium` SHALL draw it on every schematic document it writes, with `schdot.sheet_records`, and SHALL write the title-block values of `design.title_block(…)` as document parameters.
- The paper and the orientation of the sheet record MUST follow the drawing sheet.
- A part of the drawing sheet that the Altium form cannot carry MUST give its `altium.sheet.*` code; a loss MUST need `--allow-lossy`.
- A script without a drawing sheet MUST give the schematic it gave before this change.

#### Scenario: Frame on the sheet
- **GIVEN** the blink script with `design.sheet("A4", drawing_sheet="frames/generic.sheet.toml")` and `design.title_block(title="Blink", revision="B")`
- **WHEN** it is built for Altium and the schematic is read back
- **THEN** `import_sheet` of the document gives the drawing sheet of the specification inside the written scope, and the document parameters hold `Title` = `Blink` and `Revision` = `B`
