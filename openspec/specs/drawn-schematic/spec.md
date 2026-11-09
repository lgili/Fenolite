# drawn-schematic Specification

## Purpose
TBD - created by archiving change c0329-sheet-custom-properties. Update Purpose after archive.
## Requirements
### Requirement: Typed custom sheet properties
Drawn sheet references SHALL preserve ordered custom property names, texts and supported poses/fonts as typed values. Names MUST be unique, nonempty and distinct from code-owned Sheetname/Sheetfile. Empty properties MUST preserve ordinary defaults.

#### Scenario: A custom property round trip
- **GIVEN** an authored sheet reference with a custom property
- **WHEN** the closed drawn file is written and read
- **THEN** its text, order and supported effects are preserved exactly
- **AND** reserved names, duplicates and malformed records refuse

### Requirement: Custom sheet property fidelity
Supported native custom sheet properties MUST survive strict import and lowering and participate in level S and scene output. Unsupported property data SHALL refuse before staging. Electrical connectivity, source bytes, default output bytes and comparison tolerances MUST remain unchanged.

#### Scenario: A property is removed by a defective writer
- **GIVEN** a passing authored all-nine-level control with visible custom sheet text
- **WHEN** its custom property is removed from the rebuilt sheet
- **THEN** S and presentation detect the loss with no accepted difference
- **AND** the electrical comparison and original source remain unchanged

#### Scenario: Native readers disagree on legacy tilde
- **GIVEN** custom sheet text `~` in a format-9 source
- **WHEN** extraction or rendering would require choosing between conflicting native meanings
- **THEN** the operation refuses explicitly instead of substituting empty or literal text

### Requirement: Corpus rows retain native owner context
Each declared demo row SHALL be measured in every registered project root that reaches it, preserving annotation paths and the full owner's pin universe. Reports MUST bind row, owner/export-root IDs, input hashes and instance-path hashes. Unowned rows SHALL remain standalone cases; missing, unreadable or conflicting contexts MUST remain failures. No row, pin or finding may be removed to make the census pass.

#### Scenario: Child port in a repeated root
- **GIVEN** an authored root referencing one child with a hierarchical port twice
- **WHEN** the child's corpus row is measured
- **THEN** both annotated instances are covered in the native owner hierarchy and compared without unmatched artificial root ports

### Requirement: Native KiCad connection names
Resolution of read KiCad drawings SHALL use KiCad's native identity for slash spellings in connection names, including labels, sheet pins, power names and bus members. It MUST preserve the extracted drawing text and strict code partition comparison. The generic resolver MUST keep its literal name semantics.

#### Scenario: Native slash aliases join
- **GIVEN** separate wire islands labeled `A/B` and `A{slash}B`
- **WHEN** their native KiCad sheets are resolved
- **THEN** their pins join, the two drawn texts survive, and distinct code nets still fail the build guard

### Requirement: Root sheet component paths
Extraction MUST keep the root sheet instance at the empty code-module path. A common prefix of its components MUST remain in their drawn `part` paths, even when every root-sheet part belongs to one named code module. Child-sheet module paths MUST retain their existing relative behavior.

#### Scenario: Root parts share a code module
- **WHEN** an authored flat source project whose parts all have one code-module prefix is strictly imported, built and compared
- **THEN** the root drawing retains that prefix, all nine fidelity levels compare equal and source bytes remain unchanged

### Requirement: Per-unit native symbol bindings
A drawn symbol MAY name an optional library `symbol` override for its unit. Its logical pin numbers, names, types and hidden states MUST match the code symbol's unit before lowering. Extraction MUST preserve distinct source unit bodies and sync MUST retain overrides relative to code, including pin-pad variants. Missing or incompatible bindings MUST refuse; ordinary files MUST keep their bytes.

#### Scenario: Native unit aliases
- **WHEN** authored units of one component use distinct compatible embedded aliases and are strictly imported, built and synced
- **THEN** each native body survives, all nine fidelity levels compare equal and a conflicting same-unit or incompatible binding refuses

### Requirement: Pinless native graphic symbols
Extraction SHALL keep a pinless source symbol as a native opaque graphic when its instance excludes it from board and BOM. Library default flags MUST remain unchanged and MUST NOT cancel those instance exclusions. Lowering MUST embed the same definition. Missing definitions and unsupported electrical opaque instances MUST refuse; this path MUST NOT add circuit components or connectivity.

#### Scenario: Graphic symbol survives
- **WHEN** an authored pinless excluded graphic symbol is strictly imported, built and compared
- **THEN** its native body and instance survive with all nine levels equal, while an electrical lookalike refuses

### Requirement: Excluded passive native instances
A native instance excluded from board and BOM MAY remain opaque when its resolved definition is non-power with only visible passive pins. Extraction and lowering MUST preserve its definition and flags without circuit nodes. Active, hidden or power pins and missing exclusions MUST refuse; the native export's common-pin partition MUST remain equal.

#### Scenario: Excluded passive instance survives
- **WHEN** an authored excluded resistor is strictly imported, rebuilt and exported by KiCad
- **THEN** all nine authored levels are equal, its native pose survives, and the export has no node for it

### Requirement: Legacy hidden power instances
Extraction SHALL represent a legacy `#PWR` instance lacking a power flag when its definition has exactly one hidden `power_in` pin at the origin, named by the instance value. It MUST preserve the definition and poses and resolve that global connection through the hidden-pin rule. A reference prefix alone MUST NOT classify a symbol as power.

#### Scenario: Legacy power without flag
- **WHEN** an authored symbol with that hidden pin and no power flag is strictly imported and built
- **THEN** its native definition survives, all nine fidelity levels compare equal and malformed lookalikes still refuse

### Requirement: Mirrored source power symbols
A drawn power item SHALL accept optional `mirror` equal to empty, `x` or `y`. Extraction and lowering MUST preserve it and transform its pin points with that mirror. Level S MUST compare the mirror. Omitting it MUST retain existing canonical bytes.

#### Scenario: Mirrored power round trip
- **WHEN** an authored sheet with mirrored power symbols is extracted, written as TOML, lowered for either KiCad target and extracted again
- **THEN** the mirror, drawing and resolved connectivity survive and a changed mirror produces a level S difference

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
The resolver SHALL join: the two ends of a wire segment; segment ends that meet; a label anchor lying on a segment, its inside included; every segment end, segment inside and pin at a junction; local labels of one text on one sheet instance; global labels and power symbols of one text on all sheets; a hidden `power_in` pin with the global net of its name; a hierarchical label with the sheet pin of its name on its instance's reference.

#### Scenario: Hierarchical pin
- **GIVEN** `tests/data/drawn/hier/schematic.toml`, whose child sheet labels `R2` pin 1 `IN` (hierarchical) and whose root wires the sheet pin `IN` to `U1` pin 3
- **WHEN** it is resolved
- **THEN** `U1` pin 3 and `child/R2` pin 1 are one net

#### Scenario: Local labels stay on their instance
- **GIVEN** the repeated sheet fixture, whose sheet `channel` labels a local net `FB`
- **WHEN** it is resolved
- **THEN** `ch0/R1` pin 2 and `ch1/R1` pin 2 are on two different nets

### Requirement: Drawn joints need a junction
A segment end lying inside another segment (a T) and crossing segments MUST NOT join without a junction on that point, and a pin MUST join a wire at the wire's end only (`H-K-SCH-WIRE-END`), as `kicad-cli` 9.0.9 and 10.0.6 read them (measured on 2026-10-29).

#### Scenario: T joint and crossing
- **GIVEN** a drawn sheet where wire `A` ends inside wire `B`, and wire `C` crosses `B`, both without a junction
- **WHEN** it is resolved
- **THEN** the pins on `B` form one net, the pin on `A` stays apart, and the pins on `C` form another net

#### Scenario: Junction on a crossing
- **GIVEN** the same sheet with junctions on the end of `A` and on the crossing point of `C` and `B`
- **WHEN** it is resolved
- **THEN** the pins on `A`, `B` and `C` form one net

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
`drawn_connect.ISSUE_CODES` SHALL be closed: errors `drawn.netlist-differs`, `drawn.symbol-missing`, `drawn.part-unknown`, `drawn.sheet-pin-unmatched`, `drawn.sheet-unknown`, `drawn.repeated-value-differs`; warnings `drawn.net-name-differs`, `drawn.unit-missing`, `drawn.dangling`, `drawn.label-unconnected`, `drawn.bus-member-unknown`, `drawn.placements-ignored`, `drawn.coordinate-rounded`; infos `drawn.opaque-dropped`, `drawn.frozen`, `drawn.altium-repeat-flattened`.

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

### Requirement: Demo drawn census
Every manifest demo schematic row SHALL have a version-bound census of input hashes, drawn item counts, lowering/resolution and native partition/naming outcomes or explicit refusal. Comparisons MUST retain native-only pins and open singletons. Reports MUST precede strict assertions and contain no component values, labels or CAD fragments. Census completion SHALL NOT imply equality or raise evidence levels.

#### Scenario: A demo refuses or differs
- **WHEN** extraction, lowering or native export refuses a row, or pin partitions differ
- **THEN** its report records the actual stage/kinds/counts and the corpus assertion fails
- **AND** native-version incompatibility and naming warnings remain distinct from equal connectivity

### Requirement: Scoped bus resolution
Drawn bus resolution MUST preserve the native-validated pin partition for
authored bus, alias and hierarchy controls. Corrections SHALL preserve raw label
text, drawing geometry, generic/Altium literal semantics and existing strict
errors. An entry without a defining member label MUST NOT acquire a guessed net.

#### Scenario: Reproduced bus member join
- **GIVEN** an authored control reproduces a measured bus partition difference
- **WHEN** the resolver and the actual native KiCad CLI resolve it
- **THEN** their complete pin partitions agree after the bounded correction
- **AND** native evidence names only the version actually executed

#### Scenario: Unnamed or unrelated member
- **WHEN** a bus entry has no defining label, or a literal label is unrelated
- **THEN** the resolver keeps the existing refusal/unknown-member behavior
- **AND** raw labels, geometry and unrelated backend semantics remain unchanged

### Requirement: Bus contacts retain their layer
A bus label at a bus-side entry endpoint or bus-only junction SHALL remain a
bus label when no wire or pin meets its anchor. Real wire and pin contacts MUST
retain their existing meaning. The correction MUST preserve raw labels and
geometry and MUST NOT guess an unnamed member connection.

#### Scenario: Hierarchical bus label meets an entry
- **WHEN** an authored hierarchical bus label stands at the bus end of an entry with no wire or pin there
- **THEN** vector, group and alias members retain the native-validated partition
- **AND** the drawn source is unchanged

### Requirement: Bus definitions retain their scoped identity
Native-validated corresponding members on one connected bus SHALL join without
rewriting their qualified scalar labels. Unrelated bus groups and literal nets
MUST remain separate. Overbar spans in member names MUST remain literal and
MUST NOT be confused with group delimiters. The exact correspondence SHALL be
proved by authored native controls before implementation.

#### Scenario: Qualified bus members meet
- **WHEN** authored renamed or reordered bus definitions share a physical bus
- **THEN** their complete pin partition follows the measured native correspondence
- **AND** disconnected buses and raw label spellings remain unchanged

### Requirement: Native scalar label scopes stay bounded
KiCad scalar labels of the same literal text on one sheet SHALL follow the
native-measured local, hierarchical and global scope aliases. Unequal names
and other instances MUST retain their scope. Generic/Altium defaults and
unmatched sheet-pin diagnostics MUST remain unchanged.

#### Scenario: Local and hierarchical names meet on a sheet
- **WHEN** authored scalar labels of different scopes share exact text on one sheet
- **THEN** their pin partition follows the actual native control
- **AND** unequal names, unrelated instances and unmatched-port errors remain visible

### Requirement: Closed drawn font syntax
The drawn TOML codec SHALL read and canonically write optional fonts on fields, labels and sheet pins, explicit label/pin justification and sheet-property poses. Width and height MUST use exact decimal mm mapped to integer nm. Unknown keys, unsupported effects and inexact lengths MUST refuse with a locator.

#### Scenario: Asymmetric font round trip
- **GIVEN** a drawing with different font width and height on every typed text surface
- **WHEN** it is written, read and written again
- **THEN** the model and both texts are equal without swapping axes

#### Scenario: Unknown effect
- **WHEN** a drawn font table contains an unknown key
- **THEN** reading refuses and names the table and key

#### Scenario: Fraction below Decimal context precision
- **WHEN** a font length has fractional nanometres beyond the ambient decimal precision
- **THEN** reading refuses the exact remainder rather than rounding it into an accepted integer

### Requirement: Drawn field text authority
Styled drawn fields MUST continue to obtain Reference, Value and Footprint text from code, except that a
drawn symbol marked `empty_footprint` SHALL write an empty Footprint field while its part keeps its
footprint. The drawing MUST NOT hide conflicting source text in generic properties or opaque
placeholders. A font-preservation change SHALL leave an independent footprint-text disagreement visible
to fidelity comparison.

#### Scenario: Conflicting footprint texts
- **GIVEN** an original PCB selector different from its visible schematic Footprint text
- **WHEN** the drawing is converted and rebuilt with preserved fonts
- **THEN** the code selector remains authoritative and the remaining text difference is reported

#### Scenario: Empty source Footprint field
- **GIVEN** a source symbol whose visible Footprint field is empty while its board footprint is set
- **WHEN** it is imported and built
- **THEN** `schematic.toml` marks that unit `empty_footprint = true`, the part keeps the board footprint,
  and the built schematic field is empty in the same pose and font

### Requirement: Native drawn bus identifiers preserve exact members
The Altium drawn writer SHALL convert a bus-only group or alias identifier to
a native vector only when its exact scalar member set is representable by a
contiguous canonical numeric range with a common nonempty prefix. It SHALL
report each changed identifier. It MUST preserve scalar wire labels, ordinary
vectors, coordinates and independent connectivity guards, and MUST refuse an
unrepresentable group with a source locator before planning output.

#### Scenario: Alias crosses a sheet boundary
- **GIVEN** a connected two-sheet bus whose group alias expands to D0 through D3
- **WHEN** binary or ASCII native files are produced
- **THEN** the parent label and sheet entry and child port use D[0..3]
- **AND** every scalar net and its code pin membership remain unchanged

#### Scenario: A group requires a harness
- **GIVEN** a bus-only group with unrelated or missing numeric members
- **WHEN** a native build is requested, including with allow-lossy
- **THEN** it refuses at the source identifier without writing files
- **AND** no widened native acceptance or suppressed compiler finding hides it

### Requirement: Native availability does not imply acceptance
Current native metadata SHALL name the actually measured tool and report while
retaining the original unmet acceptance criterion and inferred grade. Dated
earlier unavailable-tool observations MUST remain historical, not be reused as
the current reason or be turned into a successful native gate.

#### Scenario: Available tool with source findings
- **GIVEN** actual 22.2.1 native graph/save observations with remaining findings
- **WHEN** the current hypothesis and kit metadata are checked
- **THEN** the actual report is named and acceptance remains pending
- **AND** the deliberately broken native bus control remains a refused result

### Requirement: Scoped local aliases for global power declarations
Under the KiCad scalar-alias policy, an actually global power declaration SHALL join a local scalar label of the same name in that sheet instance. A declaration elsewhere SHALL NOT by itself promote local labels on an undeclared sheet. Unequal names and generic/default resolution SHALL retain their existing rules. Complete native pin partitions and source content SHALL be preserved.

#### Scenario: Disconnected islands share a same-sheet power name
- **GIVEN** an authored local scalar label and a global power declaration of the same name on separate islands of one sheet
- **WHEN** KiCad-scoped connectivity is resolved
- **THEN** the complete partition agrees with the actual native export, without dropping pins

#### Scenario: Another sheet has only a local name
- **GIVEN** a local label on a child sheet with no corresponding power/global declaration on that sheet
- **WHEN** the same power name appears elsewhere
- **THEN** that child local net stays isolated according to the native scoped rule

### Requirement: Literal formatted group prefixes
Drawn group-bus parsing SHALL recognize natively measured balanced formatting spans in the prefix without mistaking them for group delimiters. The complete literal prefix SHALL remain part of each expanded member name, and expansion SHALL retain the existing member cardinality and native scoped identity policy. Malformed spans and unsupported nested groups SHALL NOT be guessed into connectivity. Standalone port diagnostics and the published reader floor SHALL remain independent.

#### Scenario: A formatted group crosses a hierarchy boundary
- **GIVEN** an original authored hierarchy whose group prefix contains a measured formatting span and whose actual port/member spellings agree
- **WHEN** its complete pin partition is resolved
- **THEN** it agrees with the native export without omitted pins or altered source names

#### Scenario: Formatting does not erase literal identity
- **GIVEN** scalar members whose spelling differs from the formatted prefix expansion
- **WHEN** the resolver compares those names
- **THEN** no visual flattening or invented alias joins them

#### Scenario: Unsupported braces do not invent members
- **GIVEN** malformed formatting, an unsupported nested group or trailing invalid content
- **WHEN** bus parsing is requested
- **THEN** it retains strict refusal/diagnostics and does not invent a member count

### Requirement: Qualified floor-upgrade census evidence
The census SHALL preserve an original below-floor input's explicit refusal and immutable manifest identity. It SHALL NOT relabel that original as equal. A separately identified official-tool upgraded copy MAY qualify as `upgraded/equal` only after exact tool/version/digest provenance and complete SAME-native10 original/upgraded and own/lowered/native pin/partition/name comparisons. No intersection, accepted difference, loss flag or uncompleted comparison may substitute for proof.

#### Scenario: Original remains below the supported reader floor
- **GIVEN** checked original bytes whose actual format is below the published floor
- **WHEN** the core reader and native census run
- **THEN** the original refusal is retained without writes and the independently exported native-old graph is recorded separately

#### Scenario: Upgrade is electrically exact
- **GIVEN** immutable originals and their recorded official CLI10 copy upgrade
- **WHEN** every complete native-original/upgraded and supported own/lowered/native comparison succeeds
- **THEN** only the upgraded electrical probe receives the qualified result, retaining the original refusal and every source digest

#### Scenario: Partial or changed upgrade cannot qualify
- **WHEN** an upgrade changes a pin, partition, net name, original input or expected output digest, or a required comparison is missing
- **THEN** the probe remains failed/partial and no equality or original-support claim is made

### Requirement: Versioned floor evidence requires both native jobs
The required same-commit native9 and native10 jobs SHALL retain complete primary row records and link the same checked originals. Native10 SHALL supply every required copy-upgrade probe; native9 SHALL NOT pretend to read newer upgraded formats. Missing inputs, artifacts, graph/name proofs or commit identities SHALL fail the bridge gate. Other strict failures and incompatible primary records SHALL remain visible.

#### Scenario: Native9 lacks the upgrade operation
- **WHEN** the native9 job records an original floor boundary
- **THEN** it retains its real native-old evidence and missing-upgrade capability, while the independently required native10 job supplies the upgrade proof

#### Scenario: Native major versions disagree on the original legacy graph
- **GIVEN** the maintainer-authorized native10-only copy-upgrade qualification and a below-floor original
- **WHEN** actual native9 and native10 original observations differ
- **THEN** both complete observations and the original refusal remain visible without any9 equivalence claim
- **AND** qualification still requires every exact native10 original/upgraded pin, partition and name plus all supported own/lowered/native comparisons

### Requirement: Typed fixed global-label reference field
A drawn global label MAY carry one typed optional intersheet_refs field pose. Its name and native placeholder SHALL be fixed; its pose/font/hide SHALL survive extraction and writing. Wrong kinds, duplicate/custom properties and unsupported values SHALL refuse locally. Absence SHALL preserve legacy default bytes.

#### Scenario: Native reference property round trip
- **GIVEN** one supported global-label Intersheetrefs property
- **WHEN** the drawn/native pipeline round trips it
- **THEN** its exact pose/style/hide and fixed placeholder survive with unchanged full electrical graphs

#### Scenario: Unsupported field is not omitted
- **WHEN** a duplicate, wrong-kind or noncanonical property cannot be represented
- **THEN** the operation refuses before staging rather than hiding it in opaque storage or dropping it

### Requirement: Effective reference text is contextual per instance
The viewer SHALL resolve references from the actual project settings and full sheet instances. It SHALL mirror native show/own-page/short/prefix/suffix rules and use explicit per-instance scenes where text differs. Missing or ambiguous required context SHALL refuse locally; unresolved placeholders SHALL never be displayed as effective text. Disabled/absent fields SHALL preserve legacy scenes.

#### Scenario: One child file appears on several pages
- **GIVEN** a repeated sheet and reference display enabled with own-page disabled
- **WHEN** its instances have different effective page references
- **THEN** each view has the correct explicit instance/page and reference text, without first-instance selection

#### Scenario: Project metadata alone changes
- **WHEN** reference settings change without changing the schematic bytes
- **THEN** the scene cache invalidates and native-equivalent effective reference text is recomputed

### Requirement: Native root hierarchical ports retain standalone connectivity
The KiCad drawn resolver SHALL preserve native root hierarchical labels as
same-sheet connections without requiring an invented parent sheet pin. This
exception MUST apply only to the root instance through the KiCad adapter.
Unmatched child labels or parent pins MUST retain their errors. Generic model
resolution MUST retain its existing strict absent-parent diagnostic.

#### Scenario: Root port is native standalone source
- **WHEN** authored root labels and the complete source pin universe are compared against native9/10
- **THEN** pins, partitions and names agree and no false parent requirement blocks lowering

#### Scenario: Child mismatch remains an error
- **WHEN** a child hierarchical label has no matching pin on its actual parent reference
- **THEN** drawn.sheet-pin-unmatched still refuses and repeated children remain isolated

### Requirement: Contextual metadata definitions remain complete
Imported per-sheet definitions sharing a native ID MAY differ in property nodes only when the full non-property AST and protected Reference/Value/Footprint defaults are identical. Every occurrence MUST bind its complete source definition by context and digest. Emission SHALL preserve original native IDs and all property nodes, effects, order and opaque data. No model/S field or global cache normalization is allowed.

#### Scenario: Local descriptive default snapshot
- **GIVEN** two authored sheets with one native symbol ID and distinct Description nodes
- **WHEN** the reviewed context-aware import and build run
- **THEN** each written sheet retains its complete local definition and native ID with equal full pin partitions

### Requirement: Context conflicts remain closed
Pin, body, flag, unknown non-property semantic or protected core-default differences, same-file ambiguity, missing contexts and wrong digests MUST refuse before staging. A metadata match SHALL NOT waive electrical, geometry, semantic or written-byte fidelity checks. A wrong-sheet metadata selection MUST fail even when its pins match.

#### Scenario: An apparent metadata conflict changes a pin
- **WHEN** an authored variant changes one pin, its position, a fitted/exclusion flag or protected default
- **THEN** the import refuses and stages no file

#### Scenario: A compatible body uses another sheet's defaults
- **WHEN** a context points to a full property snapshot of another sheet
- **THEN** context fidelity refuses the result rather than accepting its connectivity alone

### Requirement: Nested source pages retain their module frame
Extraction MUST encode a child page sharing its parent's code-module frame with an empty relative module. Drawing readback SHALL preserve every complete component path and pin. A duplicated frame prefix MUST NOT be normalized in comparisons or used to omit pins. This adds no model/S field or net-name rule.

#### Scenario: Two pages share one code module
- **GIVEN** two owned parts m/R1 and m/R2 drawn on nested parent/child pages
- **WHEN** their source sheets are extracted and resolved
- **THEN** the child has an empty relative module and both complete paths survive without a repeated m prefix

### Requirement: Empty Footprint flag of drawn symbols
A drawn symbol's `empty_footprint` flag SHALL mean that the unit's source `Footprint` field is empty
while its part builds with a footprint (`DrawnSymbol.empty_footprint`; `schematic.toml` key
`empty_footprint`, boolean, written only when true).
`fenolite.backends.kicad.drawn.extract` SHALL set it only when given the footprint each reference builds
with (`footprints`) and that footprint is not empty; without `footprints` it SHALL set nothing. A
non-boolean value MUST raise `FormatError` (`FEN-3004`) naming its locator.

#### Scenario: Flag read, written and extracted again
- **GIVEN** a drawn value with one unit flagged
- **WHEN** it is written, read, lowered for KiCad 9 and 10 and extracted again with the same footprints
- **THEN** each value equals the first and the lowered unit's Footprint field is empty

#### Scenario: Parts without a footprint
- **GIVEN** a source symbol with an empty Footprint field whose part has no footprint
- **WHEN** the import extracts the drawing
- **THEN** the unit is not flagged

### Requirement: Drawn content of read Altium sheets

The Altium extractor SHALL turn the read sheets of an Altium project or document into a drawn schematic, through
`fenolite.backends.altium.drawn_read.extract(sheets, *, components=None) -> tuple[DrawnSchematic, tuple[Issue, ...]]`,
where `sheets` are the read documents that `adapter.netlist.resolve` takes and `components` maps a designator
to its component path.
It SHALL map:

- each component part to a symbol pose, with its part, mirror and display mode;
- wires and buses to polylines;
- junctions, net labels, ports, power ports, sheet symbols with their entries, bus entries and no-ERC
  markers to their drawn items;
- every other record (harness connector, harness entry, signal harness, parameter set, directive, note,
  text frame, graphic, image) to a typed opaque item that keeps its record fields.

The sheet's size, orientation, border and title-block fields SHALL become the drawn sheet's `paper` and
`title_block`. Every item MUST have its pin points, so that `drawn_connect.resolve` gives its nets.

A point is converted at 127/50 nm per Altium fraction unit, with Y down from the top of the sheet's drawing
area. A length that is not a whole number of nanometres MUST be rounded to the nearest and counted, per
sheet, by `altium.import.inexact`; an opaque item keeps its exact record text. A record the extractor cannot represent MUST give
an `error` issue naming the record. The extractor reads no file.

#### Scenario: Authored flat sheet

- **GIVEN** the authored fixture `tests/data/altium/blink/blink.SchDoc`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_drawn_read.py -k blink` extracts it
- **THEN** every component of the sheet gives one symbol pose at its record position, and every wire,
  junction, net label and power port gives one item
- **AND** the nets resolved from the drawing equal the nets of `altium-import` for the same sheet

#### Scenario: Hierarchy and harnesses

- **GIVEN** the authored project `tests/data/altium/hier/altium_hier.PrjPcb`
- **WHEN** it is extracted
- **THEN** each sheet symbol gives one sheet reference with its entries as pins
- **AND** each harness record is a typed opaque item, with its record fields unchanged

#### Scenario: Public documents read without error

- **WHEN** `uv run pytest tests/corpus/test_altium_drawn_read.py -rA` extracts the public rows
  `altium-third-party-schdoc-01` to `-17`
- **THEN** no row gives an `error` issue, and the count of items per kind of each row equals the counts in
  `docs/evidence/conversion.md`

### Requirement: Altium drawing written back

A drawing extracted from Altium sheets and written again by `backends/altium/drawn.py` SHALL read back
to an equal drawing: level S of `design-equivalence` finds no difference, the typed opaque items included.
`lower_drawn` and the native readback guard SHALL accept opaque subtrees (`OWNERINDEX=@<line>`), harness
records (`215`, `216`, `217`, `218`, and harness ports `18`), and opaque `Note` (`209`) and `CompileMask`
(`225`) records in both `convert` (`carry=True`) and `build --target altium` (`carry=False`).

#### Scenario: Write and extract again

- **GIVEN** the drawing extracted from each authored Altium fixture
- **WHEN** it is written as Altium sheets, read, and extracted again
- **THEN** the second drawing equals the first at level S

#### Scenario: Direct Altium build with subtrees, harnesses and compile masks

- **GIVEN** a project imported from Altium whose `schematic.toml` holds parameter-set subtrees (`RECORD=43`
  with child `RECORD=41`), harness connectors (`RECORD=215` with child `216` and `217`), signal harnesses
  (`RECORD=218`) and compile masks (`RECORD=225`)
- **WHEN** `fenolite build <design.py> --target altium` runs
- **THEN** the build succeeds (`exit_code == 0`) and the written `.SchDoc` files keep those records and pass
  the native readback guard

