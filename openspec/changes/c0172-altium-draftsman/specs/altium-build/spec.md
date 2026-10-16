## ADDED Requirements

### Requirement: Draftsman document in an Altium build
With `--altium-draftsman on`, a written PCB document and `draftsman.NATIVE_WRITE` true, the Altium build SHALL plan `<name>.PCBDwf` (kind `altium_draftsman`), listed in the project file after the output job, and fill `result.draftsman`. Otherwise it MUST plan none and give `altium.draftsman-not-written` (info) naming the reason; with `off` every file keeps its bytes.

#### Scenario: Gate off
- **GIVEN** `NATIVE_WRITE` false
- **WHEN** the routed blink is built with `--target altium --altium-draftsman on --dry-run --json`
- **THEN** the exit code is 0, no `.PCBDwf` is planned, `result.draftsman` is `null`, and `issues` holds `altium.draftsman-not-written` naming the gate

#### Scenario: Document planned
- **GIVEN** `NATIVE_WRITE` set true in the test
- **WHEN** the same build runs
- **THEN** `B/blink.PCBDwf` is planned with the kind `altium_draftsman` and `B/blink.PrjPcb` lists it after `blink.OutJob`

### Requirement: Draftsman output in the output job
When the build writes `<name>.PCBDwf` and an output job, the job SHALL hold one more output of the type `PCBDrawing`, the category `Documentation` and the document path `<name>.PCBDwf`, enabled for the PDF container. A build without the document MUST write the job it wrote before.

#### Scenario: The job names the drawing
- **GIVEN** `NATIVE_WRITE` set true in the test
- **WHEN** the routed blink is built with `--altium-draftsman on` and `blink.OutJob` is read with `read_outjob`
- **THEN** it holds seven outputs, the last of the type `PCBDrawing` bound to `blink.PCBDwf` and enabled for the PDF container

### Requirement: Title-block parameters in the project file
When the build writes a Draftsman document, the project file it writes SHALL hold one `[Parameter<n>]` section with `Name` and `Value` per non-empty field of `design.title_block(...)`, in the order of its arguments. A build without the document MUST write the project file it wrote before.

#### Scenario: Title and revision
- **GIVEN** the routed blink with `design.title_block(title="Blink", revision="B")` and `NATIVE_WRITE` set true in the test
- **WHEN** it is built with `--altium-draftsman on` and `blink.PrjPcb` is read with the project reader
- **THEN** its parameters are `Title` = `Blink` and `Revision` = `B`, in that order
