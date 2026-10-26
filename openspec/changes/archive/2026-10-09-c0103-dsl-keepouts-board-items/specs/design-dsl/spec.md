## ADDED Requirements

### Requirement: Rule areas in the DSL
`Design.rule_area(name, outline, *, layers=None, forbid=()) -> RuleArea` SHALL declare one rule area, and `dsl.to_model` SHALL put one model `Keepout` per declared area into `Board.keepouts`, in name order. This adds rule areas to the `Board` of "DSL to model". `Design.rule_area` is the one call of the DSL that declares a rule area or a keep-out: a keep-out is a rule area with a non-empty `forbid`, and the DSL has no `keepout()` call.
- `board()` MUST have been called first, in either of its forms (`width` and `height`, or `outline=` of change c0102).
- `name` MUST match `^[A-Za-z0-9_.+-]+$`. Two areas MUST NOT have names that are equal after `str.casefold()`, because KiCad compares area names with letter case (`H-K-AREA-COND`).
- `outline` MUST hold at least three `(x, y)` pairs of lengths in the board frame of "Board and placements in the DSL". Points are written with `BOARD_ORIGIN` added.
- `layers` is `None`, which means every copper layer of the board in table order, or a non-empty sequence of distinct copper layer names of the board.
- `forbid` MUST be a tuple of distinct values among `tracks`, `vias`, `pads` and `pours` (`dsl.items.FORBID`). An area with an empty `forbid` is a named area for rules only.
- Each violation MUST raise `DslError` at the call, naming the argument, and MUST record nothing.
- `RuleArea` is a frozen dataclass of `dsl/items.py` with `name`, `outline` (the given points as nanometre pairs, without `BOARD_ORIGIN`), `layers` and `forbid`. `Design.rule_areas` MUST map each name to its `RuleArea`, in call order. `fenolite.dsl` MUST re-export `RuleArea`, as "DSL package" allows, and the package keeps importing only the standard library, `core` and `model`.
- The model keep-out MUST have the id `derived_id("kpo", "dsl", "area:<name>")` (`design-model`, "Identifier derivation"), the `name`, the outline, the layers, `no_tracks`, `no_vias`, `no_pads` and `no_copper_pour` true exactly for `tracks`, `vias`, `pads` and `pours` in `forbid`, and `no_footprints == False`.

#### Scenario: Antenna keep-out in the model
- **GIVEN** a design with `board(mm(50), mm(30))` and `d.rule_area("ANT", [(mm(40), mm(0)), (mm(50), mm(0)), (mm(50), mm(10)), (mm(40), mm(10))], forbid=("tracks", "vias", "pours"))`
- **WHEN** `to_model(d)` runs
- **THEN** `board.keepouts` holds one `Keepout` named `ANT` with the id `derived_id("kpo", "dsl", "area:ANT")`, layers `("F.Cu", "B.Cu")`, the outline (140 mm, 100 mm), (150 mm, 100 mm), (150 mm, 110 mm) and (140 mm, 110 mm), `no_tracks`, `no_vias` and `no_copper_pour` true, and `no_pads` and `no_footprints` false

#### Scenario: Area for rules only
- **GIVEN** the same board and `hv = d.rule_area("HV", [(mm(0), mm(0)), (mm(20), mm(0)), (mm(20), mm(30))], layers=("F.Cu",))`
- **WHEN** `to_model(d)` runs
- **THEN** the keep-out `HV` has layers `("F.Cu",)` and its five settings false, and `hv.name == "HV"`

#### Scenario: Refused calls
- **WHEN** `d.rule_area("HV", …)` is called before `board()`, and after it `d.rule_area("H V", …)`, `d.rule_area("A", [(mm(0), mm(0)), (mm(1), mm(1))])`, `d.rule_area("B", …, layers=("In1.Cu",))` on a two-layer board, `d.rule_area("C", …, forbid=("footprints",))`, and `d.rule_area("hv", …)` after `d.rule_area("HV", …)`
- **THEN** each raises `DslError` naming, in order, `board()`, `name`, `outline`, `In1.Cu`, `footprints` and `hv`, and `d.rule_areas` holds only `HV`

#### Scenario: A shaped board takes rule areas
- **GIVEN** `d.board(outline=shape.rect(mm(0), mm(0), mm(50), mm(30), radius=mm(3)), copper=4)`
- **WHEN** `d.rule_area("HV", [(mm(1), mm(1)), (mm(5), mm(1)), (mm(5), mm(5))], layers=("In1.Cu",))` is called and `to_model` runs
- **THEN** `d.rule_areas` holds `HV` and `board.keepouts` holds one keep-out named `HV`

#### Scenario: Call order does not matter
- **GIVEN** two designs that declare the areas `ANT` and `HV` in opposite orders
- **WHEN** `canonical.dump_texts(to_model(d))["board.json"]` is taken for both
- **THEN** the two texts are byte-identical, `ANT` first

### Requirement: Board drawings in the DSL
`Design.text(key, text, at, *, layer="F.SilkS", size=None, thickness=None, rot=0, justify=None)`, `Design.line(key, start, end, *, layer, width)`, `Design.rect(key, start, end, *, layer, width, fill=False)`, `Design.circle(key, center, edge, *, layer, width, fill=False)`, `Design.arc(key, start, mid, end, *, layer, width)`, `Design.polygon(key, points, *, layer, width, fill=False)` and `Design.dimension(key, start, end, *, offset, layer="Dwgs.User", direction=None, units="mm", precision=4, size=None, thickness=None, width=None)` SHALL each declare one board drawing. `dsl.to_model` SHALL put one `Text`, `Graphic` or `Dimension` per drawing into `Board.texts`, `Board.graphics` and `Board.dimensions`, each in key order.
- `board()` MUST have been called first, in either of its forms. `key` MUST match `^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$` and MUST NOT be the key of another drawing of the design, whichever of the seven calls made it. `Design.drawings` MUST map each key to its record, in call order.
- Points are `(x, y)` pairs of lengths in the board frame of "Board and placements in the DSL", written with `BOARD_ORIGIN` added; lengths and angles follow "DSL lengths and angles".
- `layer` MUST be a layer of the board whose kind is `silkscreen`, `soldermask`, `fabrication` or `user` (`dsl.items.DRAWING_LAYER_KINDS`). A copper layer, `Edge.Cuts` or a layer of another kind MUST raise `DslError` naming the layer.
- **Text.** `text` MUST be a non-empty `str` for which `str.isprintable()` is true. `size` and `thickness` MUST be positive and default to 1 mm and 0.15 mm, the values the KiCad writer gives created footprint fields. `justify` MUST be `None` or one of `dsl.part.FIELD_JUSTIFY`.
- **Graphics.** `width` MUST be at least 0, and above 0 for a line, an arc and a shape that is not filled. A rectangle's corners MUST differ in x and in y; a circle's `edge` MUST differ from its `center`; an arc's three points MUST be distinct and not on one line (an exact integer test); a polygon MUST hold at least three points. `fill` MUST be a `bool`.
- **Dimension.** `start` and `end` MUST differ. `offset` is a length, written as KiCad's `height`. `direction` is `None` for an aligned dimension, or `horizontal` or `vertical` for an orthogonal one, whose measured coordinate difference MUST NOT be 0. `units` MUST be `mm` or `in`, `precision` an `int` from 0 to 4, and `size`, `thickness` and `width` positive lengths or `None`.
- Each violation MUST raise `DslError` at the call, naming the argument, and MUST record nothing.
- The model entities MUST have the ids `derived_id("txt", "dsl", "text:<key>")`, `derived_id("gfx", "dsl", "graphic:<key>")` and `derived_id("dim", "dsl", "dimension:<key>")`. A text takes `Size(size, size)`, `thickness`, the rotation and the justification (`h_justify`, `v_justify`; `center` for what `justify` does not name). A graphic takes the kind `line`, `rect`, `circle`, `arc` or `polygon`, the points in the order of its call, `width` and `filled`. A dimension takes the kind `aligned` or `orthogonal`, `direction`, `units`, `precision`, and `size`, `thickness` and `width` as given (`None` meaning the backend's default).

#### Scenario: Label and fabrication line in the model
- **GIVEN** a design with `board(mm(50), mm(30))`, `d.text("rev", "REV A", (mm(2), mm(28)), justify="left bottom")` and `d.line("fab/edge", (mm(0), mm(15)), (mm(50), mm(15)), layer="F.Fab", width=mm(0.1))`
- **WHEN** `to_model(d)` runs
- **THEN** `board.texts` holds one `Text` with text `REV A`, position (102 mm, 128 mm), layer `F.SilkS`, `size == Size(1_000_000, 1_000_000)`, `thickness == 150_000`, `h_justify == "left"` and `v_justify == "bottom"`, and `board.graphics` holds one `line` on `F.Fab` from (100 mm, 115 mm) to (150 mm, 115 mm) of width 100 000 nm

#### Scenario: Dimension in the model
- **WHEN** `d.dimension("width", (mm(0), mm(0)), (mm(50), mm(0)), offset=mm(-5))` is declared on the same board and `to_model(d)` runs
- **THEN** `board.dimensions` holds one `aligned` dimension with the id `derived_id("dim", "dsl", "dimension:width")`, layer `Dwgs.User`, start (100 mm, 100 mm), end (150 mm, 100 mm), `offset == -5_000_000`, `direction is None`, `units == "mm"` and `precision == 4`

#### Scenario: Refused drawing calls
- **WHEN** `d.text("t1", "CU", (mm(1), mm(1)), layer="F.Cu")`, `d.line("l1", (mm(0), mm(0)), (mm(1), mm(0)), layer="Edge.Cuts", width=mm(0.1))`, `d.line("rev", …)` after the text `rev`, `d.arc("a1", (mm(0), mm(0)), (mm(1), mm(1)), (mm(2), mm(2)), layer="F.Fab", width=mm(0.1))`, `d.dimension("d1", (mm(0), mm(0)), (mm(0), mm(9)), offset=mm(2), direction="horizontal")`, `d.dimension("d2", …, precision=5)` and `d.text("t2", "A\nB", (mm(1), mm(1)))` are called
- **THEN** each raises `DslError`, naming `F.Cu`, `Edge.Cuts`, `rev`, the arc's points, `direction`, `precision` and `text`

#### Scenario: A shaped board takes drawings
- **GIVEN** `d.board(outline=shape.rect(mm(0), mm(0), mm(50), mm(30), radius=mm(3)))`
- **WHEN** each of the seven calls `text`, `line`, `rect`, `circle`, `arc`, `polygon` and `dimension` is called once
- **THEN** none raises, `d.drawings` holds the seven keys in call order, and the blink with `board(outline=…)` writes the rule areas, texts, drawings and dimensions, with their uuids, that the same blink with `board(mm(50), mm(30))` writes

#### Scenario: Keys, not order
- **GIVEN** two designs that make the same drawing calls in opposite orders
- **WHEN** `to_model` runs on both
- **THEN** every text, graphic and dimension has the same id in both models, and the tuples are in key order

### Requirement: Area selectors in the DSL
`fenolite.dsl.select.area(area)` SHALL return a `Select` whose model selector is `Selector("area", <name>)`, which combines with `&`, `|` and `~` as the other selectors of `fenolite.dsl.select` do (c0071).
- `area` MUST be a `RuleArea`, stored by its name, or a name. An empty name, or one holding `'`, `"`, `?`, `[` or `]`, MUST raise `DslError`. A name MAY hold `*`, which the model keeps as a glob.
- `design.rules.rule()` MUST accept area selectors in `where` and `between`. It MUST NOT check at the call that a rule area of that name exists: an area may be drawn in KiCad, and the build checks the name after the merge ("Board items in a build"). Whether a kind takes an area selector is decided by the lowering (`rules-model`, "Closed selector grammar").

#### Scenario: Neck-down rule in the model
- **GIVEN** `bga = d.rule_area("BGA", …)` and `d.rules.rule("neck", "track_width", where=select.area(bga), min=mm(0.1))`
- **WHEN** `to_model(d)` runs
- **THEN** the rule `neck` has `selector_a == Selector("area", "BGA")`

#### Scenario: High-voltage pair
- **WHEN** `(select.area("HV") & select.item("track"))` is turned into a model selector
- **THEN** it is `Selector("and", items=(Selector("area", "HV"), Selector("item_kind", "track")))`

#### Scenario: Refused names
- **WHEN** `select.area("")` and `select.area("H'V")` are called
- **THEN** each raises `DslError`

#### Scenario: No check at the call
- **WHEN** `d.rules.rule("far", "clearance", where=select.area("NOPE"), min=mm(1))` is called on a design without that area
- **THEN** it is recorded, and `to_model(d)` holds the rule

### Requirement: Board items in a build
`fenolite build` SHALL write every rule area and drawing that the script declares, for targets 9 and 10, and the written board SHALL read back with them.
- `lens.build.build_design` MUST keep the `keepouts`, `texts`, `graphics` and `dimensions` of the `Board` it is given and MUST give each of them the KiCad uuid of `boarditems.mark_items` (`kicad-file-backend`, "Board items of a script are written") before copper intents resolve. This is an addition to "Built project files" that needs no keyword.
- After the merge with an existing board, `build_design` MUST check every `area` leaf of every rule of the design against the layout it is about to write. When no `Keepout` of that layout has a `name` that the leaf's value matches with `fnmatch.fnmatchcase`, `build.area-unknown` (error) MUST name the rule and the value, with the hint "declare the area with design.rule_area() or remove the selector"; the build then returns no files, so `build` exits 5 and writes nothing. The code joins the build envelope as "Build issue codes" allows.
- Read back with `read_board`, each rule area MUST have its name, outline, layers and settings; each text its string, position, layer, size, thickness, rotation and justification; each graphic its kind, layer, points, width and fill; and each dimension its kind, layer, points, offset and direction.
- `result.board_items` MUST report the counts `rule_areas`, `texts`, `graphics` and `dimensions` of the script, as "Build command" allows.
- A build over an existing board MUST merge the items as `layout-lens` "Board items declared in the script" describes. The copper guard ("Copper guard before writing") reports `copper.keepout` (`copper-check`, "Keep-out findings") as it reports its other codes.
- `--target altium` follows `altium-build`, "Rule areas, board items and area rules in an Altium build": rule areas with a restriction, centred texts and graphics are written to a planned PCB document, and what the document has no record for (an area's name, an area that forbids nothing, a justified text, a dimension, a rule with an `area` leaf) is reported, never dropped silently.
- A design without the new calls MUST build the same bytes as before, and `--seed`, `--timestamp` and `PYTHONHASHSEED` MUST NOT change any file of a build with them.
- `docs/dsl.md` MUST describe the calls under "Rule areas" and "Board drawings", with the layers each takes, the sign of a dimension's `offset` as `H-K-DIM` measures it, and the rebuild rule; and `select.area` under "Design rules".

#### Scenario: Blink with a keep-out, a label and a dimension
- **GIVEN** a blink variant with `d.rule_area("ANT", …, forbid=("tracks", "vias"))`, `d.text("rev", "REV A", (mm(2), mm(2)))` and `d.dimension("width", (mm(0), mm(0)), (mm(40), mm(0)), offset=mm(-3))`
- **WHEN** it is built for targets 9 and 10 with `--confirm`, and each written board is read with `read_board`
- **THEN** the exit code is 0, `result.board_items` is `{"rule_areas": 1, "texts": 1, "graphics": 0, "dimensions": 1}`, and each board holds the keep-out `ANT` with `no_tracks` and `no_vias`, the text `REV A` and one `aligned` dimension, each with the uuid that `boarditems.item_uuid` gives its id

#### Scenario: Unknown area stops the build
- **GIVEN** the blink with `d.rules.rule("far", "clearance", where=select.area("NOPE"), min=mm(1))`
- **WHEN** it is built with `--confirm --json`
- **THEN** the exit code is 5, `issues` hold one `build.area-unknown` naming `far` and `NOPE`, and nothing is written

#### Scenario: An area drawn in KiCad is a valid target
- **GIVEN** a confirmed target-10 blink build whose board gets, by token edit, a rule area named `HV` with a version-4 uuid, and a script that then adds `d.rules.rule("hv", "clearance", where=select.area("HV"), min=mm(2))`
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, the area `HV` is kept, and the rules file holds the condition `"A.intersectsArea('HV')"`

#### Scenario: Reproducible builds with board items
- **WHEN** `uv run pytest tests/unit/lens/test_build_board_items.py -k reproducible` builds the variant twice for targets 9 and 10 with different seeds and `PYTHONHASHSEED` values
- **THEN** both builds write every file with the same bytes
