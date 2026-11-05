## ADDED Requirements

### Requirement: Wired sheet layout
With `layout="wired"`, `generate_schematic` SHALL draw each sheet as `fenolite.backends.kicad.schwired` lays it out (design D4 to D8 of change c0406): anchors (units with three pins or more, units of multi-unit parts, and parts whose two pins do not face each other) unturned; anchors ranked with one-sided anchors (connectors) last, then by falling pin count; each two-pin part attached to the best-ranked free node over both of its pins (an anchor pin, or the far pin of a part already attached) in the columns or rows beside that side of its anchor; a part between two signal pins of one anchor drawn level above that anchor as a bridge; parts between two supplies in the decoupling row of the first anchor with a pin on their non-ground supply; parts that attach nowhere drawn as chains; clusters in columns from left to right by the direction of their pins, a column taller than `schwired.COLUMN_HEIGHT` wrapped, and each follower (a one-sided anchor, or a unit of at most four pins none of which is an input or output) beside the cluster it shares most signal nets with, mirrored to face it; every signal net routed orthogonally on `GRID`; every supply pin on a power symbol ("Power symbols on a generated sheet"); and one label per drawn group of a signal net ("Net names on a wired sheet").
- **Wires.** Every wire MUST be horizontal or vertical with both ends on `GRID`, MUST leave and enter a pin along the pin's outward direction, and MUST NOT pass over a body, a pin line, a pin point, a text room, a label room or a power symbol, nor share a stretch with a wire of another net. Two wires of different nets MAY cross only where both run straight; no wire MAY end on the inside of another wire except at a junction.
- **Joints.** Where three wire directions meet, or a pin point holds two wires, there MUST be one `Junction`; each wire MUST be cut at the junctions on it; no point MAY hold four wire directions.
- **Per-cluster drawing.** A net MUST be drawn per cluster, each cluster's pins wired among themselves and each such group named by its own label, when it is named by an interface of kind `i2c`, `spi`, `uart` or `usb2` and has pins in two clusters, when two of its clusters lie more than `schwired.ROUTE_REACH` (101 600 000 nm, Manhattan) apart, or when one of its terminals cannot be joined within the search budget; `GeneratedSchematic.fallbacks` MUST count the nets drawn per cluster for the last reason.
- **Signal flow.** A cluster that holds a pin of type `output`, `power_out` or `open_collector` on a non-ground net MUST lie in a column to the left of every cluster that holds an `input` or `power_in` pin of that net, unless a cycle of such nets joins them.
- **Texts.** Every Reference and Value of a placed unit MUST be written at a pose the layout gives, and no text room MUST overlap a body, a pin line, a wire, a label room, a power symbol with its Value, or another text room.
- **Paper.** Each sheet MUST take the smallest paper of `schlayout.PAPERS` that holds its drawing inside `PAGE_MARGIN` and above `TITLE_BAND`.
- The function MUST be pure, MUST use integer nm, and two calls with equal arguments MUST return equal results.

#### Scenario: Divider and filter on an op-amp
- **GIVEN** the authored design `opamp_stage` of `tests/_wireddesigns.py`: an op-amp, an input RC filter, a feedback divider and decoupling capacitors on its supply pins
- **WHEN** it is built with the default layout
- **THEN** the divider's mid-point, the filter node and the output are drawn with wires and no label but their net name, the decoupling capacitors stand under the op-amp with a rail symbol above and a ground symbol below, and the build's netlist guard reports nothing

#### Scenario: Wired designs measured
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_schwired.py -k measures` builds every design of `tests/_wireddesigns.py` and measures each sheet with `schreadability.measure_sheet`
- **THEN** every design has no overlap, no wire over a pin or body, no four-way joint, no T without a junction, at most three crossings and no net drawn per cluster for want of a join, and its wired sheets hold fewer than half the labels of its readable sheets

#### Scenario: Fewer labels than the readable layout
- **WHEN** the same designs are generated with `"readable"` and with `"wired"`
- **THEN** each wired sheet holds fewer labels than the readable sheet of the same module, and every wired sheet holds wires

#### Scenario: Generated designs stay inside the guard
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_schwired.py -k gendesigns` builds the 25 designs of `tests/_gendesigns.py` of each seed with the default layout
- **THEN** no build reports `build.schematic-netlist-differs`, and every written sheet passes `grammar_issues`

#### Scenario: KiCad loads the wired sheets
- **WHEN** `tests/kicad/schematic/test_wired_oracle.py` runs `kicad-cli sch erc` and `sch export netlist` on each built design of `tests/_wireddesigns.py`
- **THEN** ERC reports no error, and the exported nets equal the circuit's nets by name and members

#### Scenario: Deterministic
- **WHEN** a design of `tests/_wireddesigns.py` is generated twice
- **THEN** the written sheets are byte-identical

### Requirement: Power symbols on a generated sheet
On a wired sheet each pin on a supply net (design D2 of change c0406: a net of an interface of kind `power` or `ground`, a net on a `power_in` or `power_out` pin of a fitted part, or a net whose stored name matches `schwired.SUPPLY_NAMES`) SHALL be joined by a wire to an instance of a Fenolite power symbol of its net, and SHALL carry no label.
- **Symbols.** `symembed.power_symbol(kind, target, library=FLAG_LIBRARY) -> EmbeddedSymbol` MUST give `GND` (kind `"ground"`) or `RAIL` (kind `"rail"`), authored for Fenolite: flagged `power` (`power global` for target 10), with one hidden `power_in` pin of length 0 at the origin and a visible Value. They MUST be embedded in the flag library (`symembed.flag_library`) beside `PWR_FLAG`, and each instance MUST have `in_bom` and `on_board` false, the Reference `#PWR<nnn>` numbered from 001 over the whole design, and the Value `netnames.stored_name` of its net.
- **Direction.** The glyph MUST continue its stub away from the pin. Ground and negative supplies MUST point down and rails up where the pin points that way or a vertical two-pin part ends there; a pin on a side edge MAY take a glyph pointing outwards.
- **Adjacent pins.** Adjacent pins of one anchor side on one supply net, with no other connected pin between them, MUST share one power symbol through a wire that joins their stubs.
- **Flags.** Each supply net drawn with power symbols on which no `power_out` pin of a fitted part lies MUST give one power flag on the root sheet, joined by one wire to a power symbol of its net; the flags of "Generated sheet content" for declared supplies are among them.

#### Scenario: Value names the net
- **GIVEN** an authored sheet with two instances of `RAIL` whose Values are `+5V` and `VBAT`, each on a pin end of a resistor, and a global label `VBAT` on the other pin of the second resistor
- **WHEN** `kicad-cli sch export netlist` of 9.0.9 and of 10.0.6 reads it
- **THEN** the nets are `+5V` and `VBAT`, each holding both pins of its resistor

#### Scenario: Decoupling capacitor
- **GIVEN** a design whose capacitor `C1` lies between `+3V3` and `GND` and whose IC `U1` has a pin on `+3V3`
- **WHEN** it is built with the default layout
- **THEN** `C1` stands vertical in the decoupling row of `U1`, a `RAIL` symbol of Value `+3V3` above it and a `GND` symbol below it, and `+3V3` and `GND` have no label on the sheet

### Requirement: Net names on a wired sheet
On a wired sheet each connected group of a signal net SHALL carry exactly one label: the global label of the net (`netnames.stored_name`), or on the sheet of a block instance the hierarchical label of "Block sheet pins" for its port nets. The label of a group of one pin MUST lie at that pin, turned away from the body; the label of a wired group MUST lie on the inside of one of its wire segments, at a point that is no corner, junction or crossing, turned across the segment, where its room is free, vertical segments first; a group whose wires leave no such point MUST take the inner point and direction whose room holds the fewest busy cells. The ids of labels MUST be derived from `<name>:label:net:<module>:<net name>:<group index>` (`hlabel` for a hierarchical label).

#### Scenario: Two-pin net
- **GIVEN** a series resistor whose far pin is wired to an LED's anode
- **WHEN** the sheet is generated
- **THEN** the net between them holds one wire run and one global label on it, and neither pin carries a label of its own

#### Scenario: Net to another sheet
- **GIVEN** a net with two pins on a module's sheet and one pin on the root
- **WHEN** the design is built with the default layout
- **THEN** the module's sheet holds one global label of the net and the root one, and KiCad joins the three pins

### Requirement: Wired layout fallbacks
A sheet with a unit named by `schematic-placements.toml`, or whose wired drawing fits no paper of `schlayout.PAPERS`, SHALL be drawn with the `"readable"` layout, and the build SHALL report one `build.schematic-wired-fallback` issue of severity `info` per such sheet, naming the sheet and the reason.

#### Scenario: Placed unit
- **GIVEN** the authored design `transistor_switch` with a symbol placement for `R1`
- **WHEN** it is built with the default layout
- **THEN** its sheet is drawn with `"readable"` (no junction, no power symbol) and the issues hold one `build.schematic-wired-fallback` naming the sheet and the placements file

### Requirement: Readability measures of a generated sheet
`fenolite.backends.kicad.schreadability.measure_sheet(sheet) -> SheetMeasures` SHALL measure one `SchematicSheet` from its own content and embedded definitions: `labels` (per kind), `wires` (segments), `junctions`, `power_symbols`, `crossings` (points inside two wires that join nothing), `wire_over_pin` (pin points inside a wire), `wire_over_body` (wire segments that enter a body box), `four_way` (points with four wire directions), `bare_tees` (wire ends on the inside of another wire without a junction) and `overlaps` (pairs of overlapping rooms among texts, labels, power symbols and bodies, text extents estimated as one character height per character and 2 mm per line). The function MUST be pure and MUST NOT read a file.

#### Scenario: Readable sheet measured
- **WHEN** the sheet that the `"readable"` layout builds for the blink is measured
- **THEN** `labels["global"]` equals the number of its labels, `junctions` is 0 and `crossings` is 0

## MODIFIED Requirements

### Requirement: Generated sheet content
`fenolite.backends.kicad.schgen.generate_schematic(design, parts, *, name, target, placements=None, vendor="all", allow_lossy=False, layout="readable") -> GeneratedSchematic` SHALL build the sheets of a design from its circuit, and SHALL return `sheet` (the root `SchematicSheet`), `children` (each child sheet keyed by its path from the root file's folder, in page order; empty for a design without module sheets, "Hierarchical sheets of a design"), `libraries` (per nickname, the symbols of its project library), `rows` (the rows of `sym-lib-table`), `pad_nets` (component id and pad number mapped to the net name of an unconnected pin), `paths` (component id mapped to the path of its symbol), `issues`, `unvendored` (the lib ids that `vendor="project"` leaves without a project library, which the build reports) `power_flags` (their number) and `satellites` (the number of snapped satellites, "Readable sheet layout"). `layout` MUST be `"readable"`, `"grid"` or `"wired"` ("Wired sheet layout", change c0406); any other value raises `ValueError`. `GeneratedSchematic` MUST also return `power_symbols` (the number of power symbol instances) and `fallbacks` (the nets a wired sheet draws per cluster because a terminal could not be joined); both are 0 for `"readable"` and `"grid"`. `build` and `fenolite build` MUST default to `"wired"`; the function itself keeps `"readable"` as its default. `parts` are the resolved parts of the build: each gives its component, its component path, its flattened symbol, the symbols that symbol extends as their library holds them, its footprint, and the origin of the row that resolved the symbol.
- **Symbols.** Each component with a resolved symbol MUST give one `SymbolInstance` per unit of that symbol, on the sheet of its module ("Hierarchical sheets of a design"), with body style 1, `lib_ref` naming the embedded definition, `ref`, `value`, `footprint` = `Component.lib_footprint_ref`, and `properties` = the component's `properties` plus `Footprint`. `dnp` MUST be `Component.dnp`; `in_bom` MUST be false when the component's footprint has the attribute `exclude_from_bom`; `on_board` MUST be true. Each instance MUST have one `SymbolUse(<name>, <use path of its sheet>, ref, unit)`: `/<root uuid>` on the root, `/<root uuid>/<kicad uuids of the sheet references from the top down>` on a child sheet. A component without a resolved symbol MUST give no instance.
- **Labels.** Each pin that a net lists and that no snap wire joins MUST give one `NetLabel("global", netnames.stored_name(<net name>), <the pin's connection point>, shape="passive")`, turned away from the symbol body, except on the sheet of a block instance for a net that "Block sheet pins" makes hierarchical, where the label is that requirement's hierarchical label. Each pair of pins that a snap wire joins MUST give one such label, at the satellite's near pin, as "Readable sheet layout" places it. With `"readable"` and `"grid"` the sheets MUST hold no junction, no label of another kind than those of these rules and of "Block sheet pins", and no wire other than snap wires. With `"wired"` the labels, wires, junctions and power symbols are those of "Wired sheet layout", "Power symbols on a generated sheet" and "Net names on a wired sheet".
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
- **Named nets.** Within one sheet, a pin's point, a wire end, a junction and a label's point MUST be joined when they coincide, the two ends of a wire MUST be joined to each other (`H-K-SCH-WIRE-END`), a label whose point lies on the inside of a wire MUST be joined to that wire, and two wires that cross inside both MUST NOT be joined (change c0406). The pin of an instance of Fenolite's `GND` or `RAIL` power symbol ("Power symbols on a generated sheet") MUST join its point like a global label whose text is the instance's Value, and two pins of different instances at one point MUST be joined when one of them is such a power symbol's. Within one sheet, groups that carry hierarchical labels of one text MUST be joined, and joined to the group of the sheet pin of that name on the reference to that sheet in its parent; a sheet pin's point joins like a label's. The nodes of every group that carries a global label of one text, in any sheet, MUST form one net named by `netnames.stored_name` of that text, which is the text itself for a label that `build` wrote (`H-K-SCH-HIER-FILE`); a net joined through hierarchical labels and sheet pins takes the name of its global label (`H-K-SCH-BLOCK-PINS`).
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
| `wire` | a sheet root holds a `bus`, `bus_entry` or `bus_alias`, counted through `sch.opaque_heads(sheet)` (the `junctions` of a created sheet and the `junction` slots of a read sheet are read, change c0406) |
| `wire-shape` | a wire that has not two points, is neither horizontal nor vertical, or has no length |
| `wire-end` | a wire end on no pin point, no end of another wire and no junction |
| `wire-touch` | a wire whose inside holds a pin point, a junction, or an end of another wire; two wires that share a stretch; or two wires that meet inside one and at an end of the other (a label on the inside of a wire and a crossing inside both are read, change c0406) |
| `label-kind` | a label whose kind is neither `global` nor `hierarchical`, or a hierarchical label on a root sheet |
| `sheet` | a sheet pin with no hierarchical label of its name on the child, a hierarchical label with no sheet pin of its name on the reference to its sheet, two sheet pins of one name on one reference, a sheet pin off the edge of its box, a sheet reference whose file (resolved from the folder of the sheet that names it) is not a key of `children`, a child named by two references or by none, a symbol with more than one use, or a symbol whose use is not at the instance path of its sheet |
| `undefined-symbol` | an instance whose definition the sheet does not embed, or embeds as a derived symbol without pins |
| `label-off-pin` | a label at a point where no pin, no wire and no sheet pin connects |
| `two-names` | labels of different texts on one connected group |
| `wire-unlabelled` | a wired group without a label |
| `shared-point` | pins of two instances at one point, unless one of them is a pin of Fenolite's `GND` or `RAIL` power symbol, or several pins of one instance at a point that carries no label, unless those pins have one name (the stacked pins of "Own netlist of a generated sheet") |
| `frame` | an instance whose rotation and mirror are not in `schlayout.PROVED_FRAMES` |
| `hidden-power` | a hidden pin of type `power_in`, or a definition flagged `power` other than Fenolite's power flag (`symembed.is_power_flag`: `PWR_FLAG` of a library named `fenolite` in any letter case); instances of Fenolite's own `GND` and `RAIL` power symbols are read (change c0406) |

- The code and its severity MUST be `sch_netlist.ISSUE_CODES`; the closed set `sch.ISSUE_CODES` of "Schematic read issue codes" is not widened, because reading a sheet never gives this issue. `sch.opaque_heads(sheet) -> Counter[str]` MUST count the heads of the opaque slots of the sheet root, and MUST be empty for a sheet that was not read from a file.
- `sch.opaque_wires(sheet) -> tuple[tuple[Point, ...], ...]` MUST give the points of each opaque root `wire` slot of a read sheet, in file order, and `()` for a created sheet; the junctions of a read sheet are those of `sch.opaque_drawing(sheet)`.
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
- **THEN** the issues hold the reasons `wire-end` and `label-kind` (its junction is read since change c0406), and `own_netlist` raises `NetlistUnsupportedError`

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

#### Scenario: Wired sheets are inside the grammar
- **WHEN** `grammar_issues` runs on the sheets generated with `layout="wired"` for the designs of `tests/_wireddesigns.py`, each with its `children`
- **THEN** it returns `()` for each

#### Scenario: Wire end inside a wire
- **GIVEN** a wired sheet changed in the test so that the two collinear wires that end on the junction of a T are joined into one, which then holds the junction and the stem's end on its inside
- **WHEN** `grammar_issues` runs
- **THEN** the issues hold the reason `wire-touch`

#### Scenario: Wired sheet read back
- **WHEN** the written root of the authored design `opamp_stage` is read back with `read_schematic`, its wires and junctions kept as opaque slots
- **THEN** `grammar_issues` returns `()` and `own_netlist` equals the own netlist of the created sheet

#### Scenario: Wire through a pin
- **GIVEN** a generated sheet changed in the test so that its snap wire runs on through the near pin to a point beyond it
- **WHEN** `grammar_issues` runs
- **THEN** the issues hold the reason `wire-touch`, and also `wire-end` when the end beyond the pin meets nothing

#### Scenario: Stacked pins are inside the grammar
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py -k stacked_grammar` runs `grammar_issues` on the sheet of the stacked design, and on a copy in which one of the stacked pins of an open pin is renamed
- **THEN** the first gives `()`, and the second gives the reason `shared-point`

#### Scenario: The flag of the catalog library is no power symbol
- **WHEN** the own netlist of the built design of "Generated sheet content", scenario "Catalog parts with a supply", is read
- **THEN** no `NetlistUnsupportedError` is raised, and the build's guard `build.schematic-netlist-differs` reports nothing
