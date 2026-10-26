## MODIFIED Requirements

### Requirement: Edited Altium outputs are not overwritten
The Altium build SHALL apply the rule of the `design-dsl` requirement "Edited outputs are not overwritten" to every planned file outside `.fenolite/`: a file changed since Fenolite last wrote it is refused with `LayoutExistsError` (`FEN-7001`, exit 7, one `build.layout-exists` issue per file) unless `--discard-layout` is given, before the plan is returned.
- `<name>.PrjPcb` MUST be planned when it does not exist in `--out`, and in one more case (change c0138): the build writes an output job, the existing project file does not list it, and the SHA-256 of the existing file is the one that `.fenolite/build.json` of `--out` records for it, so that the file is as a build wrote it. The project file is then planned with the bytes that a build into an empty folder writes, it is replaced like every other planned file whose bytes the record names (a `.bak` is kept unless `--no-backup` is given), it MUST NOT be listed in `result.kept`, and none of the infos about a kept project file (`altium.project-kept`, `altium.schlib-not-in-project`, `altium.pcb-not-in-project`, `altium.sheets-not-in-project`, `altium.outjob-not-listed`) MUST be given. `cmd_build` MUST pass that digest to `build_altium` as `project_digest`, and `None` for a file whose digest the record does not hold.
- Every other existing project file MUST be kept, whatever its content and whatever `--discard-layout`, and MUST be listed in `result.kept` with the info `altium.project-kept`: one that was changed since a build wrote it, one in a folder without a record, one that lists the job, and every one of a build that writes no job.
- **The record of a kept project file.** `.fenolite/build.json` of the build MUST hold `<name>.PrjPcb` with its digest when the project file is kept and `project_digest` is given, that is when the bytes of the kept file are the ones the record of `--out` held before the build, and MUST NOT hold it for any other kept project file: one that was changed since a build wrote it, and one in a folder whose record did not hold it. So a rebuild that keeps an unchanged project file keeps it known as built, and no build records an edited file as built. The keys of the record's `files` stay sorted. A kept project file MUST NOT be in `result.files`, in the plan or in the receipt, whether the record holds it or not.
- **What a kept project file lacks.** `cmd_build` MUST read an existing project file with `read.project.read_project` and pass the document paths it lists to `build_altium` as `project_listed` (`lens.altium.kept_documents`: case-folded). With `project_listed`, each of `altium.schlib-not-in-project`, `altium.pcb-not-in-project`, `altium.sheets-not-in-project` and `altium.outjob-not-listed` MUST be given only when the kept file does not list a document of its kind that the build writes, and MUST name those documents alone; a kept file that lists them all gets `altium.project-kept` and none of the four. This takes precedence over the requirements that state the four infos for a kept project file. Without `project_listed` (`None`: a caller that did not read the file) every document is named, as those requirements say. A project file that cannot be read MUST be passed as `project_listed=None` with `project_unreadable=True`, and each of the infos MUST then carry the hint `lens.altium.UNREAD_PROJECT_HINT`.
- `--discard-layout` MUST replace an edited `<name>.SchDoc`, and the mutation protocol keeps a `.bak` of it unless `--no-backup` is given.

#### Scenario: Edited schematic refused
- **GIVEN** a confirmed sample build in `B` and one byte of `B/altium_sample.SchDoc` changed afterwards
- **WHEN** the Altium build runs again with `--confirm`, and then with `--dry-run`
- **THEN** both exit 7 with `FEN-7001`, the envelope's `issues` holds `build.layout-exists` naming `B/altium_sample.SchDoc`, and no file under `B` changes

#### Scenario: Discarding the edited schematic
- **GIVEN** the same edited schematic
- **WHEN** the Altium build runs with `--discard-layout --confirm`
- **THEN** the exit code is 0, `B/altium_sample.SchDoc` holds the planned bytes, and `B/altium_sample.SchDoc.bak` holds the edited bytes

#### Scenario: Project saved by Altium is kept
- **GIVEN** a confirmed sample build in `B` whose `B/altium_sample.PrjPcb` gets a line appended afterwards, as when a PCB document is added to the project
- **WHEN** the Altium build runs again with `--confirm`, and then with `--discard-layout --confirm`
- **THEN** both exit 0, `B/altium_sample.PrjPcb` keeps the appended line, `result.kept` lists `B/altium_sample.PrjPcb`, no planned write names it, and `issues` holds `altium.project-kept`

#### Scenario: Project file of an earlier build gains the job
- **GIVEN** a folder `B` built with `--altium-outjob off` from the routed blink, whose `B/blink.PrjPcb` does not list an output job and whose record holds its digest (the folder a build of 0.2.x leaves)
- **WHEN** the Altium build runs again with `--confirm` and the job
- **THEN** the exit code is 0, `B/blink.PrjPcb` has the bytes of a build into an empty folder and lists `blink.OutJob` after `blink.PcbDoc`, `B/blink.PrjPcb.bak` holds the earlier bytes, `result.files` names the project file, `result.kept` is empty, and `issues` holds neither `altium.project-kept` nor `altium.outjob-not-listed`

#### Scenario: Changed project file without the job is kept
- **GIVEN** the same folder with a line appended to `B/blink.PrjPcb`, and a second such folder whose `.fenolite` folder was deleted
- **WHEN** the Altium build runs with `--confirm`, and in the first folder also with `--discard-layout --confirm`
- **THEN** every run exits 0, the project file keeps its bytes, no `blink.PrjPcb.bak` is written, `result.kept` lists the project file, `issues` holds `altium.outjob-not-listed` with a hint that names deleting the project file, and the record that the build writes does not hold the project file

#### Scenario: Unchanged kept project file stays known
- **GIVEN** a folder `B` built twice with `--altium-outjob off` from the routed blink
- **WHEN** the record of `B` is read, and the build then runs with the job
- **THEN** the record holds `blink.PrjPcb` with the SHA-256 of the file although the second build kept it, the second build's `result.files` and receipt do not name it, and the third build writes the project file again with `blink.OutJob` listed and `B/blink.PrjPcb.bak`

#### Scenario: Kept project file that lists everything
- **GIVEN** an Altium build of the routed blink with `project_exists=True` and `project_listed` holding the schematic document, the PCB document, the output job and both libraries
- **WHEN** `build_altium` runs with the job
- **THEN** the infos about the kept project file are `altium.project-kept` alone; with the PCB document taken out of `project_listed` they are `altium.project-kept` and one `altium.pcb-not-in-project` that names `blink.PcbDoc` and not `blink.PcbLib`

### Requirement: Output job in an Altium build
`fenolite build --target altium` SHALL write `<name>.OutJob` with `backends.altium.outjob.write_outjob(from_preset(preset, name=<name>, copper=<stack>))` when the build writes a PCB document, where `<stack>` is `StackSpec.copper` of that document (the Altium ids of its copper layers from top to bottom), and SHALL list it in the project file it writes, as the document after the PCB document.
- `--altium-outjob on|off` (default `on`) MUST select it, and `--altium-outjob-preset FILE` MUST name the export preset (`fenolite.export-preset.v0`, the file that `fenolite export --preset` reads); without it the preset is the default one. Both options MUST be a usage error (exit 2, `FEN-2001`) with `--target kicad`, and `--altium-outjob-preset` MUST be one with `--altium-outjob off`. A preset that cannot be read or is malformed MUST fail as it does for `export`.
- A build that writes no PCB document MUST write no output job, and `result.outjob` MUST be `null`.
- The Gerber output of the job MUST carry the complete settings record ("Output job written"), with the plotted layers of the board that the build writes and the decimals of the preset. No other output of the job MUST carry a settings record. Every output of the job MUST carry `OutputDefault<i>=0` ("Output job written").
- An output job that exists and differs from the one the build would write MUST be handled by the rule of every other planned file: when the state of the output folder (`.fenolite/build.json`) records the digest of the job as it stands, the build MUST replace it and keep the old bytes as `<name>.OutJob.bak`; when the job was edited since the build that the state records, or the state is missing, the build MUST refuse it as an edited output (exit 7, `FEN-7001`, nothing written), and `--discard-layout` MUST replace it with the same backup. So a job that a build before change c0138 wrote is replaced by a rebuild into its folder, and refused only when it was edited or its state is lost.
- When the project file exists and does not list `<name>.OutJob`, the build MUST write the project file again with the job listed when the file is as a build wrote it ("Edited Altium outputs are not overwritten": `project_digest`), and otherwise MUST keep it and report `altium.outjob-not-listed` (info), with a hint that says how to get the job listed. A kept project file that lists the job MUST give no such issue.
- `result.outjob` MUST hold, in this order, `file` (under `--out`), `media` (name and type of each container), `outputs` (per output its `kind`, `type`, `name`, `category`, `document`, `enabled` and the name of its container, in the order of `OUTPUT_KINDS`), `gerber`, `defaults` and `preset` (`null`, or the file as given and its SHA-256).
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
- **THEN** `blink.PrjPcb` is written again and lists `blink.OutJob`, `blink.PrjPcb.bak` holds the earlier bytes, and `altium.outjob-not-listed` is not reported; with a line appended to the project file before the second build, `blink.PrjPcb` keeps its bytes and `altium.outjob-not-listed` is reported

#### Scenario: The job of an earlier build is replaced
- **GIVEN** an output folder that holds the `blink.OutJob` of a build before change c0138 and the state that records its digest
- **WHEN** the build runs into that folder
- **THEN** the exit code is 0, `blink.OutJob` holds the Gerber record, and `blink.OutJob.bak` holds the bytes of the earlier job

#### Scenario: A job without its state is refused
- **GIVEN** the same folder without its `.fenolite` folder
- **WHEN** the build runs into it
- **THEN** the exit code is 7 with `FEN-7001`, the error names `blink.OutJob` and no other file, its hint names `--discard-layout`, nothing is written, and the same build with `--discard-layout` replaces the job and writes `blink.OutJob.bak`

#### Scenario: The Gerber record of the built job
- **WHEN** the routed blink is built for Altium and `blink.OutJob` is read with `read_outjob`
- **THEN** the Gerber output holds one setting of 44 fields, no other output holds a setting, `result.outjob.gerber.unit` is `Metric`, `result.outjob.gerber.decimals` is 4, and `result.outjob.gerber.layers` names Top Overlay, Top Paste, Top Solder, Top Layer, Bottom Layer, Bottom Solder, Bottom Paste, Bottom Overlay and Mechanical 13 to 16, with the ids of the record's `Plot.Set` in the same order, and no entry of `layers` is an outline

#### Scenario: The preset's precision is carried
- **GIVEN** a preset file with `[gerbers]` `precision = 6`
- **WHEN** the build runs with `--altium-outjob-preset` naming it
- **THEN** `result.outjob.gerber.decimals` is 6 and `result.outjob.defaults` is empty

#### Scenario: The set holds no outline
- **WHEN** the routed blink is built for Altium with `--json`
- **THEN** `result.outjob.gerber.outline.plotted` is `false`, `result.outjob.gerber.outline.reason` is the text of `outjob.OUTLINE_REASON`, the keys of `result.outjob.gerber` are `unit`, `decimals`, `layers` and `outline`, in that order, and the keys of `result.outjob` are `file`, `media`, `outputs`, `gerber`, `defaults` and `preset`, in that order

#### Scenario: Only the job changes
- **WHEN** the routed blink is built for Altium at this change and at the commit before it
- **THEN** `blink.OutJob` differs by eight inserted lines, `OutputDefault<i>=0` for each of its six outputs and the two configuration lines of the Gerber output, and every other written file has equal bytes in both builds
