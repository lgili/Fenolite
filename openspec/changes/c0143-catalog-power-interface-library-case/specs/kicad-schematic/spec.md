## MODIFIED Requirements

### Requirement: Generated sheet content
`fenolite.backends.kicad.schgen.generate_schematic(design, parts, *, name, target, placements=None, vendor="all", allow_lossy=False, layout="readable") -> GeneratedSchematic` SHALL build the sheets of a design from its circuit, and SHALL return `sheet` (the root `SchematicSheet`), `children` (each child sheet keyed by its path from the root file's folder, in page order; empty for a design without module sheets, "Hierarchical sheets of a design"), `libraries` (per nickname, the symbols of its project library), `rows` (the rows of `sym-lib-table`), `pad_nets` (component id and pad number mapped to the net name of an unconnected pin), `paths` (component id mapped to the path of its symbol), `issues`, `unvendored` (the lib ids that `vendor="project"` leaves without a project library, which the build reports) `power_flags` (their number) and `satellites` (the number of snapped satellites, "Readable sheet layout"). `layout` MUST be `"readable"` or `"grid"`; any other value raises `ValueError`. `parts` are the resolved parts of the build: each gives its component, its component path, its flattened symbol, the symbols that symbol extends as their library holds them, its footprint, and the origin of the row that resolved the symbol.
- **Symbols.** Each component with a resolved symbol MUST give one `SymbolInstance` per unit of that symbol, on the sheet of its module ("Hierarchical sheets of a design"), with body style 1, `lib_ref` naming the embedded definition, `ref`, `value`, `footprint` = `Component.lib_footprint_ref`, and `properties` = the component's `properties` plus `Footprint`. `dnp` MUST be `Component.dnp`; `in_bom` MUST be false when the component's footprint has the attribute `exclude_from_bom`; `on_board` MUST be true. Each instance MUST have one `SymbolUse(<name>, <use path of its sheet>, ref, unit)`: `/<root uuid>` on the root, `/<root uuid>/<kicad uuids of the sheet references from the top down>` on a child sheet. A component without a resolved symbol MUST give no instance.
- **Labels.** Each pin that a net lists and that no snap wire joins MUST give one `NetLabel("global", netnames.stored_name(<net name>), <the pin's connection point>, shape="passive")`, turned away from the symbol body. Each pair of pins that a snap wire joins MUST give one such label, at the satellite's near pin, as "Readable sheet layout" places it. The sheets MUST hold no junction, no label of another kind and no wire other than snap wires.
- **No-connect flags.** Each pin listed by `Circuit.no_connects` MUST give one `NoConnectFlag` at its connection point. A pin on no net without a mark MUST give neither a label nor a flag.
- **Pins and pads.** Net members and marks are keyed by symbol pin number; with a `pin_pad_map`, the label or flag MUST be placed at the pin whose embedded number is the mapped pad number ("Embedded symbols of a generated sheet").
- **Power flags.** Each net that is a member of an `Interface` with `kind == "power"`, and that no pin of type `power_out` of a component with `dnp == False` is on, MUST give one instance of the power flag on the root sheet, with the reference `#FLG<nn>` (numbered from 01 in the order of net names), `in_bom` and `on_board` false, and one global label of the net at its pin.
- **Library of the power flag.** The flag MUST be the symbol `PWR_FLAG` of the flag library, `symembed.flag_library(libraries)`: the first, in sorted order, of the symbol libraries of the design whose name differs from `fenolite` in letter case only, else `fenolite`. The symbol libraries of the design are the libraries of its parts' symbols and the libraries it authors (`generate_schematic(..., other_libraries=...)`), the built-in catalog's `Fenolite` among them. So a design with a part of the catalog has `Fenolite:PWR_FLAG`, and a design without such a library has `fenolite:PWR_FLAG`, as before change c0143: the files of its build MUST NOT differ from the files of a build that does not look for such a library.
- **Page.** Every sheet's `title_block` MUST be the board's title block and its `paper` the paper that its own layout chose. The root's `pages` MUST be `(SheetPage("/", "1"),)`; a child's `pages` MUST be empty. Every sheet MUST embed, in `lib_symbols`, the definitions its own instances name, sorted by lib id, the power flag last on the root.
- **Ids.** Ids MUST be derived from the design (`design-model`, "Identifiers of schematic entities"): the sheet from `<name>`, an instance from `<name>:<component path>#<unit>`, a pin label from `<name>:label:<component path>:<pin>`, a flag from `<name>:nc:<component path>:<pin>`, a power flag from `<name>:flag:<net name>` and its label from `<name>:label:flag:<net name>`, a child sheet from `<name>:<module path>`, a sheet reference from `<name>:sheet:<module path>`, a snap wire from `<name>:wire:<component path of its satellite>` and the label of its pair from `<name>:label:<component path of its satellite>:<near pin>`. KiCad uuids MUST come from `pcb.kicad_uuid`.
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

### Requirement: Embedded symbols of a generated sheet
`fenolite.backends.kicad.symembed.embed_symbol(definition, *, parents=(), target, pin_numbers=None, allow_lossy=False, issues=None) -> EmbeddedSymbol` SHALL return the definition that a generated sheet embeds for one resolved symbol, as a node built from the definition's slots, and the generator SHALL embed one definition per distinct result. `definition` is the resolved symbol, which holds its own children as slots, and `parents` are the symbols it extends as their library holds them, the nearest first (`LibraryResolver.symbol_chain`). `EmbeddedSymbol` holds `lib_id`, `nickname`, `name`, `node`, `definition` (the node as the schematic reader models it, which `write_schematic` writes back) and `authored`.
- **Flattened.** A derived symbol MUST take the sub-symbols of its root parent, renamed from `<parent>_<unit>_<style>` to `<name>_<unit>_<style>`, and its own properties over the parent's; the embedded node MUST hold no `extends`.
- **Pad numbers.** With `pin_numbers` (a `pin_pad_map`), the `number` of each mapped pin MUST be replaced by its pad number, the first of its pads when the map gives it several ("Pins with several pads on a generated sheet" adds the others), and the name MUST be `symembed.variant_name(name, pin_pad_map)`: `<name>_<first 8 hex digits of the SHA-256 of the pairs sorted by pin, the pads of one pin in map order>`. For a map of one pad per pin that list is the sorted pairs, so the name is the one it was. Two components whose pins have equal pads in equal order share one variant.
- **Hidden power inputs.** A pin of type `power_in` that is hidden MUST be embedded without its `hide`, with one `kicad.sch.power-pin-shown` info per symbol.
- **Name.** The embedded name MUST be `<nickname>:<name>`, and the sub-symbol names MUST keep the bare name.
- **Gate.** `versions.check_emittable` MUST run on the node for `target`; an error MUST raise `LossyWriteError`, or with `allow_lossy=True` remove the node of the token with one `kicad.sch.dropped-too-new` warning.
- **Empty texts.** A pin name or a property text that the library writes `~` and its reader takes as empty MUST be embedded empty for a target whose sheet format reads `~` as a tilde (10.0), so the pin has no name on both majors.
- **Authored symbols.** A symbol that the design authors has no slots; its node MUST be the one `sym.write_symbol_library` writes for it.
- **Power flag.** `symembed.power_flag(target, library="fenolite")` MUST return the authored definition `<library>:PWR_FLAG`, `fenolite:PWR_FLAG` by default: flagged `power`, reference `#FLG`, one pin of type `power_out` numbered `1` at the origin with length 0, `in_bom` and `on_board` false, and a description that says it is authored for Fenolite. It MUST hold no content of any other library, and its node in a library file MUST be the same whatever the library. `symembed.flag_library(libraries)` MUST give the library of "Generated sheet content", and `symembed.is_power_flag(lib_id)` MUST be true exactly for `PWR_FLAG` of a library named `fenolite` in any letter case.
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

#### Scenario: The flag in another library
- **WHEN** `power_flag(10, "Fenolite")` and `power_flag(10)` are each written with `write_symbol_library`
- **THEN** the two texts are equal, and the lib ids are `Fenolite:PWR_FLAG` and `fenolite:PWR_FLAG`

### Requirement: Generated schematic issue codes
`schgen.ISSUE_CODES` SHALL map every code that the generator, the layout and the embedding emit to its severity, and SHALL be exactly this table. The `build.` codes of the table SHALL join the closed build issue set of `design-dsl`, "Build issue codes".

| code | severity | when |
|---|---|---|
| `kicad.sch.pin-off-grid` | info | a library pin is not on the 1.27 mm grid |
| `kicad.sch.power-pin-shown` | info | a hidden power-input pin is embedded visible |
| `kicad.sch.unconnected-name-unproven` | warning | the net name of an unconnected pin is not written |
| `build.schematic-too-large` | error | the units of one sheet do not fit an A0 page |
| `build.symbol-overlap` | warning | two cells overlap after a placement |
| `build.symbol-short` | error | two connection points of different units coincide |
| `build.symbol-placement-unknown` | warning | the placements file names no unit of the design |
| `build.symbol-placement-invalid` | error | a placement is off the grid, has an unknown key or an unproved rotation |
| `build.reserved-library` | error | a design names a library `fenolite`, or needs a power flag and holds a symbol `PWR_FLAG` in the library that holds the flag |
| `build.schematic-replaced` | warning | an edited schematic file, the root or a child sheet, is replaced |
| `build.sheet-file-collision` | error | two modules give one child sheet file |
| `build.sheet-stale` | warning | a child sheet of the last build is no longer a sheet of the design, and is left in place |

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_schgen.py -k codes` collects the code literals of `schgen.py`, `schlayout.py`, `symembed.py` and `lens/schplacements.py`
- **THEN** each is a key of `schgen.ISSUE_CODES` or of `sch.WRITE_ISSUE_CODES`, with the severity of its table

#### Scenario: Codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** every key of `schgen.ISSUE_CODES` appears in `docs/cli-contract.md`

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
| `hidden-power` | a hidden pin of type `power_in`, or a definition flagged `power` other than Fenolite's power flag (`symembed.is_power_flag`: `PWR_FLAG` of a library named `fenolite` in any letter case) |

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

#### Scenario: The flag of the catalog library is no power symbol
- **WHEN** the own netlist of the built design of "Generated sheet content", scenario "Catalog parts with a supply", is read
- **THEN** no `NetlistUnsupportedError` is raised, and the build's guard `build.schematic-netlist-differs` reports nothing
