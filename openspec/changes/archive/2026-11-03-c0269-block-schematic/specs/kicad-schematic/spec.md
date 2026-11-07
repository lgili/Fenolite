## MODIFIED Requirements

### Requirement: Hierarchical sheets of a design
With `layout="readable"` (the default), `generate_schematic` SHALL give each module that holds a part, directly or below it, a child sheet, and SHALL return the root sheet as `sheet` and the child sheets as `children`; a design without such a module gets one sheet. With `layout="grid"`, it SHALL return the one sheet that c0061's generator builds, without satellites, and empty `children`.
- **Content.** The root MUST hold the units of the components outside every module, one sheet reference per top-level module with a part, and the power flags. A child sheet MUST hold the units of its module's own components and one sheet reference per sub-module with a part. The module of a component is its path without the last segment.
- **Files.** A child sheet's path MUST be `schgen.sheet_file(<module path>)`: `sheets/<module path with "/" replaced by ".">.kicad_sch`. The root's sheet references MUST name `sheets/<file>`, and a child's sheet references MUST name `<file>`, from the child's own folder (`H-K-SCH-HIER-FILE`). Two modules whose files are equal, or differ only in letter case, MUST give `build.sheet-file-collision` (error) naming both, and no child sheet.
- **Sheet references.** Each MUST be a `SheetRef` named by the module's last path segment (or `<name> (<block name>)` for a block instance, c0251), with no pin for a plain module and the pins of "Block sheet pins" for a block instance, a height of `REF_HEIGHT` (12 700 000 nm), or for a reference with pins the larger of `REF_HEIGHT` and `ORIGIN_STEP` × (the number of pins on its fuller side + 1), and the width `schlayout.sheet_ref_size(name)`: the larger of 25 400 000 nm and `CHAR_ROOM` × (length of the name + 2), rounded up to `ORIGIN_STEP`. Its one `SheetUse` MUST give the path of the sheet that holds it and the child's page.
- **Pages.** The root's page MUST be `1`; the children MUST be numbered from `2` in depth-first order of their module paths, in natural order, and `children` MUST be in that order.
- **Paths.** A symbol of a child sheet MUST have the use path `/<root uuid>/<kicad uuids of the sheet references from the top down>`, and its entry in `paths` the footprint path `/<those sheet uuids>/<kicad uuid of the instance with the lowest unit>` (`H-K-SCH-HIER-PATH`).
- **Nets.** On the root and on the sheet of a plain module, no hierarchical label and no sheet pin MUST be written. On the sheet of a block instance, "Block sheet pins" gives hierarchical labels for its port nets and sheet pins on its reference. Every other net crosses sheets through its global labels, and every net that crosses keeps a global label of its circuit name on some sheet, so net names stay those of the circuit (`H-K-SCH-BLOCK-PINS`).
- **Groups.** On the sheet of a block instance, the units are arranged by the block's schematic groups ("Block schematic groups on a KiCad sheet").
- **Placements.** A unit named by `placements` is placed on the sheet of its module.

#### Scenario: Two modules, one nested
- **GIVEN** a design with `U1` at the top, `Module("power")` with `R1` and `Module("ldo")` inside it with `C1`, and `Module("io")` with `R2`
- **WHEN** `generate_schematic` runs with the default layout
- **THEN** the root holds `U1` and the sheet references `io` and `power`; `children` is `sheets/io.kicad_sch` (page 2), `sheets/power.kicad_sch` (page 3) and `sheets/power.ldo.kicad_sch` (page 4) in this order; the `power` sheet names `power.ldo.kicad_sch`; and `C1`'s use path ends with the uuids of the references `power` and `ldo`

#### Scenario: Grid on request
- **WHEN** the same design is generated with `layout="grid"`
- **THEN** `children` is empty, the one sheet holds no wire and no sheet reference, and every symbol's use path is `/<root uuid>`

#### Scenario: Design without modules
- **WHEN** the blink is generated with the default layout
- **THEN** `children` is empty, and the one sheet holds `D1`, `R1` and `U1` with the satellites that "Readable sheet layout" gives

#### Scenario: Block instance with ports
- **GIVEN** `examples/blocks/design.py` of c0251, whose block `channel` has the ports `VIN`, `GND` and `EN`, used as `ch0` and `ch1`
- **WHEN** `generate_schematic` runs with the default layout
- **THEN** the sheet references `ch0 (channel)` and `ch1 (channel)` each hold the pins `EN`, `GND` and `VIN`, each child sheet holds hierarchical labels named `EN`, `GND` and `VIN` and no global label of a port net, and the root holds a global label of the circuit net at each sheet pin

#### Scenario: Plain modules unchanged
- **WHEN** the design of "Two modules, one nested" is generated before and after change c0269
- **THEN** the written sheets are byte-identical

#### Scenario: File collision
- **GIVEN** a top-level module `a.b` and a module `b` inside a module `a`, both with parts
- **WHEN** the sheets are generated
- **THEN** the issues hold `build.sheet-file-collision` naming `a.b` and `a/b`, and `children` is empty

### Requirement: Generated sheet content
`fenolite.backends.kicad.schgen.generate_schematic(design, parts, *, name, target, placements=None, vendor="all", allow_lossy=False, layout="readable") -> GeneratedSchematic` SHALL build the sheets of a design from its circuit, and SHALL return `sheet` (the root `SchematicSheet`), `children` (each child sheet keyed by its path from the root file's folder, in page order; empty for a design without module sheets, "Hierarchical sheets of a design"), `libraries` (per nickname, the symbols of its project library), `rows` (the rows of `sym-lib-table`), `pad_nets` (component id and pad number mapped to the net name of an unconnected pin), `paths` (component id mapped to the path of its symbol), `issues`, `unvendored` (the lib ids that `vendor="project"` leaves without a project library, which the build reports) `power_flags` (their number) and `satellites` (the number of snapped satellites, "Readable sheet layout"). `layout` MUST be `"readable"` or `"grid"`; any other value raises `ValueError`. `parts` are the resolved parts of the build: each gives its component, its component path, its flattened symbol, the symbols that symbol extends as their library holds them, its footprint, and the origin of the row that resolved the symbol.
- **Symbols.** Each component with a resolved symbol MUST give one `SymbolInstance` per unit of that symbol, on the sheet of its module ("Hierarchical sheets of a design"), with body style 1, `lib_ref` naming the embedded definition, `ref`, `value`, `footprint` = `Component.lib_footprint_ref`, and `properties` = the component's `properties` plus `Footprint`. `dnp` MUST be `Component.dnp`; `in_bom` MUST be false when the component's footprint has the attribute `exclude_from_bom`; `on_board` MUST be true. Each instance MUST have one `SymbolUse(<name>, <use path of its sheet>, ref, unit)`: `/<root uuid>` on the root, `/<root uuid>/<kicad uuids of the sheet references from the top down>` on a child sheet. A component without a resolved symbol MUST give no instance.
- **Labels.** Each pin that a net lists and that no snap wire joins MUST give one `NetLabel("global", netnames.stored_name(<net name>), <the pin's connection point>, shape="passive")`, turned away from the symbol body, except on the sheet of a block instance for a net that "Block sheet pins" makes hierarchical, where the label is that requirement's hierarchical label. Each pair of pins that a snap wire joins MUST give one such label, at the satellite's near pin, as "Readable sheet layout" places it. The sheets MUST hold no junction, no label of another kind than those of these rules and of "Block sheet pins", and no wire other than snap wires.
- **No-connect flags.** Each pin listed by `Circuit.no_connects` MUST give one `NoConnectFlag` at its connection point. A pin on no net without a mark MUST give neither a label nor a flag.
- **Pins and pads.** Net members and marks are keyed by symbol pin number; with a `pin_pad_map`, the label or flag MUST be placed at the pin whose embedded number is the mapped pad number ("Embedded symbols of a generated sheet").
- **Power flags.** Each net that is a member of an `Interface` with `kind == "power"`, and that no pin of type `power_out` of a component with `dnp == False` is on, MUST give one instance of the power flag on the root sheet, with the reference `#FLG<nn>` (numbered from 01 in the order of net names), `in_bom` and `on_board` false, and one global label of the net at its pin.
- **Library of the power flag.** The flag MUST be the symbol `PWR_FLAG` of the flag library, `symembed.flag_library(libraries)`: the first, in sorted order, of the symbol libraries of the design whose name differs from `fenolite` in letter case only, else `fenolite`. The symbol libraries of the design are the libraries of its parts' symbols and the libraries it authors (`generate_schematic(..., other_libraries=...)`), the built-in catalog's `Fenolite` among them. So a design with a part of the catalog has `Fenolite:PWR_FLAG`, and a design without such a library has `fenolite:PWR_FLAG`, as before change c0143: the files of its build MUST NOT differ from the files of a build that does not look for such a library.
- **Page.** Every sheet's `title_block` MUST be the board's title block and its `paper` the paper that its own layout chose. The root's `pages` MUST be `(SheetPage("/", "1"),)`; a child's `pages` MUST be empty. Every sheet MUST embed, in `lib_symbols`, the definitions its own instances name, sorted by lib id, the power flag last on the root.
- **Ids.** Ids MUST be derived from the design (`design-model`, "Identifiers of schematic entities"): the sheet from `<name>`, an instance from `<name>:<component path>#<unit>`, a pin label from `<name>:label:<component path>:<pin>`, a flag from `<name>:nc:<component path>:<pin>`, a power flag from `<name>:flag:<net name>` and its label from `<name>:label:flag:<net name>`, a child sheet from `<name>:<module path>`, a sheet reference from `<name>:sheet:<module path>`, a sheet pin from `<name>:sheetpin:<module path>:<pin name>`, a hierarchical label at a pin from `<name>:hlabel:<component path>:<pin>` and one at a sheet pin of a nested block from `<name>:hlabel:sheet:<module path>:<pin name>`, a snap wire from `<name>:wire:<component path of its satellite>` and the label of its pair from `<name>:label:<component path of its satellite>:<near pin>`. KiCad uuids MUST come from `pcb.kicad_uuid`.
- The function MUST NOT read or write a file, and two calls with equal arguments MUST return equal results.

#### Scenario: Blink
- **GIVEN** the built design and resolved parts of `examples/blink_2layer`
- **WHEN** `generate_schematic` runs for target 10
- **THEN** the sheet holds the instances `D1`, `R1` and `U1` and two power flags, every connected pin on a global label or on a snap wire whose pair carries one, one label per flag, the label names `VIN`, `GND`, `LED_DRV` and `LED_A`, empty `children`, 29 no-connect flags (the example marks the pins it does not use), each at the connection point of its pin, and `pad_nets` names the 29 pads of `U1` whose pins are on no net

#### Scenario: A pin without a mark
- **GIVEN** the blink without its `no_connect` call
- **WHEN** `generate_schematic` runs
- **THEN** the sheet holds no no-connect flag and the same labels, and `pad_nets` is unchanged

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

#### Scenario: Catalog parts with a supply
- **GIVEN** a design with `J1` of `Fenolite:Connector_2`, `U1` of `Fenolite:Linear_Regulator` and a `Power` interface of the nets on the regulator's `IN` and `GND` pins
- **WHEN** it is built for target 9 and for target 10
- **THEN** no issue is an error, the root sheet holds two instances of `Fenolite:PWR_FLAG` and none of `fenolite:PWR_FLAG`, and on `kicad-cli` of the running major the ERC report holds no `power_pin_not_driven`

#### Scenario: Other designs keep their bytes
- **WHEN** the blink of `examples/blink_2layer` is built for target 9 and for target 10
- **THEN** its sheet holds `fenolite:PWR_FLAG`, and every pin of `tests/unit/lens/test_build_bytes_pinned.py` and every committed golden is the one it was before change c0143

#### Scenario: Altium build unchanged
- **WHEN** the design of "Catalog parts with a supply" is built for Altium in the ASCII and in the binary form
- **THEN** no file holds `PWR_FLAG`, and the files equal those of a build in which `symembed.flag_library` always gives `fenolite`

### Requirement: Own netlist of a generated sheet
`fenolite.backends.kicad.sch_netlist.own_netlist(sheet, *, project, children={}) -> KicadNetlist` SHALL return the netlist of a root sheet and of the child sheets it names (`children`: each child keyed by its path from the root file's folder), inside the grammar of "Netlist grammar check", read from the sheets alone, as KiCad reads them.
- **Nodes.** Each pin of each symbol instance of every sheet whose reference does not start with `#` MUST be one node, at `schlayout.pin_point` of the instance, with the pin number of its embedded definition and the pin's electrical type as `pintype`, followed by `+no_connect` when a no-connect flag lies on its point.
- **Wires.** The wires of a sheet are its `wires` and, for a sheet read from a file, the opaque root `wire` slots that `sch.opaque_wires(sheet)` gives as point lists; both are read alike, so a built project is read back from its files.
- **Sheet pins.** The pins of a sheet reference are its `pins` and, for a sheet read from a file, the opaque `pin` slots of the reference that `sch.opaque_sheet_pins(ref)` gives as (name, shape, point); both are read alike.
- **Named nets.** Within one sheet, a pin's point, a wire end and a label's point MUST be joined when they coincide, and the two ends of a wire MUST be joined to each other (`H-K-SCH-WIRE-END`). Within one sheet, groups that carry hierarchical labels of one text MUST be joined, and joined to the group of the sheet pin of that name on the reference to that sheet in its parent; a sheet pin's point joins like a label's. The nodes of every group that carries a global label of one text, in any sheet, MUST form one net named by `netnames.stored_name` of that text, which is the text itself for a label that `build` wrote (`H-K-SCH-HIER-FILE`); a net joined through hierarchical labels and sheet pins takes the name of its global label (`H-K-SCH-BLOCK-PINS`).
- **Unconnected nets.** A node whose group carries no label and no wire MUST form a net of its own, named by `netnames.unconnected_name` with the instance's reference, unit and unit count, the pin's name and its number, flagged or not. Pins of one instance that have one name and connect at one such point (stacked pins) MUST form one net instead, named by `netnames.open_name`: with the number that is the lowest in code-point order among them, and starting with `Net-(` in place of `unconnected-(` when no flag lies on the point (`H-K-SCH-STACKED-OPEN`).
- **Components.** `components` MUST be `sch.components((sheet, *children.values()), project=project)`, each with the properties of its symbol other than `Reference` and `Value` (the fields KiCad's export lists), and `netclass` MUST be `""`. Only the pins of instances with a use of `project` are nodes.
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

#### Scenario: Block sheets
- **GIVEN** the sheets that `generate_schematic` builds for `examples/blocks/design.py` of c0251
- **WHEN** `own_netlist(root, project=<name>, children=<children>)` is called on the created sheets and on the sheets read back from the written files
- **THEN** both give every net of the circuit with its pins under its circuit name, and the net `VIN` holds the pin 1 of `ch0/R_EN` and of `ch1/R_EN`

#### Scenario: Snap wire
- **GIVEN** the sheet of "Resistor on an IC pin"
- **WHEN** it is read
- **THEN** the net of the wired pair holds the `U1` pin and `R1` pin 1 under the label's text

#### Scenario: Read back from the written files
- **GIVEN** the texts that `write_schematic` gives for the root and children of "Two modules, one nested" with a snapped satellite, each read with `read_schematic`
- **WHEN** `own_netlist` is called on the read sheets
- **THEN** it equals the netlist of the created sheets

#### Scenario: Stacked pins
- **GIVEN** the sheet of the stacked design ("Pins with several pads on a generated sheet")
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py -k stacked` reads it, as generated and as read back from the written files
- **THEN** the net `GND` holds the nodes (`U1`, `7`) with the `pintype` `power_in` and (`U1`, `27`) with `passive`; one net `unconnected-(U1-Pad15)` holds the nodes `5`, `15` and `9`, each `pintype` ending in `+no_connect`; and one net `Net-(D2-K-Pad17)` holds the nodes `21` and `17`

### Requirement: Netlist grammar check
`sch_netlist.grammar_issues(sheet, *, children={}) -> tuple[Issue, ...]` SHALL return one `kicad.sch.netlist-unsupported` issue of severity `error` for each reason that keeps Fenolite from reading the nets of the sheet and of its `children`, the reason first in the message, and `()` for sheets it can read. `sch_netlist.REASONS` MUST be exactly the reasons of this table.

| reason | when |
|---|---|
| `wire` | a sheet root holds a `junction`, `bus`, `bus_entry` or `bus_alias`, counted through `sch.opaque_heads(sheet)` |
| `wire-shape` | a wire that has not two points, is neither horizontal nor vertical, or has no length |
| `wire-end` | a wire end on no pin point |
| `wire-touch` | a wire that meets a pin point, a label or another wire anywhere but at its two ends, or a wire end shared by two wires |
| `label-kind` | a label whose kind is neither `global` nor `hierarchical`, or a hierarchical label on a root sheet |
| `sheet` | a sheet pin with no hierarchical label of its name on the child, a hierarchical label with no sheet pin of its name on the reference to its sheet, two sheet pins of one name on one reference, a sheet pin off the edge of its box, a sheet reference whose file (resolved from the folder of the sheet that names it) is not a key of `children`, a child named by two references or by none, a symbol with more than one use, or a symbol whose use is not at the instance path of its sheet |
| `undefined-symbol` | an instance whose definition the sheet does not embed, or embeds as a derived symbol without pins |
| `label-off-pin` | a label at a point where no pin connects |
| `two-names` | labels of different texts on one connected group |
| `wire-unlabelled` | a wired group without a label |
| `shared-point` | pins of two instances at one point, or several pins of one instance at a point that carries no label, unless those pins have one name (the stacked pins of "Own netlist of a generated sheet") |
| `frame` | an instance whose rotation and mirror are not in `schlayout.PROVED_FRAMES` |
| `hidden-power` | a hidden pin of type `power_in`, or a definition flagged `power` other than Fenolite's power flag (`symembed.is_power_flag`: `PWR_FLAG` of a library named `fenolite` in any letter case) |

- The code and its severity MUST be `sch_netlist.ISSUE_CODES`; the closed set `sch.ISSUE_CODES` of "Schematic read issue codes" is not widened, because reading a sheet never gives this issue. `sch.opaque_heads(sheet) -> Counter[str]` MUST count the heads of the opaque slots of the sheet root, and MUST be empty for a sheet that was not read from a file.
- `sch.opaque_wires(sheet) -> tuple[tuple[Point, ...], ...]` MUST give the points of each opaque root `wire` slot of a read sheet, in file order, and `()` for a created sheet.
- The sheets that `generate_schematic` built, with their `children`, MUST give no issue.

#### Scenario: Generated sheets are inside the grammar
- **WHEN** `grammar_issues` runs on the sheets generated for the blink, for the units design and for the design of "Two modules, one nested", each with its `children`
- **THEN** it returns `()` for each

#### Scenario: Block sheets are inside the grammar
- **WHEN** `grammar_issues` runs on the sheets generated for `examples/blocks/design.py` of c0251 with their `children`
- **THEN** it returns `()`

#### Scenario: Sheet pin without a label
- **GIVEN** those sheets changed in the test so that the hierarchical labels `EN` of the child `sheets/ch0.kicad_sch` are removed
- **WHEN** `grammar_issues` runs
- **THEN** the issues hold the reason `sheet` naming `ch0` and `EN`

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

#### Scenario: Stacked pins are inside the grammar
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py -k stacked_grammar` runs `grammar_issues` on the sheet of the stacked design, and on a copy in which one of the stacked pins of an open pin is renamed
- **THEN** the first gives `()`, and the second gives the reason `shared-point`

#### Scenario: The flag of the catalog library is no power symbol
- **WHEN** the own netlist of the built design of "Generated sheet content", scenario "Catalog parts with a supply", is read
- **THEN** no `NetlistUnsupportedError` is raised, and the build's guard `build.schematic-netlist-differs` reports nothing

### Requirement: Deterministic sheet layout
`schlayout.layout_units(units, *, placements=None, flags=(), clusters=(), refs=(), sheet="", groups=(), widths=None) -> SheetLayout` SHALL give every unit, cluster, sheet reference and power flag of one sheet a position on its page, without overlap, in a fixed order, and SHALL choose the paper of that sheet.
- **Order.** Units MUST be sorted by top-level module (units outside a module first), then by the natural order of the component path, then by unit number. On the sheet of a block instance with schematic groups (`groups`), units MUST instead be ordered by group, in the order of "Block schematic groups on a KiCad sheet", then by the member order of the group, then by unit number, and units in no group come last in the natural order. A cluster ("Readable sheet layout") MUST take the place of its anchor, and its snapped satellites MUST leave the order. Sheet references come after the units, in the natural order of their module paths, and power flags last, in the order of their nets.
- **Units.** A unit is given as `UnitBox(key, pins, body, symbol, text=0)`: `key` is the component path, with `#<unit>` for a unit above 1; `pins` are `UnitPin(number, at, angle, label)` in the library frame, `label` being the length of the label text at that pin (0 without one); `body` is the box of what the unit draws; `symbol` names the library symbol in messages; `text` is the length of the longer of its Reference and Value. A sheet reference is given as `RefBox(path, name, file, pins=())`: the module path, the sheet name, the `Sheetfile` text and its sheet pins with their sides and label lengths; its layout key is `schlayout.ref_key(path)`, and its origin is the top-left corner of its box. `SheetLayout` holds `paper`, `origins` (key to `SymbolPlacement`), `cells` and `issues`. Rows are packed by `geometry.shelf.shelf_pack`, which the Altium sheet layout uses too.
- **Cells.** A unit's cell MUST hold its body and pin connection points, grown on each side by `CHAR_ROOM` (1 524 000 nm) per character of the longest label on that side plus `LABEL_ROOM` (5 080 000 nm), by `CELL_MARGIN` (5 080 000 nm), and by `TEXT_ROOM` (7 620 000 nm) above for Reference and Value. Cell sizes MUST be rounded up to `ORIGIN_STEP` (2 540 000 nm). A cluster's cell MUST hold the cell of its anchor and, each grown by `CELL_MARGIN`, the boxes of its satellites, its wires and the rooms of its labels. A sheet reference's cell MUST hold its box, the rooms of its two properties (`REF_TEXT`, 2 540 000 nm, above and below, and `CHAR_ROOM` per character of the file text) and, on each side with sheet pins, `CHAR_ROOM` per character of the longest label at those pins plus `LABEL_ROOM`, grown by `CELL_MARGIN`. A label length of a unit pin MUST be taken from `widths` when it names the pin's key, so that instances of one block share one arrangement ("Shared arrangement of block sheets").
- **Flow.** Cells MUST fill rows from the left inside `PAGE_MARGIN` (12 700 000 nm), above a band of `TITLE_BAND` (40 640 000 nm) at the bottom. The first unit of a module, and the first unit of each schematic group, MUST start a new row; in a group whose flow is `top-to-bottom`, each cell MUST start a row of its own, at the left edge of the group's first cell. Sheet references MUST take rows of their own after the units, and power flags a last row.
- **Grid.** Every symbol origin that the flow gives, and every sheet reference position, MUST be a multiple of `ORIGIN_STEP` in both axes; a snapped satellite's origin MUST be a multiple of `GRID`. A pin whose library position is not a multiple of `GRID` (1 270 000 nm) MUST give `kicad.sch.pin-off-grid` (info) naming the symbol.
- **Paper.** `SheetLayout.paper` MUST be the first of A4, A3, A2, A1 and A0, landscape, in which the flow fits. When none fits, `layout_units` MUST return the issue `build.schematic-too-large` (error) naming the sheet (`sheet`, when given) and the number of its units.
- **Placements.** A unit named by `placements` MUST take the given origin, rotation and mirror and MUST leave the flow; the others flow as if it were absent. Two cells that overlap MUST give `build.symbol-overlap` (warning); two connection points of different units that coincide MUST give `build.symbol-short` (error). A snapped satellite lies inside the cell of its cluster and MUST NOT be reported as overlapping it; a placed anchor keeps its cluster around its given origin.
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

#### Scenario: Groups start rows
- **GIVEN** the units `d/top`, `d/bot` and `d/C1` of a block instance `d` whose groups are `chain` (`top`, `bot`, flow `top-to-bottom`) and then `filter` (`C1`)
- **WHEN** they are laid out
- **THEN** `d/top` and `d/bot` are in two rows with equal x, `d/C1` starts the next row, and every origin is a multiple of 2.54 mm

#### Scenario: Cluster takes the anchor's place
- **GIVEN** the units `R1`, `U1` and `U2`, and a cluster of `U1` with `R1` snapped to its left
- **WHEN** they are laid out
- **THEN** the order of the cells is `U1`, `U2`, the origin of `R1` is the origin of `U1` plus the cluster's offset, and the cell of `U1` holds the box of `R1`

## ADDED Requirements

### Requirement: Block sheet pins
On the sheet of a block instance, each connection point (a unit pin, or a sheet pin of a nested block) of a net that exactly one port member of that block binds SHALL carry a hierarchical label named by the member's sheet name ("Sheet names of block ports" of `design-dsl`), with the shape `input`, `output` or `bidirectional` for the port direction `in`, `out` or `inout`. The block's reference SHALL hold one sheet pin of that name and shape.

#### Scenario: Port net labelled by the port
- **GIVEN** `examples/blocks/design.py` of c0251, with the outside net `VIN` joined to `ch0.VIN`
- **WHEN** `generate_schematic` runs
- **THEN** pin 1 of `ch0/R_EN` on `sheets/ch0.kicad_sch` carries a hierarchical label `VIN` of shape `input`, the reference `ch0 (channel)` holds a sheet pin `VIN` of shape `input`, and the root holds a global label `VIN` at that sheet pin

#### Scenario: Interface port members
- **GIVEN** a block with `b.port("I2C", I2C)` whose members reach two sensor pins, used as `sen`
- **WHEN** its sheets are generated
- **THEN** the reference of `sen` holds the sheet pins `I2C_scl` and `I2C_sda`, and the sensor pins carry hierarchical labels of those names

### Requirement: Sheet pin geometry
A sheet pin of an `in` port SHALL lie on the left edge of its reference's box, and one of an `out` or `inout` port on the right edge. Pins on each side MUST be ordered by name in code-point order, at `ORIGIN_STEP` pitch from one step below the top, on the 1.27 mm grid. A member that binds no net, or whose net has no connection point on the block's sheet, MUST get no sheet pin.

#### Scenario: Sides and order
- **GIVEN** a block with the ports `VIN` and `GND` (direction `in`) and `EN` (direction `inout`)
- **WHEN** its reference is generated
- **THEN** `GND` and `VIN` lie on the left edge in this order, 2.54 mm apart, and `EN` lies on the right edge

### Requirement: Block ports sharing a net
When two or more port members of one block bind one net, that net SHALL keep the global labels of "Generated sheet content" on the block's sheet, those members SHALL get no sheet pin, and the generator SHALL give `build.block-port-merged` (info) naming the block path and the members. The code joins the closed set of "Generated schematic issue codes" as a later code.

#### Scenario: Two ports joined outside
- **GIVEN** a block with the ports `A` and `B`, used as `x`, and `connect(x.A, x.B)` in the design
- **WHEN** its sheets are generated
- **THEN** the pins of that net on `x`'s sheet carry global labels, the reference holds no pin `A` or `B`, and the issues hold one `build.block-port-merged` naming `x`, `A` and `B`

### Requirement: Block schematic groups on a KiCad sheet
With `layout="readable"`, the sheet of a block instance SHALL order its units by the block's schematic groups ("Block schematic groups in the DSL" of `design-dsl`): groups in their resolved order, members in their order with the anchor first. Parts that no group holds SHALL form the default group last, in the flow of a module's sheet. A satellite MUST snap only to an anchor of its own group.

#### Scenario: Declared chain
- **GIVEN** the block `rc_filter` with `b.schematic(schematic_group("chain", r1, c1, anchor=r1))`, used as `f1`
- **WHEN** its sheet is generated
- **THEN** `f1/R` comes before `f1/C` in the layout order, and both lie in the first row of the sheet

#### Scenario: Default group
- **GIVEN** the same block without `b.schematic`
- **WHEN** its sheet is generated
- **THEN** the sheet's unit origins equal those of a plain module holding the same parts with the same labels

### Requirement: Shared arrangement of block sheets
Instances of one block whose sheets hold the same unit keys relative to the instance path, the same groups and the same sheet pins SHALL be laid out with one label-width map, the longest label per relative pin key over those instances, so that their unit origins are equal. A unit named by `schematic-placements.toml` MUST take its placement, and its instance then leaves the shared arrangement.

#### Scenario: Two instances, one arrangement
- **GIVEN** `examples/blocks/design.py` of c0251, where `ch0` and `ch1` connect their ports to outside nets of different name lengths
- **WHEN** the sheets are generated
- **THEN** every unit of `sheets/ch0.kicad_sch` has the origin of the unit of the same local path on `sheets/ch1.kicad_sch`

### Requirement: Sheet pins and hierarchical labels written
`sch.write_schematic` SHALL write each `SheetPin` of a created sheet reference as a `pin` child of its `sheet`, after its properties and before `instances`, with its name, shape, `at`, `effects` and `uuid`, and each hierarchical label as `hierarchical_label` with `shape`, `at`, `effects` and `uuid`, on both targets. A sheet without them MUST keep its bytes.

#### Scenario: Pins read back
- **WHEN** the root of `examples/blocks/design.py` is written for targets 9 and 10 and read with `read_schematic`
- **THEN** each reference holds opaque `pin` slots whose names, shapes and points `sch.opaque_sheet_pins` gives equal to the created pins

#### Scenario: KiCad reads the block netlist
- **GIVEN** the confirmed build of `examples/blocks/design.py` for the running major
- **WHEN** the KiCad CI job exports its netlist with `kicad-cli sch export netlist` and runs ERC
- **THEN** every net of the circuit is listed under its circuit name with its pins, and the ERC report holds no violation about sheet pins or hierarchical labels (`H-K-SCH-BLOCK-PINS`, `H-K-SCH-BLOCK-ERC`)
