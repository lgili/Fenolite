## ADDED Requirements

### Requirement: Outline shapes in the DSL
`Design.cutout(path)` SHALL add one cut-out to the board, a path SHALL describe one closed ring for `board(outline=…)` ("Board and placements in the DSL") and for `cutout()`, and the module `fenolite.dsl.shape` SHALL give `rect`, `circle` and `slot`, which return paths. `fenolite.dsl` MUST re-export `shape`, as "DSL package" allows, and the package keeps importing only the standard library, `core` and `model`.
- `board()` MUST have been called before `cutout()`; cut-outs keep their call order.
- A path is a sequence whose first element is an `(x, y)` pair of lengths in the frame of `place()`, and whose other elements are such pairs and `ArcStep`s from `arc_to(mid, end)` (`design-dsl`, "Copper intents in the DSL"). Its vertices are the first point and the end point of every other element. Each element after the first is the edge from the vertex before it to its end: straight for a pair, the arc through `mid` for an `ArcStep`. When the last element ends at the first point it closes the ring, and that point is not a second vertex; otherwise a straight edge from the last vertex to the first closes it.
- `DslError` MUST be raised at the call, naming the call and the index of the element, for: a path that is not a sequence or is empty; a first element that is not a pair; an element of another type; two consecutive vertices at the same point, the closing edge included; an arc step whose `mid` equals one of its ends or lies on the line through them; a ring of one vertex, or of two vertices without an arc.
- `shape.rect(x, y, width, height, *, radius=None)` is the rectangle with the corners `(x, y)` and `(x + width, y + height)`, starting at the left end of its top edge and running along the top edge first, as the rectangle of `board(width, height)` does. `width` and `height` MUST be positive. With `radius`, `0 < radius ≤ min(width, height) / 2`, each corner is a quarter arc of that radius whose mid is the corner's centre moved by `radius / √2` on both axes towards the corner, each coordinate rounded half to even; a straight edge of length 0 is left out.
- `shape.circle(x, y, diameter)` is the ring of the two vertices `(x + r, y)` and `(x − r, y)`, joined by the arcs through `(x, y − r)` and `(x, y + r)`, with `r = diameter / 2`. `diameter` MUST be a positive, even number of nanometres; the circle is exact.
- `shape.slot(start, end, width)` is the stadium whose round ends are centred on the two `(x, y)` pairs `start` and `end`, which MUST differ, with `width` a positive, even number of nanometres; its overall length is `|end − start| + width`. With `u` the unit vector from `start` to `end`, `n = (−u_y, u_x)` and `h = width / 2`, its vertices are `start − h·n`, `end − h·n`, `end + h·n` and `start + h·n`, joined by a line, the arc through `end + h·u`, a line and the arc through `start − h·u`. Each coordinate is rounded half to even once with integer arithmetic, so a horizontal or vertical slot is exact.
- The helpers return tuples of pairs and `ArcStep`s, which a script may also write by hand. Rings that cross or touch, and cut-outs outside the board, are refused by the build ("Outline shapes in a build").

#### Scenario: Rounded corners
- **WHEN** `shape.rect(mm(0), mm(0), mm(60), mm(40), radius=mm(3))` is given to `board(outline=…)` and `to_model` runs
- **THEN** the board ring has eight vertices, its second edge is the arc from (157 mm, 100 mm) through `Point(159_121_320, 100_878_680)` to (160 mm, 103 mm), and `Outline.arcs` holds four entries of ring 0

#### Scenario: A round cut-out
- **GIVEN** `board(mm(60), mm(40))` and `d.cutout(shape.circle(mm(10), mm(10), mm(3.2)))`
- **WHEN** `to_model` runs
- **THEN** `Outline.cutouts` holds the ring (111.6 mm, 110 mm), (108.4 mm, 110 mm), and `Outline.arcs` holds `OutlineArc(1, 0, Point(110_000_000, 108_400_000))` and `OutlineArc(1, 1, Point(110_000_000, 111_600_000))`

#### Scenario: A horizontal slot
- **WHEN** `shape.slot((mm(10), mm(20)), (mm(20), mm(20)), mm(2))` is given to `cutout()` and `to_model` runs
- **THEN** the cut-out's vertices are (110 mm, 119 mm), (120 mm, 119 mm), (120 mm, 121 mm) and (110 mm, 121 mm), and its arcs pass through (121 mm, 120 mm) and (109 mm, 120 mm)

#### Scenario: Refused paths
- **WHEN** `d.cutout(())`, `d.cutout(((mm(1), mm(1)), (mm(1), mm(1)), (mm(2), mm(5))))`, `d.cutout(((mm(0), mm(0)), arc_to((mm(1), mm(0)), (mm(2), mm(0)))))`, `shape.circle(mm(5), mm(5), nm(3))` and `shape.slot((mm(1), mm(1)), (mm(1), mm(1)), mm(1))` are called after `board()`, and `d.cutout(shape.circle(mm(5), mm(5), mm(2)))` on a design without `board()`
- **THEN** each raises `DslError`, the second naming element 1 and the third naming the arc step

### Requirement: Outline shapes in a build
`lens.build.build_design` SHALL run `fenolite.backends.kicad.outline.check_outline(design)` (`kicad-file-backend`, "Outline shape checks") on the model it is given, before placing, and SHALL take the keyword-only argument `lock_outline: bool = False`, which it passes to `lens.preserve.merge_layout` (`layout-lens`, "Outline changes across rebuilds"); `cmd_build` SHALL pass `dsl.outline_locked(design)`. This requirement adds a step and a keyword to "Built project files", and codes that pass "Build issue codes" unchanged.
- An error of the check MUST stop the build: no file is returned, and `build` exits 5.
- The written board MUST hold the outline as `kicad-file-backend` "Outline lowering" writes it, and `board_outline` of the board read back MUST give the script's rings, its arcs polygonised.
- A design whose outline is the rectangle of `board(width, height)` without cut-outs MUST build every file as before, apart from the uuids of its edge lines ("Outline lowering").

#### Scenario: A rounded board with cut-outs
- **GIVEN** a blink variant with `board(outline=shape.rect(mm(0), mm(0), mm(50), mm(30), radius=mm(2)))`, `d.cutout(shape.circle(mm(45), mm(5), mm(3.2)))` and `d.cutout(shape.slot((mm(10), mm(25)), (mm(20), mm(25)), mm(1)))`
- **WHEN** it is built with `--confirm` for targets 9 and 10
- **THEN** the exit code is 0, `Edge.Cuts` holds 6 `gr_line` and 8 `gr_arc`, every arc with a positive `orient2d(start, mid, end)`, and `issues` holds no `kicad.outline.*` code

#### Scenario: A cut-out across the edge stops the build
- **GIVEN** the blink with `board(mm(50), mm(30))` and `d.cutout(shape.circle(mm(49), mm(15), mm(4)))`
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds one `kicad.outline.invalid` naming `cut-out 1` and `board`, and nothing is written

#### Scenario: The lock reaches the merge
- **GIVEN** the blink with `board(mm(50), mm(30), locked=True)`
- **WHEN** `uv run pytest tests/unit/lens/test_build_outline.py -k lock` builds it over an existing board
- **THEN** `outline_locked(design)` is true and `merge_layout` receives `lock_outline=True`

### Requirement: Board holes in the DSL
`Design.hole(ref, x, y, *, drill, length=None, rot=0, pad=None, courtyard=None, locked=True) -> Part` SHALL add and place one part that stands for a hole, whose symbol and footprint `fenolite.dsl.holes` generates in the library `Fenolite_Holes` (`holes.HOLE_LIBRARY`).
- `ref` follows "Design structure and names", and the part's path is `ref`, at the top of the design.
- `drill` MUST be a positive length. `length` MUST be `None` or a length above `drill`: the hole is then a slot of that overall length along the footprint's X axis. `pad` MUST be `None`, for a hole that is not plated, or a length above `drill`, the width of its copper. `courtyard` MUST be `None` or a length at least the width of the hole and of its copper. `rot` is an angle as in `place()`, and `locked` a `bool`. Any other value MUST raise `DslError` at the call, naming the argument.
- The footprint (`holes.hole_footprint`) MUST hold one pad at its origin. Without `pad`: an `np_thru_hole` pad numbered `""` ("Unnumbered hole pads in authored footprints") whose size is the hole's, `drill` × `drill`, or `length` × `drill`. With `pad`: a `thru_hole` pad numbered `1` whose size is `pad` × `pad`, or `(length + pad − drill)` × `pad`. The shape is `circle` for a round hole and `oval` for a slot, the layers are `*.Cu` and `*.Mask`, the drill is `drill` (a slot of length `length` along X), the kind is `unspecified` and the flags are `exclude_from_pos_files` and `exclude_from_bom`. A courtyard on `F.CrtYd` and on `B.CrtYd`, drawn 0.05 mm wide, is a circle of diameter `courtyard` for a round hole and, for a slot, a rectangle `courtyard` wide that exceeds the length of the hole, or of its copper, by as much as it exceeds its width. Without `courtyard`, the courtyard takes the width of the copper, or of the hole.
- The footprint is named `NPTH_<d>mm` or `NPTH_Slot_<d>x<l>mm` without `pad`, and `PTH_<d>mm_Pad_<p>mm` or `PTH_Slot_<d>x<l>mm_Pad_<p>mm` with it, followed by `_Courtyard_<c>mm` when `courtyard` is given, each length in millimetres as `core.units.format_length` prints it.
- The symbol (`holes.hole_symbol`) is `Fenolite_Holes:Hole`, a `SymbolDef` without pins, or, for a plated hole, `Fenolite_Holes:Hole_Pad` with one passive pin `1`; both with the reference prefix `H`, `in_bom` false and `on_board` true.
- The part is `Part(ref, <symbol lib id>, footprint=<footprint lib id>, value=<footprint name>)`, placed at `(x, y)` with `rot`, on the top side, with `locked`. A plated hole joins a net with `connect(net, part[1])`.
- Each definition MUST be registered once per lib id, the footprint in `Design.footprints` and the symbol among the design's symbols; registering another definition under one of these lib ids, the user's own included, MUST raise `DslError` naming it.
- A script hole is this part and nothing else: `to_model` MUST NOT add a `Hole` to `Board.holes` for it. `Board.holes` stays the model field that a reader fills (an Altium board), and `pcb.write_board` keeps refusing it for KiCad. `Design.hole` is the one call of the DSL that declares a hole.

#### Scenario: A round hole that is not plated
- **WHEN** `d.hole("H1", mm(3), mm(3), drill=mm(3.2))` is called after `board()`
- **THEN** the design holds the part `H1` with `lib_id == "Fenolite_Holes:Hole"` and `footprint == "Fenolite_Holes:NPTH_3.2mm"`, `placements(d)["H1"]` is `Placement(Point(103_000_000, 103_000_000), 0, "top", True)`, and the footprint's one pad is numbered `""`, of kind `np_thru_hole`, shape `circle`, size 3.2 mm × 3.2 mm and drill 3.2 mm, with a 3.2 mm courtyard circle on `F.CrtYd` and on `B.CrtYd`

#### Scenario: A plated slot on a net
- **WHEN** `h2 = d.hole("H2", mm(10), mm(3), drill=mm(1), length=mm(3), pad=mm(2), rot=90)` and `connect(gnd, h2[1])` are called
- **THEN** `h2` uses `Fenolite_Holes:Hole_Pad` and `Fenolite_Holes:PTH_Slot_1x3mm_Pad_2mm`, whose pad `1` is a `thru_hole` `oval` of 4 mm × 2 mm with a 1 mm drill slotted to 3 mm along X, and the net `GND` holds `PinRef(<H2 id>, "1")`

#### Scenario: Equal holes share a definition
- **WHEN** `d.hole("H1", mm(3), mm(3), drill=mm(3.2))` and `d.hole("H2", mm(47), mm(3), drill=mm(3.2))` are called
- **THEN** `Design.footprints` holds `Fenolite_Holes:NPTH_3.2mm` once

#### Scenario: Refused holes
- **GIVEN** `d.hole("H1", mm(3), mm(3), drill=mm(3.2))`
- **WHEN** `d.hole("H3", mm(1), mm(1), drill=mm(0))`, `d.hole("H3", mm(1), mm(1), drill=mm(1), pad=mm(1))`, `d.hole("H3", mm(1), mm(1), drill=mm(1), length=mm(1))`, `d.hole("H3", mm(1), mm(1), drill=mm(2), courtyard=mm(1))` and `d.hole("H1", mm(9), mm(9), drill=mm(2))` are called
- **THEN** each raises `DslError`, naming `drill`, `pad`, `length`, `courtyard` and the path `H1`

### Requirement: Board holes in a build
`fenolite build` SHALL build the parts of `Design.hole()` as parts with authored definitions (`dsl-footprint-authoring`, and the authored symbols of c0058), with no step of its own: the built project MUST hold `lib/Fenolite_Holes.pretty/<name>.kicad_mod` for each hole footprint used, `lib/Fenolite_Holes.kicad_sym` with the hole symbols used, their table rows, and one footprint per hole at its part's placement.
- The written footprint MUST carry the flags, the pad and the two courtyards of its definition. KiCad drills, lists and judges it as `kicad-oracle` "Outline shapes and holes pass the oracle" proves.
- The placement guard ("Placement legality in a build") MUST judge a hole by its courtyards, on both sides.
- A rebuild over the build's own output MUST write the same bytes, holes included.
- A hole part is a part for the layout lens, with no rule of its own: `layout-lens`, "Placement precedence" places it (it is locked by default, so the script's position wins over the board and over an entry of `placements.toml`, with `layout.place-forced` when they differ), and `fenolite sync --to-source` lists it in `placements.toml` with the other parts ("Placement extraction", "Placements file").
- `--target altium` follows `altium-build`, "PCB document output": a round hole that is not plated is written as a board hole, and a slot or a plated hole is reported.

#### Scenario: Holes in a build
- **GIVEN** a blink variant with `d.hole("H1", mm(4), mm(4), drill=mm(3.2))`, `h2 = d.hole("H2", mm(46), mm(4), drill=mm(3.2), pad=mm(6))` and `connect(gnd, h2[1])`
- **WHEN** it is built with `--confirm` for target 10 and the board is read with `read_board`
- **THEN** the exit code is 0, `H1`'s pad is `""` of kind `np_thru_hole`, `H2`'s pad `1` is on `GND`, both footprints have the attributes `exclude_from_pos_files` and `exclude_from_bom`, and the written files include `lib/Fenolite_Holes.pretty/NPTH_3.2mm.kicad_mod`, `lib/Fenolite_Holes.pretty/PTH_3.2mm_Pad_6mm.kicad_mod` and `lib/Fenolite_Holes.kicad_sym`

#### Scenario: A hole over a part
- **GIVEN** the same variant with `d.hole("H3", mm(32), mm(9), drill=mm(1), courtyard=mm(3))`, whose courtyard overlaps that of `R1`
- **WHEN** it is built with `--dry-run`
- **THEN** `issues` holds one `place.courtyard-overlap` warning for the footprints of `H3` and `R1`

#### Scenario: Holes rebuild to the same bytes
- **GIVEN** a confirmed target-9 build of the variant of "Holes in a build"
- **WHEN** it is built again
- **THEN** every file keeps its bytes

#### Scenario: A hole in the placements file
- **GIVEN** a confirmed target-10 build of the variant of "Holes in a build"
- **WHEN** `fenolite sync --to-source` runs on it
- **THEN** `placements.toml` holds the tables `[part."H1"]` and `[part."H2"]`, each with `locked = true`, and a build that follows gives no `layout.place-forced` and no `layout.source-stale` for them

## MODIFIED Requirements

### Requirement: Board and placements in the DSL
`Design.board(width=None, height=None, copper=2, planes=None, *, outline=None, locked=False)` SHALL declare the board's outline, its copper layer count and its internal planes, and `Part.place(x, y, rot=0, side="top", locked=False, anchor=None)` SHALL request a placement, both in a board-relative frame.
- The frame has its origin at the top-left corner of the outline given by `width` and `height`, with Y down; an outline given by `outline` is a path in that frame ("Outline shapes in the DSL"), wherever it lies. `BOARD_ORIGIN` MUST be `Point(100_000_000, 100_000_000)`, a Fenolite choice: the frame's origin is written at `BOARD_ORIGIN`, the rectangle from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)`, and a part placed at `(x, y)` at `BOARD_ORIGIN + (x, y)`.
- Exactly one form MUST be given: `width` and `height`, both positive lengths, or `outline`, a path. Both forms, or neither, MUST raise `DslError`. `copper` MUST be an `int` of `fenolite.dsl.design.COPPER_COUNTS`, which MUST be `(2, 4, 6, 8)` and equal `layers.CREATED_COPPER_COUNTS` of the KiCad backend; any other value, a `bool` or a `float` included, MUST raise `DslError` naming those counts.
- `locked` MUST be a `bool`. With `True`, the script's outline replaces an outline edited in KiCad when the board is rebuilt (`layout-lens`, "Outline changes across rebuilds"). `outline_locked(design) -> bool` (`dsl/convert.py`, re-exported by `fenolite.dsl` as "DSL package" allows) MUST return it, and false before `board()` is called.
- `inner_layers(copper)` (`dsl/design.py`) MUST return the inner copper layer names `In1.Cu` … `In<copper − 2>.Cu`, top to bottom, and an empty tuple for `copper=2`. `Design.copper_layers` MUST return `("F.Cu", *inner_layers(copper), "B.Cu")` for the declared count, and `("F.Cu", "B.Cu")` before `board()` is called.
- An inner copper layer is a signal layer unless `planes` names it. `planes` MUST be `None` or a mapping from an inner layer name of the count (`inner_layers(copper)`) to a `Net` or a net name: that layer is an internal plane on that net. `DslError` MUST be raised at the call for `planes` with `copper=2`, a key that is not an inner layer name of the count (the message names those layers), and a value that is neither a `Net` nor a valid net name. A plane holds one net; split planes cannot be declared.
- `Design.planes` MUST hold the mapping from layer name to net name, in layer order, empty by default. `planes(design) -> Mapping[str, str]` (`dsl/convert.py`, re-exported by `fenolite.dsl` as "DSL package" allows) MUST return it and MUST raise `DslError` naming a net that the design does not hold.
- A plane is a build parameter, as `copper` is: `to_model` MUST NOT change, the model gets no plane entity, and a plane layer stays a layer of kind `copper`. What a target does with a plane is its build's rule ("Planes in a build").
- `rot` is the model rotation, the stored footprint angle on both sides (c0017).
- `placements(design) -> Mapping[str, Placement]` MUST map each placed component path, in path order, to `Placement(at, rotation, side, locked, anchor=None)`. Unplaced parts MUST be absent.

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

#### Scenario: A board given by a path
- **GIVEN** `design.board(outline=((mm(0), mm(0)), (mm(40), mm(0)), (mm(40), mm(30)), (mm(10), mm(30))), copper=4, locked=True)`
- **WHEN** `to_model(design)` and `outline_locked(design)` are called
- **THEN** the outline points are (100 mm, 100 mm), (140 mm, 100 mm), (140 mm, 130 mm) and (110 mm, 130 mm), and `outline_locked(design)` is true

#### Scenario: One form only
- **WHEN** `design.board(mm(50), mm(30), outline=shape.circle(mm(20), mm(20), mm(40)))`, `design.board()` and `design.board(mm(50))` are called on fresh designs
- **THEN** each raises `DslError`

An `anchor` SHALL be a `MechanicalIntent` and SHALL require `locked=True`. It SHALL be retained in the DSL `placements` output only; build and rebuild do not persist it in native files or `.fenolite/`.

#### Scenario: Anchor requires a lock
- **WHEN** `Part.place` is called with an anchor and `locked=False`
- **THEN** it raises `DslError` naming `locked=True`

### Requirement: DSL to model
`dsl.to_model(design) -> fenolite.model.Design` SHALL convert a DSL design into model types only, with the ids of `design-model` "Identifier derivation" (fourth case).
- **Circuit.** One `Component` per added part, with `ref`, `value`, `lib_symbol_ref`, `lib_footprint_ref` (empty when `Part.footprint` is `None`), empty `pins`, empty `path` and `properties` holding `"fenolite.path"` mapped to the component path and every entry of `Part.properties` ("User properties in the DSL"), keys in code-point order. Nets whose `PinRef.pin` holds the designator as written. Net classes with `Net.netclass_id`. Interfaces. One `Module` per DSL module, with `path`, `parent` and `component_ids`.
- **Board.** A keyed `Board` without layers and footprints, or no outline when `board()` was not called. Its `Outline` holds the board ring in `points`, the cut-outs in call order in `cutouts`, and the arcs of both in `arcs` (`design-model`, "Board outline arcs"), each ring converted as "Outline shapes in the DSL" reads its path, with `BOARD_ORIGIN` added. A board given by `width` and `height` has the rectangle from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)` in the order of c0017's "Outline lowering", and no arc.
- **Other layers.** A keyed `RuleSet` holding the rules of "Rule minimums in the DSL" (empty without a `minimum()` call), a keyed `Manifest` and a keyed header named after the design.
- Every object MUST have `provenance = None`, so no absolute user path reaches `.fenolite/`.
- `to_model` MUST NOT call `Design.validate()`, MUST NOT resolve libraries, and MUST NOT change the DSL design.

#### Scenario: Blink in the model
- **GIVEN** the DSL design of `examples/blink_2layer/design.py`
- **WHEN** `to_model` runs
- **THEN** `R1` has `lib_symbol_ref == "Mini:Mini_R"`, `lib_footprint_ref == "Mini:Mini_R_0603"`, `pins == ()`, `path == ""` and `properties == {"fenolite.path": "R1"}`, and the outline points are (100 mm, 100 mm), (150 mm, 100 mm), (150 mm, 130 mm) and (100 mm, 130 mm)

#### Scenario: Designators as written
- **GIVEN** `connect(gnd, u1["GND"])`
- **WHEN** `to_model` runs
- **THEN** the net `GND` holds `PinRef(<U1 id>, "GND")`

#### Scenario: No provenance and no absolute path
- **WHEN** the texts of `canonical.dump_texts(to_model(design))` are searched for the absolute path of the script folder
- **THEN** no text contains it, and no entity has a provenance

#### Scenario: User properties in the model
- **GIVEN** `Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330", properties={"Supplier code": "S-1", "Part number": "PN-330"})` added to a design
- **WHEN** `to_model` runs
- **THEN** the component `R1` has `properties == {"Part number": "PN-330", "Supplier code": "S-1", "fenolite.path": "R1"}`, with its keys in this order

#### Scenario: Cut-outs in call order
- **GIVEN** `board(mm(50), mm(30))`, then `d.cutout(((mm(5), mm(5)), (mm(10), mm(5)), (mm(10), mm(8))))` and `d.cutout(shape.circle(mm(40), mm(15), mm(4)))`
- **WHEN** `to_model` runs
- **THEN** `Outline.cutouts` holds the triangle and then the circle's two vertices, and `Outline.arcs` holds two entries, both of ring 2

### Requirement: Zones in the DSL
`Design.zone(net, *, layers, name=None, outline=None, priority=0, clearance=None, min_thickness=None, connection=None, thermal_gap=None, thermal_spoke_width=None, islands=None, min_island_area=None, locked=False)` SHALL declare one copper zone, and `dsl.to_model` SHALL put one model `Zone` per declared zone into `Board.zones`, in name order. This adds zones to the `Board` of "DSL to model".
- `board()` MUST have been called first. `layers` MUST be a non-empty sequence of distinct copper layer names of the board, those of `Design.copper_layers`: `F.Cu`, the inner layers `In1.Cu` … `In<copper − 2>.Cu` and `B.Cu` ("Board and placements in the DSL"). The message of a refused name MUST list the board's copper layers.
- `net` MUST be a `Net`, which joins the design, or `None` for a zone without a net. `name` defaults to the net's name, and is required when `net` is `None`. Zone names MUST be unique, non-empty and without surrounding spaces.
- `outline` is `None`, which means the box of the board ring, or at least three `(x, y)` pairs of lengths in the board frame of "Board and placements in the DSL". Points are written with `BOARD_ORIGIN` added. The box of the board ring is the smallest axis-aligned rectangle that holds its vertices and the mid points of its arcs, written from its top-left corner in the order of the board rectangle; for `board(width, height)` it is the board rectangle. Cut-outs do not change it: KiCad clips a fill to the board.
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

#### Scenario: Zone on a round board
- **GIVEN** a design with `board(outline=shape.circle(mm(20), mm(20), mm(40)))` and `d.zone(gnd, layers=("B.Cu",))`
- **WHEN** `to_model(d)` runs
- **THEN** the zone's outline points are (100 mm, 100 mm), (140 mm, 100 mm), (140 mm, 140 mm) and (100 mm, 140 mm)
