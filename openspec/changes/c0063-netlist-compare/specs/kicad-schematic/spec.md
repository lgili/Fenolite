## ADDED Requirements

### Requirement: Netlist export reading
`fenolite.backends.kicad.netlist.read_netlist(text, *, file="") -> KicadNetlist` SHALL read the netlist that `kicad-cli sch export netlist --format kicadsexpr` writes into `KicadNetlist(components, nets)`.
- A `comp` MUST give `NetComponent(ref, value, footprint, properties)`, `properties` holding the entries of its `fields` by name. A `net` MUST give `NetlistNet(name, netclass, nodes)`, and each `node` a `NetNode(ref, pin, pintype)`.
- Components MUST be sorted by the natural order of their reference, nets by name, and nodes by reference and then pin, so two readings of one design are equal whatever the export order.
- The reader MUST ignore `design`, `libparts`, `libraries`, `groups` and `variants`, and inside components and nets `code`, `pinfunction`, `sheetpath`, `tstamps`, `units` and every head it does not know. No date and no path of the export MUST reach the result.
- A root head other than `export`, or a missing `components` or `nets` child, MUST raise `FormatError` (`FEN-3004`) naming it.
- `netlist.differences(a, b, *, pintypes=True, netclasses=False) -> tuple[str, ...]` MUST return, sorted, one line per component on one side only, per value or footprint that differs, per net on one side only, per node on one side only and, with `pintypes`, per node whose `pintype` differs; it MUST return `()` exactly when the two netlists are equal under those options.
- `netlist.EVIDENCE` MUST be `INFERRED` (`H-K-NETLIST-SHAPE`) until that row is `KICAD-VERIFIED (9.0.x, 10.0.x)`.

#### Scenario: Export of each major
- **GIVEN** the authored `tests/data/kicad/netlist/export_9.net` and `export_10.net`, which hold the same three components and five nets in the shape of each major
- **WHEN** `read_netlist` reads both
- **THEN** the two results are equal, each has the components `D1`, `R1` and `U1` in this order, and the net `GND` holds the nodes (`D1`, `1`, `passive`) and (`U1`, `10`, `power_in`)

#### Scenario: No date and no path
- **WHEN** the result of reading `export_10.net` is dumped as text
- **THEN** it holds neither the `date` nor the `source` path of the file

#### Scenario: Not a netlist
- **WHEN** `read_netlist("(kicad_sch (version 20260306))")` is called
- **THEN** `FormatError` is raised naming `kicad_sch`

#### Scenario: Differences are located
- **GIVEN** two netlists equal except that the second has `R1` pin `2` on `GND` instead of `LED_A`
- **WHEN** `differences(a, b)` is called
- **THEN** it returns two lines, one naming `LED_A` and `R1-2`, the other `GND` and `R1-2`

### Requirement: Own netlist of a generated sheet
`fenolite.backends.kicad.sch_netlist.own_netlist(sheet, *, project) -> KicadNetlist` SHALL return the netlist of a sheet inside the grammar of "Netlist grammar check", read from the sheet alone, as KiCad reads it.
- **Nodes.** Each pin of each symbol instance whose reference does not start with `#` MUST be one node, at `schlayout.pin_point` of the instance, with the pin number of its embedded definition and the pin's electrical type as `pintype`, followed by `+no_connect` when a no-connect flag lies on its point.
- **Named nets.** The nodes whose points carry a global label of one text MUST form one net named by that text as written.
- **Unconnected nets.** A node whose point carries no label MUST form a net of its own, named by `netnames.unconnected_name` with the instance's reference, unit and unit count, the pin's name and its number, flagged or not.
- **Components.** `components` MUST be `sch.components((sheet,), project=project)` with the properties of each symbol, and `netclass` MUST be `""`.
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

### Requirement: Netlist grammar check
`sch_netlist.grammar_issues(sheet) -> tuple[Issue, ...]` SHALL return one `kicad.sch.netlist-unsupported` issue of severity `error` for each reason that keeps Fenolite from reading the sheet's nets, the reason first in the message, and `()` for a sheet it can read. `sch_netlist.REASONS` MUST be exactly the reasons of this table.

| reason | when |
|---|---|
| `wire` | the root holds a `wire`, `junction`, `bus`, `bus_entry` or `bus_alias`, counted through `sch.opaque_heads(sheet)` |
| `label-kind` | a label whose kind is not `global` |
| `sheet` | a sheet reference, or a symbol with more than one use |
| `label-off-pin` | a label at a point where no pin connects |
| `two-names` | labels of different texts at one point |
| `shared-point` | pins of two instances at one point |
| `frame` | an instance whose rotation and mirror are not in `schlayout.PROVED_FRAMES` |
| `hidden-power` | a hidden pin of type `power_in`, or a definition flagged `power` other than `fenolite:PWR_FLAG` |

- The code joins `sch.ISSUE_CODES`. `sch.opaque_heads(sheet) -> Counter[str]` MUST count the heads of the opaque slots of the sheet root.
- A sheet that `generate_schematic` built MUST give no issue.

#### Scenario: Generated sheets are inside the grammar
- **WHEN** `grammar_issues` runs on the sheets generated for the blink and for the units design
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
