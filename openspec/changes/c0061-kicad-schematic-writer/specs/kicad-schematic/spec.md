## ADDED Requirements

### Requirement: Schematic writing per target
`fenolite.backends.kicad.sch.write_schematic(sheet, *, target=DEFAULT_TARGET, allow_lossy=False) -> WriteResult` SHALL return the text of a `.kicad_sch` file for KiCad `target`.0 from a created `SchematicSheet`, and SHALL write no file.
- The header MUST be `(version FORMAT_VERSIONS[FileKind.SCHEMATIC][target])`, `(generator "fenolite")` and `(generator_version "<target>.0")`, followed by the sheet's `uuid` and `paper`, the `title_block` when the sheet has one, and `lib_symbols`.
- The root items MUST follow in the order no-connect flags, labels, symbol instances, each kind in the order of its collection, then `sheet_instances` with the sheet's pages.
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

### Requirement: Generated sheet content
`fenolite.backends.kicad.schgen.generate_schematic(design, parts, *, name, target, placements=None, vendor="all", allow_lossy=False) -> GeneratedSchematic` SHALL build the sheet of a design from its circuit, and SHALL return `sheet` (a `SchematicSheet`), `libraries` (per nickname, the symbols of its project library), `rows` (the rows of `sym-lib-table`), `pad_nets` (component id and pad number mapped to the net name of an unconnected pin), `paths` (component id mapped to the path of its symbol) and `issues`.
- **Symbols.** Each component with a resolved symbol MUST give one `SymbolInstance` per unit of that symbol, with body style 1, `lib_ref` naming the embedded definition, `ref`, `value`, `footprint` = `Component.lib_footprint_ref`, and `properties` = the component's `properties` plus `Footprint`. `dnp` MUST be `Component.dnp`; `in_bom` MUST be false when the component's footprint has the attribute `exclude_from_bom`; `on_board` MUST be true. Each instance MUST have one `SymbolUse(<name>, "/<root uuid>", ref, unit)`. A component without a resolved symbol MUST give no instance.
- **Labels.** Each pin that a net lists MUST give one `NetLabel("global", netnames.stored_name(<net name>), <the pin's connection point>, shape="passive")`, turned away from the symbol body. The sheet MUST hold no wire, no junction and no label of another kind.
- **No-connect flags.** Each pin listed by `Circuit.no_connects` MUST give one `NoConnectFlag` at its connection point. A pin on no net without a mark MUST give neither a label nor a flag.
- **Pins and pads.** Net members and marks are keyed by symbol pin number; with a `pin_pad_map`, the label or flag MUST be placed at the pin whose embedded number is the mapped pad number ("Embedded symbols of a generated sheet").
- **Power flags.** Each net that is a member of an `Interface` with `kind == "power"`, and that no pin of type `power_out` of a component with `dnp == False` is on, MUST give one instance of `fenolite:PWR_FLAG` with the reference `#FLG<nn>` (numbered from 01 in the order of net names), `in_bom` and `on_board` false, and one global label of the net at its pin.
- **Page.** `sheet.title_block` MUST be the board's title block, `sheet.paper` the paper that the layout chose, and `sheet.pages` `(SheetPage("/", "1"),)`.
- **Ids.** Ids MUST be derived from the design (`design-model`, "Identifiers of schematic entities"): the sheet from `<name>`, an instance from `<name>:<component path>#<unit>`, a pin label from `<name>:label:<component path>:<pin>`, a flag from `<name>:nc:<component path>:<pin>`, a power flag from `<name>:flag:<net name>` and its label from `<name>:label:flag:<net name>`. KiCad uuids MUST come from `pcb.kicad_uuid`.
- The function MUST NOT read or write a file, and two calls with equal arguments MUST return equal results.

#### Scenario: Blink
- **GIVEN** the built design and resolved parts of `examples/blink_2layer`
- **WHEN** `generate_schematic` runs for target 10
- **THEN** the sheet holds the instances `D1`, `R1` and `U1` and two power flags, one global label per connected pin (seven) and one per flag, with the names `VIN`, `GND`, `LED_DRV` and `LED_A`, no no-connect flag, and `pad_nets` names the 29 pads of `U1` whose pins are on no net

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

### Requirement: Pin connection points
`fenolite.backends.kicad.schlayout.pin_point(origin, pin, rotation, mirror) -> Point` SHALL return the sheet position at which a pin connects: for a pin at (px, py) in the library frame, whose Y axis points up, the mirror is applied first (`"x"` negates py, `"y"` negates px), then the rotation by the instance angle, and the result (px′, py′) gives (x + px′, y − py′) for an instance at (x, y).
- The rotation sense MUST be the one the probes `sch-pin-frame-*` prove on both majors (`kicad-oracle`, "Schematic naming facts are probed").
- `schlayout.PROVED_FRAMES` MUST list the (rotation, mirror) pairs whose probe gave `absent` on both majors, and MUST hold at least `(0, "")`.

#### Scenario: Unrotated pin
- **GIVEN** an instance at (50.8 mm, 76.2 mm) and a pin at (−12.7 mm, 16.51 mm) in the library frame
- **WHEN** `pin_point` is called with rotation 0 and no mirror
- **THEN** it returns (38.1 mm, 59.69 mm), in nm

#### Scenario: Mirror about the Y axis
- **WHEN** the same pin is asked for with mirror `"y"`
- **THEN** the X of the result is 63.5 mm

### Requirement: Deterministic sheet layout
`schlayout.layout_units(units, *, placements=None, flags=()) -> SheetLayout` SHALL give every unit and every power flag a position on one page, without overlap, in a fixed order, and SHALL choose the paper.
- **Order.** Units MUST be sorted by top-level module (units outside a module first), then by the natural order of the component path, then by unit number. Power flags come last, in the order of their nets.
- **Cells.** A unit's cell MUST hold its body and pin connection points, grown on each side by `CHAR_ROOM` (1 524 000 nm) per character of the longest label on that side plus `LABEL_ROOM` (5 080 000 nm), by `CELL_MARGIN` (5 080 000 nm), and by `TEXT_ROOM` (7 620 000 nm) above for Reference and Value. Cell sizes MUST be rounded up to `ORIGIN_STEP` (2 540 000 nm).
- **Flow.** Cells MUST fill rows from the left inside `PAGE_MARGIN` (12 700 000 nm), above a band of `TITLE_BAND` (40 640 000 nm) at the bottom. The first unit of a module MUST start a new row. Power flags MUST take a last row.
- **Grid.** Every symbol origin MUST be a multiple of `ORIGIN_STEP` in both axes. A pin whose library position is not a multiple of `GRID` (1 270 000 nm) MUST give `kicad.sch.pin-off-grid` (info) naming the symbol.
- **Paper.** `SheetLayout.paper` MUST be the first of A4, A3, A2, A1 and A0, landscape, in which the flow fits. When none fits, `layout_units` MUST return the issue `build.schematic-too-large` (error) naming the number of units.
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

### Requirement: Embedded symbols of a generated sheet
`fenolite.backends.kicad.symembed.embed_symbol(definition, *, parents, target, pin_numbers=None, allow_lossy=False, issues=None) -> EmbeddedSymbol` SHALL return the definition that a generated sheet embeds for one resolved symbol, as a node built from the definition's slots, and the generator SHALL embed one definition per distinct result.
- **Flattened.** A derived symbol MUST take the sub-symbols of its root parent, renamed from `<parent>_<unit>_<style>` to `<name>_<unit>_<style>`, and its own properties over the parent's; the embedded node MUST hold no `extends`.
- **Pad numbers.** With `pin_numbers` (a `pin_pad_map`), the `number` of each mapped pin MUST be replaced by its pad number, and the name MUST be `symembed.variant_name(name, pin_pad_map)`: `<name>_<first 8 hex digits of the SHA-256 of the sorted pairs>`. Two components with equal maps share one variant.
- **Hidden power inputs.** A pin of type `power_in` that is hidden MUST be embedded without its `hide`, with one `kicad.sch.power-pin-shown` info per symbol.
- **Name.** The embedded name MUST be `<nickname>:<name>`, and the sub-symbol names MUST keep the bare name.
- **Gate.** `versions.check_emittable` MUST run on the node for `target`; an error MUST raise `LossyWriteError`, or with `allow_lossy=True` drop the slot with a warning.
- **Power flag.** `symembed.power_flag(target)` MUST return the authored definition `fenolite:PWR_FLAG`: flagged `power`, reference `#FLG`, one pin of type `power_out` numbered `1` at the origin with length 0, `in_bom` and `on_board` false, and a description that says it is authored for Fenolite. It MUST hold no content of any other library.
- **Project library.** `symembed.write_symbol_library(symbols, *, target) -> str` MUST write a `.kicad_sym` text with the header of the target (`FORMAT_VERSIONS[FileKind.SYMBOL_LIB][target]`, generator `fenolite`) holding the same nodes under their bare names, sorted by name. `sym.read_symbol_library` MUST read it back with equal pins.

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

### Requirement: Names of unconnected-pin nets
`fenolite.backends.kicad.netnames.unconnected_name(ref, *, unit, unit_count, pin_name, pad_number) -> str` SHALL return the net name KiCad derives for a pin on no net: `unconnected-(<ref><letter>-<pin text>-Pad<pad number>)` for a pin with a name, and `unconnected-(<ref>-Pad<pad number>)` for a pin whose name is empty.
- `<letter>` MUST be `netnames.unit_letter(unit, unit_count)`: empty for a symbol of one unit, and `A` to `Z` for units 1 to 26 otherwise. A unit above 26 MUST raise `ValueError`.
- `<pin text>` MUST be `netnames.pin_text(pin_name)`: the name with each blank replaced by `_` and each `/` by `{slash}`.
- `netnames.PROVED_PIN_CHARS` MUST hold the characters whose probe gave `equal` on both majors. The generator MUST leave out of `pad_nets` every pin whose name holds another character, with one `kicad.sch.unconnected-name-unproven` warning naming the pin.

#### Scenario: Named and unnamed pins
- **WHEN** `unconnected_name` is called for `U1`, one unit, pin name `PA1`, pad `2`, and for pin name `""`, pad `16`
- **THEN** it returns `unconnected-(U1-PA1-Pad2)` and `unconnected-(U1-Pad16)`

#### Scenario: Unit letter only with a name
- **WHEN** it is called for `U2`, unit 3 of 3, pin name `GND`, pad `7`, and for unit 1 of 3, pin name `""`, pad `1`
- **THEN** it returns `unconnected-(U2C-GND-Pad7)` and `unconnected-(U2-Pad1)`

#### Scenario: Slash and blank in a pin name
- **WHEN** it is called with pin names `A/B` and `X 1`
- **THEN** the names hold `A{slash}B` and `X_1`

#### Scenario: Unproved character
- **GIVEN** a symbol with an unconnected pin whose name holds a character outside `PROVED_PIN_CHARS`
- **WHEN** the sheet is generated
- **THEN** `pad_nets` has no entry for that pin, and the issues hold one `kicad.sch.unconnected-name-unproven` warning

### Requirement: Generated schematic issue codes
`schgen.ISSUE_CODES` SHALL map every code that the generator, the layout and the embedding emit to its severity, and SHALL be exactly this table. The `build.` codes of the table SHALL join the closed build issue set of `design-dsl`, "Build issue codes".

| code | severity | when |
|---|---|---|
| `kicad.sch.pin-off-grid` | info | a library pin is not on the 1.27 mm grid |
| `kicad.sch.power-pin-shown` | info | a hidden power-input pin is embedded visible |
| `kicad.sch.unconnected-name-unproven` | warning | the net name of an unconnected pin is not written |
| `build.schematic-too-large` | error | the units do not fit an A0 page |
| `build.symbol-overlap` | warning | two cells overlap after a placement |
| `build.symbol-short` | error | two connection points of different units coincide |
| `build.symbol-placement-unknown` | warning | the placements file names no unit of the design |
| `build.symbol-placement-invalid` | error | a placement is off the grid, has an unknown key or an unproved rotation |
| `build.reserved-library` | error | a design names a library `fenolite` |
| `build.schematic-replaced` | warning | an edited schematic is replaced |

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_schgen.py -k codes` collects the code literals of `schgen.py`, `schlayout.py`, `symembed.py` and `lens/schplacements.py`
- **THEN** each is a key of `schgen.ISSUE_CODES` or of `sch.WRITE_ISSUE_CODES`, with the severity of its table

#### Scenario: Codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** every key of `schgen.ISSUE_CODES` appears in `docs/cli-contract.md`

### Requirement: Generated schematics are documented
`docs/schematic.md` SHALL say what `build` writes for the schematic and why: one symbol per unit, global labels instead of wires, no-connect flags from marks, power flags from power interfaces, shown power pins, pad numbers on mapped symbols, the project libraries, the names of unconnected pads, the stored form of slash nets, the placements file with an example, what is replaced on a rebuild, and the limits (one sheet up to A0, no wires, no hierarchy, no buses). `docs/formats/kicad/schematic.md` SHALL gain the fact rows of the written form per target and of every probe, each with a source, a label and a hypothesis.

#### Scenario: Guide present and checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_repo_layout.py tests/residue` runs
- **THEN** it passes with `docs/schematic.md` present and linked from `README.md` and `docs/dsl.md`
