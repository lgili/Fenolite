## ADDED Requirements

### Requirement: Copper layer counts in a build
`fenolite build` SHALL write a board of every count of `COPPER_COUNTS` for targets 9 and 10, with the layer table of `layers.created_layers(copper)` (`kicad-file-backend`, "Created board header"), and SHALL treat each inner layer of that table as it treats `In1.Cu` and `In2.Cu` of a four-layer board.
- `lens.build.build_design(…, copper: int, …)` MUST take the script's count and pass it to `layers.created_layers`, which raises `ValueError` for a count outside `layers.CREATED_COPPER_COUNTS`. `cli/cmd_build.py` MUST pass `Design.copper` to the KiCad build and to the in-memory build of the Altium branch without a type suppression.
- Every `place_footprint` call MUST pass the copper names of that table ("Placement of built parts"), so a `*.Cu` pad covers every copper layer of a six- or eight-layer board.
- A zone on any copper layer of the table MUST be written as "Zones in a build" states, and script copper MUST resolve on any copper layer of the table (`track(layer=…)`, `via_step(to=…)`, `via(layers=…)`). A layer outside the table MUST give `kicad.copper.bad-layer` (error), as for two and four layers.
- The copper guard ("Copper guard before writing") MUST judge every copper layer of the table.
- With `--target altium` the count follows `altium-build`, "Script layer counts in an Altium build": the Altium build writes the same count.

#### Scenario: Six-layer build on both targets
- **GIVEN** a blink variant declared with `copper=6` and `d.zone(gnd, layers=("In4.Cu",))`
- **WHEN** it is built for targets 9 and 10 with `--confirm`, and each written board is read with `read_board`
- **THEN** each exit code is 0, the copper layers are `F.Cu`, `In1.Cu`, `In2.Cu`, `In3.Cu`, `In4.Cu` and `B.Cu` with the KiCad numbers 0, 4, 6, 8, 10 and 2 and no user name, pad `"1"` of `D1` (`Mini_LED_THT_3mm`) has those six copper layers in the built model and in the read-back board, and the zone `GND` is read back on `In4.Cu`

#### Scenario: Script copper on the deepest layer of eight
- **GIVEN** a blink variant declared with `copper=8` whose `LED_A` track holds `via_step(mm(36), mm(14), to="In6.Cu", …)` followed by a point and `via_step(mm(41.5), mm(17), to="B.Cu", …)`
- **WHEN** it is built for target 10 with `--confirm` and the board is read with `read_board`
- **THEN** the exit code is 0, the board holds a track of `LED_A` on `In6.Cu` and two vias of `LED_A`, and `issues` holds no `kicad.copper.*` error

#### Scenario: Layer outside the table
- **GIVEN** the same variant with one more track declared with `layer="In7.Cu"`
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds one `kicad.copper.bad-layer` that names `In7.Cu` and the eight copper layers, and nothing is written

## MODIFIED Requirements

### Requirement: Design structure and names
`Design(name)`, `Module(name)` and `Part(ref, lib_id, footprint=None, value="")` SHALL build a tree whose paths name every component, and SHALL raise `DslError` at the offending call for every structural error of this list.
- A design name MUST match `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, because it becomes the stem of the KiCad files. Module names and refs MUST match `[A-Za-z0-9_.+-]+`.
- `Design.add(*objs)` and `Module.add(*objs)` attach parts, modules, nets and interfaces. `Module.path` is the module name at the top and `<parent path>/<name>` below. A component path is `<module path>/<ref>` (`power/ldo/C1`), or `<ref>` at the top.
- Net names are global and literal. A module-local net is named by the script, for example `Net(f"{m.path}/FB")`.
- `DslError` MUST be raised for: a duplicate component or module path; a duplicate net, net-class or interface name; two distinct `Net` objects with one name; a net in two classes; a second `place()` or `board()`; a `copper` that is not an `int` of `COPPER_COUNTS` (2, 4, 6 and 8, "Board and placements in the DSL"); one designator connected to two nets; a `side` other than `top` and `bottom`; an invalid name or ref.
- Equal refs in different modules are not a DSL error. They are left to `Design.validate()` (`model.duplicate-ref`, exit 5 from `build`).

#### Scenario: Paths from modules
- **GIVEN** `Module("power")` holding `Module("ldo")` holding `Part("C1", "Mini:Mini_R")`, added to a design
- **WHEN** `part.path` is read
- **THEN** it is `"power/ldo/C1"`

#### Scenario: Two nets with one name
- **WHEN** `Net("GND")` and a second `Net("GND")` are both added to one design
- **THEN** `DslError` is raised at the second `add()` naming `GND`

#### Scenario: Placed twice
- **WHEN** `r1.place(mm(1), mm(1))` is called twice
- **THEN** the second call raises `DslError`

#### Scenario: Duplicate refs in two modules
- **GIVEN** a blink variant with modules `a` and `b`, each holding a part `R1` of `Mini:Mini_R`
- **WHEN** the design is built with `fenolite build ... --dry-run`
- **THEN** the exit code is 5 and `issues` holds `model.duplicate-ref`

#### Scenario: Invalid design name
- **WHEN** `Design("my board")` is called
- **THEN** `DslError` is raised naming the pattern

### Requirement: Board and placements in the DSL
`Design.board(width, height, copper=2, planes=None)` SHALL declare a rectangular board, its copper layer count and its internal planes, and `Part.place(x, y, rot=0, side="top", locked=False)` SHALL request a placement, both in a board-relative frame.
- The frame has its origin at the top-left corner of the outline, with Y down. `BOARD_ORIGIN` MUST be `Point(100_000_000, 100_000_000)`, a Fenolite choice: the outline is written from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)`, and a part placed at `(x, y)` is written at `BOARD_ORIGIN + (x, y)`.
- `width` and `height` MUST be positive lengths. `copper` MUST be an `int` of `fenolite.dsl.design.COPPER_COUNTS`, which MUST be `(2, 4, 6, 8)` and equal `layers.CREATED_COPPER_COUNTS` of the KiCad backend; any other value, a `bool` or a `float` included, MUST raise `DslError` naming those counts.
- `inner_layers(copper)` (`dsl/design.py`) MUST return the inner copper layer names `In1.Cu` … `In<copper − 2>.Cu`, top to bottom, and an empty tuple for `copper=2`. `Design.copper_layers` MUST return `("F.Cu", *inner_layers(copper), "B.Cu")` for the declared count, and `("F.Cu", "B.Cu")` before `board()` is called.
- An inner copper layer is a signal layer unless `planes` names it. `planes` MUST be `None` or a mapping from an inner layer name of the count (`inner_layers(copper)`) to a `Net` or a net name: that layer is an internal plane on that net. `DslError` MUST be raised at the call for `planes` with `copper=2`, a key that is not an inner layer name of the count (the message names those layers), and a value that is neither a `Net` nor a valid net name. A plane holds one net; split planes cannot be declared.
- `Design.planes` MUST hold the mapping from layer name to net name, in layer order, empty by default. `planes(design) -> Mapping[str, str]` (`dsl/convert.py`, re-exported by `fenolite.dsl` as "DSL package" allows) MUST return it and MUST raise `DslError` naming a net that the design does not hold.
- A plane is a build parameter, as `copper` is: `to_model` MUST NOT change, the model gets no plane entity, and a plane layer stays a layer of kind `copper`. What a target does with a plane is its build's rule ("Planes in a build").
- `rot` is the model rotation, the stored footprint angle on both sides (c0017).
- `placements(design) -> Mapping[str, Placement]` MUST map each placed component path, in path order, to `Placement(at, rotation, side, locked)`. Unplaced parts MUST be absent.

#### Scenario: Placement in board coordinates
- **GIVEN** `r1.place(mm(10), mm(5), rot=90, side="bottom", locked=True)`
- **WHEN** `placements(design)["R1"]` is read
- **THEN** it equals `Placement(Point(110_000_000, 105_000_000), 90_000_000, "bottom", True)`

#### Scenario: Unsupported copper count
- **WHEN** `design.board(mm(50), mm(30), copper=c)` is called on fresh designs for `c` equal to 3, 10, `True` and `6.0`
- **THEN** each call raises `DslError` naming the counts 2, 4, 6 and 8

#### Scenario: Six and eight copper layers
- **WHEN** `design.board(mm(50), mm(30), copper=6)` and, on another design, `copper=8` are called
- **THEN** `Design.copper_layers` is `("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")` for the first and adds `In5.Cu` and `In6.Cu` before `B.Cu` for the second, and `COPPER_COUNTS` equals `layers.CREATED_COPPER_COUNTS`

#### Scenario: Unplaced parts are absent
- **GIVEN** a design with `R1` placed and `R2` not placed
- **WHEN** `placements(design)` is called
- **THEN** its keys are exactly `("R1",)`

#### Scenario: Ground plane declared
- **GIVEN** `design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})`, where `gnd` is the net `GND` of the design
- **WHEN** `planes(design)` is read
- **THEN** it equals `{"In1.Cu": "GND"}`, and `to_model(design)` equals the model of the same script without `planes`

#### Scenario: Plane on a deep inner layer
- **WHEN** `design.board(mm(50), mm(30), copper=8, planes={"In6.Cu": gnd})` is called, and on a fresh design `design.board(mm(50), mm(30), copper=6, planes={"In5.Cu": gnd})`
- **THEN** `planes(design)` of the first equals `{"In6.Cu": "GND"}`, and the second raises `DslError` naming `In5.Cu` and the inner layers `In1.Cu` to `In4.Cu`

#### Scenario: Malformed planes fail at the call
- **WHEN** `design.board(mm(50), mm(30), planes={"In1.Cu": gnd})`, `design.board(mm(50), mm(30), copper=4, planes={"F.Cu": gnd})` and `design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": 3})` are called on fresh designs
- **THEN** each raises `DslError`, the second naming `F.Cu`

#### Scenario: Plane on a net that is not in the design
- **GIVEN** `design.board(mm(50), mm(30), copper=4, planes={"In2.Cu": "NOPE"})` and no net `NOPE`
- **WHEN** `planes(design)` is called
- **THEN** `DslError` is raised naming `NOPE`

### Requirement: Planes in a build
`fenolite build` SHALL hand the script's planes to the build of its target. This requirement extends "Build command" (a step of `cmd_build`) and "Build issue codes" (one code).
- `cmd_build` MUST call `planes(design)` with `to_model`, and a `DslError` it raises MUST become `DesignScriptError` (`FEN-3004`, exit 3) as "Build command" rules for `placements`.
- With `--target altium`, `cmd_build` MUST pass the mapping to `lens.altium.build_altium(…, planes=…)` (`altium-build`, "Internal planes in an Altium build").
- With the KiCad target the board is unchanged: the plane layer is written as the `signal` row of `layers.created_layers(copper)`, and the build MUST give one `build.plane-not-lowered` info per plane that names the layer and the net. Its hint MUST name the script call that draws that copper, `design.zone(<net>, layers=("<layer>",))` with the net and the layer of the plane, and MUST NOT send the user to the KiCad editor. `lens.build.BUILD_ISSUE_CODES` MUST gain `build.plane-not-lowered` with severity `info`, and `lens.build.plane_issues(planes)` MUST return those issues.
- A script without planes MUST build every file with the bytes it had before planes were added (change c0038), for both targets.

#### Scenario: Plane in a KiCad build
- **GIVEN** a blink variant with `design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 0, `issues` holds one `build.plane-not-lowered` info naming `In1.Cu` and `GND` whose hint names `design.zone` and `In1.Cu`, and the planned board equals the board of the variant without `planes`

#### Scenario: Plane on a six-layer board
- **GIVEN** a blink variant with `design.board(mm(50), mm(30), copper=6, planes={"In4.Cu": gnd})`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 0, `issues` holds one `build.plane-not-lowered` info naming `In4.Cu` and `GND` whose hint names `design.zone`, `GND` and `In4.Cu` and not "KiCad", and the planned board equals the board of the variant without `planes`

#### Scenario: Plane in an Altium build
- **WHEN** the variant of "Plane in a KiCad build" is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.copper.planes` is `{"In1.Cu": "GND"}`, and no `build.plane-not-lowered` is given

#### Scenario: Unknown plane net stops the build
- **GIVEN** a blink variant with `planes={"In1.Cu": "NOPE"}`
- **WHEN** it is built
- **THEN** the exit code is 3 and stderr carries `FEN-3004` naming `NOPE`

### Requirement: Zones in the DSL
`Design.zone(net, *, layers, name=None, outline=None, priority=0, clearance=None, min_thickness=None, connection=None, thermal_gap=None, thermal_spoke_width=None, islands=None, min_island_area=None, locked=False)` SHALL declare one copper zone, and `dsl.to_model` SHALL put one model `Zone` per declared zone into `Board.zones`, in name order. This adds zones to the `Board` of "DSL to model".
- `board()` MUST have been called first. `layers` MUST be a non-empty sequence of distinct copper layer names of the board, those of `Design.copper_layers`: `F.Cu`, the inner layers `In1.Cu` … `In<copper − 2>.Cu` and `B.Cu` ("Board and placements in the DSL"). The message of a refused name MUST list the board's copper layers.
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

#### Scenario: Zone on a deep inner layer
- **GIVEN** a design with `board(mm(50), mm(30), copper=8)`
- **WHEN** `d.zone(gnd, layers=("In6.Cu",))` is called, and then `d.zone(vin, layers=("In7.Cu",))`
- **THEN** the first gives a zone on `("In6.Cu",)`, and the second raises `DslError` naming `In7.Cu` and listing `F.Cu`, `In1.Cu` to `In6.Cu` and `B.Cu`

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
