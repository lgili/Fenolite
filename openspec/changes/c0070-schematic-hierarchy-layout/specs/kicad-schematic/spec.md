## ADDED Requirements

### Requirement: Readable sheet layout
With `layout="readable"`, `schlayout.snap_satellites(units, nets, *, placements=None) -> tuple[tuple[Cluster, ...], tuple[Issue, ...]]` SHALL place, in one sheet, each 2-pin part that it can beside an IC pin of its net, joined to it by one straight wire, and SHALL return one `Cluster(anchor, satellites, wires, labels)` per anchor that took at least one satellite.
- **Anchors and satellites.** An anchor MUST be a unit with three pins or more. A satellite MUST be a component with one unit and exactly two pins whose connection points lie on one horizontal or vertical axis, with opposite pin angles. References that start with `#` MUST be neither.
- **Order.** Satellites MUST be tried in the natural order of their component paths. For each, the candidate anchor pins MUST be the pins of anchors of the same sheet that lie on the net of one of its pins and hold no satellite yet, in anchor order (the order of "Deterministic sheet layout") and then in natural pin-number order; the first candidate for which every condition below holds MUST be taken, and that pin of the satellite is its near pin.
- **Conditions.** The rotation that makes the near pin face the anchor pin, with the body extending away from the anchor, MUST be in `schlayout.PROVED_FRAMES` with no mirror. The satellite's origin MUST put the near pin's connection point at `SNAP_REACH` (5 080 000 nm) from the anchor pin's, along the anchor pin's outward direction, and MUST be a multiple of `GRID` in both axes. The satellite's box (body, pin points, the room of Reference and Value, and the rooms of its two labels) MUST overlap neither the anchor's body box, nor the cell of another unit of the sheet, nor a satellite, label room or wire already snapped.
- **Wire and labels.** A snapped satellite MUST give one `Wire` from the anchor pin's connection point to the near pin's. The pair MUST carry one global label of its net at the near pin, turned perpendicular to the wire, towards the side of the anchor pin away from the centre line of the anchor's body; the far pin keeps the label that "Generated sheet content" gives it. An anchor pin MUST take at most one satellite.
- **Placements.** A satellite named by `placements` MUST NOT be snapped, unless its entry equals the origin, rotation and mirror that the snap gives; then it MUST be snapped. An anchor named by `placements` MUST be snapped around at its given origin.
- Satellites that are not snapped flow as units of their own, with c0061's labels.
- The function MUST be pure, MUST use integer nm, and two calls with equal arguments MUST return equal results.

#### Scenario: Resistor on an IC pin
- **GIVEN** a design with `U1` of `Mini:Mini_QFP32_IC` and `R1` of `Mini:Mini_R`, `R1` pin 1 on the net of `U1`'s first pin on its left side and `R1` pin 2 on `GND`, with that rotation proved
- **WHEN** the sheet is generated
- **THEN** the sheet holds one wire from that pin's connection point to `R1` pin 1, 5.08 mm to its left, `R1` lies left of `U1` along the pin's axis, the net of the pair has one global label at `R1` pin 1, and `R1` pin 2 has its `GND` label

#### Scenario: One satellite per pin
- **GIVEN** the same design with a second resistor `R2` on the same `U1` pin and on `VIN`
- **WHEN** the sheet is generated
- **THEN** `R1` is snapped to that pin, and `R2` is snapped to a pin on `VIN` when one is free, or flows with its two labels

#### Scenario: Overlap skips the snap
- **GIVEN** resistors on two adjacent pins of `U1`, 2.54 mm apart
- **WHEN** the sheet is generated
- **THEN** the first is snapped, the second is not, and the second flows with its two labels

#### Scenario: Placed satellite keeps its wire
- **GIVEN** a `schematic-placements.toml` entry for `R1` equal to its snapped origin and rotation, and another giving `R2` any other origin
- **WHEN** the sheet is generated
- **THEN** `R1` keeps its wire, and `R2` has no wire and two labels

#### Scenario: Deterministic
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_schlayout_snap.py -k deterministic` generates the sheets of the 25 designs of `tests/_gendesigns.py` twice
- **THEN** the written texts are byte-identical

### Requirement: Hierarchical sheets of a design
With `layout="readable"` (the default), `generate_schematic` SHALL give each module that holds a part, directly or below it, a child sheet, and SHALL return the root sheet as `sheet` and the child sheets as `children`; a design without such a module gets one sheet. With `layout="grid"`, it SHALL return the one sheet that c0061's generator builds, without satellites, and empty `children`.
- **Content.** The root MUST hold the units of the components outside every module, one sheet reference per top-level module with a part, and the power flags. A child sheet MUST hold the units of its module's own components and one sheet reference per sub-module with a part.
- **Files.** A child sheet's path MUST be `sheets/<module path with "/" replaced by ".">.kicad_sch`. The root's sheet references MUST name `sheets/<file>`, and a child's sheet references MUST name `<file>`, from the child's own folder (`H-K-SCH-HIER-FILE`). Two modules with one path MUST give `build.sheet-file-collision` (error) naming both, and no sheet.
- **Sheet references.** Each MUST be a `SheetRef` named by the module's last path segment, with no pin, a height of 12 700 000 nm and the width `schlayout.sheet_ref_size(name)`: the larger of 25 400 000 nm and `CHAR_ROOM` × (length of the name + 2), rounded up to `ORIGIN_STEP`. Its one `SheetUse` MUST give the path of the sheet that holds it and the child's page.
- **Pages.** The root's page MUST be `1`; the children MUST be numbered from `2` in depth-first order of their module paths, in natural order, and `children` MUST be in that order.
- **Paths.** A symbol of a child sheet MUST have the use path `/<root uuid>/<kicad uuids of the sheet references from the top down>`, and its entry in `paths` the footprint path `/<those sheet uuids>/<kicad uuid of the instance with the lowest unit>` (`H-K-SCH-HIER-PATH`).
- **Nets.** No hierarchical label and no sheet pin MUST be written; every net crosses sheets through its global labels, so net names stay those of the circuit.
- The codes `build.sheet-file-collision` (error) and `build.sheet-stale` (warning) MUST join `schgen.ISSUE_CODES`.

#### Scenario: Two modules, one nested
- **GIVEN** a design with `U1` at the top, `Module("power")` with `R1` and `Module("ldo")` inside it with `C1`, and `Module("io")` with `R2`
- **WHEN** `generate_schematic` runs with the default layout
- **THEN** the root holds `U1` and the sheet references `io` and `power`; `children` is `sheets/io.kicad_sch` (page 2), `sheets/power.kicad_sch` (page 3) and `sheets/power.ldo.kicad_sch` (page 4) in this order; the `power` sheet names `power.ldo.kicad_sch`; and `C1`'s use path ends with the uuids of the references `power` and `ldo`

#### Scenario: Grid on request
- **WHEN** the same design is generated with `layout="grid"`
- **THEN** `children` is empty, the one sheet holds no wire, and its written text equals that of c0061's generator

#### Scenario: Design without modules
- **WHEN** the blink is generated with the default layout
- **THEN** `children` is empty, and the one sheet holds `D1`, `R1` and `U1` with the satellites that "Readable sheet layout" gives

#### Scenario: File collision
- **GIVEN** a top-level module `a.b` and a module `b` inside a module `a`, both with parts
- **WHEN** the sheets are generated
- **THEN** the issues hold `build.sheet-file-collision` naming `a.b` and `a/b`, and the result holds no sheet

## MODIFIED Requirements

### Requirement: Schematic writing per target
`fenolite.backends.kicad.sch.write_schematic(sheet, *, target=DEFAULT_TARGET, allow_lossy=False) -> WriteResult` SHALL return the text of a `.kicad_sch` file for KiCad `target`.0 from a created `SchematicSheet`, and SHALL write no file.
- The header MUST be `(version FORMAT_VERSIONS[FileKind.SCHEMATIC][target])`, `(generator "fenolite")` and `(generator_version "<target>.0")`, followed by the sheet's `uuid` and `paper`, the `title_block` when the sheet has one, and `lib_symbols`.
- The root items MUST follow in the order no-connect flags, wires, labels, symbol instances, sheet references, each kind in the order of its collection, then `sheet_instances` with the sheet's pages when the sheet has pages. A child sheet, which has none, MUST have no `sheet_instances`.
- A wire MUST hold `pts` with its two points, `stroke` with width 0 and type `default`, and `uuid`. A sheet reference MUST hold `at`, `size`, `exclude_from_sim`, `in_bom`, `on_board`, `dnp`, `stroke`, `fill`, `uuid`, the properties `Sheetname` and `Sheetfile`, and `instances` with one `path` per use and its `page`, in this form on both targets (`H-K-SCH-HIER-FILE`).
- A symbol instance MUST hold `lib_id`, `at`, `unit`, `exclude_from_sim`, `in_bom`, `on_board`, `dnp`, `uuid`, one `property` per entry of `properties` (Reference, Value, Footprint, Datasheet and Description first, the others in sorted order), one `pin` with a uuid per pin of its unit, and `instances`.
- **Target 10** MUST also write `body_style` and `in_pos_files` on a symbol, `hide`, `show_name` and `do_not_autoplace` as children of each property, and an `Intersheetrefs` property on each global label. **Target 9** MUST write `hide` inside `effects`, no `body_style`, no `in_pos_files`, and `(embedded_fonts no)` at the end of the root.
- `versions.check_emittable(root, FileKind.SCHEMATIC, target)` MUST run on the final tree. A token the target does not read MUST raise `LossyWriteError` (`FEN-7001`); with `allow_lossy=True` the innermost opaque slot holding it MUST be dropped with one `kicad.sch.dropped-too-new` warning.
- `target` MUST be in `TARGET_MAJORS`; any other value raises `ValueError`. A sheet read from a file MUST raise `ValueError` naming `rebuild_schematic`.
- Writing the same sheet twice MUST give identical text, printed by `dumps` in `kicad` style and ending with a newline. `WriteResult.issues` MUST hold only warnings and infos.
- The writer's codes MUST be the closed set `sch.WRITE_ISSUE_CODES`: `kicad.sch.dropped-too-new` (warning).

#### Scenario: Header for target 9
- **GIVEN** a created sheet with one instance of `Mini:Mini_R` and one global label
- **WHEN** `write_schematic(sheet, target=9)` is called and the text is parsed
- **THEN** the root has `(version 20250114)`, `(generator "fenolite")` and `(generator_version "9.0")`, the symbol has no `body_style` child, and the root ends with `(embedded_fonts no)`

#### Scenario: Target 10 form
- **WHEN** the same sheet is written for target 10
- **THEN** the root has `(version 20260306)`, the symbol holds `(body_style 1)` and `(in_pos_files yes)`, every property holds `show_name` and `do_not_autoplace`, the global label holds an `Intersheetrefs` property, and the root holds no `embedded_fonts`

#### Scenario: Read back equal
- **WHEN** the text written for each target is read with `read_schematic`
- **THEN** the symbol instances, labels and no-connect flags have the positions, names, references and values of the created sheet, and `roundtrip_schematic` passes on the text

#### Scenario: Too-new symbol for target 9
- **GIVEN** a created sheet whose embedded symbol was read from `tests/data/libs/Mini.kicad_sym` (header `20251024`) and holds a token that the inventory dates after the 9.0 constant
- **WHEN** it is written for target 9, and again with `allow_lossy=True`
- **THEN** the first call raises `LossyWriteError` naming the token, and the second returns a text without it and one `kicad.sch.dropped-too-new` warning

#### Scenario: Read sheet refused
- **GIVEN** `tests/data/kicad/schematic/flat.kicad_sch` read with `read_schematic`
- **WHEN** it is passed to `write_schematic`
- **THEN** `ValueError` is raised naming `rebuild_schematic`

#### Scenario: Child sheet form
- **GIVEN** a created child sheet with one instance of `Mini:Mini_R`, one wire, one sheet reference and no pages
- **WHEN** it is written for targets 9 and 10 and each text is parsed
- **THEN** the root holds one `wire` with two points, one `sheet` with the properties `Sheetname` and `Sheetfile`, and no `sheet_instances`

### Requirement: Generated sheet content
`fenolite.backends.kicad.schgen.generate_schematic(design, parts, *, name, target, placements=None, vendor="all", allow_lossy=False, layout="readable") -> GeneratedSchematic` SHALL build the sheets of a design from its circuit, and SHALL return `sheet` (the root `SchematicSheet`), `children` (each child sheet keyed by its path from the root file's folder, in page order; empty for a design without module sheets, "Hierarchical sheets of a design"), `libraries` (per nickname, the symbols of its project library), `rows` (the rows of `sym-lib-table`), `pad_nets` (component id and pad number mapped to the net name of an unconnected pin), `paths` (component id mapped to the path of its symbol) and `issues`.
- **Symbols.** Each component with a resolved symbol MUST give one `SymbolInstance` per unit of that symbol, on the sheet of its module ("Hierarchical sheets of a design"), with body style 1, `lib_ref` naming the embedded definition, `ref`, `value`, `footprint` = `Component.lib_footprint_ref`, and `properties` = the component's `properties` plus `Footprint`. `dnp` MUST be `Component.dnp`; `in_bom` MUST be false when the component's footprint has the attribute `exclude_from_bom`; `on_board` MUST be true. Each instance MUST have one `SymbolUse(<name>, <use path of its sheet>, ref, unit)`: `/<root uuid>` on the root, `/<root uuid>/<sheet uuids from the top down>` on a child sheet. A component without a resolved symbol MUST give no instance.
- **Labels.** Each pin that a net lists and that no wire joins MUST give one `NetLabel("global", netnames.stored_name(<net name>), <the pin's connection point>, shape="passive")`, turned away from the symbol body. Each pair of pins that a snap wire joins MUST give one such label, at the satellite's near pin, as "Readable sheet layout" places it. The sheets MUST hold no junction, no label of another kind and no wire other than snap wires.
- **No-connect flags.** Each pin listed by `Circuit.no_connects` MUST give one `NoConnectFlag` at its connection point. A pin on no net without a mark MUST give neither a label nor a flag.
- **Pins and pads.** Net members and marks are keyed by symbol pin number; with a `pin_pad_map`, the label or flag MUST be placed at the pin whose embedded number is the mapped pad number ("Embedded symbols of a generated sheet").
- **Power flags.** Each net that is a member of an `Interface` with `kind == "power"`, and that no pin of type `power_out` of a component with `dnp == False` is on, MUST give one instance of `fenolite:PWR_FLAG` on the root sheet, with the reference `#FLG<nn>` (numbered from 01 in the order of net names), `in_bom` and `on_board` false, and one global label of the net at its pin.
- **Page.** Every sheet's `title_block` MUST be the board's title block and its `paper` the paper that its own layout chose. The root's `pages` MUST be `(SheetPage("/", "1"),)`; a child's `pages` MUST be empty.
- **Ids.** Ids MUST be derived from the design (`design-model`, "Identifiers of schematic entities"): the sheet from `<name>`, an instance from `<name>:<component path>#<unit>`, a pin label from `<name>:label:<component path>:<pin>`, a flag from `<name>:nc:<component path>:<pin>`, a power flag from `<name>:flag:<net name>` and its label from `<name>:label:flag:<net name>`, a child sheet from `<name>:<module path>`, a sheet reference from `<name>:sheet:<module path>` and a snap wire from `<name>:wire:<component path of its satellite>`. KiCad uuids MUST come from `pcb.kicad_uuid`.
- The function MUST NOT read or write a file, and two calls with equal arguments MUST return equal results.

#### Scenario: Blink
- **GIVEN** the built design and resolved parts of `examples/blink_2layer`
- **WHEN** `generate_schematic` runs for target 10
- **THEN** the sheet holds the instances `D1`, `R1` and `U1` and two power flags, every connected pin is on a global label or on a snap wire whose pair carries one, the label names are `VIN`, `GND`, `LED_DRV` and `LED_A`, there is no no-connect flag, `children` is empty, and `pad_nets` names the 29 pads of `U1` whose pins are on no net

#### Scenario: Marks become flags
- **GIVEN** the blink variant whose unused pins of `U1` are all marked with `no_connect`
- **WHEN** `generate_schematic` runs
- **THEN** the sheet holds 29 no-connect flags, each at the connection point of its pin, and `pad_nets` is unchanged

#### Scenario: Every unit is placed
- **GIVEN** a design with one part `U2` of `Mini:Mini_DualGate`, whose power unit is connected and whose gate pins are marked
- **WHEN** `generate_schematic` runs
- **THEN** the sheet holds three instances with `ref == "U2"` and units 1, 2 and 3

#### Scenario: Power output needs no flag
- **GIVEN** a design whose net `VOUT` is in a power interface and holds a pin of type `power_out` of a part that is not DNP
- **WHEN** `generate_schematic` runs
- **THEN** no power flag carries a label `VOUT`

#### Scenario: Symbol fields equal footprint fields
- **GIVEN** a blink variant whose `R1` has the user property `MPN`
- **WHEN** it is generated
- **THEN** the instance `R1` has `properties["MPN"]` and `properties["fenolite.path"] == "R1"`, equal to the properties of the component

#### Scenario: Deterministic
- **WHEN** `generate_schematic` runs twice on the blink and each sheet is written for target 10
- **THEN** the two texts are byte-identical and hold no date and no absolute path

### Requirement: Deterministic sheet layout
`schlayout.layout_units(units, *, placements=None, flags=(), clusters=(), refs=()) -> SheetLayout` SHALL give every unit, cluster, sheet reference and power flag of one sheet a position on its page, without overlap, in a fixed order, and SHALL choose the paper of that sheet.
- **Order.** Units MUST be sorted by top-level module (units outside a module first), then by the natural order of the component path, then by unit number. A cluster ("Readable sheet layout") MUST take the place of its anchor, and its snapped satellites MUST leave the order. Sheet references come after the units, in the natural order of their module paths, and power flags last, in the order of their nets.
- **Cells.** A unit's cell MUST hold its body and pin connection points, grown on each side by `CHAR_ROOM` (1 524 000 nm) per character of the longest label on that side plus `LABEL_ROOM` (5 080 000 nm), by `CELL_MARGIN` (5 080 000 nm), and by `TEXT_ROOM` (7 620 000 nm) above for Reference and Value. Cell sizes MUST be rounded up to `ORIGIN_STEP` (2 540 000 nm). A cluster's cell MUST hold the boxes of its anchor and satellites, its wires and the rooms of its labels, grown the same way. A sheet reference's cell MUST hold its box and the rooms of its two properties, grown by `CELL_MARGIN`.
- **Flow.** Cells MUST fill rows from the left inside `PAGE_MARGIN` (12 700 000 nm), above a band of `TITLE_BAND` (40 640 000 nm) at the bottom. The first unit of a module MUST start a new row. Sheet references MUST take a row of their own after the units, and power flags a last row.
- **Grid.** Every symbol origin, except a snapped satellite's, and every sheet reference position MUST be a multiple of `ORIGIN_STEP` in both axes; a snapped satellite's origin MUST be a multiple of `GRID`. A pin whose library position is not a multiple of `GRID` (1 270 000 nm) MUST give `kicad.sch.pin-off-grid` (info) naming the symbol.
- **Paper.** `SheetLayout.paper` MUST be the first of A4, A3, A2, A1 and A0, landscape, in which the flow fits. When none fits, `layout_units` MUST return the issue `build.schematic-too-large` (error) naming the sheet and the number of its units.
- **Placements.** A unit named by `placements` MUST take the given origin, rotation and mirror and MUST leave the flow; the others flow as if it were absent. Two cells that overlap MUST give `build.symbol-overlap` (warning); two connection points of different units that coincide MUST give `build.symbol-short` (error).
- Lengths MUST be integer nm; the function MUST use no float.

#### Scenario: Three parts on A4
- **WHEN** the three units of the blink are laid out
- **THEN** the paper is `A4`, the three cells do not overlap, the order is `D1`, `R1`, `U1`, and every origin is a multiple of 2.54 mm

#### Scenario: Modules start rows
- **GIVEN** units `a/R1`, `a/R2` and `b/R1`
- **WHEN** they are laid out
- **THEN** `a/R1` and `a/R2` share a row, and `b/R1` starts the next row

#### Scenario: Larger paper
- **GIVEN** forty units of the 32-pin IC
- **WHEN** they are laid out
- **THEN** the paper is larger than `A4`, and no cell lies outside the page margin or inside the title band

#### Scenario: Too large
- **GIVEN** more units than A0 holds
- **WHEN** they are laid out
- **THEN** the issues hold `build.schematic-too-large` with severity `error`

#### Scenario: Placed unit and a short
- **GIVEN** placements that put `R1` at (25.4 mm, 25.4 mm) and `D1` at a position where one pin of each coincides
- **WHEN** the blink is laid out
- **THEN** `R1` has that origin, and the issues hold one `build.symbol-short` error naming both units

#### Scenario: Sheet references take a row
- **GIVEN** a root with `U1` and the sheet references `io` and `power`
- **WHEN** it is laid out
- **THEN** both references lie in one row below `U1`'s cell, `io` left of `power`, and their positions are multiples of 2.54 mm

### Requirement: Own netlist of a generated sheet
`fenolite.backends.kicad.sch_netlist.own_netlist(sheet, *, project, children={}) -> KicadNetlist` SHALL return the netlist of a root sheet and of the child sheets it names (`children`: each child keyed by its path from the root file's folder), inside the grammar of "Netlist grammar check", read from the sheets alone, as KiCad reads them.
- **Nodes.** Each pin of each symbol instance of every sheet whose reference does not start with `#` MUST be one node, at `schlayout.pin_point` of the instance, with the pin number of its embedded definition and the pin's electrical type as `pintype`, followed by `+no_connect` when a no-connect flag lies on its point.
- **Named nets.** Within one sheet, a pin's point, a wire end and a label's point MUST be joined when they coincide, and the two ends of a wire MUST be joined to each other. The nodes of every group that carries a global label of one text, in any sheet, MUST form one net named by that text as written (`H-K-SCH-WIRE-END`, `H-K-SCH-HIER-FILE`).
- **Unconnected nets.** A node whose group carries no label and no wire MUST form a net of its own, named by `netnames.unconnected_name` with the instance's reference, unit and unit count, the pin's name and its number, flagged or not.
- **Components.** `components` MUST be `sch.components((sheet, *children.values()), project=project)` with the properties of each symbol, and `netclass` MUST be `""`.
- Pins of references that start with `#` MUST NOT be nodes, and a net without a node MUST NOT be listed.
- A sheet outside the grammar MUST raise `NetlistUnsupportedError` carrying the issues of `grammar_issues`.
- The function MUST NOT read the circuit model, a file or a tool.
- `sch_netlist.EVIDENCE` MUST be `INFERRED` (`H-K-NETLIST-OWN`) until that row is `KICAD-VERIFIED (9.0.x, 10.0.x)`.

#### Scenario: Blink sheet
- **GIVEN** the sheet that `generate_schematic` builds for the blink
- **WHEN** `own_netlist(sheet, project="blink")` is called
- **THEN** it holds the components `D1`, `R1` and `U1`, the nets `GND`, `LED_A`, `LED_DRV` and `VIN` with the pins of the circuit, 29 nets whose names start with `unconnected-(U1-`, and no node of a `#FLG` reference

#### Scenario: Flag marks the pin type
- **GIVEN** the blink variant whose unused pins of `U1` are marked
- **WHEN** its sheet is read
- **THEN** the node `U1` `2` has the `pintype` `bidirectional+no_connect`, and its net is still `unconnected-(U1-PA1-Pad2)`

#### Scenario: Pad numbers of a mapped part
- **GIVEN** a design whose `D1` maps pin `1` to pad `2` and pin `2` to pad `1`, with pin `1` on `GND`
- **WHEN** the sheet is generated and read
- **THEN** the net `GND` holds the node (`D1`, `2`)

#### Scenario: Stored names
- **GIVEN** a design with the net `mod/LED_A`
- **WHEN** its sheet is read
- **THEN** the net is named `mod{slash}LED_A`

#### Scenario: Module sheets
- **GIVEN** the sheets that `generate_schematic` builds for the design of "Two modules, one nested"
- **WHEN** `own_netlist(root, project=<name>, children=<children>)` is called
- **THEN** it lists `U1`, `R1`, `C1` and `R2`, and every net of the circuit with its pins, across the four sheets

#### Scenario: Snap wire
- **GIVEN** the sheet of "Resistor on an IC pin"
- **WHEN** it is read
- **THEN** the net of the wired pair holds the `U1` pin and `R1` pin 1 under the label's text

### Requirement: Netlist grammar check
`sch_netlist.grammar_issues(sheet, *, children={}) -> tuple[Issue, ...]` SHALL return one `kicad.sch.netlist-unsupported` issue of severity `error` for each reason that keeps Fenolite from reading the sheet's nets, the reason first in the message, and `()` for a sheet it can read. `sch_netlist.REASONS` MUST be exactly the reasons of this table.

| reason | when |
|---|---|
| `wire` | a sheet root holds an opaque `wire`, `junction`, `bus`, `bus_entry` or `bus_alias`, counted through `sch.opaque_heads(sheet)` |
| `wire-shape` | a modelled wire that is neither horizontal nor vertical, or has no length |
| `wire-end` | a wire end on no pin point |
| `wire-touch` | a wire that meets a pin point, a label or another wire anywhere but at its two ends, or a wire end shared by two wires |
| `label-kind` | a label whose kind is not `global` |
| `sheet` | a sheet reference with pins, one whose file is not a key of `children`, a child named by two references, or a symbol with more than one use |
| `label-off-pin` | a label at a point where no pin connects |
| `two-names` | labels of different texts on one connected group |
| `wire-unlabelled` | a wired group without a label |
| `shared-point` | pins of two instances at one point |
| `frame` | an instance whose rotation and mirror are not in `schlayout.PROVED_FRAMES` |
| `hidden-power` | a hidden pin of type `power_in`, or a definition flagged `power` other than `fenolite:PWR_FLAG` |

- The code joins `sch.ISSUE_CODES`. `sch.opaque_heads(sheet) -> Counter[str]` MUST count the heads of the opaque slots of the sheet root.
- The sheets that `generate_schematic` built, with their `children`, MUST give no issue.

#### Scenario: Generated sheets are inside the grammar
- **WHEN** `grammar_issues` runs on the sheets generated for the blink, for the units design and for the design of "Two modules, one nested", each with its `children`
- **THEN** it returns `()` for each

#### Scenario: Authored sheet with a wire
- **WHEN** it runs on `read_schematic` of `tests/data/kicad/schematic/flat.kicad_sch`
- **THEN** the issues hold the reasons `wire` and `label-kind`, and `own_netlist` raises `NetlistUnsupportedError`

#### Scenario: Hierarchy refused
- **WHEN** it runs on `tests/data/kicad/schematic/hier/top.kicad_sch`
- **THEN** the issues hold the reason `sheet`

#### Scenario: Closed reasons
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py -k reasons` collects the reasons the module emits
- **THEN** they are exactly `sch_netlist.REASONS`

#### Scenario: Missing child
- **GIVEN** the root generated for "Two modules, one nested" and `children` without `sheets/io.kicad_sch`
- **WHEN** `grammar_issues` runs
- **THEN** the issues hold the reason `sheet` naming `sheets/io.kicad_sch`

#### Scenario: Wire through a pin
- **GIVEN** a generated sheet changed in the test so that its snap wire runs on through the near pin to a point beyond it
- **WHEN** `grammar_issues` runs
- **THEN** the issues hold the reasons `wire-end` and `wire-touch`

### Requirement: Generated schematics are documented
`docs/schematic.md` SHALL say what `build` writes for the schematic and why: one symbol per unit, global labels instead of wires, no-connect flags from marks, power flags from power interfaces, shown power pins, pad numbers on mapped symbols, the project libraries, the names of unconnected pads, the stored form of slash nets, the placements file with an example, what is replaced on a rebuild, one sheet per module with the file names under `sheets/`, satellites and their snap wires, `--schematic-layout`, and the limits (each sheet up to A0, only snap wires, no hierarchical labels and no sheet pins, no sheet used twice, no buses). `docs/formats/kicad/schematic.md` SHALL gain the fact rows of the written form per target and of every probe, each with a source, a label and a hypothesis.

#### Scenario: Guide present and checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_repo_layout.py tests/residue` runs
- **THEN** it passes with `docs/schematic.md` present and linked from `README.md` and `docs/dsl.md`
