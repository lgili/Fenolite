## MODIFIED Requirements

### Requirement: Zones in a build
`fenolite build` SHALL write every zone that the script declares, with its settings, for targets 9 and 10, and the written board SHALL read back with those zones.
- `lens.build.build_design` MUST keep the `Board.zones` of the model it is given, an addition to "Built project files" that needs no keyword. The writer follows `kicad-file-backend` "Zone settings are written" for these created zones.
- Read back with `read_board`, each zone MUST have the script's name, outline, layers, net, priority and `locked`, `settings.effective()` equal to the script's, and `filled == False`.
- A build over an existing board MUST merge zones as `layout-lens` "Zones declared in the script" describes.
- `fenolite build --target altium` MUST keep one copper source (`altium-build`, "Copper in an Altium build"). Without `--copper-from` and without copper intents, the script's zones are the zones of the model source. With copper intents and without `--copper-from`, `cmd_build` MUST give the build the model without the script's zones: the script source holds them, as the in-memory KiCad build keeps them (`altium-build`, "Script copper in an Altium build"). With `--copper-from`, `cmd_build` MUST give the build the model without the script's zones: the routed board is the copper source, and its zones stand for the `zone()` calls that the KiCad build wrote into it.

#### Scenario: Blink with a pour on both targets
- **GIVEN** a blink variant with `d.zone(gnd, layers=("B.Cu",), clearance=mm(0.3), connection="solid")`
- **WHEN** it is built for targets 9 and 10 with `--confirm`, and each written board is read with `read_board`
- **THEN** the exit code is 0, each board holds a zone `GND` on `B.Cu` with `clearance == 300_000` and `connection == "solid"`, and only the target-9 text holds `(filled_areas_thickness no)`

#### Scenario: Altium build of a script with a zone
- **GIVEN** a confirmed target-10 build of the pour variant in `B`
- **WHEN** the script is built with `--target altium --confirm`, and again into another folder with `--copper-from B/blink.kicad_pcb`
- **THEN** both exit codes are 0, `result.copper.source` is `model` and then `board`, and `result.copper.zones` is 1 in both

#### Scenario: Zone uuid from the name
- **GIVEN** the same variant built twice into empty folders
- **WHEN** the two board texts are compared
- **THEN** they are byte-identical, and the zone's uuid is `pcb.kicad_uuid` of a zone with id `derived_id("zon", "dsl", "zone:GND")`

#### Scenario: Altium build of a script with a zone and copper intents
- **GIVEN** a variant of `examples/blink_routed/design.py` with `design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.copper.source` is `script` and `result.copper.zones` is 1
