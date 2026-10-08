## ADDED Requirements

### Requirement: Pins with several pads on a generated sheet
For a component whose `pin_pad_map` gives a pin several pads, the generated sheet SHALL embed a symbol in which the pin is followed by one stacked pin per further pad, so that KiCad's netlist of the sheet holds every pad of the pin on the pin's net (`H-K-SCH-STACKED`).
- **First pad.** The pin of the library symbol MUST take the first pad of the pin as its number and keep everything else ("Embedded symbols of a generated sheet", "Pad numbers").
- **Stacked pins.** For each further pad, in map order, the embedded sub-symbol MUST hold one more `pin` node directly after that pin: at the same position, with the same rotation, length and name, the pad as its number, the electrical type `passive`, the graphic style `line`, hidden in the form the target reads, and without alternates. A stacked pin MUST lie in the unit and body style of its pin, and the project symbol library MUST hold the same node as the sheet.
- **Labels and flags.** The sheet MUST hold one label, or one no-connect flag, at the point of such a pin, as for any pin. No label, flag or wire is added for a stacked pin.
- **Pin on no net.** The pads of such a pin on no net are one net in KiCad, named after the pad whose number is the lowest in code-point order (`netnames.stack_pad`): `unconnected-(…-Pad<n>)` when a no-connect flag marks the pin, and `Net-(…-Pad<n>)` with the same text between the brackets when none does, because several pins without a flag are a net like any other to KiCad (`H-K-SCH-STACKED-OPEN`). `GeneratedSchematic.pad_nets` MUST hold that name (`netnames.open_name`) for every pad of the pin, and `lower_for_schematic` MUST put those pads on one net of that name. A pin whose name `netnames.proved` refuses MUST leave every one of its pads out of `pad_nets`, with the one `kicad.sch.unconnected-name-unproven` warning of "Names of unconnected-pin nets".
- **Netlist guard.** `schematic_netlist_issue` MUST expect one element `REF-<pad>` per pad of each pin of a net, and MUST give no issue for a sheet built by these rules.
- **One pad per pin.** A component whose pins have one pad each MUST get the embedded symbol, and a design of such components the sheets, the project libraries, the board, `pad_nets` and the layer files, that they got before this requirement, byte for byte (`H-G-PINMAP-BYTES`).
- `schgen` and `symembed` MUST read the map through `Component.pads_of` and `Component.pin_pads` only.
- **Evidence.** A design that holds a pin with several pads rests on what KiCad does with stacked pins, and MUST say so: the evidence of its `build`, and of `netlist`, `parity` and the parity stage of `check` when they read its sheets themselves, MUST be the evidence of a design without such a pin combined with `H-K-SCH-STACKED` (lowest level wins, ids listed), and with `H-K-SCH-STACKED-OPEN` too when one of its stacks carries no label (`sch_netlist.stack_evidence`, `sch_netlist.evidence_of`). The evidence constants of `schgen` and `sch_netlist` MUST stay as they are, and the evidence of a design without a stack MUST be what it was, so that the envelopes of such a design keep their bytes.

#### Scenario: Thermal pad stacked
- **GIVEN** a component of `Mini:Mini_LED` with `pin_pad_map == (("1", "1"), ("1", "T1"), ("1", "T2"))`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_symembed.py -k stacked` embeds its symbol for targets 9 and 10
- **THEN** the pin named `K` is followed by two pins at its position with its name, the numbers `T1` and `T2`, the type `passive` and hidden; the other pin of the symbol is as the library holds it; and `sym.read_symbol_library` of the written project library gives the same four pins

#### Scenario: Pads on the label's net
- **GIVEN** the stacked design of `tests/_schbuild.py`: `U1` (a gate symbol on a 32-pad footprint) with `pad_map={"3": ("3", "23"), "5": ("5", "15", "9"), "7": ("7", "27"), "14": ("14", "24")}`, pin `7` on `GND` and pin `14` on `VCC`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_schgen.py -k stacked` generates the sheet and `own_netlist` reads it
- **THEN** the sheet holds one label `GND` at the point that the pins `7` and `27` share, the net `GND` holds the nodes (`U1`, `7`) and (`U1`, `27`), and `tests/unit/lens/test_build_netlist_guard.py -k stacked` finds no `build.schematic-netlist-differs`

#### Scenario: Open pin with three pads
- **GIVEN** the same design: pin `5` of `U1` is unnamed, on no net and marked as not connected; pin `K` of `D2` has `pad_map={"1": ("21", "17")}`, is on no net and carries no mark
- **WHEN** `uv run pytest tests/unit/lens/test_build_schematic.py -k stacked_open` builds the project with a schematic
- **THEN** the sheet holds one no-connect flag at pin `5`; `pad_nets` gives the pads `5`, `15` and `9` the name `unconnected-(U1-Pad15)` and the pads `21` and `17` the name `Net-(D2-K-Pad17)`; and the written board has the pads of each pin on one net of that name

#### Scenario: Evidence of a design with stacked pins
- **GIVEN** the stacked design and the units design of `tests/_schbuild.py`, each built and written to a folder
- **WHEN** `uv run pytest tests/unit/cli/test_netlist_cmd.py -k stacked_rows tests/unit/backends/kicad/test_sch_netlist.py -k "stack and evidence or names_the_rows or evidence_it_had"` reads the evidence of the builds and of `fenolite netlist --source fenolite` and `fenolite parity --netlist own` on them
- **THEN** the stacked design lists `H-K-SCH-STACKED` and `H-K-SCH-STACKED-OPEN` in all three, the units design lists neither, a sheet whose stacks are all on labels lists the first alone, and `sch_netlist.evidence_of` of a sheet without a stack is `sch_netlist.EVIDENCE` itself

#### Scenario: Builds of one pad per pin are pinned
- **WHEN** `uv run pytest tests/unit/lens/test_build_bytes_pinned.py` builds the units design, the 25 designs of `tests/_gendesigns.py`, `examples/blink_2layer` and `examples/board_40parts` for targets 9 and 10
- **THEN** the digest of each build equals the digest pinned on the base commit of change c0123, before any product code of it

## MODIFIED Requirements

### Requirement: Embedded symbols of a generated sheet
`fenolite.backends.kicad.symembed.embed_symbol(definition, *, parents=(), target, pin_numbers=None, allow_lossy=False, issues=None) -> EmbeddedSymbol` SHALL return the definition that a generated sheet embeds for one resolved symbol, as a node built from the definition's slots, and the generator SHALL embed one definition per distinct result. `definition` is the resolved symbol, which holds its own children as slots, and `parents` are the symbols it extends as their library holds them, the nearest first (`LibraryResolver.symbol_chain`). `EmbeddedSymbol` holds `lib_id`, `nickname`, `name`, `node`, `definition` (the node as the schematic reader models it, which `write_schematic` writes back) and `authored`.
- **Flattened.** A derived symbol MUST take the sub-symbols of its root parent, renamed from `<parent>_<unit>_<style>` to `<name>_<unit>_<style>`, and its own properties over the parent's; the embedded node MUST hold no `extends`.
- **Pad numbers.** With `pin_numbers` (a `pin_pad_map`), the `number` of each mapped pin MUST be replaced by its pad number, the first of its pads when the map gives it several ("Pins with several pads on a generated sheet" adds the others), and the name MUST be `symembed.variant_name(name, pin_pad_map)`: `<name>_<first 8 hex digits of the SHA-256 of the pairs sorted by pin, the pads of one pin in map order>`. For a map of one pad per pin that list is the sorted pairs, so the name is the one it was. Two components whose pins have equal pads in equal order share one variant.
- **Hidden power inputs.** A pin of type `power_in` that is hidden MUST be embedded without its `hide`, with one `kicad.sch.power-pin-shown` info per symbol.
- **Name.** The embedded name MUST be `<nickname>:<name>`, and the sub-symbol names MUST keep the bare name.
- **Gate.** `versions.check_emittable` MUST run on the node for `target`; an error MUST raise `LossyWriteError`, or with `allow_lossy=True` remove the node of the token with one `kicad.sch.dropped-too-new` warning.
- **Empty texts.** A pin name or a property text that the library writes `~` and its reader takes as empty MUST be embedded empty for a target whose sheet format reads `~` as a tilde (10.0), so the pin has no name on both majors.
- **Authored symbols.** A symbol that the design authors has no slots; its node MUST be the one `sym.write_symbol_library` writes for it.
- **Power flag.** `symembed.power_flag(target)` MUST return the authored definition `fenolite:PWR_FLAG`: flagged `power`, reference `#FLG`, one pin of type `power_out` numbered `1` at the origin with length 0, `in_bom` and `on_board` false, and a description that says it is authored for Fenolite. It MUST hold no content of any other library.
- **Project library.** `symembed.write_symbol_library(symbols, *, target) -> str` MUST write a `.kicad_sym` text with the header of the target (`FORMAT_VERSIONS[FileKind.SYMBOL_LIB][target]`, generator `fenolite`) holding the same nodes under their bare names, sorted by name. `sym.read_symbol_library` MUST read it back with equal pins. A library whose symbols are all authored by the design and have no pin-pad variant MUST be the text of `sym.write_symbol_library`, whose header version is `FORMAT_VERSIONS[FileKind.SYMBOL_LIB][target]` too.

#### Scenario: Derived symbol flattened
- **WHEN** `Mini:Mini_LED_Red`, which extends `Mini_LED`, is embedded for target 10
- **THEN** the node is named `Mini:Mini_LED_Red`, every sub-symbol name starts with `Mini_LED_Red_`, it holds no `extends`, and its Value is that of the derived symbol

#### Scenario: Pin-pad variant
- **GIVEN** a component of `Mini:Mini_LED` with `pin_pad_map == (("1", "2"), ("2", "1"))`
- **WHEN** its symbol is embedded
- **THEN** the embedded name starts with `Mini:Mini_LED_`, ends with 8 hex digits, the pin named `K` has the number `2`, and a component without a map still embeds `Mini:Mini_LED`

#### Scenario: Hidden power input shown
- **GIVEN** a symbol with one hidden pin of type `power_in`
- **WHEN** it is embedded with an `issues` list
- **THEN** that pin has no `hide`, and `issues` holds one `kicad.sch.power-pin-shown` info

#### Scenario: Library equals embedded copy
- **WHEN** the symbols of the blink are embedded and `write_symbol_library` writes the nickname `Mini`
- **THEN** each symbol of the library, renamed to `Mini:<name>`, is tree-equal to its embedded node

#### Scenario: Flag is authored
- **WHEN** `power_flag(10)` and `power_flag(9)` are read back
- **THEN** each has `power` set, one pin of type `power_out`, and the reference `#FLG`

#### Scenario: Variant name of one pad per pin is unchanged
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_symembed.py -k variant_name` computes `variant_name("Mini_LED", (("2", "1"), ("1", "2")))` and the name for `(("1", "2"), ("2", "1"))`
- **THEN** both are `Mini_LED_b0bb1b70`, the name the units design embeds today; and `(("1", "1"), ("1", "T1"))` and `(("1", "T1"), ("1", "1"))` give two different names

### Requirement: Own netlist of a generated sheet
`fenolite.backends.kicad.sch_netlist.own_netlist(sheet, *, project, children={}) -> KicadNetlist` SHALL return the netlist of a root sheet and of the child sheets it names (`children`: each child keyed by its path from the root file's folder), inside the grammar of "Netlist grammar check", read from the sheets alone, as KiCad reads them.
- **Nodes.** Each pin of each symbol instance of every sheet whose reference does not start with `#` MUST be one node, at `schlayout.pin_point` of the instance, with the pin number of its embedded definition and the pin's electrical type as `pintype`, followed by `+no_connect` when a no-connect flag lies on its point.
- **Wires.** The wires of a sheet are its `wires` and, for a sheet read from a file, the opaque root `wire` slots that `sch.opaque_wires(sheet)` gives as point lists; both are read alike, so a built project is read back from its files.
- **Named nets.** Within one sheet, a pin's point, a wire end and a label's point MUST be joined when they coincide, and the two ends of a wire MUST be joined to each other (`H-K-SCH-WIRE-END`). The nodes of every group that carries a global label of one text, in any sheet, MUST form one net named by `netnames.stored_name` of that text, which is the text itself for a label that `build` wrote (`H-K-SCH-HIER-FILE`).
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
| `label-kind` | a label whose kind is not `global` |
| `sheet` | a sheet reference with pins, one whose file (resolved from the folder of the sheet that names it) is not a key of `children`, a child named by two references or by none, a symbol with more than one use, or a symbol whose use is not at the instance path of its sheet |
| `undefined-symbol` | an instance whose definition the sheet does not embed, or embeds as a derived symbol without pins |
| `label-off-pin` | a label at a point where no pin connects |
| `two-names` | labels of different texts on one connected group |
| `wire-unlabelled` | a wired group without a label |
| `shared-point` | pins of two instances at one point, or several pins of one instance at a point that carries no label, unless those pins have one name (the stacked pins of "Own netlist of a generated sheet") |
| `frame` | an instance whose rotation and mirror are not in `schlayout.PROVED_FRAMES` |
| `hidden-power` | a hidden pin of type `power_in`, or a definition flagged `power` other than `fenolite:PWR_FLAG` |

- The code and its severity MUST be `sch_netlist.ISSUE_CODES`; the closed set `sch.ISSUE_CODES` of "Schematic read issue codes" is not widened, because reading a sheet never gives this issue. `sch.opaque_heads(sheet) -> Counter[str]` MUST count the heads of the opaque slots of the sheet root, and MUST be empty for a sheet that was not read from a file.
- `sch.opaque_wires(sheet) -> tuple[tuple[Point, ...], ...]` MUST give the points of each opaque root `wire` slot of a read sheet, in file order, and `()` for a created sheet.
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

#### Scenario: Stacked pins are inside the grammar
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py -k stacked_grammar` runs `grammar_issues` on the sheet of the stacked design, and on a copy in which one of the stacked pins of an open pin is renamed
- **THEN** the first gives `()`, and the second gives the reason `shared-point`
