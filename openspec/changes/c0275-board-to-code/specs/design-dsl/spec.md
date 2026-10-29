## ADDED Requirements

### Requirement: Copper tables in the DSL
`Design.track_table(key, *, net, layer, width, rows_nm, locked=False)`, `Design.arc_table(key, *, net, layer, width, rows_nm, locked=False)` and `Design.via_table(key, *, net, diameter, drill, rows_nm, kind="through", layers=None, locked=False, protection=None)` SHALL each record one copper intent of many items. Rows MUST be tuples of `int` nanometres in the frame of `place()`: `(x1, y1, x2, y2)`, `(sx, sy, mx, my, ex, ey)` and `(x, y)`.

#### Scenario: Table of two segments
- **GIVEN** a design with `board(mm(50), mm(30))` and `d.track_table("GND/F.Cu/1", net=gnd, layer="F.Cu", width=mm("0.25"), rows_nm=((0, 0, 5_000_000, 0), (5_000_000, 0, 5_000_000, 5_000_000)))`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the model holds two tracks of `GND` on `F.Cu`, from (100 mm, 100 mm) to (105 mm, 100 mm) and on to (105 mm, 105 mm), each 250 000 nm wide

### Requirement: Copper table checks
A table SHALL raise `DslError` at the call, naming the table key and the row index, for a row of the wrong length, a value that is not an `int` (a `bool` included), a zero-length segment, three collinear arc points, an empty `rows_nm`, a layer outside the board's copper layers, or a key already used by any copper intent. Widths and via sizes MUST be `Length` values as for `track` and `via`.

#### Scenario: Refused rows
- **WHEN** `track_table` is called with a row `(0, 0, 0, 0)`, then with a row `(0, 0, 1.5, 0)`, then with `rows_nm=()`
- **THEN** each raises `DslError`, the first two naming the table key and row 0, the last naming `rows_nm`

### Requirement: Copper tables in a build
`fenolite build` SHALL write row `i` of table `key` with the copper uuid it derives for item `i` of intent `key`, the table's net, layer, width or via sizes, kind, layers, protection and lock flag, for targets 9 and 10. Table copper MUST take part in the copper guard and in "Script copper in a merge" as script copper. With `--target altium` it follows the rules of `track` and `via`.

#### Scenario: Rebuild keeps table copper
- **GIVEN** a confirmed target-10 build of a design with one `track_table` of three rows and one `via_table` of two rows
- **WHEN** it is built again with `--confirm`
- **THEN** the board holds the same three tracks and two vias with the same uuids, no `kicad.copper.*` warning is reported, and the second build writes the same bytes

#### Scenario: Designs without tables are unchanged
- **WHEN** every example is built before and after this change with the same flags
- **THEN** each written file has the same bytes

## MODIFIED Requirements

### Requirement: Zones in the DSL
`Design.zone(net, *, layers, name=None, outline=None, priority=0, clearance=None, min_thickness=None, connection=None, thermal_gap=None, thermal_spoke_width=None, islands=None, min_island_area=None, locked=False, key=None)` SHALL declare one copper zone, and `dsl.to_model` SHALL put one model `Zone` per declared zone into `Board.zones`, in key order. This adds zones to the `Board` of "DSL to model".
- `board()` MUST have been called first. `layers` MUST be a non-empty sequence of distinct copper layer names of the board, those of `Design.copper_layers`: `F.Cu`, the inner layers `In1.Cu` … `In<copper − 2>.Cu` and `B.Cu` ("Board and placements in the DSL"). The message of a refused name MUST list the board's copper layers.
- `net` MUST be a `Net`, which joins the design, or `None` for a zone without a net. `name` defaults to the net's name when `key` is `None`, and is required when both `net` and `key` are `None`. A given name MUST be non-empty and without surrounding spaces, and given names MUST be unique.
- `key` (change c0275) is `None` or a string matching `^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$`: the zone's identity across builds, written nowhere in the board. Without `key`, the key is the name, which is today's rule. With `key` and no `name`, the zone has no name (`name == ""` in the model) and the net's name is not taken. Keys MUST be unique among zones.
- `outline` is `None`, which means the box of the board ring, or at least three `(x, y)` pairs of lengths in the board frame of "Board and placements in the DSL". Points are written with `BOARD_ORIGIN` added. The box of the board ring is the smallest axis-aligned rectangle that holds its vertices and the mid points of its arcs, written from its top-left corner in the order of the board rectangle; for `board(width, height)` it is the board rectangle. Cut-outs do not change it: KiCad clips a fill to the board.
- A setting given as `None` MUST take the `ZoneSettings` default. Lengths follow "DSL lengths and angles". `clearance` MUST be at least 0, and `min_thickness`, `thermal_gap` and `thermal_spoke_width` above 0.
- `connection` MUST be one of `solid`, `thermal`, `none` and `thru_hole_only`, and `islands` one of `always`, `never` and `below_area`.
- `min_island_area` MUST be a string with the unit `mm2`, such as `"2.5mm2"`, converted exactly to square nanometres, and is accepted only together with `islands="below_area"`.
- `priority` MUST be an `int` of at least 0, and `locked` a `bool`.
- Each violation MUST raise `DslError` at the call, naming the argument.
- The model zone MUST have the id `derived_id("zon", "dsl", "zone:<key>")` (`design-model`, "Identifier derivation"), `name`, the layers, the net's id, `priority`, `locked`, the settings, `filled == False` and no fills. Hatching and smoothing are not DSL arguments and keep their defaults.

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

#### Scenario: Unnamed zone with a key
- **GIVEN** a design with `board(mm(50), mm(30))`, `d.zone(gnd, layers=("F.Cu",), key="GND/1")` and `d.zone(gnd, layers=("B.Cu",), key="GND/2")`
- **WHEN** `to_model(d)` runs
- **THEN** `board.zones` holds two zones with `name == ""`, the ids `derived_id("zon", "dsl", "zone:GND/1")` and `derived_id("zon", "dsl", "zone:GND/2")`, in that order, and a design without `key=` builds the same bytes as before this change

### Requirement: Rule areas in the DSL
`Design.rule_area(name, outline, *, layers=None, forbid=(), key=None) -> RuleArea` SHALL declare one rule area, and `dsl.to_model` SHALL put one model `Keepout` per declared area into `Board.keepouts`, in key order. This adds rule areas to the `Board` of "DSL to model". `Design.rule_area` is the one call of the DSL that declares a rule area or a keep-out: a keep-out is a rule area with a non-empty `forbid`, and the DSL has no `keepout()` call.
- `board()` MUST have been called first, in either of its forms (`width` and `height`, or `outline=` of change c0102).
- `name` MUST match `^[A-Za-z0-9_.+-]+$`, or be `""` when `key` is given (change c0275): an unnamed area, which no `select.area` leaf matches. `key` is `None` or a string matching `^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$`, the area's identity across builds, written nowhere in the board; without it the key is the name. Keys MUST be unique among rule areas. Two areas MUST NOT have names that are equal after `str.casefold()`, because KiCad compares area names with letter case (`H-K-AREA-COND`).
- `outline` MUST hold at least three `(x, y)` pairs of lengths in the board frame of "Board and placements in the DSL". Points are written with `BOARD_ORIGIN` added.
- `layers` is `None`, which means every copper layer of the board in table order, or a non-empty sequence of distinct copper layer names of the board.
- `forbid` MUST be a tuple of distinct values among `tracks`, `vias`, `pads`, `pours` and `footprints` (`dsl.items.FORBID`). An area with an empty `forbid` is a named area for rules only. An area that forbids `footprints` is a placement keep-out: the KiCad build writes `(footprints not_allowed)`, and the legality checks of `place` and `build` judge it (`placement`, "Placement legality").
- Each violation MUST raise `DslError` at the call, naming the argument, and MUST record nothing.
- `RuleArea` is a frozen dataclass of `dsl/items.py` with `name`, `outline` (the given points as nanometre pairs, without `BOARD_ORIGIN`), `layers` and `forbid`. `Design.rule_areas` MUST map each key to its `RuleArea`, in call order; `RuleArea` gains `key`, equal to `name` when no key was given. `fenolite.dsl` MUST re-export `RuleArea`, as "DSL package" allows, and the package keeps importing only the standard library, `core` and `model`.
- The model keep-out MUST have the id `derived_id("kpo", "dsl", "area:<key>")` (`design-model`, "Identifier derivation"), the `name`, the outline, the layers, and `no_tracks`, `no_vias`, `no_pads`, `no_copper_pour` and `no_footprints` true exactly for `tracks`, `vias`, `pads`, `pours` and `footprints` in `forbid`.
- **The Altium target.** `build --target altium` MUST handle an area that forbids footprints as it handles any rule area. The restriction on footprints MUST NOT be dropped silently: the build MUST give one `altium.not-lowered` info whose `where` is the kind `keepout-footprints` (`backends.altium.lower`), naming the areas, and the kind MUST NOT be in `LOSS_KINDS`. No Altium record is written for the restriction until `docs/formats/altium/` holds a fact row for it.

#### Scenario: Antenna keep-out in the model
- **GIVEN** a design with `board(mm(50), mm(30))` and `d.rule_area("ANT", [(mm(40), mm(0)), (mm(50), mm(0)), (mm(50), mm(10)), (mm(40), mm(10))], forbid=("tracks", "vias", "pours"))`
- **WHEN** `to_model(d)` runs
- **THEN** `board.keepouts` holds one `Keepout` named `ANT` with the id `derived_id("kpo", "dsl", "area:ANT")`, layers `("F.Cu", "B.Cu")`, the outline (140 mm, 100 mm), (150 mm, 100 mm), (150 mm, 110 mm) and (140 mm, 110 mm), `no_tracks`, `no_vias` and `no_copper_pour` true, and `no_pads` and `no_footprints` false

#### Scenario: Area for rules only
- **GIVEN** the same board and `hv = d.rule_area("HV", [(mm(0), mm(0)), (mm(20), mm(0)), (mm(20), mm(30))], layers=("F.Cu",))`
- **WHEN** `to_model(d)` runs
- **THEN** the keep-out `HV` has layers `("F.Cu",)` and its five settings false, and `hv.name == "HV"`

#### Scenario: A shaped board takes rule areas
- **GIVEN** `d.board(outline=shape.rect(mm(0), mm(0), mm(50), mm(30), radius=mm(3)), copper=4)`
- **WHEN** `d.rule_area("HV", [(mm(1), mm(1)), (mm(5), mm(1)), (mm(5), mm(5))], layers=("In1.Cu",))` is called and `to_model` runs
- **THEN** `d.rule_areas` holds `HV` and `board.keepouts` holds one keep-out named `HV`

#### Scenario: Refused calls
- **WHEN** `d.rule_area("HV", …)` is called before `board()`, and after it `d.rule_area("H V", …)`, `d.rule_area("A", [(mm(0), mm(0)), (mm(1), mm(1))])`, `d.rule_area("B", …, layers=("In1.Cu",))` on a two-layer board, `d.rule_area("C", …, forbid=("silkscreen",))`, and `d.rule_area("hv", …)` after `d.rule_area("HV", …)`
- **THEN** each raises `DslError` naming, in order, `board()`, `name`, `outline`, `In1.Cu`, `silkscreen` and `hv`, and `d.rule_areas` holds only `HV`

#### Scenario: Call order does not matter
- **GIVEN** two designs that declare the areas `ANT` and `HV` in opposite orders
- **WHEN** `canonical.dump_texts(to_model(d))["board.json"]` is taken for both
- **THEN** the two texts are byte-identical, `ANT` first

#### Scenario: Antenna keep-out
- **GIVEN** the blink with `design.rule_area("ANT", <a 6 mm × 6 mm square over R1>, layers=("F.Cu",), forbid=("footprints",))`
- **WHEN** `uv run pytest tests/unit/dsl/test_placement_rules.py -k keepout` builds it with `--dry-run --json`
- **THEN** the model's `Keepout` named `ANT` has `no_footprints` true, the planned board text holds `(footprints not_allowed)` once, and `issues` hold one `place.keepout` warning naming `R1` and `ANT`

#### Scenario: Antenna keep-out in an Altium build
- **GIVEN** the same design
- **WHEN** `uv run pytest tests/unit/cli/test_build_altium.py -k keepout_footprints` builds it with `--target altium --dry-run --json`
- **THEN** the exit code is 0, and `issues` hold one `altium.not-lowered` info whose `where` is `keepout-footprints` and whose message names `ANT`

#### Scenario: Unnamed area with a key
- **GIVEN** a design with `board(mm(50), mm(30))` and `d.rule_area("", [(mm(0), mm(0)), (mm(5), mm(0)), (mm(5), mm(5))], forbid=("vias",), key="area/1")`
- **WHEN** `to_model(d)` runs
- **THEN** `board.keepouts` holds one keep-out with `name == ""`, `no_vias` true and the id `derived_id("kpo", "dsl", "area:area/1")`, and `d.rule_area("", …)` without `key` raises `DslError` naming `name`
