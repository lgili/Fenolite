## MODIFIED Requirements

### Requirement: Output job in an Altium build
`fenolite build --target altium` SHALL write `<name>.OutJob` with `backends.altium.outjob.write_outjob(from_preset(preset, name=<name>, copper=<stack>))` when the build writes a PCB document, where `<stack>` is `StackSpec.copper` of that document (the Altium ids of its copper layers from top to bottom), and SHALL list it in the project file it writes, as the document after the PCB document.
- `--altium-outjob on|off` (default `on`) MUST select it, and `--altium-outjob-preset FILE` MUST name the export preset (`fenolite.export-preset.v0`, the file that `fenolite export --preset` reads); without it the preset is the default one. Both options MUST be a usage error (exit 2, `FEN-2001`) with `--target kicad`, and `--altium-outjob-preset` MUST be one with `--altium-outjob off`. A preset that cannot be read or is malformed MUST fail as it does for `export`.
- A build that writes no PCB document MUST write no output job, and `result.outjob` MUST be `null`.
- The Gerber output of the job MUST carry the complete settings record ("Output job written"), with the plotted layers of the board that the build writes and the decimals of the preset. No other output of the job MUST carry a settings record. Every output of the job MUST carry `OutputDefault<i>=0` ("Output job written").
- An output job that exists and differs from the one the build would write MUST be refused as an edited output, by the rule of every other planned file. This holds for a job that a build before change c0138 wrote.
- When the project file exists and does not list `<name>.OutJob`, the build MUST report `altium.outjob-not-listed` (info) and MUST NOT rewrite the project file. A kept project file that lists it MUST give no such issue.
- `result.outjob` MUST hold, in this order, `file` (under `--out`), `preset` (`null`, or the file as given and its SHA-256), `media` (name and type of each container), `outputs` (per output its `kind`, `type`, `name`, `category`, `document`, `enabled` and the name of its container, in the order of `OUTPUT_KINDS`), `gerber` and `defaults`.
- `result.outjob.gerber` MUST hold, in this order, `unit` (`"Metric"`), `decimals` (the integer written), `layers` and `outline`. `layers` MUST hold one object per entry of the record's `Plot.Set`, in its order, with `id` (the long layer id) and `name` (the layer's name as `pcbrecords.LAYER_NAMES` gives it).
- `result.outjob.gerber.outline` MUST be the object `{"plotted": false, "reason": outjob.OUTLINE_REASON}`, and `OUTLINE_REASON` MUST be the text `the PCB document holds the board outline as the board shape and on no layer, and no public source gives the entry of the board shape among the plotted layers; turn the outline on in the Gerber setup in Altium`. The Gerber set of the written job holds no plot of the board outline, and `docs/altium.md` MUST say so beside the description of the job.
- `result.outjob.defaults` MUST hold the options that the preset sets and the writer has no key for, as sorted `table.key` texts; `gerbers.precision` is not among them.
- With `--altium-outjob off`, and for every file other than `<name>.OutJob`, the bytes MUST be those of the build before change c0138.
- The evidence of a build with a job MUST name `H-A-OUTJOB-READBACK`, `H-A-OUTJOB-OPEN`, `H-A-OUTJOB-RUN-2`, `H-A-OUTJOB-GERBER-RECORD`, `H-A-OUTJOB-GERBER-ACCEPT` and `H-A-OUTJOB-GERBER-LAYERS`, and the level stays `INFERRED`.

#### Scenario: Job beside the board
- **WHEN** the routed blink is built for Altium into an empty folder
- **THEN** `blink.OutJob` is written, `blink.PrjPcb` lists it after `blink.PcbDoc`, `result.outjob.outputs` holds six entries, all enabled, and `result.outjob.defaults` is empty

#### Scenario: Turned off
- **WHEN** the same build runs with `--altium-outjob off`
- **THEN** no output job is written, `result.outjob` is `null`, and every other file holds the bytes it held before change c0087

#### Scenario: A preset names what the job does not set
- **GIVEN** a preset file with `[drill]` `units = "in"`
- **WHEN** the build runs with `--altium-outjob-preset` naming it
- **THEN** `result.outjob.defaults` is `["drill.units"]` and `result.outjob.preset.sha256` is the SHA-256 of the file

#### Scenario: Kept project file
- **GIVEN** a folder that holds the `blink.PrjPcb` of a build made with `--altium-outjob off`
- **WHEN** the build runs again with the job
- **THEN** `blink.PrjPcb` keeps its bytes and `altium.outjob-not-listed` is reported

#### Scenario: The Gerber record of the built job
- **WHEN** the routed blink is built for Altium and `blink.OutJob` is read with `read_outjob`
- **THEN** the Gerber output holds one setting of 44 fields, no other output holds a setting, `result.outjob.gerber.unit` is `Metric`, `result.outjob.gerber.decimals` is 4, and `result.outjob.gerber.layers` names Top Overlay, Top Paste, Top Solder, Top Layer, Bottom Layer, Bottom Solder, Bottom Paste, Bottom Overlay and Mechanical 13 to 16, with the ids of the record's `Plot.Set` in the same order, and no entry of `layers` is an outline

#### Scenario: The preset's precision is carried
- **GIVEN** a preset file with `[gerbers]` `precision = 6`
- **WHEN** the build runs with `--altium-outjob-preset` naming it
- **THEN** `result.outjob.gerber.decimals` is 6 and `result.outjob.defaults` is empty

#### Scenario: The set holds no outline
- **WHEN** the routed blink is built for Altium with `--json`
- **THEN** `result.outjob.gerber.outline.plotted` is `false`, `result.outjob.gerber.outline.reason` is the text of `outjob.OUTLINE_REASON`, and the keys of `result.outjob.gerber` are `unit`, `decimals`, `layers` and `outline`, in that order

#### Scenario: Only the job changes
- **WHEN** the routed blink is built for Altium at this change and at the commit before it
- **THEN** `blink.OutJob` differs by eight inserted lines, `OutputDefault<i>=0` for each of its six outputs and the two configuration lines of the Gerber output, and every other written file has equal bytes in both builds
