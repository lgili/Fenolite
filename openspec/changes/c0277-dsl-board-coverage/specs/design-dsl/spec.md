## ADDED Requirements

### Requirement: Builds of up to thirty-two copper layers
`fenolite build` SHALL write a board of every count of `COPPER_COUNTS` as "Copper layer counts in a build" states, 10 to 32 included, with zones, planes, script copper, exports and the copper guard on every layer of the table. The stack-up rule of "Stack-up in the DSL" applies unchanged; no stack-up preset is added.

#### Scenario: Sixteen layers with planes
- **GIVEN** a blink variant with `copper=16`, `planes={"In1.Cu": gnd, "In14.Cu": vin}` and a track stepping to `In13.Cu` and back
- **WHEN** it is built for targets 9 and 10 with `--confirm` and each board is read with `read_board`
- **THEN** the exit code is 0, the board has 16 copper layers numbered as `created_layers(16)`, and the track on `In13.Cu` and its two vias are read back

### Requirement: Teardrop settings of vias in the DSL
`teardrop(*, max_length=None, max_width=None, length_ratio=None, width_ratio=None, curved=None, filter_ratio=None, two_segments=None, prefer_zones=None, enabled=True)` (exported by `fenolite.dsl`) SHALL return a model `Teardrop`; `Design.via` and `Design.via_table` SHALL take it as `teardrop=` (default `None`), and the via, or every via of the table, SHALL carry it. `max_length` and `max_width` MUST be positive lengths; the three ratios MUST be `int` parts per million from 0 to 1 000 000; `curved`, `two_segments` and `prefer_zones` MUST be bools or `None`; `enabled` MUST be a bool. A field of `None` MUST write nothing, so KiCad's default applies. Any other value, and a `teardrop=` that is not the value of `teardrop()`, MUST raise `DslError` naming the argument or the copper key.

#### Scenario: Settings on a via and a table
- **GIVEN** the blink with `design.via("tv", mm(5), mm(26), net=gnd, teardrop=teardrop(max_length=mm(1), length_ratio=500_000))` and a via table with `teardrop=teardrop(enabled=False)`
- **WHEN** it is built for targets 9 and 10 with `--confirm`
- **THEN** the via `tv` holds `(teardrops (best_length_ratio 0.5) (max_length 1) (enabled yes))` between `layers` and `net`, each via of the table `(teardrops (enabled no))`, a via without settings no `teardrops`, and a second build writes the same bytes

#### Scenario: Refused settings
- **WHEN** `teardrop(length_ratio=0.5)`, `teardrop(width_ratio=1_000_001)`, `teardrop(max_length=1)` and `design.via("v", mm(1), mm(1), net=gnd, teardrop={})` are called
- **THEN** each raises `DslError`, naming `length_ratio`, `width_ratio`, `max_length` and `via v: teardrop`

### Requirement: Teardrops in the DSL
`Design.teardrops(*, where=None, pads=True, vias=True, max_length=None, max_width=None, length_ratio=None, width_ratio=None, curved=None)` SHALL set teardrop settings on every matching pad and via of the built board; `None` omits the token so KiCad's default applies. Ratios are `int` parts per million. A pad or via matched by two calls MUST take the later call with `build.teardrops-overlap` (info). A via's own `teardrop=` wins over every call.

#### Scenario: Teardrops on a class
- **GIVEN** the blink with `d.teardrops(where=select.netclass("Default"), max_length=mm(1), length_ratio=500_000)`
- **WHEN** it is built with `--dry-run --json`
- **THEN** every pad and via of the class has a `Teardrop` with `max_length == 1_000_000`, `length_ratio == 500_000` and the other fields `None`, and `d.teardrops(length_ratio=0.5)` raises `DslError` naming `length_ratio`

### Requirement: Blind vias over the board in via tables
`Design.via_table` SHALL accept `kind="blind"` with `layers` naming the first and the last copper layer, a via KiCad writes (`docs/formats/kicad/board.md`: every via of the demo `RoyalBlue54L-Feather`), and the build SHALL write each row as `(via blind … (layers "F.Cu" "B.Cu") …)`. `Design.via` and `via_step` MUST keep refusing that span with `kicad.copper.bad-layer` ("Layers that do not fit the kind").

#### Scenario: Table and single via
- **GIVEN** the blink with `design.via_table("tt", …, kind="blind", layers=("F.Cu", "B.Cu"))` and, in a second script, `design.via("b", …, kind="blind", layers=("F.Cu", "B.Cu"))`
- **WHEN** both are built
- **THEN** the first writes the blind via with both layers and exits 0, and the second exits 5 with `kicad.copper.bad-layer`

### Requirement: Groups in the DSL
`Design.group(name, *members, locked=False, key=None)` SHALL declare one group; members are parts and keys of zones, rule areas, drawings and groups declared before it (keys of copper intents, images and verbatim items join with their tasks). A key that names no item or more than one, a member of two groups, no member or a repeated key (the key, else the name) MUST raise `DslError`; a group declared after its members cannot form a cycle. The model `Group` of `Board.groups` has the id `derived_id("grp", "dsl", "group:<key>")` and the sorted ids of its members. The KiCad writer SHALL write each group after the zones as `(group "name" (uuid …) [(locked yes)] (members …))`, a part by the uuid of its footprint, and a rebuild SHALL replace the group of the same uuid. An Altium build SHALL report each group as `altium.not-lowered` (info).

#### Scenario: A labelled block
- **GIVEN** the blink with `d.text("lbl", "PWR", …)` and `d.group("power", r1, d1, "lbl", locked=True)`
- **WHEN** `to_model(d)` runs
- **THEN** `board.groups` holds one locked group `power` whose members are the ids of `R1`, `D1` and the text `lbl`, and `d.group("other", r1)` raises `DslError` naming `R1`

#### Scenario: Groups written
- **GIVEN** the blink with `design.text("silk/logo", …)`, `design.group("logo", r1, "silk/logo", locked=True)` and `design.group("", "logo", d1, key="outer")`
- **WHEN** it is built for KiCad 9 and 10
- **THEN** the board ends with the two groups, `logo` locked with the uuids of R1's footprint and of the text, the unnamed one with the uuids of `logo` and of D1's footprint; a rebuild changes no byte, and after `locked=True` is removed a rebuild holds one `logo` group, unlocked

### Requirement: Parts not populated in the DSL
`Part(..., dnp=True)` (and `design.part(..., dnp=True)`) SHALL mark a part that is not populated: the model `Component.dnp` is true, the schematic symbol is written with `(dnp yes)` and the board footprint with the `dnp` attribute. A value that is not a bool MUST raise `DslError`.

#### Scenario: One part not populated
- **GIVEN** the blink whose R1 is `Part(..., dnp=True)`
- **WHEN** it is built for KiCad 9 and 10
- **THEN** R1's footprint attribute ends with `dnp`, no other footprint holds it, and the schematic holds one `(dnp yes)`

### Requirement: Board-only parts in the DSL
`Part(..., board_only=True)` (and `design.part(..., board_only=True)`) SHALL declare a part on the board only (change c0277). Its ref MUST be given, and MAY be any printable text without surrounding spaces, the empty text included; board-only parts MAY share a ref. `name=` MUST be given when the ref is not a name of the path alphabet. The model `Component.board_only` is true (left out of the canonical JSON when false), the build MUST NOT assign, renumber or lock its ref, its footprint SHALL carry KiCad's `board_only` attribute after its type atom, the generated schematic SHALL hold no symbol for it, and its value is the one `value=` gives (empty without it). A value of `board_only` that is not a bool MUST raise `DslError`.

#### Scenario: Stitching vias and a logo
- **GIVEN** the blink with three board-only parts: two of ref `STITCH1` named `stitch_1` and `stitch_2`, and one `REF**` named `logo`
- **WHEN** it is built for targets 9 and 10
- **THEN** their footprints hold `(attr smd board_only)`, no other footprint holds `board_only`, the schematic names neither `STITCH1` nor `REF**`, and the design lock holds no entry for them; `Part("REF**", …, board_only=True)` without a name raises `DslError`

### Requirement: User layers in the DSL
`Design.user_layers(count, *, names=None)` SHALL declare the user layers `User.1` … `User.<count>`, `count` an int from 1 to 45, once per design (change c0277). The model board SHALL hold them as `Layer` rows of kind `user`, a name of `names` as the `user_name` of its `kicad` bag; the build SHALL write them after `B.Fab` as `(39 + 2(k − 1) "User.<k>" user [user name])`, and a rebuild SHALL add a declared user layer the existing board lacks. A second call, a count outside 1 to 45, a name of a layer not declared or a user name that is not printable text MUST raise `DslError`.

#### Scenario: Nine user layers
- **GIVEN** the blink with `design.user_layers(9, names={"User.9": "plugins.config"})` and a text, a circle and a dimension on `User.2` and `User.4`
- **WHEN** it is built for targets 9 and 10, twice
- **THEN** the layer table ends with `(39 "User.1" user)` … `(55 "User.9" user "plugins.config")` after `(33 "B.Fab" user)`, the three items are on their layers, and the second build writes the same board

### Requirement: Free vias in the DSL
`Design.via(..., free=False)` and `Design.via_table(..., free=False)` SHALL take `free=True` for KiCad's free vias (change c0277): the model `Via.free` is true (left out of the canonical JSON when false), and the KiCad writer SHALL write `(free yes)` after the via's `layers` and before its protection children. A value that is not a bool MUST raise `DslError`.

#### Scenario: A free via and a free table
- **WHEN** the blink with `design.via("fv", …, free=True)` and `design.via_table("ft", …, free=True)` is built for targets 9 and 10
- **THEN** both vias hold `(free yes)` right after `layers` and before `net`

### Requirement: Placement rule areas in the DSL
`Design.rule_area(..., placement=None)` SHALL take the sheet a placement rule area of KiCad's multichannel tool places, as KiCad names it (`"/CH1/"`; change c0277): the model `Keepout.placement` holds it (left out of the canonical JSON when `None`) and the KiCad writer SHALL write `(placement (enabled yes) (sheetname …))` after the area's `keepout`. A rule-area name MAY hold a slash. An empty or unprintable `placement` MUST raise `DslError`.

#### Scenario: An automatic placement area
- **WHEN** the blink with `design.rule_area("auto-placement-area-/CH1/", …, placement="/CH1/")` is built for targets 9 and 10
- **THEN** the area's zone holds `(placement (enabled yes) (sheetname "/CH1/"))` right after its `keepout`

### Requirement: Images in the DSL
`Design.image(key, file, at, *, layer="F.SilkS", scale="1")` SHALL declare one board image of the PNG `file`, a path relative to the script folder, which the build reads. `scale` MUST be a positive decimal string. A missing file MUST give `build.image-missing` and a file that is not a PNG `build.image-format` (both errors); the file is a declared input of the build.

#### Scenario: Logo image
- **GIVEN** an authored `logo.png` beside the script and `d.image("logo", "logo.png", (mm(5), mm(5)), scale="0.5")`
- **WHEN** the design is built with `--dry-run --json`
- **THEN** the model holds one `Image` on `F.SilkS` with `scale == "0.5"` and the base64 text of the file, `result.board_items.images` is 1, and with the file removed the exit code is 5 with `build.image-missing`

### Requirement: More dimension kinds in the DSL
`Design.radial_dimension(key, center, edge, *, leader_length, layer="Dwgs.User")`, `Design.leader(key, start, knee, *, text, frame="none", layer="Dwgs.User")` and `Design.center_mark(key, center, edge, *, layer="Dwgs.User")` SHALL declare dimensions of the kinds `radial`, `leader` and `center`, with the checks, units, precision and text sizes of `dimension`.

#### Scenario: Three new kinds
- **WHEN** one call of each is declared on a board and `to_model(d)` runs
- **THEN** `board.dimensions` holds one `radial` with its `leader_length`, one `leader` with its `text` and `frame`, and one `center`, each with the id `derived_id("dim", "dsl", "dimension:<key>")`, and `d.leader("l2", …, frame="star")` raises `DslError` naming `frame`

### Requirement: Footprint-instance overrides in the DSL
`Part.override(*, clearance=None, mask_margin=None, paste_margin=None, paste_ratio=None, zone_connection=None, thermal_gap=None, thermal_spoke_width=None)` SHALL set footprint-level settings of this part's instance, once per part. `Part.edit_pad(number, **fields)` SHALL replace pad fields of this instance only. The model holds them in `FootprintInstance.overrides` and the instance pads.

#### Scenario: Override and an edited pad
- **GIVEN** a part `U1` whose footprint has pad `EP` of 3 × 3 mm, with `u1.override(clearance=mm("0.15"))` and `u1.edit_pad("EP", size=(mm("3.2"), mm("3.2")))`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the instance's `overrides.clearance` is 150 000, its pad `EP` is 3.2 × 3.2 mm, the vendored library footprint is unchanged, and `u1.edit_pad("NOPE", …)` gives `build.pad-unknown` (error)

### Requirement: Field fonts in the DSL
`Part.field` SHALL accept `bold=None`, `italic=None` and `face=None`; `bold` and `italic` MUST be bools and `face` a non-empty font name. The built `FootprintField` takes them, and they are left out of canonical JSON when unset.

#### Scenario: Bold reference
- **WHEN** `u1.field("Reference", dx=mm(0), dy=mm(-3), bold=True, face="KiCad Font")` is built
- **THEN** the field `Reference` of `U1` has `bold` true and `face == "KiCad Font"`, and a part without the arguments builds the same bytes as before this change

### Requirement: 3D model references in the DSL
`Part.model(name, *, offset=(0, 0, 0), rotation=(0, 0, 0), scale=("1", "1", "1"), hidden=False)` SHALL add one model reference to this part's instance; any call replaces the footprint's own list for the instance. `name` is a reference only, never read. Offsets are lengths, rotations angles, scales positive decimal strings.

#### Scenario: Model by name
- **WHEN** `u1.model("${KICAD10_3DMODEL_DIR}/Package_SO.3dshapes/SOIC-8.step", offset=(mm(0), mm(0), mm("0.1")))` is built
- **THEN** the instance holds one `ModelRef` with that name and a z offset of 100 000 nm, and no file is opened

### Requirement: Verbatim items in the DSL
`Design.verbatim(key, text, *, target="kicad_pcb")` and `Part.verbatim(key, text)` SHALL record one item kept as given: a board root child, a rule of the rules file (`target="kicad_dru"`) or a child of the part's footprint. `key` follows the drawing key rule and MUST be unique among verbatim items; `text` MUST be a non-empty string. The DSL MUST NOT parse it.

#### Scenario: Recorded, not parsed
- **WHEN** `d.verbatim("art/qr", "(barcode (at 120 80))")` and `d.verbatim("bad", "")` are called
- **THEN** the first is recorded with its text unchanged, and the second raises `DslError` naming `text`

### Requirement: Verbatim items in a build
The build SHALL parse each verbatim item and write it in place with every `uuid` atom replaced by `embed.placement_uuid(<key>, "/verbatim/<n>")` and nets rewritten as opaque content is. A parse failure, a refused head, a layer not on the board or an unknown net MUST give `build.verbatim-invalid`, `-head`, `-layer` or `-net` (error). Each item MUST give `build.verbatim-item` (info).

#### Scenario: Barcode kept
- **GIVEN** the blink with `d.verbatim("art/qr", '(barcode (at 120 80) (layer "F.SilkS") (text "X") (uuid "00000000-0000-4000-8000-000000000001"))')`
- **WHEN** it is built for target 10 with `--confirm`, twice
- **THEN** the board holds the `barcode` node with the derived uuid, `issues` hold one `build.verbatim-item` naming `art/qr` and `barcode`, and both builds write the same bytes

#### Scenario: Refused heads
- **WHEN** verbatim items headed `footprint`, `setup` and `layers` are built
- **THEN** the exit code is 5 with one `build.verbatim-head` per item and nothing is written

#### Scenario: Too new for target 9
- **GIVEN** a verbatim item holding a token that the target-9 inventory does not know
- **WHEN** it is built for target 9 without `--allow-lossy`
- **THEN** the exit code is 7 with `FEN-7001`

### Requirement: Coverage items keep existing builds
Every model field and entity added by change c0277 SHALL default to empty and be left out of canonical JSON when empty, and every new writer branch SHALL run only for the new calls, so every example and test design that uses none of them builds the same bytes for targets 9, 10 and `altium`.

#### Scenario: Examples keep their bytes
- **WHEN** `uv run pytest tests/unit/test_examples.py tests/unit/test_build_bytes.py -q` builds every example with fixed `--seed` and `--timestamp`
- **THEN** every written file has the SHA-256 recorded before this change

## MODIFIED Requirements

### Requirement: Board and placements in the DSL
`Design.board(width=None, height=None, copper=2, planes=None, *, outline=None, locked=False)` SHALL declare the board's outline, its copper layer count and its internal planes, and `Part.place(x, y, rot=0, side="top", locked=False, anchor=None)` SHALL request a placement, both in a board-relative frame.
- The frame has its origin at the top-left corner of the outline given by `width` and `height`, with Y down; an outline given by `outline` is a path in that frame ("Outline shapes in the DSL"), wherever it lies. `BOARD_ORIGIN` MUST be `Point(100_000_000, 100_000_000)`, a Fenolite choice: the frame's origin is written at `BOARD_ORIGIN`, the rectangle from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)`, and a part placed at `(x, y)` at `BOARD_ORIGIN + (x, y)`.
- Exactly one form MUST be given: `width` and `height`, both positive lengths, or `outline`, a path. Both forms, or neither, MUST raise `DslError`. `copper` MUST be an `int` of `fenolite.dsl.design.COPPER_COUNTS`, which MUST hold every even count from 2 to 32 (change c0277), and 1 exactly when `H-K-PCB-ONE-COPPER` records that both majors load a one-copper table, and MUST equal `layers.CREATED_COPPER_COUNTS` of the KiCad backend; any other value, an odd count above 1, a `bool` or a `float` included, MUST raise `DslError` naming those counts. While 1 is not a count, `copper=1` MUST raise `DslError` whose message says that a single-sided board is `copper=2` with nothing on `B.Cu`.
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
- **WHEN** `design.board(mm(50), mm(30), copper=c)` is called on fresh designs for `c` equal to 3, 5, 34, `True` and `6.0`
- **THEN** each call raises `DslError` naming the even counts 2 to 32

#### Scenario: Six and eight copper layers
- **WHEN** `design.board(mm(50), mm(30), copper=6)` and, on another design, `copper=8` are called
- **THEN** `Design.copper_layers` is `("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")` for the first and adds `In5.Cu` and `In6.Cu` before `B.Cu` for the second, and `COPPER_COUNTS` equals `layers.CREATED_COPPER_COUNTS`

#### Scenario: Thirty-two copper layers
- **WHEN** `design.board(mm(50), mm(30), copper=32, planes={"In30.Cu": gnd})` is called
- **THEN** `Design.copper_layers` is `F.Cu`, `In1.Cu` to `In30.Cu` and `B.Cu`, `planes(design)` equals `{"In30.Cu": "GND"}`, and `COPPER_COUNTS` equals `layers.CREATED_COPPER_COUNTS`

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

### Requirement: Board drawings in the DSL
`Design.text(key, text, at, *, layer="F.SilkS", size=None, thickness=None, rot=0, justify=None, knockout=False, bold=False, italic=False, face=None)`, `Design.line(key, start, end, *, layer, width, net=None)`, `Design.rect(key, start, end, *, layer, width, fill=False, net=None)`, `Design.circle(key, center, edge, *, layer, width, fill=False, net=None)`, `Design.arc(key, start, mid, end, *, layer, width, net=None)`, `Design.polygon(key, points, *, layer, width, fill=False, net=None)` and `Design.dimension(key, start, end, *, offset, layer="Dwgs.User", direction=None, units="mm", precision=4, size=None, thickness=None, width=None, extension_offset=None)` SHALL each declare one board drawing. `dsl.to_model` SHALL put one `Text`, `Graphic` or `Dimension` per drawing into `Board.texts`, `Board.graphics` and `Board.dimensions`, each in key order.
- `board()` MUST have been called first, in either of its forms. `key` MUST match `^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$` and MUST NOT be the key of another drawing of the design, whichever of the seven calls made it. `Design.drawings` MUST map each key to its record, in call order.
- Points are `(x, y)` pairs of lengths in the board frame of "Board and placements in the DSL", written with `BOARD_ORIGIN` added; lengths and angles follow "DSL lengths and angles".
- `layer` MUST be a layer of the board whose kind is `silkscreen`, `soldermask`, `fabrication` or `user` (`dsl.items.DRAWING_LAYER_KINDS`), a user layer declared by `Design.user_layers` ("User layers in the DSL"), or, for a text and the five graphics (change c0277), a copper layer of `Design.copper_layers`. A copper layer for a dimension, `Edge.Cuts` or a layer of another kind MUST raise `DslError` naming the layer.
- **Copper art** (change c0277). `net` MUST be `None` or a `Net`, which joins the design, and is accepted only on a copper layer; the graphic takes the net's id as `net_id`. `knockout` MUST be a `bool`, and `True` only on a copper or silkscreen layer; the text takes it as `knockout`. Both fields are left out of the model's canonical JSON when unset. The KiCad writer SHALL write a graphic's net as `(net …)` after its `layer`, in the net form of the target. The copper check SHALL judge a graphic on a copper layer as copper of its net (of no net without one): its stroke around its outline, and its inside when it is filled; a copper text stays `copper.text-unchecked`.
- **Text.** `text` MUST be a `str` whose lines, split at `\n`, are each printable (`str.isprintable()`); an empty text is accepted, as KiCad keeps one (change c0277). `size` MUST be a positive length or a `(width, height)` pair of positive lengths, and `thickness` positive; they default to 1 mm and 0.15 mm, the values the KiCad writer gives created footprint fields. `justify` MUST be `None` or one of `dsl.part.FIELD_JUSTIFY`. `bold` and `italic` MUST be bools and `face` `None` or a printable font name; the text takes them, left out of the canonical JSON when unset.
- **Graphics.** `width` MUST be at least 0, and above 0 for a line, an arc and a shape that is not filled; a filled shape MAY take `width=None`, no outline, which the model holds as −1 nm and the KiCad writer writes as `(width -0.000001)` (change c0277). A rectangle's corners MUST differ in x and in y; a circle's `edge` MUST differ from its `center`; an arc's three points MUST be distinct and not on one line (an exact integer test); a polygon MUST hold at least three points. `fill` MUST be a `bool`.
- **Dimension.** `start` and `end` MUST differ. `offset` is a length, written as KiCad's `height`. `direction` is `None` for an aligned dimension, or `horizontal` or `vertical` for an orthogonal one, whose measured coordinate difference MUST NOT be 0. `text_at` MAY place the text by hand, written as `text_position_mode 2` with the text at that point (change c0277). `units` MUST be `mm`, `in`, `mils` or `auto` (change c0277; the codes 2, 0, 1 and 3 of the file, a created `auto` dimension caching its text in millimetres), `precision` an `int` from 0 to 4, `size`, `thickness` and `width` positive lengths or `None`, and `extension_offset` a length of at least 0 or `None` (change c0277; the model's `Dimension.extension_offset`, left out of the canonical JSON when `None`).
- Each violation MUST raise `DslError` at the call, naming the argument, and MUST record nothing.
- The model entities MUST have the ids `derived_id("txt", "dsl", "text:<key>")`, `derived_id("gfx", "dsl", "graphic:<key>")` and `derived_id("dim", "dsl", "dimension:<key>")`. A text takes `Size(size, size)` (or the pair as `Size(width, height)`), `thickness`, the rotation and the justification (`h_justify`, `v_justify`; `center` for what `justify` does not name). A graphic takes the kind `line`, `rect`, `circle`, `arc` or `polygon`, the points in the order of its call, `width` and `filled`. A dimension takes the kind `aligned` or `orthogonal`, `direction`, `units`, `precision`, and `size`, `thickness` and `width` as given (`None` meaning the backend's default).

#### Scenario: Label and fabrication line in the model
- **GIVEN** a design with `board(mm(50), mm(30))`, `d.text("rev", "REV A", (mm(2), mm(28)), justify="left bottom")` and `d.line("fab/edge", (mm(0), mm(15)), (mm(50), mm(15)), layer="F.Fab", width=mm(0.1))`
- **WHEN** `to_model(d)` runs
- **THEN** `board.texts` holds one `Text` with text `REV A`, position (102 mm, 128 mm), layer `F.SilkS`, `size == Size(1_000_000, 1_000_000)`, `thickness == 150_000`, `h_justify == "left"` and `v_justify == "bottom"`, and `board.graphics` holds one `line` on `F.Fab` from (100 mm, 115 mm) to (150 mm, 115 mm) of width 100 000 nm

#### Scenario: Dimension in the model
- **WHEN** `d.dimension("width", (mm(0), mm(0)), (mm(50), mm(0)), offset=mm(-5))` is declared on the same board and `to_model(d)` runs
- **THEN** `board.dimensions` holds one `aligned` dimension with the id `derived_id("dim", "dsl", "dimension:width")`, layer `Dwgs.User`, start (100 mm, 100 mm), end (150 mm, 100 mm), `offset == -5_000_000`, `direction is None`, `units == "mm"` and `precision == 4`

#### Scenario: Refused drawing calls
- **WHEN** `d.dimension("t1", (mm(0), mm(0)), (mm(5), mm(0)), offset=mm(1), layer="F.Cu")`, `d.line("l1", (mm(0), mm(0)), (mm(1), mm(0)), layer="Edge.Cuts", width=mm(0.1))`, `d.line("rev", …)` after the text `rev`, `d.arc("a1", (mm(0), mm(0)), (mm(1), mm(1)), (mm(2), mm(2)), layer="F.Fab", width=mm(0.1))`, `d.dimension("d1", (mm(0), mm(0)), (mm(0), mm(9)), offset=mm(2), direction="horizontal")`, `d.dimension("d2", …, precision=5)` and `d.text("t2", "A\tB", (mm(1), mm(1)))` are called
- **THEN** each raises `DslError`, naming `F.Cu`, `Edge.Cuts`, `rev`, the arc's points, `direction`, `precision` and `text`

#### Scenario: Copper text and text styles
- **WHEN** `d.text("cu/rev", "REV B", (mm(5), mm(5)), layer="F.Cu", knockout=True)`, `d.text("silk/wide", "WIDE", (mm(5), mm(10)), size=(mm(2), mm("1.25")), bold=True)` and `d.text("silk/lines", "A\nB", (mm(5), mm(15)), italic=True, face="KiCad Font")` are declared and the blink with them is built for targets 9 and 10
- **THEN** the model texts hold `knockout`, `Size(2_000_000, 1_250_000)` with `bold`, and `italic` with the face; the board writes `(layer "F.Cu" knockout)` and `(font (face "KiCad Font") (size 1.25 2) (thickness 0.15) (bold yes) (italic yes))` in that order for a text with every style; `issues` hold one `copper.text-unchecked`; and `d.text("t", "A", …, layer="F.Fab", knockout=True)` raises `DslError` naming `knockout`

#### Scenario: Copper text and a copper shape on a net
- **WHEN** `d.text("logo", "REV B", (mm(5), mm(5)), layer="F.Cu", knockout=True)` and `d.polygon("spreader", [(mm(10), mm(10)), (mm(20), mm(10)), (mm(20), mm(20))], layer="B.Cu", width=mm(0.2), fill=True, net=gnd)` are declared and `to_model(d)` runs
- **THEN** `board.texts` holds `REV B` on `F.Cu` with `knockout` true, `board.graphics` holds one filled polygon on `B.Cu` whose `net_id` is the id of `GND`, and `d.line("x", (mm(0), mm(0)), (mm(1), mm(0)), layer="F.SilkS", width=mm(0.1), net=gnd)` raises `DslError` naming `net`

#### Scenario: A copper shape across a pad of another net
- **GIVEN** the blink with `d.rect("cu/bad", (mm(30), mm(7)), (mm(34), mm(11)), layer="F.Cu", width=mm("0.2"), fill=True, net=gnd)` over a pad of `LED_DRV`
- **WHEN** it is built for target 10
- **THEN** the build exits 5 with `copper.short`; without the overlap the rectangle is written as `(gr_rect … (layer "F.Cu") (net "GND") (uuid …))` for target 10 and with the net's number for target 9

#### Scenario: A shaped board takes drawings
- **GIVEN** `d.board(outline=shape.rect(mm(0), mm(0), mm(50), mm(30), radius=mm(3)))`
- **WHEN** each of the seven calls `text`, `line`, `rect`, `circle`, `arc`, `polygon` and `dimension` is called once
- **THEN** none raises, `d.drawings` holds the seven keys in call order, and the blink with `board(outline=…)` writes the rule areas, texts, drawings and dimensions, with their uuids, that the same blink with `board(mm(50), mm(30))` writes

#### Scenario: Keys, not order
- **GIVEN** two designs that make the same drawing calls in opposite orders
- **WHEN** `to_model` runs on both
- **THEN** every text, graphic and dimension has the same id in both models, and the tuples are in key order

### Requirement: Zones in the DSL
`Design.zone(net, *, layers, name=None, outline=None, priority=0, clearance=None, min_thickness=None, connection=None, thermal_gap=None, thermal_spoke_width=None, islands=None, min_island_area=None, locked=False, key=None, smoothing=None, smoothing_radius=None)` SHALL declare one copper zone, and `dsl.to_model` SHALL put one model `Zone` per declared zone into `Board.zones`, in name order. This adds zones to the `Board` of "DSL to model".
- `board()` MUST have been called first. `layers` MUST be a non-empty sequence of distinct copper layer names of the board, those of `Design.copper_layers`: `F.Cu`, the inner layers `In1.Cu` … `In<copper − 2>.Cu` and `B.Cu` ("Board and placements in the DSL"). The message of a refused name MUST list the board's copper layers.
- `net` MUST be a `Net`, which joins the design, or `None` for a zone without a net. `name` defaults to the net's name, and is required when `net` is `None`. Zone names MUST be unique, non-empty and without surrounding spaces.
- `outline` is `None`, which means the box of the board ring, or a closed path in the board frame of "Board and placements in the DSL": at least three `(x, y)` pairs of lengths, which may be followed by `arc_to` steps as in "Outline shapes in the DSL" (change c0277). The model zone holds the points and, for each arc edge, an `OutlineArc` in `Zone.arcs`, which is left out of canonical JSON when empty. Points are written with `BOARD_ORIGIN` added. The box of the board ring is the smallest axis-aligned rectangle that holds its vertices and the mid points of its arcs, written from its top-left corner in the order of the board rectangle; for `board(width, height)` it is the board rectangle. Cut-outs do not change it: KiCad clips a fill to the board.
- A setting given as `None` MUST take the `ZoneSettings` default. Lengths follow "DSL lengths and angles". `clearance` MUST be at least 0, and `min_thickness`, `thermal_gap` and `thermal_spoke_width` above 0.
- `connection` MUST be one of `solid`, `thermal`, `none` and `thru_hole_only`, and `islands` one of `always`, `never` and `below_area`.
- `min_island_area` MUST be a string with the unit `mm2`, such as `"2.5mm2"`, converted exactly to square nanometres, and is accepted only together with `islands="below_area"`.
- `smoothing` MUST be `None`, `chamfer` or `fillet`, and `smoothing_radius` a length of at least 0 accepted only with a smoothing (change c0277); they set `ZoneSettings.smoothing` and `smoothing_radius`.
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

#### Scenario: Zone with an arc edge
- **GIVEN** a design with `board(mm(50), mm(30))` and `d.zone(gnd, layers=("F.Cu",), outline=((mm(0), mm(0)), (mm(20), mm(0)), arc_to((mm(30), mm(10)), (mm(20), mm(20))), (mm(0), mm(20))))`
- **WHEN** `to_model(d)` runs
- **THEN** the zone has four outline points and one `OutlineArc` whose mid point is (130 mm, 110 mm), and a zone without arcs gives the same canonical JSON as before this change

#### Scenario: Zone on a round board
- **GIVEN** a design with `board(outline=shape.circle(mm(20), mm(20), mm(40)))` and `d.zone(gnd, layers=("B.Cu",))`
- **WHEN** `to_model(d)` runs
- **THEN** the zone's outline points are (100 mm, 100 mm), (140 mm, 100 mm), (140 mm, 140 mm) and (100 mm, 140 mm)
