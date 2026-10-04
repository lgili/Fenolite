## ADDED Requirements

### Requirement: Zones in the DSL
`Design.zone(net, *, layers, name=None, outline=None, priority=0, clearance=None, min_thickness=None, connection=None, thermal_gap=None, thermal_spoke_width=None, islands=None, min_island_area=None, locked=False)` SHALL declare one copper zone, and `dsl.to_model` SHALL put one model `Zone` per declared zone into `Board.zones`, in name order. This adds zones to the `Board` of "DSL to model".
- `board()` MUST have been called first. `layers` MUST be a non-empty sequence of distinct copper layer names of the board: `F.Cu` and `B.Cu`, and also `In1.Cu` and `In2.Cu` for `copper=4`.
- `net` MUST be a `Net`, which joins the design, or `None` for a zone without a net. `name` defaults to the net's name, and is required when `net` is `None`. Zone names MUST be unique, non-empty and without surrounding spaces.
- `outline` is `None`, which means the board rectangle, or at least three `(x, y)` pairs of lengths in the board frame of "Board and placements in the DSL". Points are written with `BOARD_ORIGIN` added.
- A setting given as `None` MUST take the `ZoneSettings` default. Lengths follow "DSL lengths and angles". `clearance` MUST be at least 0, and `min_thickness`, `thermal_gap` and `thermal_spoke_width` above 0.
- `connection` MUST be one of `solid`, `thermal`, `none` and `thru_hole_only`, and `islands` one of `always`, `never` and `below_area`.
- `min_island_area` MUST be a string with the unit `mm2`, such as `"2.5mm2"`, converted exactly to square nanometres, and is accepted only together with `islands="below_area"`.
- `priority` MUST be an `int` of at least 0, and `locked` a `bool`.
- Each violation MUST raise `DslError` at the call, naming the argument.
- The model zone MUST have the id `derived_id("zon", "dsl", "zone:<name>")` (`design-model`, "Identifier derivation"), `name`, the layers, the net's id, `priority`, `locked`, the settings, `filled == False` and no fills. Hatching and smoothing are not DSL arguments and keep their defaults.

#### Scenario: Pour with a 0.3 mm clearance
- **GIVEN** a design with `board(mm(50), mm(30))` and `d.zone(gnd, layers=("F.Cu", "B.Cu"), clearance=mm(0.3))`
- **WHEN** `to_model(d)` runs
- **THEN** `board.zones` holds one zone named `GND`, with layers `("F.Cu", "B.Cu")`, the id of net `GND`, `settings == ZoneSettings(clearance=300_000)`, and the outline points (100 mm, 100 mm), (150 mm, 100 mm), (150 mm, 130 mm) and (100 mm, 130 mm)

#### Scenario: Zone before the board
- **WHEN** `d.zone(gnd, layers=("F.Cu",))` is called before `board()`
- **THEN** `DslError` is raised

#### Scenario: Inner layer on a two-layer board
- **GIVEN** a design with `board(mm(50), mm(30))`
- **WHEN** `d.zone(gnd, layers=("In1.Cu",))` is called
- **THEN** `DslError` is raised naming `In1.Cu`

#### Scenario: Bare number refused
- **WHEN** `d.zone(gnd, layers=("F.Cu",), clearance=0.3)` is called
- **THEN** `DslError` is raised naming `clearance`

#### Scenario: Island area needs below_area
- **WHEN** `d.zone(gnd, layers=("F.Cu",), islands="never", min_island_area="2mm2")` is called, and then `d.zone(vin, layers=("B.Cu",), islands="below_area", min_island_area="2mm2")`
- **THEN** the first raises `DslError` naming `min_island_area`, and the second gives a zone with `min_island_area == 2_000_000_000_000`

#### Scenario: Names are unique
- **GIVEN** `d.zone(gnd, layers=("F.Cu",))`
- **WHEN** `d.zone(gnd, layers=("B.Cu",))` is called, and then `d.zone(gnd, layers=("B.Cu",), name="GND_BOTTOM")`
- **THEN** the first raises `DslError` naming the name `GND`, and the second is accepted

### Requirement: Zones in a build
`fenolite build` SHALL write every zone that the script declares, with its settings, for targets 9 and 10, and the written board SHALL read back with those zones.
- `lens.build.build_design` MUST keep the `Board.zones` of the model it is given, an addition to "Built project files" that needs no keyword. The writer follows `kicad-file-backend` "Zone settings are written" for these created zones.
- Read back with `read_board`, each zone MUST have the script's name, outline, layers, net, priority and `locked`, `settings.effective()` equal to the script's, and `filled == False`.
- A build over an existing board MUST merge zones as `layout-lens` "Zones declared in the script" describes.
- `fenolite build --target altium` MUST keep one copper source (`altium-build`, "Copper in an Altium build"). Without `--copper-from`, the script's zones are the zones of the model source. With `--copper-from`, `cmd_build` MUST give the build the model without the script's zones: the routed board is the copper source, and its zones stand for the `zone()` calls that the KiCad build wrote into it.

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
