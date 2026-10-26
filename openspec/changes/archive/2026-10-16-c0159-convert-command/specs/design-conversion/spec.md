## ADDED Requirements

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
- **GIVEN** a KiCad board with one custom pad and two pads without a number
- **WHEN** it is converted to Altium with `allow_lossy=True`
- **THEN** the row `pad` has `lost` 3 and two reasons, one with count 2 and one with count 1

### Requirement: Conversion kinds
`fenolite.convert.report.KINDS` SHALL be a closed table with, per kind, a `group` and a `loss` class, `refuse` or `report`. Every kind of `lower.LOSS_KINDS` and the kind `dnp` MUST be `refuse`, and every kind that a registered direction's writer names MUST be a row of `KINDS`. A report's `lossy` MUST be true when any row has `lost` above 0, and its `refused` MUST name the `refuse` kinds with losses.

#### Scenario: Vocabulary is closed
- **WHEN** `uv run pytest tests/unit/convert/test_report.py -k closed` collects the kinds that `lower` can report and the kinds of every registered direction
- **THEN** each is a row of `KINDS`

### Requirement: Lossy conversions need consent
A conversion whose report has a `refuse` kind with losses SHALL raise `fenolite.convert.LossyConversionError` (`cli_code` `FEN-7001`) unless `allow_lossy` is true; the error MUST carry one issue per such kind, with the kind as `where` and the counts per reason in the message. With `allow_lossy` the conversion MUST complete and give one `convert.lossy` warning per such kind.

#### Scenario: Exit 7 without consent
- **GIVEN** the KiCad 10.0.6 demo board `RoyalBlue54L-Feather` in the corpus
- **WHEN** `fenolite convert <board> --to altium --out out --dry-run --json` runs, and again with `--allow-lossy`
- **THEN** the first exits 7 with `FEN-7001` and issues whose `where` include `pad` and `dnp`, and the second exits 0 with a plan and `convert.lossy` warnings for the same kinds

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
In the report of the direction from KiCad to Altium, a polygon written unpoured (kind `zone-fill`) and a schematic generated from the circuit (kind `schematic`) SHALL be counted under `changed`, not `lost`, each under its reason.

#### Scenario: Unpoured polygon is a change
- **GIVEN** the routed two-layer KiCad sample, whose board holds a filled zone
- **WHEN** it is converted to Altium
- **THEN** the row `zone-fill` has `changed` above 0 and `lost` 0, and the row `schematic` has `changed` 1 and `lost` 0

### Requirement: KiCad to KiCad direction
The direction from KiCad to KiCad SHALL, for a target major not older than the source's, write the board read from the source with `write_board` for the target, the project file updated from the source's, and the rules file re-written for the target. Schematic files MUST be copied unchanged when the source's major equals the target and MUST otherwise be reported as not converted.

#### Scenario: Version 9 project to KiCad 10
- **GIVEN** the blink example built for target 9
- **WHEN** `fenolite --kicad-version 10 convert <project> --to kicad --out out --confirm` runs and `kicad-cli` 10.0.6 runs DRC on `out/blink.kicad_pcb`
- **THEN** the board's header is `20260206`, the DRC reports the violation types of the source in 9.0.9, and the probe `convert-retarget` records `equal`

### Requirement: KiCad downgrade refused
A conversion from KiCad to KiCad whose target major is older than the source's SHALL raise `DowngradeRefusedError` (`FEN-7002`) until a direction for it is registered.

#### Scenario: Older target refused
- **GIVEN** a project whose board holds the header of KiCad 10
- **WHEN** `fenolite --kicad-version 9 convert <project> --to kicad --out out --dry-run` runs
- **THEN** the exit code is 7 with `FEN-7002`
