# design-conversion Specification

## Purpose
How `fenolite convert` turns a project of one backend or KiCad major into another: the directions, the report of what is kept, changed or lost per kind and reason, the consent a lossy conversion needs, and the read-back of every conversion compared with its source through `equivalent` (created by c0159).
## Requirements
### Requirement: Conversion package
`fenolite.convert` SHALL provide `convert_project(source, *, to, kicad_version=10, allow_lossy=False, bodies="extruded", name=None) -> Conversion`. It MUST read the source project, pick the registered direction for the source backend and `to`, and return the target project's files in memory with a `ConversionReport`. It MUST write no file and run no tool.

#### Scenario: Nothing is written
- **GIVEN** a snapshot of the source folder and `subprocess.run` patched to raise
- **WHEN** `uv run pytest tests/unit/convert -k hermetic` converts the two-layer board to Altium
- **THEN** the call returns files and the folder is unchanged

### Requirement: Conversion sources
A KiCad source SHALL be a `.kicad_pro`, a `.kicad_pcb` or a folder, resolved as `check` resolves it, and its design MUST be the board read completed by `KicadBackend.design_rules` with the project's files. An Altium source SHALL be a `.PrjPcb`, a `.PcbDoc` or a folder, read by the Altium backend. A source of another kind, or a pair of backends without a registered direction, MUST raise `ValueError`.

#### Scenario: Net classes come from the project
- **GIVEN** a KiCad project built from a script that declares a net class `POWER` with a 0.5 mm track width
- **WHEN** `convert_project(<project>, to="altium")` runs
- **THEN** the written PCB document holds the class `POWER` with its nets, and the report's row `netclass` has `lost` 0

#### Scenario: Unknown source refused
- **GIVEN** a text file `notes.txt`
- **WHEN** `convert_project("notes.txt", to="altium")` runs
- **THEN** it raises `ValueError` and reads nothing else

### Requirement: Conversion report
A `ConversionReport` SHALL hold one row per kind of `fenolite.convert.report.KINDS` that the source holds or the write touches, in table order, each with `kind`, `source`, `written`, `changed`, `lost` and `reasons`. `reasons` MUST count every changed or lost item under its own reason, sorted by count and then by reason; a first reason standing for all MUST NOT be used.

#### Scenario: Reasons are counted apart
- **GIVEN** a KiCad board with one custom pad and two connector pads
- **WHEN** it is converted to Altium with `allow_lossy=True`
- **THEN** the row `pad` has `lost` 1 and `changed` 2, each under its own reason: the custom shape with count 1 and the connector pads with count 2

### Requirement: Conversion kinds
`fenolite.convert.report.KINDS` SHALL be a closed table with, per kind, a `group` and a `loss` class, `refuse` or `report`. Every kind of `lower.LOSS_KINDS` and the kind `dnp` MUST be `refuse`, and every kind that a registered direction's writer names MUST be a row of `KINDS`. A report's `lossy` MUST be true when any row has `lost` above 0, and its `refused` MUST name the `refuse` kinds with losses.

#### Scenario: Vocabulary is closed
- **WHEN** `uv run pytest tests/unit/convert/test_report.py -k closed` collects the kinds that `lower` can report and the kinds of every registered direction
- **THEN** each is a row of `KINDS`

### Requirement: Lossy conversions need consent
A conversion whose report has a `refuse` kind with losses SHALL raise `fenolite.convert.LossyConversionError` (`cli_code` `FEN-7001`) unless `allow_lossy` is true; the error MUST carry one `convert.lossy` issue per kind with lost items, in report order, with the kind as `where` and the counts per reason in the message. Those are the `refuse` kinds, which `refused` names, and the `report` kinds that `allow_lossy` would lose with them (change c0434), so a consent covers every loss it was shown. Its message MUST name the `refuse` kinds and, after `--allow-lossy also loses items of`, the others. With `allow_lossy` the conversion MUST complete and give one `convert.lossy` warning per kind with lost items. A `report` kind is refused too when its losses hold a reason of `report.REFUSE_REASONS`: for `rule`, `SOURCE_RULE_LOST`, a rule that a record of the source document gave (requirement "Rule records through KiCad").

#### Scenario: Exit 7 without consent
- **GIVEN** the KiCad 10.0.6 demo board `RoyalBlue54L-Feather` in the corpus
- **WHEN** `fenolite convert <board> --to altium --out out --dry-run --json` runs, and again with `--allow-lossy`
- **THEN** the first exits 7 with `FEN-7001` and issues whose `where` include `pad` and `dnp`, and the second exits 0 with a plan and `convert.lossy` warnings for the same kinds

#### Scenario: The refusal lists every loss
- **GIVEN** a conversion whose report loses one pad (a `refuse` kind) and one rule (a `report` kind)
- **WHEN** `convert_project` runs without `allow_lossy`
- **THEN** it raises `LossyConversionError` with the issues `pad` and `rule`, `refused` is `("pad",)`, and the message ends with `(pad); --allow-lossy also loses items of rule`

### Requirement: Conversion verified by equivalence
`fenolite.api.convert(source, *, to, kicad_version=10, allow_lossy=False, bodies="extruded", name=None, verify=True) -> ConversionResult` SHALL call `convert_project`, and with `verify` read the written project with the target backend from a private temporary folder and compare it with the source through `fenolite.api.equivalent` at the highest level both hold, under the direction's profile of `src/fenolite/convert/data/profiles.toml`.

#### Scenario: Sample verified
- **GIVEN** the routed two-layer KiCad sample
- **WHEN** `fenolite.api.convert(<sample>, to="altium")` runs
- **THEN** the result's equivalence ran level 5 under the profile `kicad-to-altium` and is equivalent

### Requirement: Differences matched to the report
A difference of a verification that no rule of the profile excludes SHALL be explained when its kind and `where` match a lost item of the report by the closed table `convert.report.EXPLAINS`; it is then listed under `equivalence.explained` with the lost kind. Any other difference MUST give one `convert.unexplained` error.

#### Scenario: Lost pad explains its pin
- **GIVEN** a KiCad board with one custom pad `U1-3`, converted to Altium with `allow_lossy=True`
- **WHEN** `fenolite.api.convert` verifies it
- **THEN** the `pad-missing` and `pin-missing` differences at `U1-3` are under `explained` with the kind `pad`, and no `convert.unexplained` is reported

#### Scenario: Undeclared change is caught
- **GIVEN** a direction registered for the test whose writer moves one footprint by 1 mm and reports nothing
- **WHEN** `fenolite.api.convert` verifies its output
- **THEN** it reports one `convert.unexplained` error whose `where` is the footprint's reference

### Requirement: Conversion without verification
With `verify=False` the result of `fenolite.api.convert` SHALL hold no equivalence, MUST give one `convert.no-verify` warning, and its evidence MUST be `UNVERIFIED`.

#### Scenario: Verification skipped
- **WHEN** `fenolite.api.convert(<two-layer sample>, to="altium", verify=False)` runs
- **THEN** its `equivalence` is `None`, its issues hold one `convert.no-verify` warning, and its evidence level is `UNVERIFIED`

### Requirement: Convert command
`fenolite convert SRC --to {kicad,altium} --out DIR` SHALL be registered by `src/fenolite/cli/cmd_convert.py` with `mutates=True`, take the global `--kicad-version` and `--allow-lossy`, and accept `--name NAME`, `--altium-bodies {extruded,off}`, `--report-ids` and `--no-verify`. It SHALL plan every file of the converted project under `DIR` and write them under `--confirm`, all or none.

#### Scenario: Plan of a conversion
- **WHEN** `fenolite convert tests/data/kicad/board/two_layer.kicad_pcb --to altium --out out --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `out/two_layer.PcbDoc` and `out/two_layer.PrjPcb`, `result.experimental` is `true`, and `result.equivalence.equivalent` is `true`

### Requirement: Convert output folder
`DIR` that is the source's folder, or holds it, SHALL exit 2 with `FEN-2001` and plan nothing: a conversion never writes over its source. Any other existing folder MUST be accepted, and a file of it that the conversion overwrites MUST be kept as a `.bak` copy unless `--no-backup` is given.

#### Scenario: Output over the source refused
- **WHEN** `fenolite convert <project> --to altium --out <project> --dry-run` runs
- **THEN** the exit code is 2 with `FEN-2001` and nothing is planned

#### Scenario: Existing output folder
- **GIVEN** a folder `out` that holds an earlier `two_layer.PcbDoc`
- **WHEN** `fenolite convert tests/data/kicad/board/two_layer.kicad_pcb --to altium --out out --confirm` runs
- **THEN** the exit code is 0 and `out/two_layer.PcbDoc.bak` holds the earlier bytes

### Requirement: Convert result and exit codes
The `result` of `fenolite convert` SHALL hold `source`, `target`, `files`, `report`, `equivalence` and `experimental`, and MUST validate against `schemas/fenolite.convert.v0.json`. A `convert.unexplained` error MUST exit 5 and plan no write; a refused loss MUST exit 7.

#### Scenario: Consistency suite
- **WHEN** `uv run pytest tests/consistency` runs from a temporary working directory
- **THEN** it passes for `convert`, and its `result` validates against `fenolite.convert.v0.json`

### Requirement: KiCad to Altium direction
The direction from KiCad to Altium SHALL project the footprint items of the source design (`backends.kicad.fpitems.with_footprint_items`) and write it with `backends.altium.lower.write_design(…, allow_lossy=True, bodies=…)`, mapping the write's lost items per kind and reason into the report. It MUST mark the reply `experimental`, and its evidence MUST be at most the Altium writers' level.

#### Scenario: Demo boards are explained
- **WHEN** `uv run pytest tests/corpus/test_convert_census.py -rA` converts every KiCad 10.0.6 demo board of the corpus that the direction writes
- **THEN** no board gives `convert.unexplained`, and the counts per kind and reason equal those recorded in `docs/evidence/conversion.md`

#### Scenario: KiCad reads the converted document as the source
- **GIVEN** `kicad-cli` 10.0.6 and the routed two-layer sample
- **WHEN** `uv run pytest tests/kicad/convert/test_triangle.py -rA` converts it to Altium and imports the PCB document with `kicad-cli pcb import`
- **THEN** the import equals the source at level 5 under the profile `kicad-import`, and the probe `convert-triangle` records `equal`

### Requirement: Changes of the Altium direction
In the report of the direction from KiCad to Altium, a polygon whose fill is not carried from the source (kind `zone-fill`) and a schematic generated from the circuit (kind `schematic`) SHALL be counted under `changed`, not `lost`, each under its reason. A source whose sheets are drawn keeps its drawing (requirement "A converted schematic keeps the source drawing"): its `schematic` row has no change, and its drawn items are counted under their own kinds.

#### Scenario: Detailed contract for changes of the altium direction
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

In the report of the direction from KiCad to Altium, a polygon whose fill is not carried from the source (kind `zone-fill`) and a schematic generated from the circuit (kind `schematic`) SHALL be counted under `changed`, not `lost`, each under its reason. The reason of `zone-fill` MUST be "a polygon is written unpoured; Altium fills it on a repour" with the pour mode `outline`, and "the pour is computed by Fenolite from the written document (experimental)" for a polygon poured with `computed`; a polygon refused with `computed` keeps the first reason. A schematic is generated, and counted under `changed`, only when the source has no drawing or its drawing cannot be written.

#### Scenario: Unpoured polygon is a change
- **GIVEN** the routed two-layer KiCad sample, whose board holds a filled zone
- **WHEN** it is converted to Altium with `--altium-pour outline`
- **THEN** the row `zone-fill` has `changed` above 0 and `lost` 0 with the reason of an unpoured polygon, and the row `schematic` has `changed` 1 and `lost` 0

#### Scenario: Computed polygon is a change
- **WHEN** the same sample is converted with `--altium-pour computed`
- **THEN** the row `zone-fill` has `changed` above 0 and `lost` 0 with the reason of a computed pour

#### Scenario: Drawn sheets are not generated
- **GIVEN** the authored nested KiCad project of `tests/_schbuild.py`
- **WHEN** it is converted to Altium
- **THEN** the row `schematic` has `changed` 0 and `lost` 0, and the report holds a `sheet` row

### Requirement: KiCad to KiCad direction
The direction from KiCad to KiCad SHALL, for a target major not older than the source's, write the board read from the source with `write_board` for the target, the project file updated from the source's, and the rules file re-written for the target. Schematic files MUST be copied unchanged when the source's major equals the target and MUST otherwise be reported as not converted.

#### Scenario: Version 9 project to KiCad 10
- **GIVEN** the blink example built for target 9
- **WHEN** `fenolite --kicad-version 10 convert <project> --to kicad --out out --confirm` runs and `kicad-cli` 10.0.6 runs DRC on `out/blink.kicad_pcb`
- **THEN** the board's header is `20260206`, the DRC reports the violation types of the source in 9.0.9, and the probe `convert-retarget` records `equal`

### Requirement: KiCad downgrade direction
`fenolite convert SRC --to kicad` with a `--kicad-version` older than the major of the source's board SHALL write the project for that target with `downgrade=True`: the board, the root schematic and its sheets, the footprint and symbol libraries of the project's own library tables, and the project and rules files. `build`, `place`, `route` and `fill` MUST keep refusing such a source.

#### Scenario: Demo project for KiCad 9
- **GIVEN** the KiCad 10.0.6 demo project `pic_programmer` in the corpus
- **WHEN** `fenolite --kicad-version 9 --allow-lossy convert <project> --to kicad --out out --confirm` runs, and `kicad-cli` 9.0.9 loads `out/pic_programmer.kicad_pcb` and runs its DRC
- **THEN** the exit code is 0, the board loads, its DRC by violation type equals 10.0.6's on the source apart from the `design` rows of the report, and the probe `down-demos` records `equal`

#### Scenario: Build keeps refusing
- **GIVEN** a target-9 project whose board was re-saved by KiCad 10.0.6
- **WHEN** `fenolite --kicad-version 9 build <script> --out <project> --dry-run` runs
- **THEN** the exit code is 7 with `FEN-7002`, and its hint names `fenolite convert`

### Requirement: KiCad downgrade report
The report of a downgrade MUST hold one row per resolver id with its counts per action: `rewrite` and `same` as `changed`, `presentation` as a `report` loss, `design` as a `refuse` loss. The verification MUST compare the board at level 5 and the root schematic at level 2 under the profile `kicad-downgrade`.

#### Scenario: Rows per resolver id
- **GIVEN** the KiCad 10.0.6 demo project `pic_programmer` in the corpus
- **WHEN** it is converted for KiCad 9 with `allow_lossy`
- **THEN** the report holds the row `downgrade:footprint-units` with 63 `report` losses, the row `downgrade:tenting-front` as a change, and the verification finds no unexplained difference

### Requirement: Altium to KiCad direction
`fenolite convert SRC --to kicad` SHALL convert an Altium project, PCB document or folder into a KiCad project for the target of `--kicad-version` (9 or 10): the board, the project file, the rules file, a footprint library derived from the board's instances, a symbol library, the library tables and a schematic. The schematic is the drawing of the source sheets (requirement "A converted schematic keeps the source drawing"); a source without sheets, or whose drawing cannot be written, gets a schematic generated from the circuit. Each item that the KiCad project cannot hold MUST be a lost row of the report with its reason, and the conversion MUST be verified against the import under the profile `altium-to-kicad`.

#### Scenario: Public documents converted
- **WHEN** `uv run pytest tests/corpus/test_convert_altium_census.py -rA` converts the eight public PCB documents of the corpus to KiCad 10 with `--allow-lossy`
- **THEN** each is written, none gives `convert.unexplained`, and the counts per kind and reason equal those of `docs/evidence/conversion.md`

#### Scenario: Plan of an Altium sample
- **WHEN** `fenolite convert tests/data/altium/blink/blink.PrjPcb --to kicad --out out --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `out/blink.kicad_pcb`, `out/blink.kicad_pro`, `out/blink.kicad_dru`, `out/blink.kicad_sch` and `out/blink.pretty/`, and `result.equivalence.equivalent` is `true`

### Requirement: Layers of a converted Altium board
The board of a conversion to KiCad SHALL have one KiCad layer row per layer it holds: copper rows for an even count from 2 to 32 (an odd count of signal layers gets one empty inner layer, counted `changed` under `stackup`); the non-copper layers by name; `Mech.<n>` onto KiCad's user layers in order of `n`, then `Altium.DrillGuide` and `Altium.DrillDrawing` (change c0428), as many as the target holds; a closed outline on `Altium.KeepOut` as a rule area that keeps out tracks, vias and copper pour on every copper layer. Every other item on a layer without a row MUST be a lost row with its reason.

#### Scenario: Mechanical and keep-out layers
- **GIVEN** the public document `altium-third-party-pcbdoc-06`, whose items lie on `Mech.1`, `Mech.2`, `Altium.KeepOut` and `Altium.74`
- **WHEN** it is converted to KiCad 10
- **THEN** the lines of `Mech.1` and `Mech.2` are on the first two user layers, each closed keep-out outline is a rule area, and the three items of `Altium.74` are lost under their kinds with the reason "a layer outside the stack"

#### Scenario: Drill layers
- **GIVEN** a board with lines on `Mech.3`, `Altium.DrillGuide` and `Altium.DrillDrawing`
- **WHEN** `uv run pytest tests/unit/convert/test_to_kicad.py -q -k drill` converts it
- **THEN** they lie on `User.1`, `User.2` and `User.3`, and no `graphic` is lost

### Requirement: Slots of a converted Altium board
A pad whose slot is turned against the pad SHALL be written with the pad turned to the slot's angle when the pad is a circle, or an oval whose long axis lies along the slot; any other such pad MUST be a lost `pad` with the reason "a slot turned against a pad of this shape".

#### Scenario: Round pad with a turned slot
- **GIVEN** a footprint with a round pad of 2 mm and a slot of 1 x 3 mm at 45 degrees
- **WHEN** the board is converted to KiCad and read back
- **THEN** the pad and its slot have the copper and the hole of the source, and the report loses no pad

### Requirement: Conversion agrees with KiCad's importer
For each public PCB document of the corpus that the direction writes, the written KiCad board SHALL equal the board that `kicad-cli pcb import` (10.0) makes of the same document at level 5 under the profile `kicad-import`, apart from the items the report names lost.

#### Scenario: Two converters agree
- **GIVEN** `kicad-cli` 10.0.6 and the corpus cached
- **WHEN** `uv run pytest tests/kicad/convert/test_a2k_import.py -rA` runs
- **THEN** every written document agrees with KiCad's import at level 5, and the probe `convert-a2k-import` records `equal`

#### Scenario: KiCad loads the converted board
- **WHEN** `uv run pytest tests/kicad/convert/test_a2k_load.py -rA` runs in the pinned 9.0.9 and 10.0.6 images
- **THEN** each board written for that major loads, its DRC writes a report, and the probe `convert-a2k-load` records `equal`

### Requirement: Mask and paste of imported pads
A pad read from an Altium document SHALL be given mask and paste layers by its kind when it is converted to KiCad: a surface pad its side's paste and mask layers, a plated or unplated through-hole pad both mask layers and no paste.
- A manual expansion MUST become the pad's margin, an expansion of 0 included (change c0440: it MUST NOT be left to the board's setting); a rule expansion the margin of the record that governs the pad (change c0462, design D6): the first enabled record of its kind, by priority, whose scope, read with the full grammar and the document, selects the pad. The pad's subject is its net, every net class of the document that holds the net, its component's designator, its one copper layer (a surface pad only), its hole and its pad type. A pad that no record selects gets none.
- The modes and manual expansions MUST be read from each pad's Altium bag as the source holds it, before the conversion empties the bags of the target (change c0440).
- A pad before whose governing record comes a record that may select it and that the conversion cannot judge for it (a scope outside the grammar, a room, or a layer of a pad with a hole when the rest of the scope does not decide it) MUST be a `pad-margin` loss, and MUST take the governing record's expansion. A record whose scope selects no pad (`IsVia`) is not such a record.

#### Scenario: Openings after conversion
- **GIVEN** an imported design with a surface pad of manual mask expansion 2 mil, a plated through-hole pad and an unplated hole, all with the paste mode of a rule
- **WHEN** `uv run pytest tests/unit/convert/test_pad_layers.py` prepares it for KiCad
- **THEN** the surface pad holds `F.Cu`, `F.Paste` and `F.Mask` with a mask margin of 50 800 nm, the two holes hold both masks and no paste, and the written board loads in `kicad-cli`

#### Scenario: A scoped rule governs the pads it selects
- **GIVEN** records of scope `InNetClass('Ground')` (1 mil), `InComponent('R1')` (2 mil) and `All` (4 mil), in that order, a net `GND` in the classes `Power` and `Ground`, and a paste record of scope `InNet('VCC') and OnLayer('Layer 1')`
- **WHEN** `uv run pytest tests/unit/convert/test_expansion_scopes_c0462.py` reads the pads of the document
- **THEN** the pad of `U1` on `GND` takes 1 mil, the pad of `U1` on `VCC` 4 mil and paste -1 mil, the through-hole pad of `R1` 2 mil, and no pad is listed under `pad-margin`

#### Scenario: A record that cannot be judged is reported
- **GIVEN** a record whose scope is outside the grammar before the record of scope `All`
- **WHEN** a rule-mode pad is opened
- **THEN** it takes the `All` record's expansion and the ledger lists it under `pad-margin`

#### Scenario: A rule of vias is no pad's
- **GIVEN** the same design whose `SolderMaskExpansion` rule of scope `IsVia` comes before the one of scope `All`
- **WHEN** `uv run pytest tests/unit/convert/test_pad_layers.py -k no_pad` prepares it
- **THEN** the pads take the `All` rule's expansion and the ledger lists no `pad-margin` row

#### Scenario: A manual pad keeps its own expansion
- **GIVEN** `altium-third-party-pcbdoc-01`, whose pads hold a manual mask expansion of 0 (20 pads) or 3.1496 mil (16 pads) under a `SolderMaskExpansion` rule of 3 mil of scope `All`
- **WHEN** `uv run pytest tests/corpus/test_altium_pad_mask_c0440.py` converts it to KiCad and back to Altium
- **THEN** every pad common to both documents holds the mask it held, a pad that followed the rule holding the manual expansion of 3 mil, and level 3 of `equivalent` between the two documents gives no `pad-mask` difference

### Requirement: Pad margins in the KiCad writers
`Pad.mask_margin` and `Pad.paste_margin` SHALL be optional lengths that the KiCad board and footprint writers write as `solder_mask_margin` and `solder_paste_margin` for a pad that holds no such child; the readers SHALL project the first such child into the field and keep the child as read.
- A field that disagrees with a kept child MUST be refused with `projection-read-only`.

#### Scenario: A margin written and a kept one guarded
- **GIVEN** an authored footprint whose pad sets `mask_margin` to 0.1 mm, and a read footprint whose pad holds `(solder_mask_margin 0.05)`
- **WHEN** `uv run pytest tests/unit/convert/test_pad_layers.py -k writer` writes both, the second with `mask_margin` set to 0.1 mm
- **THEN** the first holds `(solder_mask_margin 0.1)` and the second is refused

### Requirement: Model placement of imported footprints
`FootprintDef.placements` SHALL hold, for a footprint read from another format, each 3D model's path, offset, rotation and scale, and the KiCad footprint writer SHALL write one `model` child per placement.
- An embedded Altium model MUST be extracted beside the derived library and placed so that KiCad's model pose (`H-K-MODEL-POSE`) equals the source's (`H-A-BODY-MODEL-PLACE`), for any turn about X, Y and Z and on either side.
- The board's footprints MUST hold the same placements, and every model file that the library or the board names MUST be written.

#### Scenario: A rotated body
- **GIVEN** an imported top-side footprint whose body names an embedded model turned by 90° about Z and raised by 0.5 mm
- **WHEN** `uv run pytest tests/unit/convert/test_model_placement.py` converts it to KiCad
- **THEN** the library footprint names the extracted `.step` with `(offset (xyz 0 0 0.5))` and `(rotate (xyz 0 0 -90))`, and the file holds the model's bytes

#### Scenario: A model on the bottom turned about X and Y
- **GIVEN** the same footprint on the bottom side, its model turned about X, Y and Z
- **WHEN** it is converted
- **THEN** the model is written, the report lists it under `model` as changed, and KiCad's pose of the written offset and rotation equals the source's within 1 nm and 1 µdeg

### Requirement: Library made from a board
`fenolite library BOARD --out LIB [--diff LIBRARY]` SHALL write each footprint of a KiCad board, brought back to its origin, rotation 0 and the top side, into the footprint library `LIB` (a `.pretty` folder), under the mutation protocol.
- Instances of one name that differ MUST be written as `<name>_2` and so on, with `library.instances-differ` (warning). A variant MUST take the next suffix that no footprint of the board and no earlier variant holds, so no two written footprints share a name (change c0425).
- `--diff` MUST report per footprint the kinds that differ and write nothing.

#### Scenario: Silkscreen edited on the board
- **GIVEN** an authored board whose instances of `R_0603` have their silkscreen clipped, and a library with the unclipped footprint
- **WHEN** `fenolite library <board> --diff old.pretty --json` runs
- **THEN** the reply names `R_0603` with the kind `silkscreen`, the exit code is 5, and nothing is written

#### Scenario: Two instances that differ
- **GIVEN** an authored board with two `R_0603` instances, one with a pad moved
- **WHEN** `fenolite library <board> --out lib.pretty --dry-run --json` runs
- **THEN** the plan writes `R_0603.kicad_mod` and `R_0603_2.kicad_mod`, and the issues hold one `library.instances-differ`

#### Scenario: A variant name the board already holds
- **GIVEN** the authored two-layer board with a second `R_0603` instance whose pad is moved, and its LED footprint renamed `R_0603_2`
- **WHEN** `uv run pytest tests/unit/library/test_derive.py -k already` derives the library
- **THEN** the footprints are `R_0603`, `R_0603_2` (the board's own) and `R_0603_3` (the variant of `R_0603`)

### Requirement: Library command result
The result of `fenolite library` (schema `fenolite.library.v0`) SHALL hold `board`, `library` and either `footprints` (one row per written footprint: `name`, `source` and `refs`) or, with `--diff`, `drift` (one row per footprint: `name` and `kinds`); that list is paged with `--limit`.

#### Scenario: Paged rows
- **GIVEN** the example board of the command
- **WHEN** `uv run pytest tests/unit/cli/test_paging.py` lists the paged commands
- **THEN** `library` pages `drift|footprints`

### Requirement: Slots and cut-outs in a conversion
A conversion SHALL count every inner edge ring of the source under the kind `cutout` (group `board`, class `report`): `kept`, `changed` with the reason "merged" or "arcs polygonised", or `lost` with its reason. To Altium, inner rings MUST follow c0168's region lowering through `edge_outline`. To KiCad, overlapping rings MUST be merged; an overlap that cannot be merged MUST be a `refuse` loss, and each board `Hole` MUST become a generated `Fenolite_Holes` footprint.

#### Scenario: Fixture to Altium
- **GIVEN** the shared fixture built for KiCad 10
- **WHEN** `uv run pytest tests/unit/convert/test_convert_slots.py -k altium` converts it with `--to altium`
- **THEN** the report's `cutout` row counts three rings (written as regions and changed with "arcs polygonised" with the gate on, lost with its reason with the gate off), and no ring is reported under `outline`

#### Scenario: Overlapping Altium cut-outs to KiCad
- **GIVEN** an Altium document with two overlapping board cut-out regions and a free slot pad
- **WHEN** it is converted with `--to kicad`
- **THEN** the board holds one merged cut-out ring, `cutout` counts one ring changed with "merged", the slot is an `NPTH_Slot_…` footprint, and `kicad-cli pcb drc` reports no `invalid_outline`

### Requirement: Edge rings verified after a conversion
After writing, a conversion SHALL compare the edge rings of the source and of the written project read back, through `BoardFrame.board_edges`, within 1 µm plus the region chord, a merged ring against the union of its sources. A ring that differs and that the report does not explain MUST be a difference of the verification.

#### Scenario: A dropped ring is a difference
- **GIVEN** a conversion whose writer is patched in the test to drop one cut-out without reporting it
- **WHEN** `uv run pytest tests/unit/convert/test_convert_slots.py -k verify` runs it
- **THEN** the verification names that ring and the exit code is 5

### Requirement: Bottom-side angles in a derived footprint
A footprint derived from a bottom-side instance SHALL turn each stored angle of its pads, properties and texts back to `(θ − stored) mod 360°`, the inverse of the bottom placement `(−φ + θ) mod 360°`, so that placing the derived footprint where the instance was gives the instance's angles back.

#### Scenario: Reference at 270° on the bottom
- **GIVEN** the authored two-layer board with `R1` replaced by a footprint whose Reference and pad 1 stand at 90°, placed on the bottom side at 0°, 90° and 180° (at 0° the board stores the Reference at 270°)
- **WHEN** `uv run pytest tests/unit/library/test_derive.py -k bottom` derives the library from each board
- **THEN** the derived footprint holds the Reference and pad 1 at 90° again, as it was before placement

### Requirement: Bounded variant signature work
Board library derivation SHALL serialize each instance's normalized comparison signature at most once. It MUST preserve footprint variants, names, ordering, native text, issues, nickname filtering and preparation callbacks. This changes no public argument, format or evidence level.

#### Scenario: Many variants and one repeated instance
- **GIVEN** an authored board with twelve differing instances of one footprint and one repeated instance
- **WHEN** library derivation runs for each supported target
- **THEN** it retains the same twelve variants and reference memberships, with no more signature serializations than source instances

#### Scenario: Existing native outputs remain unchanged
- **WHEN** existing derivation and importer vendor regressions run
- **THEN** their native bytes, diagnostics and nickname mappings remain equal to their existing expectations

### Requirement: Derived footprints preserve safe interior spaces
Altium-to-KiCad conversion SHALL preserve interior ASCII spaces in a portable derived footprint name. The board link, component link, library filename and footprint header MUST agree. Project/symbol sanitization, reserved-name and path guards, and case-insensitive collision allocation SHALL remain unchanged. Name comparison MUST detect a real rename.

#### Scenario: Space and underscore are distinct names
- **GIVEN** authored footprints named `M Mount` and `M_Mount`
- **WHEN** their derived KiCad project is written and read
- **THEN** both names retain distinct matching board links and library files
- **AND** a deliberate rename still produces a footprint-name difference

### Requirement: KiCad to Altium closes the measured losses
`fenolite convert --to altium` SHALL write every KiCad 10.0.6 demo board of the corpus, and its report SHALL lose no pad for a per-layer stack of plain shapes, a connector pad or a pad without a number, and no drawing or text on a layer of `lower.KICAD_MECHANICAL` or on a copper layer. `docs/evidence/conversion.md` MUST hold, per board, the counts per kind and reason before and after this change.

#### Scenario: Census after the change
- **WHEN** `uv run pytest tests/corpus/test_convert_census.py -rA` runs with the corpus cached
- **THEN** all 18 demo boards are written, no board gives `convert.unexplained`, and the lost `pad` rows hold only custom shapes

#### Scenario: Part T recorded
- **GIVEN** the maintainer's author report of Part T in `docs/evidence/altium-pcb.md`
- **WHEN** `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py` runs
- **THEN** the rows of this change name the report with the tool, the date and no artefact, and no write kind is marked out of `experimental`

### Requirement: Conversion of a source without a PCB design
`convert` SHALL refuse a source whose design has no PCB with `FEN-3001` (exit 3) before a direction
writes anything. The message SHALL name the PCB documents the project declares and lacks, or say that
the project declares no PCB document. It SHALL NOT fail with an internal error.

#### Scenario: An Altium project whose PcbDoc is missing
- **WHEN** an Altium project declares `PCB/Board.PcbDoc`, that file is absent, and `fenolite convert --to kicad` runs
- **THEN** the command exits 3 with `FEN-3001` and the message names `PCB/Board.PcbDoc`
- **AND** no file is planned

### Requirement: Board comparison of placed components
The verification of a conversion that wrote a schematic SHALL compare the written board with the
components that have a footprint on the board, and SHALL leave the other components to the comparison of
the written schematic. A component without a footprint that the written schematic lacks SHALL still be
reported. A conversion without a written schematic SHALL compare every component with the board.

#### Scenario: A schematic-only component
- **WHEN** an Altium project holds a component that no footprint of its PCB places, and `fenolite convert --to kicad` runs
- **THEN** no `convert.unexplained` names that component
- **AND** the written schematic holds it

### Requirement: Several footprints of one component
The KiCad direction SHALL count each footprint of a source component that more than one footprint links
as a changed `shared-footprint` item (class `report`), and the explanation SHALL explain a
`ref-ambiguous` difference at its reference.

#### Scenario: One component linked to two footprints
- **WHEN** a source board links two footprints to one component and the conversion runs
- **THEN** the report lists both footprints under `shared-footprint`
- **AND** the `ref-ambiguous` difference of that reference is explained

### Requirement: A refused generated schematic is a declared loss
When the schematic generator of an Altium to KiCad conversion refuses the circuit, the conversion SHALL
still write the board and its libraries, SHALL count the schematic as lost with a reason that needs
`--allow-lossy`, and SHALL NOT report the generator's refusal as an error finding. The lost schematic SHALL
explain the `component-missing` of each component that no footprint places.

#### Scenario: A circuit larger than one A0 page
- **WHEN** a PCB document alone holds more units than one A0 page and `fenolite convert --to kicad --allow-lossy` runs
- **THEN** the plan holds the board and exits 0 or 5 without `build.schematic-too-large` as an error
- **AND** without `--allow-lossy` the command exits 7 naming `schematic`

### Requirement: Source sheets and pages of a generated schematic
The schematic that an Altium to KiCad conversion generates SHALL place the parts of each source schematic
document of a flat project on a KiCad sheet of its own, and SHALL spread a sheet that no paper holds over
sibling pages before it refuses the circuit; a page SHALL be refused only when one part alone does not fit.
The written sheets SHALL load in KiCad 9 and 10 with the source's netlist, and two conversions of one
source SHALL write equal bytes.

#### Scenario: A flat project of several sheets
- **WHEN** a flat Altium project whose parts lie on two schematic documents is converted to KiCad
- **THEN** each document's parts lie on `sheets/<document stem>.kicad_sch` under the root sheet
- **AND** the conversion verifies without unexplained differences

#### Scenario: A circuit larger than one page
- **WHEN** a sheet of the generated schematic holds more units than one A0 page
- **THEN** its parts are spread over `<sheet>-1`, `<sheet>-2`, … (`page-1`, … at the root)
- **AND** KiCad's ERC reads every page and its exported netlist is the circuit's

### Requirement: Boards that place other PCB documents are refused losses
A conversion from an Altium PCB document whose `EmbeddedBoards6` storage holds records SHALL count the
document once under the kind `embedded-board`, lost with a reason that needs `--allow-lossy`, until the
records are read. The detection SHALL use only the storage's record count and data length.

#### Scenario: A board that places other boards
- **WHEN** a project's board holds an Embedded Board Array and `fenolite convert --to kicad` runs without `--allow-lossy`
- **THEN** the command exits 7 naming `embedded-board`
- **AND** with `--allow-lossy` the report lists the document as lost with its reason

### Requirement: Embedded board arrays are read and named
The Altium reader SHALL read each record of `EmbeddedBoards6` as an array: its referenced document, location,
rotation, mirror, column and row counts, column and row pitch, and Link Location. A storage whose `Header`
count differs from its records, or a record without one of these keys, SHALL be refused as unreadable.
A conversion SHALL list each array as one `embedded-board` item named by the document, the array's number,
the referenced document and its columns and rows, and SHALL keep the loss refused while the copies'
placement is not measured.

#### Scenario: A panel of two arrays
- **WHEN** a board holds two arrays and `fenolite convert --to kicad --allow-lossy` runs
- **THEN** the `embedded-board` row counts 2 items, each named with its referenced document and counts

#### Scenario: Records that do not read
- **WHEN** the `Header` count differs from the records of `EmbeddedBoards6`
- **THEN** the reader refuses the storage and the conversion names the document alone

### Requirement: Copies of an embedded board array are placed only where measured
A conversion SHALL place the copies of an Embedded Board Array that is unmirrored and turned by a multiple of 90 degrees, and whose referenced document reads.
- The copy in column `c` and row `r` SHALL take a point `p` of the referenced board to (`X`, `Y`) + R((`c` · `COLSPACING`, `r` · `ROWSPACING`) + `p` − `O`), where R is the array's turn.
- `O` SHALL be the board's origin when the origin lies within 1 µm of its shape's lower-left corner, or when the array links its location to the origin. Otherwise `O` SHALL be that corner.
- What S-1592 measured is the rule for 0 and 90 degrees with the origin at the corner. Each other case (180 or 270 degrees, origin away from the corner) MUST carry its inferred rule in the item's reason.
- A referenced document that is not at its path relative to the panel MUST be looked for in this order: relative to the project's folder, by its file name beside the panel or in the project's folder, then at the absolute path stored. Names MUST match without letter case. The reason MUST say how the document was found.
- A mirrored array, an array turned by another angle, and an array whose document is missing or does not read MUST stay refused `embedded-board` losses that name the cause.
- An absolute path MUST be named by its file name only.

#### Scenario: A measured plain array
- **WHEN** a board holds an unturned, unmirrored array whose placement is recorded and its referenced document reads
- **THEN** the conversion writes each copy's components and copper at the measured places, with each copy's designators and nets kept apart

#### Scenario: A turned array
- **WHEN** a board holds an unmirrored array with `ROTATION` 90, 180 or 270
- **THEN** the conversion turns the whole array about its location by one, two or three counter-clockwise quarter turns and turns each copy's footprints with it, and the reason names the inferred rule for 180 and 270

#### Scenario: An origin away from the corner
- **WHEN** the referenced board's origin lies 1 mil right of its shape's lower-left corner
- **THEN** an array that links its location to the origin places the copies by the origin, any other array places them by the corner, and each reason names the inferred rule

#### Scenario: A document found by its name
- **WHEN** an array stores `C:\Work\x.PcbDoc` and `x.pcbdoc` lies beside the panel
- **THEN** the array is placed, its item names `x.PcbDoc` alone, and its reason says the document was read by its file name

#### Scenario: A mirrored array
- **WHEN** a board holds a mirrored array and no saved output records which copper side a mirrored copy takes
- **THEN** the array stays a refused `embedded-board` loss whose reason names the mirror

#### Scenario: An angle that is not a quarter turn
- **WHEN** a board holds an array turned by 45 degrees
- **THEN** the array stays a refused `embedded-board` loss and the conversion exits 7 without `--allow-lossy`

### Requirement: Keep-Out layer drawings of a converted Altium board
A conversion of an Altium board to KiCad SHALL make one rule area on every copper layer per drawing of the Keep-Out layer: a line, an arc or a circle drawn with a width the band that width covers, and a filled polygon or rectangle (or a closed outline of width 0) its outline.

- The rule areas are what KiCad 10.0.6's `pcb import` writes for keep-out tracks.
- Strokes MUST NOT be joined into one area over what they enclose.
- A stroke of width 0 covers no area and is reported as a loss.

#### Scenario: A ring of keep-out tracks
- **GIVEN** an authored document with four 1 mm keep-out tracks round a 10 mm square on the Keep-Out layer
- **WHEN** it is converted to KiCad
- **THEN** the board holds four rule areas on `F.Cu` and `B.Cu`, each 1 mm wide and 11 mm long, the inside
  of the square in none of them; the layers, boxes and areas match KiCad's import of the same document

#### Scenario: Open keep-out strokes of a public document
- **GIVEN** the public row `altium-third-party-pcbdoc-01`, with 12 lines and 8 arcs on the Keep-Out layer
- **WHEN** it is converted to KiCad
- **THEN** each is a changed rule area and none is a `graphic` loss

### Requirement: Footprint graphics of an imported footprint
A conversion to KiCad SHALL write each footprint's own lines, arcs, circles, rectangles and regions as `fp_line`, `fp_arc`, `fp_circle`, `fp_rect` and `fp_poly` children of the board footprint and of its library footprint, on the layer the conversion maps, and SHALL NOT lose one in silence (change c0409, B8).
- The report MUST count `footprint-graphic` and `footprint-text` items of the source.
- A footprint text that the target does not write MUST be a `footprint-text` loss with its reason.
- A `footprint-graphic` or `footprint-text` loss MUST give one `convert.lossy` warning per kind, without refusing the conversion.

#### Scenario: Lines, arcs, circles and regions reach the board and the library
- **GIVEN** the blink sample with one authored filled region on `Mech.13` and one authored text added to a footprint
- **WHEN** `uv run pytest tests/unit/convert/test_footprint_graphics.py -k convert -q` converts it to KiCad
- **THEN** the board footprints hold 24 `fp_line`, 2 `fp_arc`, 1 `fp_circle` and 1 filled `fp_poly` on the user layer named `Mech.13`, the library footprints hold the same, the report counts 28 graphics written and 1 text lost, and one `convert.lossy` warning names `footprint-text`

### Requirement: Polygon connect styles of an Altium board
A conversion of an Altium board SHALL give each zone the connection, thermal gap and spoke width of the PolygonConnect rule that governs the pads of its net, and SHALL give a pad whose narrower rule differs its own zone connection (change c0409, B5).

#### Scenario: A board-wide style and a narrower one
- **GIVEN** the committed `board6` sample (two GND zones) with authored PolygonConnect records `All` (relief, gap 0.3 mm, spoke 0.4 mm) and a higher-ranked `InComponent('D1')` (direct)
- **WHEN** `uv run pytest tests/unit/convert/test_polygon_connect.py -q` converts it to KiCad
- **THEN** both zones have thermal reliefs with `(thermal_gap 0.3)` and `(thermal_bridge_width 0.4)`, the GND pad of D1 alone has `(zone_connect 2)`, and without records the zones keep their connection

### Requirement: Governing zone clearance
A conversion of an Altium board SHALL write as each zone's clearance the value of the Altium clearance rule that governs the polygon against any item, not the default (change c0409, B6).

#### Scenario: A class clearance governs the polygon
- **GIVEN** the `board6` sample, whose polygons are on GND in the class `PWR`, with its class x All clearance set to 0.35 mm above the board clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/convert/test_polygon_connect.py -k clearance -q` converts it to KiCad
- **THEN** the zone's clearance is 0.35 mm

### Requirement: Project parameters and special strings
A conversion of an Altium project SHALL write its `[Parameter<n>]` entries whose names are variable names as project text variables, report the others, and write a board text that is the special string `.NAME` of a project parameter, or holds it as `'.NAME'` inside other text, with `${NAME}` in its place; a predefined special string of `altium_strings.PREDEFINED` SHALL be written as KiCad's variable of the same meaning, and every other special string whose name is a variable name SHALL be written as `${NAME}`, a variable the project does not define, with a `text` change in the report (change c0451; before, as typed). A conversion of a KiCad project to Altium SHALL write a board text `${NAME}` as `.NAME` and `${NAME}` inside other text as `'.NAME'`, KiCad's `CURRENT_DATE`, `FILENAME`, `FILEPATH` and `LAYER` as `.Print_Date`, `.Pcb_File_Name_No_Path`, `.Pcb_File_Name` and `.Layer_Name`, and the project's text variables as the project file's `[Parameter<n>]` entries (change c0451).

#### Scenario: A parameter on the silkscreen
- **GIVEN** a copy of the blink sample whose project holds `[Parameter1]` `Name=REV_CODE`, `Value=B2` and `[Parameter2]` `Name=Made By`, and whose board holds the texts `.REV_CODE`, `Rev '.REV_CODE' on '.Print_Time'` and `.Comment`
- **WHEN** `uv run pytest tests/unit/convert/test_project_parameters.py -q` converts and imports it
- **THEN** the `.kicad_pro` holds the text variable `REV_CODE` = `B2` alone, `Made By` gives `altium.import.unmapped`, the board texts are `${REV_CODE}`, `Rev ${REV_CODE} on ${Print_Time}` and `${Comment}` with `text` changes in the report, and the imported code declares the variable and keeps `${REV_CODE}`

#### Scenario: Parameters come back
- **GIVEN** the same source converted to KiCad
- **WHEN** `uv run pytest tests/unit/convert/test_project_parameters.py -q -k back` converts that project to Altium
- **THEN** the board texts are `.REV_CODE`, `Rev '.REV_CODE' on '.Print_Time'` and `.Comment`, and the project file holds `[Parameter1]` `Name=REV_CODE`, `Value=B2`

### Requirement: Keep-Out layer rule areas forbid pads
Each rule area that a conversion of an Altium board to KiCad makes of a Keep-Out layer drawing SHALL forbid tracks, vias, pads and poured copper, as KiCad 10.0.6's `pcb import` does for keep-out tracks and regions.

#### Scenario: Restrictions match KiCad's import
- **GIVEN** the authored c0407 document with a ring of keep-out tracks, a keep-out track on Top and a
  polygon cut-out
- **WHEN** it is converted to KiCad and also imported by `kicad-cli pcb import` 10.0.6
- **THEN** the six rule areas hold the same restrictions on both sides: five forbid tracks, vias, pads and
  pours, and the cut-out forbids pours alone

### Requirement: Named polygon connect scopes
A conversion of an Altium board SHALL read a Polygon Connect Style scope of named polygons (`IsNamedPolygon('n')`, or such terms joined by `Or` or `||`, one pair of parentheses round the whole allowed) as the pours of those names, compared without case, and SHALL give each zone the connection of the record that governs it by its own name. A pad whose governing records give it one style, other than its zones give, for every zone of its net SHALL get that style as its own zone connection; a pad whose records give different styles between the zones of its net MUST keep its setting, with a `pad` change in the report (change c0420, B5).

#### Scenario: A named polygon
- **GIVEN** the committed `board6` sample (GND pours `GND_L01_P000` and `GND_L06_P001`) with authored records `All` (relief) and a higher-ranked `All` × `IsNamedPolygon('gnd_l01_p000')` (direct)
- **WHEN** `uv run pytest tests/unit/convert/test_polygon_connect.py -k named -q` resolves the connections
- **THEN** `GND_L01_P000` is solid, `GND_L06_P001` thermal, and no zone or pad has a change

#### Scenario: Pad styles differ between zones
- **GIVEN** the same sample with `All` (relief) and a higher-ranked `InComponent('D1')` × `IsNamedPolygon('GND_L06_P001')` (direct)
- **WHEN** `uv run pytest tests/unit/convert/test_polygon_connect.py -k differ -q` resolves them
- **THEN** both zones are thermal, the GND pad of D1 keeps no own connection, and the report holds its `pad` change

### Requirement: Smallest governing zone clearance
A conversion of an Altium board SHALL write as each zone's clearance the smallest `min` of the Altium clearance rules that govern a pair of its polygon and an item: in Altium's order, every rule with a scope matching the polygon, up to and with the first whose other scope is `All`. Ignored rules MUST NOT count. Without such a rule against any item, the zone MUST keep its clearance with a `zone` change; a zone whose written clearance differs from the one it was read with MUST also have a `zone` change (`CLEARANCE_FROM_RULES`). KiCad lets a matching custom rule decide a fill's gap and takes the larger of the zone's clearance and a netclass clearance (`H-K-ZONE-CLEARANCE`), so the written DRU rules carry every wider value (change c0420, B6; it replaces the first-rule value of change c0409).

#### Scenario: A narrower pad rule ranks above the class rule
- **GIVEN** the `board6` sample with its class × All clearance set to 0.35 mm and an authored higher-ranked `IsPad` × All clearance of 0.25 mm
- **WHEN** `uv run pytest tests/unit/convert/test_polygon_connect.py -k smaller -q` converts it to KiCad
- **THEN** both zones have the clearance 0.25 mm, and the report holds a `zone` change for each

#### Scenario: KiCad's rule over the zone's clearance
- **GIVEN** an authored board with a zone of net `A` round a track of net `B`
- **WHEN** `uv run pytest tests/kicad/fill/test_zone_clearance_oracle.py -q` refills it with KiCad 10.0.6
- **THEN** a zone clearance of 1.0 mm with a custom rule of 0.2 mm on `B` gives a 0.2 mm gap, a zone of 0.2 mm with a rule of 1.0 mm a 1.0 mm gap, and without a rule the larger of the zone's and the netclass clearance

### Requirement: Keep-out restrictions of the Keep-Out layer
A conversion of an Altium board SHALL give the rule area of a keep-out of the Keep-Out layer (second flag byte 2) the restrictions of its own value: a region's `KEEPOUTRESTRICTIONS`, or the byte of a track, arc or fill. 1 forbids vias, 2 tracks, 4 poured copper, and 8 with 16 pads. The conversion MUST read the value from the drawing's record in the source document, found by its locator, and MUST add no model field or extension key. A drawing of the Keep-Out layer without the flag, or whose record or document cannot be read unchanged, MUST forbid all four, as before (change c0420, N2 and N3).

#### Scenario: A keep-out forbids what its value forbids
- **GIVEN** four authored Keep-Out-layer polygons with the values 7, 24, 8 and none
- **WHEN** `uv run pytest tests/unit/convert/test_to_kicad.py -k restrictions -q` converts them
- **THEN** their rule areas forbid vias, tracks and pours; pads alone; nothing; and all four

#### Scenario: The value is read from the source record
- **GIVEN** the authored keep-out document with four keep-out tracks of value 31 on the Keep-Out layer
- **WHEN** `uv run pytest tests/unit/convert/test_to_kicad.py -k source_records -q` reads their restrictions, then reads them again after one byte is added to the document
- **THEN** the first read gives 31 for each of the four drawings and the second gives none

### Requirement: Net-tie components of an Altium board
An import of an Altium board SHALL give a component whose `COMPONENTKIND` is 3 (net tie in the BOM) or 4 (net tie) one net-tie group of its distinct pad numbers in pad order, and none when it has fewer than two numbers. A conversion to KiCad SHALL write the group (change c0420, N1).

#### Scenario: A net-tie kind
- **WHEN** `uv run pytest tests/unit/backends/altium/test_net_tie_kind.py -q` imports authored component records of every kind
- **THEN** kinds 3 and 4 give one group of the distinct numbers, the other kinds none

#### Scenario: A converted net tie in KiCad's DRC
- **GIVEN** the blink sample with one two-pad footprint given a net-tie group and a copper line joining its pads
- **WHEN** `uv run pytest tests/kicad/convert/test_a2k_load.py -k net_tie -q` converts it and runs KiCad's DRC
- **THEN** the board holds one `net_tie_pad_groups`, reads back with the group, and has the violations of the board without the line; without the group the line adds `clearance` and `solder_mask_bridge`

### Requirement: Board holes counted as changed
A conversion to KiCad SHALL count each board `Hole` that it writes as a board-only generated footprint under `hole` as changed: an unplated hole with `HOLE_REASON`, a plated one with `PLATED_REASON`. KiCad holds no hole outside a footprint (change c0167), so no hole changes kind without an entry (change c0420).

#### Scenario: An unplated hole
- **WHEN** `uv run pytest tests/unit/convert/test_convert_slots.py -k unplated -q` converts the committed slots document
- **THEN** the `hole` row counts every hole of the source as changed, with `HOLE_REASON`, and none as written or lost

### Requirement: Footprint texts of an imported footprint
A conversion to KiCad SHALL write each footprint's own texts (neither its designator nor its comment) as
`fp_text user` children of the board footprint and of its library footprint, after the footprint's drawings
and before its pads, on the layer the conversion maps, with the text's string, size, stroke, justification
and angle on the board, mirrored on a back layer (change c0422).
- The report MUST count each such text under `footprint-text` and MUST NOT report it lost.
- A text on a layer without a KiCad row MUST stay a `footprint-text` loss with its reason.
- `import --to python` of an Altium source MUST vendor library footprints that hold the texts.

#### Scenario: Texts and drawings of an authored Altium document
- **GIVEN** the authored document of `tests/_fpcontent.py`: footprints with a silkscreen arc, a filled
  silkscreen polygon and rectangle, drawings on three mechanical layers, two free texts on R1 (silkscreen and
  mechanical) and one mirrored free text on the bottom LED
- **WHEN** `uv run pytest tests/unit/convert/test_footprint_content.py -q` converts it to KiCad and imports it
  to Python
- **THEN** the report counts 3 texts and 13 drawings, all written and none lost, with no `convert.lossy`
  warning of a footprint kind; the board footprints hold each drawing on its silkscreen or on the user layer
  named after its mechanical layer, and each text after the drawings and before the pads, the bottom one
  mirrored; the derived and the vendored libraries hold the 3 texts

#### Scenario: KiCad keeps the texts
- **GIVEN** the authored document converted to KiCad for the running major
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/convert/test_footprint_content_oracle.py -q` runs
- **THEN** the board loads, and on 10.0 a re-save keeps every `fp_text` with its string, layer, place, angle
  and mirror

#### Scenario: Public boards lose no footprint text
- **GIVEN** the public rows `altium-third-party-pcbdoc-01` to `-08`
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_convert_altium_census.py -k converted_reports -q`
  converts each to KiCad
- **THEN** the `footprint-text` row of rows `-02`, `-03`, `-04`, `-06`, `-07` and `-08` counts 4, 46, 3, 25,
  12 and 554 texts written and none lost, and every other loss is as before

### Requirement: Generated models of imported bodies
A conversion to KiCad SHALL write each imported component body as a STEP model file of Fenolite's own writer, beside the derived library, unless its embedded model carries it, and count it under `body` as changed.
- An extruded body MUST become the prism over its outline from standoff to overall height; a cylinder (`MODEL.MODELTYPE` 2) with a square outline and no turn about X or Y a faceted cylinder; a sphere (3) whose outline side equals its height span a faceted sphere; any other of these the prism over its outline.
- A body of unknown geometry MUST be a `body` loss with its reason; `body` and `model` losses MUST give `convert.lossy` warnings.

#### Scenario: Every body type
- **GIVEN** the authored PCB document of `tests/_altium_models.py` with extruded, cylinder, sphere and embedded-model bodies, its models turned about X, Y and Z on the top and the bottom
- **WHEN** `uv run pytest tests/unit/convert/test_body_models.py -q` converts it to KiCad
- **THEN** the report holds no `body` and no `model` loss, every footprint names its model files, and each generated file is the STEP solid of its body

#### Scenario: KiCad shows the source pose
- **GIVEN** the same conversion
- **WHEN** `uv run pytest tests/kicad/convert/test_altium_model_pose.py -q` exports each component with `kicad-cli pcb export stl` on 9.0.9 and 10.0.6
- **THEN** every model vertex lies within 2 µm of where the source's pose puts it, and every generated body's vertices lie on its shape

### Requirement: Fate of every Altium rule record
The conversion of an Altium board to KiCad SHALL give each rule record of the source document exactly one fate, from the one table `convert.altium_rules.FATES`: written, changed, kept, or lost.
- A record MUST be lost only when it is malformed.
- A disabled record and a record of a kind KiCad cannot hold MUST be kept, with a reason that names the format limit.
- A rule that the KiCad lowering refuses MUST be kept when it came from a kept record.
- The per-kind group losses `unmapped-rule-group-<n>` MUST NOT be reported.
- Kept rules MUST be reported by one `convert.kept` info per kind.

#### Scenario: One rule of each kind
- **GIVEN** an authored PCB document with one rule record of each kind of the table and one disabled record
- **WHEN** `uv run pytest tests/unit/convert/test_altium_rule_fates.py` converts it to KiCad
- **THEN** the row `rule` lists no lost item, every record is written, changed or kept, and the written rules file holds the silk, courtyard, pair and `disallow track` rules

### Requirement: Limits the KiCad rule cannot take
When the KiCad lowering refuses an imported rule only for a limit that the kind's KiCad constraint does not take, the conversion SHALL write the rule without that limit and report it as `changed`, and the model SHALL keep the limit.

#### Scenario: Preferred via drill
- **GIVEN** an imported Routing Via Style rule with a minimum, preferred and maximum hole
- **WHEN** it is converted to KiCad, and when the board is imported with `import --to python`
- **THEN** the rules file holds the via drill's `min` and `max`, the row `rule` lists the rule as changed, and `design.py` holds the drill limits

### Requirement: Shadowed imported rules keep Altium's order
The governing rule of two overlapping imported rules SHALL be the one with the higher Altium priority (the lower number), in the converted design and after `import --to python` and a build.

#### Scenario: A net rule below an All rule
- **GIVEN** an authored document whose clearance for all objects has priority 1 and whose clearance of one net has priority 2
- **WHEN** `uv run pytest tests/unit/convert/test_altium_rule_fates.py -k shadowed` imports it to Python and builds it
- **THEN** `rules.shadowed` names the All rule as governing over the net rule, as Altium applies them

### Requirement: Contents of an embedded board array's copies
Each placed copy of an Embedded Board Array SHALL carry what the referenced board holds, moved with the copy:
- each zone with its outline, a zone whose outline has arc vertices taking its record's flattened ring;
- each 3D model, placed in the frame of the original footprint by the referenced document's own model records;
- each board cut-out (a closed `Edge.Cuts` polygon), as a `cutout` change.

The ring check of the written board SHALL explain the copies' cut-outs, and each source cut-out that the written board merged with one of them, by the `cutout` row.

#### Scenario: Copies keep their models
- **GIVEN** an authored 2 × 2 panel whose referenced board is the authored document of change c0423, with its bodies and models
- **WHEN** `uv run pytest tests/unit/convert/test_embedded_arrays.py -q -k models` converts the panel
- **THEN** the report has no `model` and no `body` loss, and each copy's footprint names its models with the offset and rotation of the board converted alone

#### Scenario: Copies carry the cut-outs
- **WHEN** the referenced board holds one cut-out and the array has 4 copies
- **THEN** the converted design holds the cut-out 4 times, each at its copy's place (`uv run pytest tests/unit/convert/test_embedded_arrays.py -q -k cutouts`)

#### Scenario: A cut-out merged with a copy's cut-out
- **WHEN** the written board merged a source cut-out with a cut-out that a copy carries
- **THEN** the ring check explains the source ring and the merged ring by the `cutout` row, and explains neither when no copy carries a cut-out (`uv run pytest tests/unit/convert/test_embedded_arrays.py -q -k rings`)

### Requirement: Zones without an outline of a converted Altium board
A conversion to KiCad SHALL give each Altium zone that the import leaves without an outline, or with an outline of fewer than 3 points, the flattened outline of its `Polygons6` record, on the board and in an array's copies. A zone whose record is missing MUST be a `zone` loss that says so. A zone whose record encloses no area (its vertices coincide) pours no copper: it MUST be left out as a `changed` zone whose reason says so, not a loss.

#### Scenario: Records with arcs, without area and missing
- **WHEN** `uv run pytest tests/unit/convert/test_embedded_arrays.py -q -k arc_outlines` outlines three zones whose records are an arc ring, two vertices at one point, and none
- **THEN** the first takes the ring, the second is left out as enclosing no area, and the third as having no record

#### Scenario: A pour without area needs no consent
- **WHEN** `uv run pytest tests/unit/convert/test_to_kicad.py -q -k without_area` converts a zone whose record encloses no area
- **THEN** the zone is not written and is counted `changed`, and the report loses no zone

### Requirement: Duplicate designators of a converted Altium project
A conversion of an Altium project whose circuit holds one designator on several parts, at most one of them on the board, SHALL write its schematic. The part on the board (or the first, when none is) SHALL keep the designator, and each other part SHALL be written as `<ref>_<n>` on the schematic, with a `schematic` change; the design that the conversion verifies SHALL hold the same designators. When several parts on the board share a designator, the board MUST keep them and the schematic MUST be a `schematic` loss whose reason names them.

#### Scenario: A schematic part shares a placed part's designator
- **GIVEN** the blink project with one more schematic part that shares the designator `<ref>` of a placed part
- **WHEN** `uv run pytest tests/unit/convert/test_new_losses.py -q` converts it
- **THEN** the `schematic` row loses nothing, the schematic holds `<ref>` and `<ref>_2`, the board holds no `<ref>_2`, and the read-back leaves no difference of `<ref>` unexplained

#### Scenario: Two parts on the board share a designator
- **WHEN** the twin part is on the board too
- **THEN** the board keeps both designators and the `schematic` row loses the schematic with the reason that names the shared designator

### Requirement: Report and issues agree
The issues of a conversion SHALL agree with its report, for every kind of `KINDS`: one `convert.lossy`
warning per row with lost items, with the kind as `where` and the counts per lost reason, whatever the
kind's loss class; one `convert.changed` info per row with changed items; one `convert.kept` info per row
with kept items. A row without lost, changed or kept items MUST NOT have that issue. The refusal of a
`refuse` kind without `allow_lossy` is unchanged.

#### Scenario: A lost report kind warns
- **GIVEN** a report whose `rule` row (loss class `report`) has lost items
- **WHEN** the issues of the conversion are built with `allow_lossy`
- **THEN** one `convert.lossy` warning has `where` `rule`, and the conversion does not refuse without
  `allow_lossy`

#### Scenario: Every kind
- **GIVEN** for each kind of `KINDS` a report with one lost, one changed and one kept item of that kind
- **WHEN** its issues are built
- **THEN** the kinds of `convert.lossy`, `convert.changed` and `convert.kept` are each exactly that kind

### Requirement: Rule records through KiCad
A conversion of an Altium document to KiCad SHALL write the root board property `Fenolite.Altium.Rules6` into the `.kicad_pcb` (`convert.rulecarrier`, schema `fenolite.altium-rules.v0`, packed by `backends.kicad.boardcarrier`: zlib, then base64). It holds every rule record of the document, in record order: its kind number, its keys from `RULEKIND` on, and the SHA-256 of each rule list of `<name>.kicad_dru` that the record's rules gave, as written (`dru.rule_text`). No file is written beside the board. A conversion of a KiCad board to Altium SHALL read the property when the board holds it.
- A record all of whose rule lists are in the rules file as written, or that gave none, MUST be written as it was read (`lower.write_design(source_rules=…)`). The rules it gave MUST NOT be lowered again.
- A record whose rule lists were edited or removed MUST NOT be written from the property; the rules the project holds are lowered.
- A loss of a rule that came from such a record MUST be a loss of reason `SOURCE_RULE_LOST`, which needs `--allow-lossy`. A loss of a rule that only KiCad holds stays a loss of class `report`.
- The report's `rule` row MUST count the rules the written records stand for as source and written.

#### Scenario: Every record back as it was read
- **GIVEN** a document written by Fenolite with an authored Width (its own name, priority 3), an enabled and a disabled Clearance, a Height and a Minimum Solder Mask Sliver
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0434.py` converts it to KiCad and back
- **THEN** the KiCad board's property lists every record, the Width and the enabled Clearance with the hashes of their rule lists, no file lies beside the board, and the document written back holds every record as the source does, keys and values from `RULEKIND` on, and no other

#### Scenario: A rule edited in KiCad
- **GIVEN** the same KiCad project whose Width rule list now holds `(opt 0.2mm)`
- **WHEN** it is converted back
- **THEN** the other records are written as they were read and the Width record holds `PREFEREDWIDTH=7.874mil`

#### Scenario: A rule that KiCad lost needs consent
- **GIVEN** the same project whose Width rule list holds no `opt`, which no Width record can hold
- **WHEN** it is converted back without `--allow-lossy`
- **THEN** `LossyConversionError` names the kind `rule`, while a rule that only KiCad holds and that no record can hold is reported without refusal

#### Scenario: Public row -08
- **GIVEN** `altium-third-party-pcbdoc-08`, whose 56 rule records include 48 that KiCad holds no rule for
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_rules_c0434.py` converts it to KiCad and back with `--altium-pour outline`
- **THEN** the document written back holds the 56 records as the source does and the `rule` row loses none

### Requirement: Fenolite board properties
`fenolite.backends.kicad.boardcarrier` SHALL write data a conversion carries for the way back as root properties of a KiCad board, `(property "Fenolite.Altium.<Name>" "<value>")`, the value being the base64 text of the data's zlib compression. `with_carried` MUST write every such property in name order right after `setup` (after `layers` without one), replace a property of the same name, keep the others and change no other byte; `carried` MUST give back the bytes of each. A name outside `Fenolite.Altium.<Name>` MUST raise `ValueError`.

#### Scenario: Written, replaced, read back
- **GIVEN** the committed `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0434.py -k board_property` writes two properties and then one of them again
- **THEN** `carried` gives the newer value and the other, and the board without the property lines is the committed text

#### Scenario: KiCad keeps them
- **GIVEN** that board with a short property and one of 80 kB
- **WHEN** `uv run pytest tests/kicad/convert/test_board_carrier_oracle.py` exports it and re-saves it with `kicad-cli pcb upgrade --force` (10.0)
- **THEN** the export exits 0 and `carried` gives both values back after the re-save

### Requirement: Pour mode of a conversion to Altium

A conversion to Altium SHALL pour its polygons in the mode it is given, `computed` when none is given, and
SHALL NOT write them unpoured unless the mode `outline` is given. Without the `geo` extra, `computed`, the
default included, SHALL refuse the conversion: `convert_project` raises `BackendUnavailable`, and
`fenolite convert` exits 6 with `FEN-6001` (`where` `--altium-pour`), plans no file, and gives a hint that
names the `geo` extra and `--altium-pour outline`.

#### Scenario: The geo extra is missing

- **GIVEN** a KiCad board with polygons and no `geo` extra
- **WHEN** it is converted with `fenolite convert --to altium` and no `--altium-pour`
- **THEN** the command exits 6 with `FEN-6001`, plans nothing, and its hint names `fenolite[geo]` and
  `--altium-pour outline`
- **AND** with `--altium-pour outline` the same conversion exits 0 with no `altium.pour-unavailable` warning

### Requirement: Copper shapes keep their net

A conversion from KiCad to Altium SHALL give each copper graphic of the board the net its KiCad slot names,
as a build does, so a netted copper shape is written with its net.

#### Scenario: A netted copper polygon

- **GIVEN** the authored board `polygon_cutouts.kicad_pcb`, whose filled polygon on F.Cu is on net `A`
- **WHEN** it is converted to Altium and read back
- **THEN** the polygon is a region on Top with the net `A`, and nothing is unexplained

### Requirement: Altium round trip keeps the board
An Altium document converted to KiCad and that project converted back to Altium SHALL keep the board's
shape and connections (change c0441): every arc of the board ring comes back as an arc, every via and pad
comes back (a via whose hole equals its diameter included, a rounded-rectangle pad with its corner ratio),
a free copper region of a net comes back with that net,
and every pad and via is its source moved by one translation, to the nanometre.

#### Scenario: Vias and pads come back
- **GIVEN** the authored `routed` sample moved by 1 mm, its first via with a hole equal to its diameter
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_shape.py -k vias` takes it to KiCad and back
- **THEN** the report of the second conversion loses no via and no pad, and the pads and vias of the round
  trip are those of the source moved by one translation

#### Scenario: The board shape comes back
- **GIVEN** the `routed` sample with one corner rounded by a 5 mm arc, written as an Altium document
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_shape.py -k rounded` takes it to KiCad and back
- **THEN** the written outline holds one arc vertex, and `equivalent` at level 7 in the relative frame
  reports no difference of the board shape

#### Scenario: A region of a net comes back with it
- **GIVEN** the `routed` sample with a filled 2 mm square copper region of a net on `F.Cu`, written as an
  Altium document
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_shape.py -k region` takes it to KiCad and back
- **THEN** the copper graphic of the round trip has the same net

### Requirement: Keep-out strokes carry their form

A conversion of an Altium board to KiCad SHALL name each rule area made from a plain track, arc or circle
of the Keep-Out layer (one that has no keep-out record in the source document) with that stroke:
`Altium.KeepOut/line/x1/y1/x2/y2/w`, `/arc/x1/y1/xm/ym/x2/y2/w` or `/circle/cx/cy/ex/ey/w`, the second ring
of a circle with `/2` added. Numbers are nanometres in the frame of the area. A rule area from a drawing
with a keep-out record, or from a filled shape, SHALL have no such name.

#### Scenario: Plain strokes name their rule areas

- **GIVEN** a board drawing a line, an arc with a keep-out record, a circle and a filled square on the
  Keep-Out layer, and a footprint drawing a line there
- **WHEN** its drawings are converted into rule areas
- **THEN** the line's area, the circle's two areas and the footprint's area are named with their strokes,
  and the arc's and the square's areas have no name

### Requirement: Mask of imported vias
A design read from an Altium document SHALL be given, when it is converted to KiCad, `Board.mask_margin` from its untented vias (S-2041, S-2043):
- Each via that is untented on a side MUST give how far its mask opening extends beyond its copper. In the manual state (2 at offset 66 of its record) that is its own expansion. Otherwise it is the value of the record that governs the via (change c0462, design D6): the first enabled `SolderMaskExpansion` record, by priority, whose scope, read with the full grammar and the document, selects the via (its net, the net classes that hold it, its hole). With `SOLDERMASKFROMHOLE=TRUE` the value is measured from the hole: `(drill − diameter) / 2 + expansion`. A via without a value gives none.
- The board MUST take the most frequent value, the smaller on a tie. Each via with another value MUST be counted `changed` under `via`. So MUST a via that takes the rule while an enabled record that the conversion cannot judge for it comes first.
- With a margin other than 0, a pad that holds a mask layer and no margin of its own MUST get a margin of 0.
- Converted to Altium, the board's `pad_to_mask_clearance` (0 when absent) MUST become `Board.mask_margin` of the written model.

#### Scenario: A via record of one net
- **GIVEN** records of scope `InNet('GND')` (2 mil), `IsVia` (1 mil from the hole) and `All` (4 mil), in that order
- **WHEN** `uv run pytest tests/unit/convert/test_expansion_scopes_c0462.py -k via` reads them
- **THEN** a via on `GND` takes 2 mil, a via on another net 1 mil from the hole, and a pad on another net 4 mil

#### Scenario: A rule measured from the hole
- **GIVEN** 20 mil vias with a 10 mil hole in the rule state, under a rule of scope `IsVia` of 1 mil from the hole that comes before one of scope `All` of 3 mil
- **WHEN** `uv run pytest tests/unit/convert/test_via_mask_c0445.py` computes their margins
- **THEN** each via gives -4 mil, and a via in the manual state gives its own expansion

#### Scenario: The most frequent margin
- **GIVEN** two vias of -4 mil and one of 1 mil, and a board whose pads hold `F.Mask` with no margin, with 3 mil, and no mask layer
- **WHEN** the board is given its mask
- **THEN** its `mask_margin` is -4 mil, the ledger lists the third via `changed` under `via`, and the pads hold 0, 3 mil and no margin

#### Scenario: Row -01 back to Altium
- **GIVEN** the public row `altium-third-party-pcbdoc-01`, whose 646 vias are 20 mil with a 10 mil hole and take a rule of scope `IsVia` of 1 mil from the hole
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_via_mask_c0445.py` converts it to KiCad and back to Altium
- **THEN** the KiCad board holds `(pad_to_mask_clearance -0.1016)` and every via written back opens 12 mil, as in the source

### Requirement: Altium round trip keeps free pads
An Altium document converted to KiCad and that project converted back to Altium SHALL keep each free pad
as a free pad (change c0447): the KiCad footprint the first conversion makes for it (link
`<project>:FREE_<footprint id>`, no reference, one pad) is written back with no component, so the document
holds as many components as its source and no Designator or Comment text of an unnamed component.

#### Scenario: A free pad comes back free
- **GIVEN** the authored `routed` sample with one more free pad of a net, written as an Altium
  document
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_shape.py -n 0 -q -k free_pad` takes it to KiCad
  and back
- **THEN** the KiCad footprint of the pad is linked `routed:FREE_…`, and the round trip holds the source's
  components, one free pad at the pad's place (moved by the round trip's translation) with its net, and
  no component without a designator

### Requirement: Altium round trip keeps texts, values and library links
An Altium document converted to KiCad and that project converted back to Altium SHALL keep (change c0451):
each component's footprint link and symbol link as the source holds them, carried by the hidden KiCad
footprint properties `Altium Footprint` and `Altium Symbol` (`convert.altium_links`), which no Altium
parameter receives; each `Value` field, with an empty value too, on its layer and with its shown flag; and
each footprint text, an empty one too. A footprint link comes back only while the KiCad footprint's link
item is the name the conversion derived from the source pattern; otherwise neither property is used.

#### Scenario: Links and values come back
- **GIVEN** the authored `routed` sample whose `D1` has the footprint link `Lib_A:Mini_LED_THT_3mm` and the symbol link `Sym_A:Mini_LED`, whose `R1` has an empty value, and whose `U1` holds an empty text
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_texts.py -n 0 -q` takes it to KiCad and back
- **THEN** the KiCad footprint of `D1` holds the hidden properties `Altium Footprint` = `Lib_A:Mini_LED_THT_3mm` and `Altium Symbol` = `Sym_A:Mini_LED`; the round trip's `D1` holds those links and no such property; `R1` holds its hidden `Value` field; `U1` holds the empty text

#### Scenario: A swapped footprint drops the link
- **GIVEN** the KiCad project of that conversion with `D1` linked to another footprint
- **WHEN** the same test converts it to Altium
- **THEN** `D1` holds the conversion's own links, as before

### Requirement: Designators used twice explained by a lost schematic
When a conversion to KiCad loses the schematic because the imported circuit has duplicate designators, the `schematic` row SHALL explain, besides the components that only a schematic holds, the level 1 `ref-ambiguous` difference at each designator that the source circuit holds more than once (`Explains("schematic", ("component-missing", "ref-ambiguous"), "ref")`).

#### Scenario: Designator used twice
- **GIVEN** the public Altium blink's design with a second `R1`, made in memory, and a report whose `schematic` row is lost for duplicate designators
- **WHEN** `uv run pytest tests/unit/convert/test_report.py -k twice` asks its `Explainer`
- **THEN** the `ref-ambiguous` difference at `R1` (2 in the source, 1 or 0 written) is explained by `schematic`, one at `D1` (held once) is not, and without the lost row nothing is explained

### Requirement: Models of a KiCad board in an Altium target
The direction from KiCad to Altium SHALL embed each STEP model that a board footprint names and the source project holds, as a model body of that footprint's component ("Embedded model bodies" of `altium-pcb-writer`), and SHALL count every `model` child of a board footprint under the kind `model`: written, changed or lost (S-2080; `H-A-BODY-MODEL-PLACE`, `H-K-MODEL-POSE`).
- A child is embedded when its path, with `${KIPRJMOD}` or `$(KIPRJMOD)` read as the source project's folder, or relative to that folder, names a file inside it whose bytes start with `ISO-10303-21;`, its scale is 1 on each axis, and `stepbox.model_box` bounds its geometry. Any other child MUST be one `model` loss with its reason: a file that is not found, a path under another variable or outside the project, a KiCad embedded file (`kicad-embed://`), a file that is no STEP text, a scale other than 1, or a STEP whose geometry the reader cannot bound. A child of a footprint that is not written MUST be lost with that reason. A hidden model MUST be written and counted changed ("Altium has no hidden model"). Without `--altium-bodies extruded` (`bodies="off"`) a child that would be embedded MUST be lost with the reason of the bodies, and `Models` stays empty.
- The pose MUST be the inverse of "Model placement of imported footprints": `MODEL.2D.X/Y` the footprint's placement of the offset (its Y negated on the bottom side), `MODEL.3D.DZ` the offset's Z, and `MODEL.3D.ROTX/Y/Z` the turns of `Rz(−θ')·R`, where `R` is the child's rotation and `θ'` the footprint's rotation on the bottom side and its negation on the top.
- The outline MUST be the rectangle of the placed model's box in the footprint frame, placed as the footprint's pads are, and `STANDOFFHEIGHT` and `OVERALLHEIGHT` its lowest and highest Z.
- `stepbox.model_box(data)` MUST give the box, in nanometres in the model's frame, of the vertex points, the points of each circular or elliptic edge where a coordinate is extreme within the edge's span, and the control points of B-spline edges of the STEP text, each scaled by its context's length unit and moved into the root frame by the item-defined transformations of the representation relationships, the component of each relationship taken from the product structure (`H-G-STEP-BOX`); `None` for a text without such geometry.

#### Scenario: A model goes to Altium and comes back
- **GIVEN** the authored board `tests/data/kicad/convert/roundrect_roundtrip.kicad_pcb` with one footprint on the top turned by 90 degrees and one on the bottom, each naming `${KIPRJMOD}/m.3dshapes/box.step` (a box written by `backends.step` in the test) with an offset, a rise of 0.5 mm and a turn about Z
- **WHEN** `uv run pytest tests/unit/convert/test_embedded_models.py -k roundtrip` converts it to Altium and the document back to KiCad
- **THEN** the document holds one `Models` record whose stream inflates to the file's bytes and two model bodies whose outlines and heights are the placed box within 3 nm; the report's row `model` has `written` 2; and the KiCad board of the way back names a file with the same bytes at each footprint with the source's offset within 3 nm and the same turns

#### Scenario: Models that cannot be embedded
- **GIVEN** footprints that name a missing file, `${KICAD9_3DMODEL_DIR}/x.step`, a `.wrl` file beside the project, a scaled model and `kicad-embed://x.step`
- **WHEN** `uv run pytest tests/unit/convert/test_embedded_models.py -k losses` converts the board to Altium
- **THEN** the row `model` has `lost` 5, each with its own reason, `Models` is empty, and the conversion succeeds

#### Scenario: Public rows keep their models
- **GIVEN** the eight public PCB documents of the corpus manifest
- **WHEN** each is converted to KiCad and back to Altium
- **THEN** every model body of the source comes back as a model body whose model inflates to the same STEP text, at the same `MODEL.2D.X/Y` within 2.54 nm (after the board's offset), on the same side, with the same rotation and rise, and with an outline box and heights within the tolerance that `docs/formats/altium/pcb-bodies.md` records for the box reader (S-2081)

### Requirement: Keep-out fills named through KiCad

A conversion of an Altium design to KiCad SHALL name the rule area of each keep-out fill of copper of the
board and of its footprints `Altium.KeepOut/flag<r>/fill/<x1>/<y1>/…/<x4>/<y4>`, r its restriction byte and
the numbers its four corners in the frame of the area, when the area is still the fill's.

#### Scenario: A keep-out fill names its rule area

- **GIVEN** an Altium document with a keep-out fill of a component on the bottom layer
- **WHEN** it is converted to KiCad
- **THEN** the KiCad board holds one rule area of the footprint named `Altium.KeepOut/flag<r>/fill/…` with
  the fill's restriction byte and corners

### Requirement: Carried rule records matched by content
The board property `Fenolite.Altium.Rules6` SHALL key each rule list a record gave by two SHA-256 keys (`rulecarrier.rule_keys`, schema `fenolite.altium-rules.v1`, change c0457): its content and its shape. Both are taken over the rule's children after its name, each in compact form, in sorted order, with a condition in the form `rulecarrier.condition_key` gives (schema `fenolite.altium-rules.v2`): its parsed selectors when KiCad's closed grammar reads it, else its text with runs of spaces made one and balanced outer parentheses taken off. A property of schema `fenolite.altium-rules.v1` MUST still be compared with the keys of that version. The shape also leaves out the values of each constraint's `min`, `opt` and `max`. A conversion back to Altium (`rulecarrier.match`) MUST keep a record when each of its lists is a distinct rule of the rules file of the same content, one of its own name first. A rule of the same content as a rule a kept record took MUST be taken too and not lowered. A property of schema `fenolite.altium-rules.v0` MUST still be read: a list then matches a rule printed under the record's name with the same text.

#### Scenario: Rules written again under other names
- **GIVEN** a KiCad board converted from an authored Altium document, whose rules file is written again with every rule renamed, in reverse order, and with other spaces in its conditions
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k names` converts it back without `--allow-lossy`
- **THEN** every record comes back as the source holds it, and the `rule` row has no change and no loss

#### Scenario: Conditions of one meaning
- **GIVEN** `A.Type == 'Via' && A.NetClass == 'X'` with and without outer parentheses, with doubled spaces, and with each term in parentheses
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k meaning` keys them
- **THEN** they share one key, and a condition of another class does not

#### Scenario: A version 1 property
- **GIVEN** the same board with a version 1 property
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k version_1` converts it back
- **THEN** every record comes back as the source holds it

#### Scenario: A version 0 property
- **GIVEN** the same board with a version 0 property and one rule renamed
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k version_0` converts it back
- **THEN** every record comes back as the source holds it

### Requirement: Source rules edited in KiCad
A record whose rule lists are all rules of the file under their own names, of the same shapes, with other limits, SHALL be written with the limits KiCad holds and with its own name, priority, scopes and enabled state (`rulemap.edited_fields`). A key whose value did not change keeps its text. Its rules count `changed` under `rule` with the reason `to_altium.LIMITS_EDITED`. The rules of any other record not kept that are still in the file MUST be lowered as rules of their kind and count `changed` with `to_altium.EDITED_LOWERED`. Only such a rule that no Altium record can hold MUST be a loss of reason `SOURCE_RULE_LOST`.

#### Scenario: An edited limit
- **GIVEN** the same board whose scoped clearance of 10 mil (0.254 mm) holds 0.26 mm in the rules file
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k limit` converts it back without `--allow-lossy`
- **THEN** the record keeps its name, priority 2 and scope with `GAP` and `GENERICCLEARANCE` of `10.2362mil`, every other record comes back as read, and the `rule` row has one change and no loss

#### Scenario: An added condition
- **GIVEN** the same board whose unscoped clearance holds a condition on net `GND`
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k otherwise` converts it back
- **THEN** a Clearance record `Clearance_net_GND` of scope `InNet('GND')` is written, the record `Board Gap` is not, and the `rule` row counts one change and no `SOURCE_RULE_LOST`

#### Scenario: Flow A with one clearance edited
- **GIVEN** the authored Altium document imported with `import --to python`, whose script holds `design.rules.minimum(...)`, one clearance edited in `design.py` and built with `build`, which writes the via rule's condition in parentheses
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k imported` converts the board to Altium without `--allow-lossy`
- **THEN** `convert --to altium` exits 0, the edited record keeps its name and priority with the new gap, no other record changes, and the `rule` row counts one change (`LIMITS_EDITED`) and no loss

### Requirement: Board minimums of an imported design
A conversion back to Altium of a board that carries rule records SHALL NOT lower a rule that a build writes for `design.rules.minimum()` on the whole board (`rulecarrier.board_minimum`: named `fenolite_0_min_<constraint>`, without a condition or a layer, one constraint of that name holding a `min` alone) and that no record holds. When another rule of the file without a condition or a layer holds the same `min` of that constraint, the minimum MUST be taken without a report. Otherwise it MUST be a loss of reason `to_altium.BOARD_MINIMUM`, of the class `report`, which never needs `--allow-lossy`.

#### Scenario: A minimum no rule holds
- **GIVEN** the authored board with a rule `fenolite_0_min_via_diameter` of `min 0.3mm` added to its rules file
- **WHEN** `uv run pytest tests/unit/convert/test_rule_carrier_c0457.py -k board_minimum` converts it back without `--allow-lossy`
- **THEN** every record comes back as read, and the `rule` row loses one rule for `BOARD_MINIMUM`, class `report`

### Requirement: The pour of the way back follows the source
A document converted to KiCad and back to Altium with the computed pour SHALL pour what the computed pour of the source document pours. A Clearance record whose scope the pour does not read, carried back by the property, MUST refuse the polygons it could govern on the way back as it does in the source (`rule-scope`, then `depends-on-refused`), each reported `altium.zone-unpoured`, and the polygon itself MUST be written.

#### Scenario: Public row -04
- **GIVEN** public row `altium-third-party-pcbdoc-04`, whose source pour refuses its 9 polygons (4 `rule-scope`, 5 `depends-on-refused`) under a Clearance record of unread scope
- **WHEN** `uv run pytest tests/corpus/test_altium_pour_c0457.py` converts it to KiCad and back with the computed pour
- **THEN** the way back reports 9 `altium.zone-unpoured` and no `altium.zones-poured`, writes the 9 polygons, and loses no rule

### Requirement: Model paths read as KiCad reads them
The direction from KiCad to Altium SHALL find the file of a footprint's `model` child as KiCad finds it ("Models of a KiCad board in an Altium target", change c0449; `docs/formats/kicad/libraries.md`, "3D models"): `${KIPRJMOD}` or `$(KIPRJMOD)` is the folder of the source board, a relative path is read from that folder, an absolute path where it is, and a path that climbs out of the folder is followed (change c0458).
- A path under a variable other than `KIPRJMOD`, and a KiCad embedded file, MUST keep their c0449 losses.
- An absent file MUST be lost with the reason "the model file is not found in the project folder" when the path lies inside the folder, and "the model file is not found at its path" otherwise. A Windows drive path read on another system names no file.

#### Scenario: Model paths outside the project
- **GIVEN** a project folder and, beside it, a folder holding a STEP box
- **WHEN** `uv run pytest tests/unit/convert/test_built_models.py -k paths` resolves the box's absolute path, `${KIPRJMOD}/../shared/box.step`, `$(KIPRJMOD)/../shared/box.step` and `../shared/box.step`
- **THEN** each names the box; an absent file outside the folder gives "not found at its path", inside it "not found in the project folder"

#### Scenario: A built design converted to Altium
- **GIVEN** the build of "A built project keeps its own models" (capability design-dsl)
- **WHEN** `uv run pytest tests/unit/convert/test_built_models.py -k copies` converts its board to Altium
- **THEN** the row `model` has `written` 1, and the two official models are lost under their variable

### Requirement: Frame-bound Altium storages are not carried

A conversion of an Altium design to KiCad SHALL NOT carry the `BoardRegions` storage of the source PCB
document, whose records hold the source's geometry in its frame and name its layer stack by id, nor its
`CustomMaskShapes` storage, whose content no public source shows. It SHALL count each lost under
`altium-storage` when it holds data, and a conversion back to Altium SHALL NOT write a
`Fenolite.Altium.BoardRegions` or `Fenolite.Altium.CustomMaskShapes` board property that a KiCad board
holds.

#### Scenario: The board region stays behind

- **GIVEN** an Altium document whose `BoardRegions` storage holds a record
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the KiCad board holds no `Fenolite.Altium.BoardRegions` property, the report counts
  `BoardRegions` lost under `altium-storage`, and the written document does not hold the source's record

#### Scenario: A custom mask shape stays behind

- **GIVEN** an Altium document whose `CustomMaskShapes` storage holds a record
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the report counts `CustomMaskShapes` lost under `altium-storage` with a reason that says its
  content is not known, and the written document does not hold the source's record

### Requirement: Altium classes of every kind through KiCad

A conversion of an Altium design to KiCad SHALL carry as board properties:
- every record of `Classes6` that is no net class and no super class (`Classes6.Kept`);
- the records of `SignalClasses` that are no super class (`SignalClasses.Kept`);
- the `PINPAIR` keys of `Board6` (`Board6.PinPairs`);
- `DifferentialPairs6`.

The conversion back SHALL write each carried record as it was, its members unchanged. It SHALL leave out a
class whose kind and name the writer wrote, and a differential pair whose two nets the written document
does not hold. Each such pair SHALL be counted lost under `altium-storage`. A board property
`Classes6.Component` of change c0450 SHALL read as `Classes6.Kept`.

#### Scenario: Classes of every kind survive the round trip

- **GIVEN** an Altium document that holds:
  - a component class;
  - a class of component classes (kind 5), one of whose members names nothing;
  - a net class whose name differs from it in case alone;
  - a class of differential pairs;
  - an xSignal class and its xSignal;
  - a differential pair of two nets of the board
- **WHEN** it is converted to KiCad and back to Altium
- **THEN** each of those records comes back byte for byte, and the xSignal keys stand in `Board6`
- **AND** no `Default` net class and no sheet class of the writer stand beside them

### Requirement: Internal planes on the way to KiCad

A conversion of an Altium design to KiCad SHALL count each Split Plane polygon of an internal plane in the
copper chain lost under `plane`, with a reason. It SHALL count the plane itself when the plane holds none.

#### Scenario: A split plane is counted lost

- **GIVEN** a four-layer Altium document whose second layer is a plane on `GND`, with its one Split Plane
  polygon
- **WHEN** it is converted to KiCad
- **THEN** the report holds one `plane` loss, a refused kind

### Requirement: The Altium frame travels through KiCad

A conversion of an Altium design to KiCad SHALL write the source board's origin (`ORIGINX`, `ORIGINY`), in
the frame of the design, and the low corner of the KiCad board's edge as a board property
`Fenolite.Altium.Frame`. A conversion of a KiCad board that carries it back to Altium SHALL write the board
at its KiCad coordinates, Y negated, with the origin at the carried origin moved by the translation of the
edge's corner. When that would put a point of the outline at a negative coordinate, the conversion SHALL
anchor the board at its corner, as before, and report the change under `outline`.

#### Scenario: Row -04 comes back where it was

- **GIVEN** the public row `altium-third-party-pcbdoc-04`, whose origin lies 29.528 mil above its
  outline's low corner
- **WHEN** it is converted to KiCad and the KiCad board back to Altium
- **THEN** the written `ORIGINX`, `ORIGINY` and outline vertices equal the source's

#### Scenario: Flow A keeps the frame

- **GIVEN** the public row `altium-third-party-pcbdoc-04` imported with `import --to python` and built
- **WHEN** the built board is converted to Altium
- **THEN** the written origin, outline vertices and component positions equal the source's

#### Scenario: A board moved in KiCad keeps its origin with it

- **GIVEN** a converted board whose items KiCad moved by (10 mm, 5 mm)
- **WHEN** it is converted back to Altium
- **THEN** the written origin is the source's moved by (10 mm, −5 mm) in Altium's frame

### Requirement: A converted schematic keeps the source drawing

A conversion between Altium and KiCad of a source that holds schematic sheets SHALL write the source's
drawing, extracted by the backend's drawn extractor, through the drawn writer of the target. A generated
schematic MUST be written only for a source without sheets. For every item of the source drawing, the
written drawing SHALL keep:

- the sheet;
- the position, within 1 nm;
- the rotation and mirror;
- the pin points and the text;
- for a symbol, its part and display mode.

#### Scenario: Altium sheets to KiCad

- **GIVEN** the authored project `tests/data/altium/blink/blink.PrjPcb`
- **WHEN** `fenolite convert <project> --to kicad --out out --confirm --json` runs
- **THEN** level S between the source drawing and the drawing extracted from `out` finds no difference
- **AND** `kicad-cli` 10.0.6 loads every written sheet, and its netlist equals the source circuit

#### Scenario: KiCad sheets to Altium

- **GIVEN** a public KiCad 10.0.6 demo project of the corpus with several sheets
- **WHEN** it is converted to Altium and the written sheets are read back
- **THEN** level S between the source drawing and the read-back drawing finds no difference

#### Scenario: Board alone keeps the generated schematic

- **GIVEN** an Altium PCB document converted alone
- **WHEN** it is converted to KiCad
- **THEN** the schematic is generated, and the report counts it under `schematic` with the reason
  "the source has no schematic sheets"

### Requirement: Converted symbols keep their source graphics

A conversion between Altium and KiCad SHALL write each component with its source symbol:

- the body graphics;
- every part and display mode;
- each pin's position, length, orientation, name, number, electrical type, visibility and decoration.

A pin decoration or graphic that the target cannot draw MUST be written as the closest form the target
holds and counted `changed`, with its reason, under `symbol-graphic` or `pin`.

#### Scenario: Multi-part symbol

- **GIVEN** an authored Altium sheet with a two-part component whose parts sit on different sheets
- **WHEN** it is converted to KiCad
- **THEN** the KiCad symbol has two units with the source's graphics and pins
- **AND** each unit is placed where its part was

### Requirement: Schematic report per object

The report of a conversion that writes a drawing SHALL hold one row for each of these kinds:

- `sheet`, `schematic-symbol`, `symbol-graphic`, `pin`;
- `wire`, `junction`, `label`, `port`, `power`, `bus`, `bus-entry`, `sheet-symbol`, `harness`;
- `no-connect`, `directive`, `schematic-text`, `schematic-graphic`, `image`, `title-block`.

Each row SHALL hold `source`, `written`, `changed` and `lost`, with reasons. The single row `schematic`
MUST NOT be written for such a conversion.

#### Scenario: Rows of the blink project

- **GIVEN** the conversion of `tests/data/altium/blink/blink.PrjPcb` to KiCad
- **WHEN** its report is read
- **THEN** it holds a `wire` row whose `source` equals the number of wires of the source sheet
- **AND** no row named `schematic` is present

### Requirement: Schematic items carried through the other format

An item of a source sheet that the target format cannot hold SHALL be carried in the target. The carrier
for Altium items in KiCad is `Fenolite.Altium.Sheet`, schema `fenolite.altium-sheet.v0`, stored as
canonical JSON in the title-block `comment 9` of each written sheet, which KiCad keeps on a save and its
default worksheet does not draw. The carrier for KiCad items in Altium is the document parameter
`Fenolite.KiCad.Sheet`, schema `fenolite.kicad-sheet.v0`. On the way back the conversion SHALL write the
carried items again, moved with the item that stands for them. Each carried item MUST be counted
`changed`, not `lost`.

#### Scenario: KiCad keeps the carrier on a save

- **GIVEN** a sheet written with a carrier
- **WHEN** `kicad-cli` 10.0.6 saves it again (`kicad-cli sch upgrade --force`)
- **THEN** the carrier read from the saved sheet equals the written one

#### Scenario: Harness through KiCad

- **GIVEN** the authored project `tests/data/altium/hier/altium_hier.PrjPcb`, which holds no PCB document
- **WHEN** its drawing is written to KiCad by the drawing writer of the conversion, read back, and written
  to Altium the same way
- **THEN** level S between the source drawing and the final drawing finds no difference, the harness items
  included

#### Scenario: Hierarchical board through KiCad

- **GIVEN** the Altium project built from the authored example `examples/altium_hier_board` with module
  sheets
- **WHEN** it is converted to KiCad and the KiCad project back to Altium
- **THEN** level S between the source drawing and the final drawing finds no difference, the sheet symbols
  and their entries included

### Requirement: Schematic conversion verified at level S

A conversion that writes a drawing SHALL run level S between the source drawing and the drawing read
back from the written files. It SHALL also compare the resolved drawn netlist with the circuit. A
difference that no report row explains MUST give `convert.unexplained` and exit 5, unless the conversion
ran with `--no-verify`.

#### Scenario: An unexplained moved symbol

- **GIVEN** a test writer that moves one symbol by 1 mm and reports nothing
- **WHEN** the conversion runs
- **THEN** it gives `convert.unexplained` naming that symbol's component path and unit

