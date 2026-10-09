## ADDED Requirements

### Requirement: Fiducials in the DSL
`Design.fiducial(ref, x, y, *, copper, mask, clear=None, side="top", local=False) -> Part` SHALL add, place and lock one part that stands for a fiducial, whose footprint and symbol `fenolite.dsl.assembly` generates in the library `Fenolite_Assembly` (`assembly.ASSEMBLY_LIBRARY`), and SHALL declare its copper keep-out with `Design.rule_area` (c0103).
- `board()` MUST have been called first. `ref` follows "Design structure and names", and the part's path is `ref`, at the top of the design.
- `copper` MUST be a positive length and `mask` a length above `copper`; `clear` MUST be `None`, which means `mask`, or a length of at least `mask`. `side` MUST be `top` or `bottom` and `local` a `bool`. Any other value MUST raise `DslError` at the call, naming the argument, and MUST record nothing.
- The footprint (`assembly.fiducial_footprint`) MUST hold two unnumbered `smd` pads of shape `circle` at its origin: the copper pad, `copper` × `copper` on `F.Cu` and `F.Mask`, with `fab_property` `fiducial_local` when `local` is true and `fiducial_global` otherwise; and the aperture pad, `mask` × `mask` on `F.Mask` only, without a mark. A courtyard circle of diameter `clear` is drawn 0.05 mm wide on `F.CrtYd`. The kind is `smd` and the flags are `exclude_from_bom`.
- The footprint is named `Fiducial_<c>_Mask<m>`, or `Fiducial_Local_<c>_Mask<m>` when `local` is true, followed by `_Clear<k>` when `clear` differs from `mask`, each length in millimetres as `core.units.format_length` prints it (`Fiducial_1mm_Mask2mm`).
- The symbol (`assembly.fiducial_symbol`) is `Fenolite_Assembly:Fiducial`, a `SymbolDef` without pins, with the reference prefix `FID`, `in_bom` false and `on_board` true.
- The part is `Part(ref, "Fenolite_Assembly:Fiducial", footprint=<footprint lib id>, value=<footprint name>)`, placed at `(x, y)` with rotation 0 on `side`, locked. `fiducial()` takes no `locked`: its keep-out stays where the script draws it.
- The keep-out MUST be `rule_area(f"clear_{ref}", assembly.clear_outline(x, y, clear), layers=("F.Cu",), forbid=("tracks", "vias", "pours"))`, with `("B.Cu",)` on the bottom side. `clear_outline(x, y, d)` MUST return, in this order, the points `(x + a, y − b)`, `(x + a, y + b)`, `(x + b, y + a)`, `(x − b, y + a)`, `(x − a, y + b)`, `(x − a, y − b)`, `(x − b, y − a)` and `(x + b, y − a)`, with `a = ⌈d / 2⌉` and `b = ⌈√(2a²)⌉ − a` computed in integer nanometres with `math.isqrt`: an octagon that contains the circle of diameter `d`.
- Each definition MUST be registered once per lib id, the footprint in `Design.footprints` and the symbol among the design's symbols; registering another definition under one of these lib ids, the user's own included, MUST raise `DslError` naming it.

#### Scenario: A global fiducial
- **GIVEN** `d.board(mm(50), mm(30))`
- **WHEN** `d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))` is called
- **THEN** the part `FID1` has `lib_id == "Fenolite_Assembly:Fiducial"` and `footprint == "Fenolite_Assembly:Fiducial_1mm_Mask2mm"`, `placements(d)["FID1"]` is `Placement(Point(103_000_000, 103_000_000), 0, "top", True)`, the footprint's copper pad is `""`, `smd`, `circle`, 1 mm × 1 mm on `("F.Cu", "F.Mask")` with `fab_property == "fiducial_global"`, its aperture pad is 2 mm × 2 mm on `("F.Mask",)`, and `d.rule_areas["clear_FID1"]` lies on `("F.Cu",)`, forbids `("tracks", "vias", "pours")` and has the outline (4 000 000, 2 585 786), (4 000 000, 3 414 214), (3 414 214, 4 000 000), (2 585 786, 4 000 000), (2 000 000, 3 414 214), (2 000 000, 2 585 786), (2 585 786, 2 000 000), (3 414 214, 2 000 000) in nanometres

#### Scenario: A local fiducial on the bottom
- **WHEN** `d.fiducial("FID4", mm(20), mm(10), copper=mm(0.5), mask=mm(1.5), clear=mm(3), side="bottom", local=True)` is called after `board()`
- **THEN** the part uses `Fenolite_Assembly:Fiducial_Local_0.5mm_Mask1.5mm_Clear3mm`, whose copper pad has `fab_property == "fiducial_local"` and whose courtyard circle has a diameter of 3 mm, the placement is on the bottom side and locked, and `clear_FID4` lies on `("B.Cu",)`

#### Scenario: Refused fiducials
- **GIVEN** `d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))`
- **WHEN** `d.fiducial("FID2", mm(9), mm(9), copper=mm(0), mask=mm(1))`, `d.fiducial("FID2", mm(9), mm(9), copper=mm(1), mask=mm(1))`, `d.fiducial("FID2", mm(9), mm(9), copper=mm(1), mask=mm(2), clear=mm(1.5))`, `d.fiducial("FID2", mm(9), mm(9), copper=mm(1), mask=mm(2), side="left")` and `d.fiducial("FID1", mm(9), mm(9), copper=mm(1), mask=mm(2))` are called
- **THEN** each raises `DslError`, naming `copper`, `mask`, `clear`, `side` and the path `FID1`, and the design holds one fiducial and one rule area

### Requirement: Test points in the DSL
`Design.test_point(ref, net, x, y, *, size, shape="circle", drill=None, courtyard=None, side="top", locked=False) -> Part` SHALL add and place one part that stands for a test point on `net`, whose footprint and symbol `fenolite.dsl.assembly` generates in `Fenolite_Assembly`.
- `board()` MUST have been called first; `ref` and the path are as for `fiducial()`.
- `net` MUST be a `Net`. `size` MUST be a positive length; `shape` `circle` or `rect`; `drill` `None` for an SMD pad, or a positive length below `size` for a plated through-hole pad; `courtyard` `None` or a length of at least `size`; `side` `top` or `bottom`; `locked` a `bool`. Any other value MUST raise `DslError` at the call, naming the argument, and MUST record nothing.
- The footprint (`assembly.test_point_footprint`) MUST hold one pad `1` at its origin, `size` × `size`, of the given shape, with `fab_property` `test_point`: kind `smd` on `F.Cu` and `F.Mask` without `drill`, kind `thru_hole` on `*.Cu` and `*.Mask` with that drill otherwise. Its courtyard, `courtyard` wide or by default `size`, is a circle for `circle` and a square for `rect`, drawn 0.05 mm wide on `F.CrtYd`, and also on `B.CrtYd` for a through-hole pad. The kind is `unspecified` and the flags are `exclude_from_pos_files` and `exclude_from_bom`.
- The footprint is named `TestPoint_Pad_D<s>` for a round SMD pad, `TestPoint_Pad_<s>x<s>` for a square one, `TestPoint_THTPad_D<s>_Drill<d>` and `TestPoint_THTPad_<s>x<s>_Drill<d>` for through-hole pads, followed by `_Courtyard_<c>` when `courtyard` is given, each length in millimetres as `core.units.format_length` prints it.
- The symbol (`assembly.test_point_symbol`) is `Fenolite_Assembly:TestPoint`, with one passive pin `1`, the reference prefix `TP`, `in_bom` false and `on_board` true.
- The part is `Part(ref, "Fenolite_Assembly:TestPoint", footprint=<footprint lib id>, value=<footprint name>)`. `test_point()` MUST connect it with `connect(net, part[1])` and place it at `(x, y)` with rotation 0 on `side`, with `locked`.
- Definitions are registered as for `fiducial()`.

#### Scenario: An SMD test point on a net
- **GIVEN** `d.board(mm(50), mm(30))` and the net `led_a = Net("LED_A")` added to the design
- **WHEN** `tp = d.test_point("TP1", led_a, mm(30), mm(12), size=mm(1.5))` is called
- **THEN** `tp` uses `Fenolite_Assembly:TestPoint` and `Fenolite_Assembly:TestPoint_Pad_D1.5mm`, whose pad `1` is `smd`, `circle`, 1.5 mm × 1.5 mm on `("F.Cu", "F.Mask")` with `fab_property == "test_point"`, the net `LED_A` holds `PinRef(<TP1 id>, "1")`, and `placements(d)["TP1"]` is `Placement(Point(130_000_000, 112_000_000), 0, "top", False)`

#### Scenario: A through-hole test point on the bottom
- **WHEN** `d.test_point("TP2", gnd, mm(5), mm(25), size=mm(2), shape="rect", drill=mm(1), courtyard=mm(3), side="bottom")` is called
- **THEN** the part uses `Fenolite_Assembly:TestPoint_THTPad_2x2mm_Drill1mm_Courtyard_3mm`, whose pad `1` is `thru_hole`, `rect`, with a 1 mm drill on `("*.Cu", "*.Mask")`, with 3 mm square courtyards on `F.CrtYd` and `B.CrtYd`, placed on the bottom side

#### Scenario: Refused test points
- **WHEN** `d.test_point("TP3", "GND", mm(1), mm(1), size=mm(1))`, `d.test_point("TP3", gnd, mm(1), mm(1), size=mm(0))`, `d.test_point("TP3", gnd, mm(1), mm(1), size=mm(1), shape="oval")`, `d.test_point("TP3", gnd, mm(1), mm(1), size=mm(1), drill=mm(1))` and `d.test_point("TP3", gnd, mm(1), mm(1), size=mm(1), courtyard=mm(0.5))` are called
- **THEN** each raises `DslError`, naming `net`, `size`, `shape`, `drill` and `courtyard`, and nothing is recorded

### Requirement: Tooling holes in the DSL
`Design.tooling_hole(ref, x, y, *, drill, clear=None) -> Part` SHALL add, place and lock one part that stands for a non-plated tooling hole, whose footprint `fenolite.dsl.assembly` generates in `Fenolite_Assembly`.
- `board()` MUST have been called first; `ref` and the path are as for `fiducial()`. `drill` MUST be a positive length and `clear` `None` or a length of at least `drill`. Any other value MUST raise `DslError` at the call, naming the argument, and MUST record nothing.
- The footprint (`assembly.tooling_hole_footprint`) MUST hold one unnumbered `np_thru_hole` pad of shape `circle`, `drill` × `drill` with the drill `drill`, on `*.Cu` and `*.Mask`, without a mark; courtyard circles of diameter `clear`, by default `drill`, drawn 0.05 mm wide on `F.CrtYd` and `B.CrtYd`. The kind is `unspecified` and the flags are `exclude_from_pos_files` and `exclude_from_bom`. It is named `ToolingHole_<d>`, followed by `_Clear<c>` when `clear` is given, each length as for `fiducial()`. The lib id prefix `Fenolite_Assembly:ToolingHole_` is the tooling mark that the report reads ("Test-point report rows").
- The symbol is c0102's `Fenolite_Holes:Hole` ("Board holes in the DSL"), registered once.
- The part is `Part(ref, "Fenolite_Holes:Hole", footprint=<footprint lib id>, value=<footprint name>)`, placed at `(x, y)` with rotation 0 on the top side, locked; `tooling_hole()` takes no `locked`.
- With `clear`, it MUST also call `rule_area(f"clear_{ref}", assembly.clear_outline(x, y, clear), layers=None, forbid=("tracks", "vias", "pours"))`: every copper layer of the board.

#### Scenario: A tooling hole with a clear area
- **GIVEN** `d.board(mm(50), mm(30))`
- **WHEN** `d.tooling_hole("TH1", mm(46), mm(4), drill=mm(3), clear=mm(5))` is called
- **THEN** the part uses `Fenolite_Holes:Hole` and `Fenolite_Assembly:ToolingHole_3mm_Clear5mm`, whose pad is `""`, `np_thru_hole`, `circle`, 3 mm × 3 mm with a 3 mm drill, with 5 mm courtyard circles on `F.CrtYd` and `B.CrtYd`; `placements(d)["TH1"]` is `Placement(Point(146_000_000, 104_000_000), 0, "top", True)`; and `d.rule_areas["clear_TH1"]` lies on every copper layer of the board (`("F.Cu", "B.Cu")`: `rule_area` records the layers that `layers=None` names) and forbids `("tracks", "vias", "pours")`

#### Scenario: A tooling hole without a clear area
- **WHEN** `d.tooling_hole("TH2", mm(4), mm(26), drill=mm(3))` is called after `board()`
- **THEN** the part uses `Fenolite_Assembly:ToolingHole_3mm` with 3 mm courtyard circles, and the design holds no rule area `clear_TH2`

#### Scenario: Refused tooling holes
- **WHEN** `d.tooling_hole("TH3", mm(1), mm(1), drill=mm(0))` and `d.tooling_hole("TH3", mm(1), mm(1), drill=mm(3), clear=mm(2))` are called
- **THEN** each raises `DslError`, naming `drill` and `clear`, and nothing is recorded

### Requirement: Assembly and test features in a build
`fenolite build` SHALL build the parts of `fiducial()`, `test_point()` and `tooling_hole()` as parts with authored definitions, with no step of its own: the built project MUST hold `lib/Fenolite_Assembly.pretty/<name>.kicad_mod` for each such footprint used, `lib/Fenolite_Assembly.kicad_sym` with the symbols used, `lib/Fenolite_Holes.kicad_sym` when a tooling hole is used, their table rows, one footprint per part at its placement, and the rule areas of their keep-outs (c0103).
- The written pads MUST carry their marks, in the footprint files and on the board ("Assembly and test pad properties on boards and footprints").
- The placement guard ("Placement legality in a build") MUST judge these parts by their courtyards.
- A rebuild over the build's own output MUST write the same bytes.
- `--target altium` follows `altium-build`, "Assembly and test features in an Altium build".

#### Scenario: Features in a build
- **GIVEN** a variant of `examples/blink_2layer/design.py` with `d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))`, `d.fiducial("FID2", mm(47), mm(27), copper=mm(1), mask=mm(2), side="bottom")`, `d.test_point("TP1", led_a, mm(30), mm(12), size=mm(1.5))` and `d.tooling_hole("TH1", mm(46), mm(4), drill=mm(3), clear=mm(5))`
- **WHEN** it is built with `--confirm` for target 10 and the board is read with `read_board`
- **THEN** the exit code is 0; the copper pad of `FID1` has `fab_property == "fiducial_global"` on `F.Cu` and that of `FID2` on `B.Cu`; pad `1` of `TP1` is on `LED_A` with `fab_property == "test_point"`; the pad of `TH1` is `np_thru_hole`; `board.keepouts` holds `clear_FID1` on `F.Cu`, `clear_FID2` on `B.Cu` and `clear_TH1` on both copper layers; and the written files include `lib/Fenolite_Assembly.pretty/Fiducial_1mm_Mask2mm.kicad_mod`, `lib/Fenolite_Assembly.pretty/TestPoint_Pad_D1.5mm.kicad_mod`, `lib/Fenolite_Assembly.pretty/ToolingHole_3mm_Clear5mm.kicad_mod` and `lib/Fenolite_Assembly.kicad_sym`

#### Scenario: Features rebuild to the same bytes
- **GIVEN** a confirmed target-9 build of the variant of "Features in a build"
- **WHEN** it is built again
- **THEN** every file keeps its bytes
