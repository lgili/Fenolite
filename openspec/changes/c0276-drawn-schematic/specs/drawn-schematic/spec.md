## ADDED Requirements

### Requirement: Drawn schematic file
`fenolite.lens.drawn.read_drawn(text, *, file="") -> DrawnSchematic` SHALL read a `schematic.toml` of schema `fenolite.drawn-schematic.v0`: the root keys `schema`, `root` and one or more `[[sheet]]` tables. An unknown key, a missing key, a wrong type, a duplicate sheet key or a `root` naming no sheet MUST raise `FormatError` (`FEN-3004`) naming the file and the locator. It reads no other file.

#### Scenario: Minimal file
- **GIVEN** the authored file `tests/data/drawn/flat/schematic.toml` (CC0, authored for Fenolite)
- **WHEN** `uv run pytest tests/unit/lens/test_drawn_file.py -k minimal` reads it
- **THEN** the value has one sheet `root` with the symbols `U1` and `R1`, three wire segments, one junction, one local label and one power item

#### Scenario: Unknown key located
- **GIVEN** the same file with `colour = "red"` added to its second wire
- **WHEN** it is read
- **THEN** `FormatError` is raised naming the file and `sheet[0].wire[1].colour`

#### Scenario: Wrong schema
- **GIVEN** a file whose `schema` is `fenolite.drawn-schematic.v1`
- **WHEN** it is read
- **THEN** `FormatError` is raised naming `schema`

### Requirement: Drawn file numbers
Positions and sizes of a drawn file SHALL be millimetres read with `parse_float=Decimal` and stored as integer nanometres; a value that is not a whole number of nanometres MUST raise `FormatError`. Rotations of symbols, power symbols, labels and sheet pins MUST be 0, 90, 180 or 270, field rotations 0 or 90, and `mirror` empty, `x` or `y`; any other value MUST raise `FormatError`. No float is created.

#### Scenario: Exact decimals
- **GIVEN** a symbol at `[25.4, 50.8]` and a wire point at `[0.0001, 1.27]`
- **WHEN** the file is read
- **THEN** the symbol is at `(25_400_000, 50_800_000)` and the point at `(100, 1_270_000)`

#### Scenario: Below a nanometre
- **GIVEN** a junction at `[1.0000001, 2]`
- **WHEN** the file is read
- **THEN** `FormatError` is raised naming `sheet[0].junction[0].at`

### Requirement: Drawn sheet items
Each `[[sheet]]` SHALL hold `key`, `paper`, and MAY hold `title_block`, `generated` and the item arrays `symbol`, `power`, `wire`, `bus`, `bus_entry`, `junction`, `no_connect`, `label`, `bus_alias`, `sheet_ref` (with `pin`) and `opaque`, each with the closed keys that `docs/drawn-schematic.md` lists. A `wire` or `bus` MUST have two or more points. A `label` kind MUST be `local`, `global` or `hierarchical`. An `opaque` item MUST hold one `kicad` S-expression.

#### Scenario: Every kind read
- **WHEN** `uv run pytest tests/unit/lens/test_drawn_file.py -k kinds` reads `tests/data/drawn/full/schematic.toml`
- **THEN** each item array of the table is read with its count, and a wire of four points gives three segments

#### Scenario: One-point wire
- **GIVEN** a wire with `pts = [[0, 0]]`
- **WHEN** the file is read
- **THEN** `FormatError` is raised naming that wire

#### Scenario: Bad opaque item
- **GIVEN** an opaque item whose `kicad` text is `(text "a"`
- **WHEN** the file is read
- **THEN** `FormatError` is raised naming the item

### Requirement: Repeated drawn sheets
A `sheet_ref` SHALL name a drawn sheet by `sheet` and a code module by `module`, relative to the module of the instance that holds it. Several references MAY name one sheet; each is one instance whose symbols are the components `<module path>/<part>`. A reference naming no sheet, a cycle of references, and a sheet other than the root that no reference reaches MUST give `drawn.sheet-unknown` (error).

#### Scenario: Two channels, one sheet
- **GIVEN** `tests/data/drawn/repeat/schematic.toml`, whose root holds references `ch0` and `ch1` to the sheet `channel` with the modules `ch0` and `ch1`
- **WHEN** `uv run pytest tests/unit/model/test_drawn_instances.py` lists the instances
- **THEN** there are three instances, and the symbol `R1` of `channel` stands for the components `ch0/R1` and `ch1/R1`

#### Scenario: Cycle refused
- **GIVEN** a sheet `a` that references `b`, and `b` that references `a`
- **WHEN** the instances are listed
- **THEN** one `drawn.sheet-unknown` error names `a` and `b`

### Requirement: Canonical drawn file
`fenolite.lens.drawn.write_drawn(drawn) -> str` SHALL write a drawn schematic in canonical form: root keys, then sheets in page order, keys in the documented order, items in their order, numbers as the shortest exact decimal of millimetres, ending with a newline. Reading the written text MUST give an equal value, and writing a value read from a canonical file MUST give the file's bytes.

#### Scenario: Stable bytes
- **WHEN** `uv run pytest tests/unit/lens/test_drawn_file.py -k canonical` writes, reads and writes again each authored drawn file
- **THEN** both texts are equal and equal to the committed file

#### Scenario: Property test
- **WHEN** generated drawn values are written and read
- **THEN** each read value equals the written one

### Requirement: Drawn connectivity resolver
`fenolite.model.drawn_connect.resolve(drawn, pins, *, design_name) -> DrawnNetlist` SHALL give the nets of a drawn schematic: per net its members as (component path, pin number), its name and the items that name it, plus open pins, dangling segment ends, unconnected labels and unmatched sheet pins. `pins` gives each symbol's pin points in the sheet frame. It MUST read no file, run no tool and use no float.

#### Scenario: Hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/model/test_drawn_connect.py -k hermetic` resolves `tests/data/drawn/full/schematic.toml`
- **THEN** it returns nets and the AST check of the module finds no float literal and no float call

#### Scenario: Order and splitting do not matter
- **WHEN** a property test shuffles the items of a drawn sheet and splits or joins collinear wire segments
- **THEN** the nets and their names are unchanged

### Requirement: Drawn connectivity rules
The resolver SHALL join: the two ends of a wire segment; segment ends that meet; a label anchor lying on a segment, its inside included; every segment end, segment inside and pin at a junction; local labels of one text on one sheet instance; global labels and power symbols of one text on all sheets; a hidden `power_in` pin with the global net of its name; a hierarchical label with the sheet pin of its name on its instance's reference. A segment end lying inside another segment (a T) and crossing segments MUST NOT join without a junction on that point, and a pin MUST join a wire at the wire's end only (`H-K-SCH-WIRE-END`), as `kicad-cli` 9.0.9 and 10.0.6 read them (measured on 2026-10-29).

#### Scenario: T joint and crossing
- **GIVEN** a drawn sheet where wire `A` ends inside wire `B`, and wire `C` crosses `B`, both without a junction
- **WHEN** it is resolved
- **THEN** the pins on `B` form one net, the pin on `A` stays apart, and the pins on `C` form another net

#### Scenario: Junction on a crossing
- **GIVEN** the same sheet with junctions on the end of `A` and on the crossing point of `C` and `B`
- **WHEN** it is resolved
- **THEN** the pins on `A`, `B` and `C` form one net

#### Scenario: Hierarchical pin
- **GIVEN** `tests/data/drawn/hier/schematic.toml`, whose child sheet labels `R2` pin 1 `IN` (hierarchical) and whose root wires the sheet pin `IN` to `U1` pin 3
- **WHEN** it is resolved
- **THEN** `U1` pin 3 and `child/R2` pin 1 are one net

#### Scenario: Local labels stay on their instance
- **GIVEN** the repeated sheet fixture, whose sheet `channel` labels a local net `FB`
- **WHEN** it is resolved
- **THEN** `ch0/R1` pin 2 and `ch1/R1` pin 2 are on two different nets

### Requirement: Drawn bus connectivity
The resolver SHALL expand bus labels of the forms `NAME[a..b]` and `{A B}` and the sheet's bus aliases into member names, and SHALL carry each member net between a sheet pin and its hierarchical label of bus form. A wire on a bus entry MUST join a member only through its own label. A bus member that no label carries MUST give `drawn.bus-member-unknown` (warning).

#### Scenario: Data bus through a sheet
- **GIVEN** `tests/data/drawn/bus/schematic.toml`, whose root bus `D[0..3]` reaches the sheet pin `D[0..3]` and whose child labels wires `D0` to `D3` on bus entries
- **WHEN** it is resolved
- **THEN** each root wire labelled `D<k>` and the child pin labelled `D<k>` are one net, for `k` from 0 to 3

#### Scenario: Entry without a label
- **GIVEN** the same child with the label of `D2` removed
- **WHEN** it is resolved
- **THEN** the child wire on that entry is a net of its own, and one `drawn.bus-member-unknown` warning names `D2`

### Requirement: Drawn net names
The resolver SHALL name each net: a net with a global label or power symbol takes that text; a net named only by local or hierarchical labels takes `/` plus the names of the sheet references from the root, `/`, and the text; an unnamed net takes the rule of "Names of unconnected-pin nets" and `netnames`. Ties MUST go to the text that sorts first in code-point order.

#### Scenario: Names in a child sheet
- **WHEN** the hierarchical fixture is resolved
- **THEN** the net of the child's local label `FB` is named `/child/FB`, and the net of the global label `VCC` is named `VCC`

#### Scenario: Two global labels on one net
- **GIVEN** a net that carries the global labels `VIN` and `IN_PWR`
- **WHEN** it is resolved
- **THEN** its name is `IN_PWR`

### Requirement: Drawing compared with the circuit
`fenolite.model.drawn_connect.compare(netlist, circuit) -> tuple[Issue, ...]` SHALL compare the drawn nets with the circuit as partitions of (component path, pin number) over components with a drawn symbol, and MUST give `drawn.netlist-differs` (error) for the first differing `REF-PIN` in sorted order, naming both nets and the reason `split`, `merged` or `open`, and `drawn.net-name-differs` (warning) for equal groups whose names differ.

#### Scenario: A faithful drawing
- **GIVEN** the design `examples/drawn/design.py` and its `schematic.toml`
- **WHEN** `uv run pytest tests/unit/model/test_drawn_compare.py -k faithful` compares them
- **THEN** no issue is returned

#### Scenario: A wire moved to the wrong pin
- **GIVEN** the same drawing with the wire end on `R1` pin 1 moved to `R1` pin 2
- **WHEN** they are compared
- **THEN** one `drawn.netlist-differs` error names `R1-1` with the reason `open` or `split`

#### Scenario: Name only
- **GIVEN** the drawing with the label `SDA` renamed `I2C_SDA`
- **WHEN** they are compared
- **THEN** there is no error and one `drawn.net-name-differs` warning names `SDA` and `I2C_SDA`

### Requirement: Drawn schematic coverage
Before a drawn schematic is lowered, every unit of every code component with a resolved symbol SHALL be drawn exactly once per instance of its module. A missing unit MUST give `drawn.symbol-missing` (error), or `drawn.unit-missing` (warning) when that unit has no pin on a net; a drawn part that code lacks, or a unit drawn twice, MUST give `drawn.part-unknown` (error).

#### Scenario: Part added in code only
- **GIVEN** `examples/drawn/design.py` with one more resistor `R9` connected to `SDA`
- **WHEN** the coverage is checked
- **THEN** one `drawn.symbol-missing` error names `R9` unit 1

#### Scenario: Unused unit
- **GIVEN** a quad op-amp whose fourth unit has no pin on a net and is not drawn
- **WHEN** the coverage is checked
- **THEN** one `drawn.unit-missing` warning names that unit and no error is given

### Requirement: Drawn schematic issue codes
`fenolite.model.drawn_connect.ISSUE_CODES` SHALL be the closed set: errors `drawn.netlist-differs`, `drawn.symbol-missing`, `drawn.part-unknown`, `drawn.sheet-pin-unmatched`, `drawn.sheet-unknown` and `drawn.repeated-value-differs`; warnings `drawn.net-name-differs`, `drawn.unit-missing`, `drawn.dangling`, `drawn.label-unconnected`, `drawn.bus-member-unknown` and `drawn.placements-ignored`; infos `drawn.opaque-dropped`, `drawn.frozen` and `drawn.altium-repeat-flattened`.

#### Scenario: Closed and explained
- **WHEN** `uv run pytest tests/unit/model/test_drawn_codes.py` collects the codes the modules emit
- **THEN** they equal `ISSUE_CODES`, each matches `ISSUE_CODE`, and `fenolite explain` knows each one

### Requirement: Repeated sheet values
Components that one symbol of a repeated drawn sheet stands for SHALL have equal values and footprints, because a KiCad repeated sheet carries one value per symbol. Otherwise `drawn.repeated-value-differs` (error) MUST name the symbol, the instances and the differing field, with a hint to split the sheet.

#### Scenario: Different resistor per channel
- **GIVEN** the repeated fixture with `ch1/R1` set to `22k` in code and `ch0/R1` to `10k`
- **WHEN** the coverage is checked
- **THEN** one `drawn.repeated-value-differs` error names `R1`, `ch0`, `ch1` and `value`

### Requirement: Drawn sheets lowered for KiCad
`fenolite.backends.kicad.drawn.lower_drawn(drawn, design, parts, *, name, target, vendor="all", allow_lossy=False) -> GeneratedSchematic` SHALL build the created sheets of a drawn schematic, returning the fields that `generate_schematic` returns, with symbols posed as drawn, references, values and footprints from code, power symbols from their library, and child sheets keyed by file, one per drawn sheet.

#### Scenario: Same contract as the generator
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_drawn_lower.py -k contract` lowers the example for targets 9 and 10
- **THEN** `paths` names every component with a symbol, `pad_nets` names the open pins, `libraries` holds the used symbols, and the build steps after the generator run unchanged

#### Scenario: Deterministic ids
- **WHEN** the example is lowered twice
- **THEN** every uuid and every text is equal

### Requirement: Drawn content of read KiCad sheets
`fenolite.backends.kicad.drawn.extract(root, children, *, components) -> tuple[DrawnSchematic, tuple[Issue, ...]]` SHALL turn read sheets into a drawn schematic: modelled items directly, the opaque root slots `wire`, `bus`, `bus_entry`, `junction` and `bus_alias` parsed into items, `#` power symbols into power items, and a sheet named by several references into one sheet with several references.

#### Scenario: Hand-drawn fixture
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_drawn_extract.py -k flat` extracts `tests/data/kicad/schematic/flat.kicad_sch` with its components
- **THEN** every opaque `wire` and `junction` slot gives one item, and no slot is lost

#### Scenario: Write and extract again
- **GIVEN** the drawn value extracted from each authored KiCad fixture
- **WHEN** it is lowered, written for its target, read and extracted again
- **THEN** the second value equals the first

### Requirement: Opaque items of read sheets
Every root slot of a read sheet that extraction does not map, and every symbol whose reference maps to no component, SHALL become an `opaque` item holding its fragment verbatim with its minimum version; the unmapped symbol MUST also give `drawn.part-unknown`. A slot whose numbers are not whole nanometres MUST stay opaque with `kicad.sch.inexact-length`.

#### Scenario: Text kept
- **GIVEN** a read sheet with a `text` item and a `rectangle`
- **WHEN** it is extracted and lowered again
- **THEN** both fragments are written unchanged, at the place of the opaque items in root order

#### Scenario: Unknown symbol kept
- **GIVEN** a read sheet with a symbol `X1` and a component map without `X1`
- **WHEN** it is extracted
- **THEN** one `drawn.part-unknown` names `X1` and its symbol is an opaque item

### Requirement: Freezing a generated schematic
Extraction of the sheets that `generate_schematic` built SHALL give a drawn schematic which, lowered for the same target, gives the generated texts with every byte equal except the uuids of labels, wires, junctions and flags (drawn items take their ids from their sheet and index), the same board, and the same drawn value when extracted again, so a generated schematic can be frozen into a drawn one with `drawn.frozen` (info) and a hint to call `design.load_schematic`.

#### Scenario: Frozen blink
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_drawn_freeze.py` freezes the generated blink and the design of "Two modules, one nested" and lowers the result for targets 9 and 10
- **THEN** each text equals the generated one once uuids are left out, the board's bytes are equal, and extraction gives the frozen value again

### Requirement: Generated sheets inside a drawing
A drawn sheet with `generated = true` SHALL hold no item. For each reference to it, the build MUST generate the sheet of that module instance with the rules of c0269's block sheets and write it at `schgen.sheet_file(<module path>)`. The reference MUST carry the sheet pins the generator gives, by name and shape; else `drawn.sheet-pin-unmatched` (error).

#### Scenario: Drawn top, generated block
- **GIVEN** a drawn root that references the block instance `ch0` of the block example through a `generated` sheet with the pins `VIN`, `EN` and `GND`
- **WHEN** it is built for target 10
- **THEN** the build writes the drawn root and `sheets/ch0.kicad_sch`, and its guard reports nothing

#### Scenario: Missing pin
- **GIVEN** the same reference without the pin `EN`
- **WHEN** it is built
- **THEN** one `drawn.sheet-pin-unmatched` error names `ch0` and `EN`, and nothing is written

### Requirement: Drawn schematic evidence
Each connectivity and naming rule of the resolver SHALL be a row of `docs/formats/kicad/schematic.md` with its source (S-0046 or S-0367) and label, `INFERRED` until its hypothesis passes. The KiCad CI job MUST compare the resolver's nets with `kicad-cli sch export netlist` on the authored drawn fixtures and the demo rows, and record the probes `drawn-connect`, `drawn-names`, `drawn-bus` and `drawn-repeat`.

#### Scenario: Oracle on 9.0 and 10.0
- **WHEN** `uv run pytest tests/kicad/schematic/test_drawn_oracle.py -rA` runs with `kicad-cli` 9.0.9 or 10.0.6
- **THEN** every authored fixture gives the nets of the export, and the probes record `equal` or the differences by kind

### Requirement: Drawn schematic documentation
`docs/drawn-schematic.md` SHALL describe the file schema with every key, repeated sheets, ownership (CAD owns the drawing, code owns the nets), the build, the check stage, sync, freezing, generated sheets and the codes. `docs/dsl.md` MUST document `load_schematic`, and the agent guide page `design-script` MUST hold a tested line for it.

#### Scenario: Pages cover the names
- **WHEN** `uv run pytest tests/consistency tests/unit/agent/test_pages.py` runs
- **THEN** both pass, and every key of the reader's closed sets appears in `docs/drawn-schematic.md`
