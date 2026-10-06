# kicad-schematic Specification

## Purpose
Reading a KiCad schematic file into Fenolite's sheet model and writing it back unchanged for the same KiCad version: what of a `.kicad_sch` is modelled, what is kept as written, how a project's sheets form a tree, and how the result is checked against `kicad-cli` on the demo schematics of the corpus.
## Requirements
### Requirement: Schematic file reading
`fenolite.backends.kicad.sch.read_schematic(source, *, file="", issues=None) -> SchematicSheet` SHALL read one `.kicad_sch` file, given as a path, file text or a parsed node, into the `SchematicSheet` of `design-model`, "Schematic sheet definitions", without writing any file and without running any tool.
- The root head MUST be `kicad_sch`; any other root MUST raise `FormatError` (`FEN-3004`) naming the head.
- `SchematicSheet.name` MUST be the file stem, or `""` for text read without a file name.
- Reader issues MUST be appended to `issues` when a list is given, and MUST use only the codes of "Schematic read issue codes" and the `kicad.version.*` codes of `kicad-version-gating`.
- The reader MUST NOT derive nets: wires, junctions, buses and bus entries are never interpreted.
- Reading the same text twice MUST give equal sheets.

#### Scenario: Authored flat sheet
- **WHEN** `read_schematic(Path("tests/data/kicad/schematic/flat.kicad_sch"))` is called
- **THEN** the sheet has `name == "flat"`, six symbol instances, the references `R1`, `D1`, `U1`, `#PWR01`, `R2` and `R3`, one label of kind `local`, and at least three labels of kind `global`

#### Scenario: Wrong root
- **WHEN** `read_schematic("(kicad_pcb (version 20241229))")` is called
- **THEN** `FormatError` is raised naming `kicad_pcb`

#### Scenario: Reads are repeatable
- **WHEN** `flat.kicad_sch` is read twice
- **THEN** the two sheets are equal, ids included

### Requirement: Schematic version policy
`read_schematic` SHALL apply to `FileKind.SCHEMATIC` the policy that `kicad-file-backend`, "Board version policy", applies to boards.
- A format version below `READ_FLOOR[FileKind.SCHEMATIC]` MUST raise `UnsupportedFormatError` (`FEN-3003`) naming the version and the floor.
- A version above the newest constant MUST be read, with the warning `kicad.version.future`, and `rebuild_schematic` MUST refuse that sheet with `versions.require_editable`.
- A version between two constants MUST belong to the major that `versions.major_for` gives.
- A file without a `version` child MUST raise `FormatError`.

#### Scenario: Older than the floor
- **GIVEN** `flat.kicad_sch` with its header rewritten to `(version 20230121)`
- **WHEN** it is read
- **THEN** `UnsupportedFormatError` is raised naming `20230121` and `20231120`

#### Scenario: Newer than the newest constant
- **GIVEN** `flat.kicad_sch` with its header rewritten to `(version 20990101)`
- **WHEN** it is read with an `issues` list, and the sheet is passed to `rebuild_schematic`
- **THEN** `issues` holds `kicad.version.future`, and the rebuild raises the error of `versions.require_editable`

#### Scenario: Development version
- **GIVEN** `flat_v9.kicad_sch` with its header rewritten to `(version 20250610)`
- **WHEN** it is read
- **THEN** no version issue of severity `error` is reported, and the sheet's source major is 10

### Requirement: Modelled schematic content
The reader SHALL map the root children `uuid`, `paper`, `title_block`, `lib_symbols`, `symbol`, `label`, `global_label`, `hierarchical_label`, `no_connect`, `sheet` and `sheet_instances`, and SHALL keep every other root child as an opaque slot at its position.
- `uuid` MUST become `native_ids["kicad"]` of the sheet.
- `paper` MUST become `SchematicSheet.paper` through the board reader's paper projection (`pcb.project_paper`), and `title_block` MUST become `SchematicSheet.title_block` through `pcb.project_title_block`; a sheet without a `title_block` child has `title_block == None`.
- `sheet_instances` MUST become `SchematicSheet.pages`, one `SheetPage(path, page)` per `path` child, in file order.
- The heads `wire`, `junction`, `bus`, `bus_entry`, `bus_alias`, `polyline`, `text`, `text_box`, `rectangle`, `image`, `netclass_flag`, `rule_area`, `table` and `embedded_fonts`, the header atoms, and every head the reader does not know MUST stay opaque.
- Collections MUST keep file order.

#### Scenario: Wire and junction stay opaque
- **WHEN** `flat.kicad_sch` is read and the slot list of the sheet is inspected
- **THEN** its `wire` and `junction` children are `Opaque` slots at their source positions, and `sheet.wires` is empty: only a created sheet holds `Wire` entities (`design-model`, "Schematic sheet definitions")

#### Scenario: Unknown root child survives in place
- **GIVEN** `flat.kicad_sch` with `(frobnicate 1)` inserted as the seventh child of the root
- **WHEN** it is read
- **THEN** the seventh slot of the sheet is an `Opaque` slot whose fragment is `(frobnicate 1)`

#### Scenario: Paper and title block
- **GIVEN** `flat.kicad_sch`, which holds `(paper "A4")` and a title block with title `Flat` and revision `A`
- **WHEN** it is read
- **THEN** `sheet.paper == SheetFrameRef("A4")`, and `sheet.title_block` has `title == "Flat"` and `revision == "A"`

### Requirement: Symbol instances
Each root `symbol` child SHALL become one `SymbolInstance`.
- `lib_id` MUST give `lib_ref`, and `lib_name` MUST give `lib_name` (`""` when absent).
- `at` MUST give `position` and `rotation`; `mirror` MUST give `mirror` (`"x"`, `"y"`, or `""` when absent); `unit` MUST give `unit`; `body_style`, or `convert` in a file that writes that head, MUST give `body_style` (1 when absent).
- `exclude_from_sim`, `in_bom`, `on_board` and `dnp` MUST give the booleans of the same names; an absent child means `False` for `exclude_from_sim` and `dnp`, and `True` for `in_bom` and `on_board`.
- Every `property` child MUST stay an opaque slot, and its name and text MUST be copied into `properties`; the texts of `Reference`, `Value` and `Footprint` MUST also give `ref`, `value` and `footprint`. A name that repeats MUST keep the last text and give the warning `kicad.sch.duplicate-property`.
- `instances` MUST stay an opaque slot, and each `path` of each `project` MUST give one `SymbolUse(project, path, ref, unit)` in `uses`, in file order.
- An instance whose `lib_name`, or whose `lib_id` when it has no `lib_name`, names no embedded symbol MUST give the warning `kicad.sch.symbol-undefined` and MUST still be read.
- The `pin` children and `fields_autoplaced` MUST stay opaque.

#### Scenario: Resistor of the flat sheet
- **WHEN** `flat.kicad_sch` is read
- **THEN** the instance with `ref == "R1"` has `lib_ref == "Mini:Mini_R"`, `unit == 1`, `value == "330"`, `footprint == "Mini:Mini_R_0603"`, `dnp == False`, and one use whose `project` is `flat`, whose `ref` is `R1` and whose `path` starts with `/`

#### Scenario: Flags
- **WHEN** `flat.kicad_sch` is read
- **THEN** `R2` has `dnp == True`, and `R3` has `on_board == False`

#### Scenario: Three units under one reference
- **WHEN** `tests/data/kicad/schematic/units.kicad_sch` is read
- **THEN** it has three instances with `ref == "U2"`, whose `unit` values are 1, 2 and 3

#### Scenario: Rotated and mirrored
- **GIVEN** a copy of `flat.kicad_sch`, built in the test, whose `D1` holds `(at 100 50 90)` and `(mirror y)`
- **WHEN** it is read
- **THEN** `D1` has `rotation == 90_000_000` and `mirror == "y"`

#### Scenario: Undefined symbol
- **GIVEN** a copy of `flat.kicad_sch` whose `lib_symbols` lacks `Mini:Mini_LED`
- **WHEN** it is read with an `issues` list
- **THEN** `D1` is read, and `issues` holds one `kicad.sch.symbol-undefined` warning naming `Mini:Mini_LED`

### Requirement: Labels, no-connect flags and sheet references
The reader SHALL map labels, no-connect flags and sheet references as follows.
- `label`, `global_label` and `hierarchical_label` MUST each give a `NetLabel` whose `kind` is `local`, `global` or `hierarchical`, whose `name` is the text atom, whose `position` and `rotation` come from `at`, and whose `shape` comes from `shape` (`""` when absent). Their `effects`, `fields_autoplaced` and `property` children MUST stay opaque.
- `no_connect` MUST give a `NoConnectFlag` with the `position` of `at`.
- `sheet` MUST give a `SheetRef` with `position` from `at` and `size` from `size`. Its properties MUST stay opaque slots; the texts of `Sheetname` and `Sheetfile` MUST give `name` and `file`. Each `path` of its `instances` MUST give one `SheetUse(project, path, page)` in `uses`. Its `pin`, `stroke` and `fill` children MUST stay opaque.
- A sheet reference without a `Sheetfile` property MUST give the warning `kicad.sch.sheet-file-missing` and `file == ""`.

#### Scenario: Three kinds of label
- **WHEN** `tests/data/kicad/schematic/hier/child.kicad_sch` is read
- **THEN** it holds one label of kind `hierarchical` named `IN` with shape `input`, and `flat.kicad_sch` holds labels of kinds `local` and `global`

#### Scenario: No-connect flags
- **WHEN** `flat.kicad_sch` is read
- **THEN** `sheet.no_connects` holds one flag per `no_connect` child, each at the position its `at` gives, in nm

#### Scenario: Sheet reference
- **WHEN** `tests/data/kicad/schematic/hier/top.kicad_sch` is read
- **THEN** it holds one `SheetRef` with `name == "Child"`, `file == "child.kicad_sch"` and one use whose `page` is `2`, and its sheet pin is an opaque slot of the reference

### Requirement: Embedded symbol definitions
Each `symbol` child of `lib_symbols` SHALL become one `SymbolDef` of `SchematicSheet.lib_symbols`, read by the symbol reader of `kicad-library-read` as it reads a library symbol, in file order.
- The text before the first `:` of the embedded name MUST give `library` and the rest `name`; a name without `:` MUST give an empty library.
- The definitions MUST be read as written: an `extends` child is kept and not resolved.
- The id MUST be `derived_id("sym", "kicad", "sch:<sheet uuid>:<embedded name>")`, so an embedded copy never has the id of the library symbol of the same name.
- Sub-symbols MUST stay opaque slots of their symbol, as in a library.

#### Scenario: Embedded resistor
- **WHEN** `flat.kicad_sch` is read
- **THEN** `sheet.lib_symbols` holds a definition with `library == "Mini"` and `name == "Mini_R"`, with two pins numbered `1` and `2`, and its id differs from the id of `Mini_R` read from `tests/data/libs/Mini.kicad_sym`

#### Scenario: Name without a library
- **GIVEN** a copy of `flat.kicad_sch` whose first embedded symbol is named `Local_R`
- **WHEN** it is read
- **THEN** that definition has `library == ""` and `name == "Local_R"`

### Requirement: Unmodelled schematic content is kept as slots
The reader SHALL record the slot list of the sheet root in `SchematicSheet.ext["kicad"]`, and the slot list of every symbol instance, label, no-connect flag, sheet reference and embedded symbol in its own `ext["kicad"]`, with the encoding of `kicad-slots`.
- Every child of a modelled item that is not modelled MUST be an `Opaque` slot at its position.
- A projected child (a `property`, `instances`) MUST be an `Opaque` slot whose value is also copied into the model.
- After mapping an item, the reader MUST re-emit every modelled child and MUST keep as an `Opaque` projected slot any child that the emitter does not reproduce tree-equal, with the info `kicad.sch.kept-opaque` naming the reason.
- Opaque fragments MUST carry the minimum version that `_libread.Context.min_version` gives for the chains `("kicad_sch", …)` and `("kicad_sch", "lib_symbols", "symbol", …)`, and the file version when the inventory has no row for the fragment's head.

#### Scenario: Property is projected
- **WHEN** `flat.kicad_sch` is read
- **THEN** the `property "Value"` child of `R1` is an `Opaque` slot of that instance, and `R1.value == "330"`

#### Scenario: Older spelling kept
- **GIVEN** a copy of `flat_v9.kicad_sch`, built in the test, whose `R1` holds `(convert 1)` after its `unit` child and whose header is `20231120`
- **WHEN** it is read with an `issues` list
- **THEN** `R1.body_style == 1`, that child is an `Opaque` slot with fragment `(convert 1)`, and `issues` holds one info `kicad.sch.kept-opaque`

#### Scenario: Minimum version from the inventory
- **GIVEN** `flat.kicad_sch`, whose symbols hold a child that an inventory row of kind `kicad_sch` dates after the 9.0 constant
- **WHEN** it is read
- **THEN** the opaque slot of that child carries the row's version, not the file version

### Requirement: Exact numbers on schematics
Lengths SHALL be read with `Atom.to_nm(exact=True)` and angles with `core.units.parse_angle`, and the reader MUST NOT round.
- A length that is not a whole number of nm, or an angle that is not a whole number of µdeg, MUST leave the whole item an `Opaque` slot of the root, with the info `kicad.sch.inexact-length` or `kicad.sch.inexact-angle` naming the locator.
- A symbol angle that is not 0, 90, 180 or 270 degrees, and a `mirror` value other than `x` or `y`, MUST leave the instance an `Opaque` slot of the root, with the info `kicad.sch.kept-opaque`.

#### Scenario: Sub-nanometre position
- **GIVEN** a copy of `flat.kicad_sch` whose `D1` holds `(at 100.0000001 50 0)`
- **WHEN** it is read with an `issues` list
- **THEN** no `SymbolInstance` exists for `D1`, the symbol is an `Opaque` slot of the root at its position, and `issues` holds one info `kicad.sch.inexact-length`

#### Scenario: Odd symbol angle
- **GIVEN** a copy of `flat.kicad_sch` whose `D1` holds `(at 100 50 45)`
- **WHEN** it is read with an `issues` list
- **THEN** the symbol is an `Opaque` slot of the root, and `issues` holds one info `kicad.sch.kept-opaque`

### Requirement: Identifiers of schematic items
Ids of items read from a schematic SHALL follow `design-model`, "Identifiers of schematic entities", with these native ids: the sheet, its root `uuid`; a symbol instance, a label, a no-connect flag and a sheet reference, their own `uuid`.
- An item without a uuid MUST take `content_id(<prefix>, "kicad", <sheet uuid>, <head>, content_hash(<compact text>, <occurrence>))`.
- A uuid already used in the file MUST take the suffix `"<uuid>:<k>"` for its k-th repetition, with the warning `kicad.sch.duplicate-uuid`.
- KiCad uuids MUST be kept in `native_ids["kicad"]`.
- A sheet without a root `uuid` MUST take `derived_id("sch", "kicad", "file:<name>")`.

#### Scenario: Stable ids
- **WHEN** `flat.kicad_sch` is read twice
- **THEN** every id of the two sheets is equal, and no two entities of one sheet share an id

#### Scenario: Repeated uuid
- **GIVEN** a copy of `flat.kicad_sch` whose two no-connect flags carry the same uuid `U`
- **WHEN** it is read with an `issues` list
- **THEN** the flags have the ids `derived_id("ncf", "kicad", "U")` and `derived_id("ncf", "kicad", "U:1")`, and `issues` holds one warning `kicad.sch.duplicate-uuid`

### Requirement: Schematic read issue codes
`sch.ISSUE_CODES` SHALL map every code the schematic reader and the sheet tree emit to its severity, and SHALL be exactly this table. Every `kicad.sch.` literal under `src/fenolite/backends/kicad/sch.py` MUST be a key of it.

| code | severity | when |
|---|---|---|
| `kicad.sch.kept-opaque` | info | a modelled child or item is kept as an opaque slot |
| `kicad.sch.inexact-length` | info | a length is not a whole number of nm |
| `kicad.sch.inexact-angle` | info | an angle is not a whole number of µdeg |
| `kicad.sch.duplicate-property` | warning | a property name repeats in one symbol |
| `kicad.sch.duplicate-uuid` | warning | a uuid repeats in one file |
| `kicad.sch.symbol-undefined` | warning | an instance names no embedded symbol |
| `kicad.sch.sheet-file-missing` | warning | a sheet reference has no file property |
| `kicad.sch.sheet-missing` | warning | a referenced sheet file does not exist |
| `kicad.sch.sheet-outside` | info | a referenced sheet file lies outside the root file's folder tree |
| `kicad.sch.sheet-cycle` | error | a sheet references a file on its own path from the root |

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_sch_read.py -k codes` collects every `kicad.sch.` literal of `sch.py`
- **THEN** each is a key of `sch.ISSUE_CODES` with the severity of this table, and the table has no other key

### Requirement: Same-version rebuild of schematics
`sch.rebuild_schematic(sheet) -> Node` SHALL rebuild the tree of a sheet read by `read_schematic`, at the sheet's own format version, by walking its slot lists: modelled fields are emitted from the model, opaque fragments verbatim.
- An unchanged sheet MUST give a tree that `tree_equal` accepts against the parsed source.
- A changed modelled field MUST be emitted from the model at the position of its slot.
- A projection that differs from its fragment (a property text, a use, a sheet name or file) MUST raise `ValueError` naming the entity's id and the field.
- An entity added to or removed from a collection of a read sheet MUST raise `ValueError` naming the collection; created sheets are written by another change.
- The order of a collection MUST NOT matter: slots decide the position of each item.

#### Scenario: Unchanged sheet
- **WHEN** each fixture under `tests/data/kicad/schematic/` is read, rebuilt and compared
- **THEN** every rebuilt tree is tree-equal to `parse` of its file

#### Scenario: Moved symbol
- **GIVEN** `flat.kicad_sch` read, and `R1.position` moved by 2.54 mm in X
- **WHEN** the sheet is rebuilt
- **THEN** the `at` child of `R1` holds the new X, and every other node is tree-equal to the source

#### Scenario: Edited projection refused
- **GIVEN** `flat.kicad_sch` read, and `R1.value` changed to `470`
- **WHEN** the sheet is rebuilt
- **THEN** `ValueError` is raised naming the id of `R1` and `value`

### Requirement: Schematic round-trip verdict
`sch.roundtrip_schematic(text, *, file="") -> RoundTrip` SHALL return the `RoundTrip` of `backend-protocol`, "Validation operation", with level `RT1`, for one schematic text.
- `tree_equal` MUST say that `rebuild_schematic(read_schematic(text))` equals `parse(text)`.
- `model_equal` MUST say that reading `dumps` of the rebuilt tree gives a sheet equal to the first reading.
- `opaque_equal` MUST say that both readings have equal `opaque_digests`, and `opaque_count` MUST be `sch.opaque_count` of the first reading.
- `difference` MUST be the locator of the first tree difference, `model` or `opaque`, and `""` when it passed.
- A read error MUST propagate; the function MUST NOT return a verdict for a file it cannot read.
- `sch.opaque_count(sheet)` MUST count the `Opaque` slots across the `ext["kicad"]` bags of the sheet and of every entity in it, embedded symbols included, and `sch.opaque_digests(sheet)` MUST return a `collections.Counter` of the SHA-256 hex digests of their fragments.

#### Scenario: Fixture passes
- **WHEN** `roundtrip_schematic` runs on the text of `flat.kicad_sch`
- **THEN** `passed`, `tree_equal`, `model_equal` and `opaque_equal` are true, and `opaque_count` equals `sch.opaque_count(read_schematic(text))`

#### Scenario: Bus content does not prevent a round trip
- **WHEN** `roundtrip_schematic` runs on the text of `tests/data/kicad/schematic/bus.kicad_sch`
- **THEN** it passes, and the `bus` and `bus_entry` children count in `opaque_count`

#### Scenario: Count follows the slots
- **GIVEN** `flat.kicad_sch`, and the same text with one more `wire` at the end of the root
- **WHEN** both are read
- **THEN** the second `opaque_count` is the first plus one

### Requirement: Sheet tree of a project
`sch.sheet_files(root_file) -> SheetTree` SHALL list the schematic files of a hierarchy, reading the root and every file that a sheet reference names, relative to the folder of the referencing file, breadth first. `SheetTree` holds `files` (paths relative to the root file's folder, in first-visit order, the root first), `references` (each file mapped to the number of sheet references that name it; 0 for the root) and `issues`.
- A file named by several references MUST be read once.
- A reference to a file that is on the path from the root to the referencing sheet MUST give `kicad.sch.sheet-cycle` and MUST NOT be followed.
- A file that does not exist MUST give `kicad.sch.sheet-missing` and MUST be left out of `files`.
- A file outside the root file's folder tree MUST be listed in `files`, MUST NOT be read, and MUST give `kicad.sch.sheet-outside`.
- A referenced file that cannot be read MUST propagate its error with the file named.

#### Scenario: Two-sheet hierarchy
- **WHEN** `sheet_files(Path("tests/data/kicad/schematic/hier/top.kicad_sch"))` is called
- **THEN** `files` is `("top.kicad_sch", "child.kicad_sch")` and `references["child.kicad_sch"] == 1`

#### Scenario: Sheet used twice
- **WHEN** `sheet_files` runs on `tests/data/kicad/schematic/multi/top.kicad_sch`
- **THEN** `files` holds `cell.kicad_sch` once, and `references["cell.kicad_sch"] == 2`

#### Scenario: Cycle and missing file
- **GIVEN** in `tmp_path`, a root that references `a.kicad_sch`, which references the root, and a second root that references `gone.kicad_sch`
- **WHEN** `sheet_files` runs on each
- **THEN** the first gives one `kicad.sch.sheet-cycle` error and `files` of two entries, and the second gives one `kicad.sch.sheet-missing` warning and `files` of one entry

### Requirement: Components of a project
`sch.components(sheets, *, project, on_board_only=False) -> tuple[SchComponent, ...]` SHALL list one `SchComponent(ref, value, footprint)` per reference of the uses whose `project` equals `project`, across the given sheets, sorted by reference.
- A reference that starts with `#` MUST be left out.
- Several instances with one reference (the units of one symbol) MUST count once, with the value and footprint of the instance with the lowest `unit`.
- With `on_board_only=True`, instances with `on_board == False` MUST be left out.
- The function MUST NOT read a file and MUST NOT derive nets.

#### Scenario: Flat sheet
- **WHEN** `sch.components((read_schematic(flat),), project="flat")` is called
- **THEN** it returns `D1`, `R1`, `R2`, `R3` and `U1` in this order, without `#PWR01`, and `R1` has value `330` and footprint `Mini:Mini_R_0603`

#### Scenario: Units count once
- **WHEN** it is called on the sheet of `units.kicad_sch` with `project="units"`
- **THEN** it returns exactly one component, `U2`

#### Scenario: Symbols left off the board
- **WHEN** it is called on the flat sheet with `on_board_only=True`
- **THEN** `R3` is not in the result

### Requirement: Components of a hierarchy
`sch.hierarchy_components(root_file, *, on_board_only=False) -> tuple[SchComponent, ...]` SHALL list one `SchComponent` per reference of the hierarchy under `root_file`, resolved by instance path as `kicad-cli` resolves it, sorted by reference.
- The root sheet has the instance path `/<root uuid>`; a sheet reference with uuid `U` gives the file it names the path `<parent path>/U`, once per reference, so a file that is referenced twice is counted twice.
- A symbol MUST take the reference and unit of its use whose `path` is the path of its sheet: the use of the project named after the root file's stem when several projects hold that path, else the first one in file order. A symbol with no use for that path MUST take the text of its `Reference` property and its own `unit`.
- The rules of "Components of a project" apply to the result: references that start with `#` are left out, the lowest unit gives value and footprint, and `on_board_only=True` leaves out instances with `on_board == False`.
- Property texts MUST be given as written: a text variable is not resolved, and a lone `~` is not turned into an empty text.
- Files outside the root file's folder tree, missing files and references that close a cycle MUST NOT be followed; `sheet_files` reports them.
- The function MUST NOT derive nets.

#### Scenario: Authored hierarchies
- **WHEN** it is called on `hier/top.kicad_sch` and on `multi/top.kicad_sch`
- **THEN** each result is `R1` and `R2`, and for the flat sheet the result equals `sch.components((sheet,), project="flat")`

#### Scenario: Instance data filed under another project
- **GIVEN** copies of `multi/top.kicad_sch` and `multi/cell.kicad_sch` whose `instances` name the project `another`
- **WHEN** it is called on the copy of the root
- **THEN** it returns `R1` and `R2`, and `sch.components(…, project="top")` returns nothing

#### Scenario: Symbol without a use
- **GIVEN** a copy of `flat.kicad_sch` whose `R1` has no `instances` child
- **WHEN** it is called
- **THEN** `R1` is in the result, named by its `Reference` property

### Requirement: Schematic reading evidence
`sch.EVIDENCE` SHALL name `H-K-SCH-READ` and the components hypothesis that holds in `docs/hypotheses.md` (`H-K-SCH-COMPONENTS`, or its successor `H-K-SCH-COMPONENTS-2` when the first is refuted), and its level SHALL be the lowest level of the rows it names: `INFERRED` until both hold, and `CORPUS-VERIFIED` when the reading holds over two corpus origins and the components hypothesis is `KICAD-VERIFIED (9.0.x, 10.0.x)`. A round-trip claim over the corpus MUST carry `CORPUS-VERIFIED` only while `H-K-SCH-RT1` holds on two origins.

#### Scenario: Level follows the register
- **WHEN** `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py` runs
- **THEN** it passes, and the level of `sch.EVIDENCE` is not above the lowest level of the rows it names

### Requirement: Schematic format facts are documented
`docs/formats/kicad/schematic.md` SHALL hold the schematic facts in a table with the header `| fact | source | label | hypothesis |`. It covers the root children per format version, the modelled, projected and opaque content per head, the instance paths and uses, the sheet properties, the version constants, and the two load checks. Every row MUST cite a source id, and every row below `KICAD-VERIFIED` or `CORPUS-VERIFIED` MUST name a hypothesis. `docs/evidence/kicad-schematic.md` SHALL hold the census and the round-trip results as ids and counts only.

#### Scenario: Fact table checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** it passes with `schematic.md` present

#### Scenario: No demo content committed
- **WHEN** `uv run pytest tests/residue tests/unit/test_repo_layout.py` runs
- **THEN** it passes, and `docs/evidence/kicad-schematic.md` holds row ids, counts and head names only

### Requirement: Authored schematic fixtures
`tests/data/kicad/schematic/` SHALL hold authored CC0 schematics written for the Mini library, each declared `origin = "authored"` in `tests/data/MANIFEST.toml`: `flat.kicad_sch` (`20260306`) and `flat_v9.kicad_sch` (`20250114`), `units.kicad_sch` and `units_v9.kicad_sch`, `hier/top.kicad_sch` with `hier/child.kicad_sch` and their `20250114` copies under `hier_v9/`, `multi/top.kicad_sch` with `multi/cell.kicad_sch`, and `bus.kicad_sch`.
- The flat sheets MUST hold a resistor, an LED, the 32-pin IC, the power symbol, global labels, one local label on a wire with a junction, no-connect flags, one text, one symbol with `(dnp yes)` and one with `(on_board no)`.
- `Mini_DualGate` MUST be authored for `tests/data/libs/Mini_v9.kicad_sym`, so the units sheet exists in both formats.
- The `20250114` fixtures MUST NOT hold a `body_style` child in a symbol instance: `kicad-cli` 9.0.9 refuses it there and reads `convert` (S-0020).
- Their generator MUST NOT be `eeschema` (S-0367).
- `kicad-cli` of the file's major MUST load each of them (`kicad-oracle`, "Schematic components agree with kicad-cli").

#### Scenario: Fixtures declared
- **WHEN** `uv run pytest tests/unit/test_repo_layout.py tests/residue` runs
- **THEN** it passes, and every file under `tests/data/kicad/schematic/` has a row in `tests/data/MANIFEST.toml`

#### Scenario: Generator of the fixtures
- **WHEN** the `generator` atom of each fixture is read
- **THEN** none is `eeschema`

### Requirement: Schematic writing per target
`fenolite.backends.kicad.sch.write_schematic(sheet, *, target=DEFAULT_TARGET, allow_lossy=False) -> WriteResult` SHALL return the text of a `.kicad_sch` file for KiCad `target`.0 from a created `SchematicSheet`, and SHALL write no file.
- The header MUST be `(version FORMAT_VERSIONS[FileKind.SCHEMATIC][target])`, `(generator "fenolite")` and `(generator_version "<target>.0")`, followed by the sheet's `uuid` and `paper`, the `title_block` when the sheet has one, and `lib_symbols`.
- The root items MUST follow in the order no-connect flags, wires, labels, symbol instances, sheet references, each kind in the order of its collection, then `sheet_instances` with the sheet's pages when the sheet has pages. A child sheet, which has none, MUST have no `sheet_instances`.
- A wire MUST hold `pts` with its two points, `stroke` with width 0 and type `default`, and `uuid`. A sheet reference MUST hold `at`, `size`, `exclude_from_sim`, `in_bom`, `on_board`, `dnp`, `stroke` (width 0, type `solid`), `fill` (colour `0 0 0 0.0`), `uuid`, the properties `Sheetname` (above the box) and `Sheetfile` (below it), and `instances` with one `path` per use and its `page`, in this form on both targets (`H-K-SCH-HIER-FILE`); the two properties take the target's property form.
- A symbol instance MUST hold `lib_id`, `at`, `unit`, `exclude_from_sim`, `in_bom`, `on_board`, `dnp`, `uuid`, one `property` per entry of `properties` (Reference, Value, Footprint, Datasheet and Description first, the others in sorted order), one `pin` with a uuid per pin of its unit, and `instances`.
- **Target 10** MUST also write `body_style` and `in_pos_files` on a symbol, `hide`, `show_name` and `do_not_autoplace` as children of each property, and an `Intersheetrefs` property on each global label. **Target 9** MUST write `hide` inside `effects`, no `body_style`, no `in_pos_files`, and `(embedded_fonts no)` at the end of the root.
- `versions.check_emittable(root, FileKind.SCHEMATIC, target)` MUST run on the final tree. A token the target does not read MUST raise `LossyWriteError` (`FEN-7001`); with `allow_lossy=True` the node of that token MUST be removed with one `kicad.sch.dropped-too-new` warning. Only the token's own node is removed: the slots of a symbol are whole properties and sub-symbols, and dropping one of those would remove the symbol's body.
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
- **THEN** the first call raises `LossyWriteError` naming the token, and the second returns a text without it and one `kicad.sch.dropped-too-new` warning per removed token

#### Scenario: Read sheet refused
- **GIVEN** `tests/data/kicad/schematic/flat.kicad_sch` read with `read_schematic`
- **WHEN** it is passed to `write_schematic`
- **THEN** `ValueError` is raised naming `rebuild_schematic`

#### Scenario: Child sheet form
- **GIVEN** a created child sheet with one instance of `Mini:Mini_R`, one wire, one sheet reference and no pages
- **WHEN** it is written for targets 9 and 10 and each text is parsed
- **THEN** the root holds one `wire` with two points, one `sheet` with the properties `Sheetname` and `Sheetfile`, and no `sheet_instances`, and `read_schematic` of the text gives the sheet reference with its name, file, position, size and use

### Requirement: Generated sheet content
`fenolite.backends.kicad.schgen.generate_schematic(design, parts, *, name, target, placements=None, vendor="all", allow_lossy=False, layout="readable") -> GeneratedSchematic` SHALL build the sheets of a design from its circuit, and SHALL return `sheet` (the root `SchematicSheet`), `children` (each child sheet keyed by its path from the root file's folder, in page order; empty for a design without module sheets, "Hierarchical sheets of a design"), `libraries` (per nickname, the symbols of its project library), `rows` (the rows of `sym-lib-table`), `pad_nets` (component id and pad number mapped to the net name of an unconnected pin), `paths` (component id mapped to the path of its symbol), `issues`, `unvendored` (the lib ids that `vendor="project"` leaves without a project library, which the build reports) `power_flags` (their number) and `satellites` (the number of snapped satellites, "Readable sheet layout"). `layout` MUST be `"readable"` or `"grid"`; any other value raises `ValueError`. `parts` are the resolved parts of the build: each gives its component, its component path, its flattened symbol, the symbols that symbol extends as their library holds them, its footprint, and the origin of the row that resolved the symbol.
- **Symbols.** Each component with a resolved symbol MUST give one `SymbolInstance` per unit of that symbol, on the sheet of its module ("Hierarchical sheets of a design"), with body style 1, `lib_ref` naming the embedded definition, `ref`, `value`, `footprint` = `Component.lib_footprint_ref`, and `properties` = the component's `properties` plus `Footprint`. `dnp` MUST be `Component.dnp`; `in_bom` MUST be false when the component's footprint has the attribute `exclude_from_bom`; `on_board` MUST be true. Each instance MUST have one `SymbolUse(<name>, <use path of its sheet>, ref, unit)`: `/<root uuid>` on the root, `/<root uuid>/<kicad uuids of the sheet references from the top down>` on a child sheet. A component without a resolved symbol MUST give no instance.
- **Labels.** Each pin that a net lists and that no snap wire joins MUST give one `NetLabel("global", netnames.stored_name(<net name>), <the pin's connection point>, shape="passive")`, turned away from the symbol body. Each pair of pins that a snap wire joins MUST give one such label, at the satellite's near pin, as "Readable sheet layout" places it. The sheets MUST hold no junction, no label of another kind and no wire other than snap wires.
- **No-connect flags.** Each pin listed by `Circuit.no_connects` MUST give one `NoConnectFlag` at its connection point. A pin on no net without a mark MUST give neither a label nor a flag.
- **Pins and pads.** Net members and marks are keyed by symbol pin number; with a `pin_pad_map`, the label or flag MUST be placed at the pin whose embedded number is the mapped pad number ("Embedded symbols of a generated sheet").
- **Power flags.** Each net that is a member of an `Interface` with `kind == "power"`, and that no pin of type `power_out` of a component with `dnp == False` is on, MUST give one instance of `fenolite:PWR_FLAG` on the root sheet, with the reference `#FLG<nn>` (numbered from 01 in the order of net names), `in_bom` and `on_board` false, and one global label of the net at its pin.
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
`schlayout.layout_units(units, *, placements=None, flags=(), clusters=(), refs=(), sheet="") -> SheetLayout` SHALL give every unit, cluster, sheet reference and power flag of one sheet a position on its page, without overlap, in a fixed order, and SHALL choose the paper of that sheet.
- **Order.** Units MUST be sorted by top-level module (units outside a module first), then by the natural order of the component path, then by unit number. A cluster ("Readable sheet layout") MUST take the place of its anchor, and its snapped satellites MUST leave the order. Sheet references come after the units, in the natural order of their module paths, and power flags last, in the order of their nets.
- **Units.** A unit is given as `UnitBox(key, pins, body, symbol, text=0)`: `key` is the component path, with `#<unit>` for a unit above 1; `pins` are `UnitPin(number, at, angle, label)` in the library frame, `label` being the length of the label text at that pin (0 without one); `body` is the box of what the unit draws; `symbol` names the library symbol in messages; `text` is the length of the longer of its Reference and Value. A sheet reference is given as `RefBox(path, name, file)`: the module path, the sheet name and the `Sheetfile` text; its layout key is `schlayout.ref_key(path)`, and its origin is the top-left corner of its box. `SheetLayout` holds `paper`, `origins` (key to `SymbolPlacement`), `cells` and `issues`. Rows are packed by `geometry.shelf.shelf_pack`, which the Altium sheet layout uses too.
- **Cells.** A unit's cell MUST hold its body and pin connection points, grown on each side by `CHAR_ROOM` (1 524 000 nm) per character of the longest label on that side plus `LABEL_ROOM` (5 080 000 nm), by `CELL_MARGIN` (5 080 000 nm), and by `TEXT_ROOM` (7 620 000 nm) above for Reference and Value. Cell sizes MUST be rounded up to `ORIGIN_STEP` (2 540 000 nm). A cluster's cell MUST hold the cell of its anchor and, each grown by `CELL_MARGIN`, the boxes of its satellites, its wires and the rooms of its labels. A sheet reference's cell MUST hold its box and the rooms of its two properties (`REF_TEXT`, 2 540 000 nm, above and below, and `CHAR_ROOM` per character of the file text), grown by `CELL_MARGIN`.
- **Flow.** Cells MUST fill rows from the left inside `PAGE_MARGIN` (12 700 000 nm), above a band of `TITLE_BAND` (40 640 000 nm) at the bottom. The first unit of a module MUST start a new row. Sheet references MUST take rows of their own after the units, and power flags a last row.
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

#### Scenario: Cluster takes the anchor's place
- **GIVEN** the units `R1`, `U1` and `U2`, and a cluster of `U1` with `R1` snapped to its left
- **WHEN** they are laid out
- **THEN** the order of the cells is `U1`, `U2`, the origin of `R1` is the origin of `U1` plus the cluster's offset, and the cell of `U1` holds the box of `R1`

### Requirement: Embedded symbols of a generated sheet
`fenolite.backends.kicad.symembed.embed_symbol(definition, *, parents=(), target, pin_numbers=None, allow_lossy=False, issues=None) -> EmbeddedSymbol` SHALL return the definition that a generated sheet embeds for one resolved symbol, as a node built from the definition's slots, and the generator SHALL embed one definition per distinct result. `definition` is the resolved symbol, which holds its own children as slots, and `parents` are the symbols it extends as their library holds them, the nearest first (`LibraryResolver.symbol_chain`). `EmbeddedSymbol` holds `lib_id`, `nickname`, `name`, `node`, `definition` (the node as the schematic reader models it, which `write_schematic` writes back) and `authored`.
- **Flattened.** A derived symbol MUST take the sub-symbols of its root parent, renamed from `<parent>_<unit>_<style>` to `<name>_<unit>_<style>`, and its own properties over the parent's; the embedded node MUST hold no `extends`.
- **Pad numbers.** With `pin_numbers` (a `pin_pad_map`), the `number` of each mapped pin MUST be replaced by its pad number, and the name MUST be `symembed.variant_name(name, pin_pad_map)`: `<name>_<first 8 hex digits of the SHA-256 of the sorted pairs>`. Two components with equal maps share one variant.
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
| `build.schematic-too-large` | error | the units of one sheet do not fit an A0 page |
| `build.symbol-overlap` | warning | two cells overlap after a placement |
| `build.symbol-short` | error | two connection points of different units coincide |
| `build.symbol-placement-unknown` | warning | the placements file names no unit of the design |
| `build.symbol-placement-invalid` | error | a placement is off the grid, has an unknown key or an unproved rotation |
| `build.reserved-library` | error | a design names a library `fenolite` |
| `build.schematic-replaced` | warning | an edited schematic file, the root or a child sheet, is replaced |
| `build.sheet-file-collision` | error | two modules give one child sheet file |
| `build.sheet-stale` | warning | a child sheet of the last build is no longer a sheet of the design, and is left in place |

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_schgen.py -k codes` collects the code literals of `schgen.py`, `schlayout.py`, `symembed.py` and `lens/schplacements.py`
- **THEN** each is a key of `schgen.ISSUE_CODES` or of `sch.WRITE_ISSUE_CODES`, with the severity of its table

#### Scenario: Codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** every key of `schgen.ISSUE_CODES` appears in `docs/cli-contract.md`

### Requirement: Generated schematics are documented
`docs/schematic.md` SHALL say what `build` writes for the schematic and why: one symbol per unit, global labels instead of wires, no-connect flags from marks, power flags from power interfaces, shown power pins, pad numbers on mapped symbols, the project libraries, the names of unconnected pads, the stored form of slash nets, the placements file with an example, what is replaced on a rebuild, one sheet per module with the file names under `sheets/`, satellites and their snap wires, `--schematic-layout`, and the limits (each sheet up to A0, only snap wires, no hierarchical labels and no sheet pins, no sheet used twice, no buses). `docs/formats/kicad/schematic.md` SHALL gain the fact rows of the written form per target and of every probe, each with a source, a label and a hypothesis.

#### Scenario: Guide present and checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_repo_layout.py tests/residue` runs
- **THEN** it passes with `docs/schematic.md` present and linked from `README.md` and `docs/dsl.md`

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
`fenolite.backends.kicad.sch_netlist.own_netlist(sheet, *, project, children={}) -> KicadNetlist` SHALL return the netlist of a root sheet and of the child sheets it names (`children`: each child keyed by its path from the root file's folder), inside the grammar of "Netlist grammar check", read from the sheets alone, as KiCad reads them.
- **Nodes.** Each pin of each symbol instance of every sheet whose reference does not start with `#` MUST be one node, at `schlayout.pin_point` of the instance, with the pin number of its embedded definition and the pin's electrical type as `pintype`, followed by `+no_connect` when a no-connect flag lies on its point.
- **Wires.** The wires of a sheet are its `wires` and, for a sheet read from a file, the opaque root `wire` slots that `sch.opaque_wires(sheet)` gives as point lists; both are read alike, so a built project is read back from its files.
- **Named nets.** Within one sheet, a pin's point, a wire end and a label's point MUST be joined when they coincide, and the two ends of a wire MUST be joined to each other (`H-K-SCH-WIRE-END`). The nodes of every group that carries a global label of one text, in any sheet, MUST form one net named by `netnames.stored_name` of that text, which is the text itself for a label that `build` wrote (`H-K-SCH-HIER-FILE`).
- **Unconnected nets.** A node whose group carries no label and no wire MUST form a net of its own, named by `netnames.unconnected_name` with the instance's reference, unit and unit count, the pin's name and its number, flagged or not.
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
| `shared-point` | pins of two instances at one point, or several pins of one instance at a point that carries no label |
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

### Requirement: Readable sheet layout
With `layout="readable"`, `schlayout.snap_satellites(units, nets, *, placements=None) -> tuple[Cluster, ...]` SHALL place, in one sheet, each 2-pin part that it can beside an IC pin of its net, joined to it by one straight wire, and SHALL return one `Cluster(anchor, satellites, wires, labels, boxes)` per anchor that took at least one satellite, in anchor order. `nets` maps (unit key, pin number) to the label text of that pin. Every position of a cluster is relative to the origin of its anchor: `satellites` holds each satellite's key and `SymbolPlacement`, `wires` one `SnapWire(satellite, anchor_pin, near_pin, start, end)` per satellite, `labels` one `SnapLabel(satellite, pin, at, angle)` per satellite, and `boxes` what the satellites, their wires and their labels cover.
- **Anchors and satellites.** An anchor MUST be a unit with three pins or more. A satellite MUST be a component with one unit and exactly two pins on different nets, whose connection points lie on one horizontal or vertical axis, with opposite pin angles. Keys that start with `#` MUST be neither.
- **Order.** Satellites MUST be tried in the natural order of their component paths. For each, the candidate anchor pins MUST be the pins of anchors that lie on the net of one of its pins and hold no satellite yet, in anchor order (the order of "Deterministic sheet layout") and then in natural pin-number order; the first candidate for which every condition below holds MUST be taken, and that pin of the satellite is its near pin.
- **Conditions.** The rotation that makes the near pin face the anchor pin, with the body extending away from the anchor, MUST be in `schlayout.PROVED_FRAMES` with no mirror. The satellite's origin MUST put the near pin's connection point at `SNAP_REACH` (5 080 000 nm) from the anchor pin's, along the anchor pin's outward direction, and MUST be a multiple of `GRID` in both axes relative to the anchor's origin. The satellite's boxes (its body with its pins, the room of Reference and Value where the writer puts them, the room of the far pin's label and the room of the pair's label) and its wire MUST overlap neither the anchor's body, nor the room of Reference and Value of the anchor, nor the room of the label of another connected pin of the anchor, nor a box or wire of a satellite already snapped; the room of the pair's label MUST overlap neither the satellite's own body nor its own text room; and no pin point of the anchor or of a snapped satellite, other than the two ends, MUST lie on the wire. A label's room is `CHAR_ROOM` per character plus `LABEL_ROOM` long and `GRID` wide on each side of its axis. Boxes that only touch do not overlap.
- **Wire and labels.** A snapped satellite MUST give one wire from the anchor pin's connection point to the near pin's. The pair MUST carry one global label of its net at the near pin, turned perpendicular to the wire, towards the side of the anchor pin away from the centre line of the anchor's body (upwards or to the left for a pin on that line); the far pin keeps the label that "Generated sheet content" gives it. An anchor pin MUST take at most one satellite.
- **Placements.** A satellite named by `placements` MUST be snapped only when its anchor is named too and its entry equals the origin, rotation and mirror that the snap gives: that is what `sync` writes for a built sheet, so `sync` followed by a build keeps every wire. An anchor named by `placements` MUST be snapped around at its given origin, rotation and mirror, and then the cells of the other placed units of the sheet that are no satellite candidates MUST NOT be overlapped either. A satellite candidate that is placed elsewhere is not snapped.
- **Texts.** On a sheet that `build` writes without a placements file, no Reference or Value text of a symbol MUST overlap a label, the Reference or Value of any symbol, the body or pins of a symbol, or the end of a wire. KiCad draws a field turned with its symbol and may flip the side of a justified text, so the writer MUST write the Reference and the Value of a turned or mirrored instance centred on their points, at the field angle that draws them level (90 degrees in an instance turned by 90 or 270 degrees), in the room `schlayout.turned_text_room(bounds, ends, origin, upwards, length, across=None)`: two lines of `ORIGIN_STEP` (2 540 000 nm), `CHAR_ROOM` long per character of the longer text, the Reference in the upper line. For an instance with a pin that leaves it upwards the room MUST lie to the right of the instance, `ORIGIN_STEP` from it, around the height of its origin. Otherwise it MUST lie above the instance, from its left edge, at least `GRID` above its pins; when a label at one of its pins points up or down, across its axis (the label of a wired pair), the room MUST lie on that label's side of the instance (above for a label that points up, below for one that points down), MUST start `ORIGIN_STEP` from the label's axis and MUST extend towards the other pin. `schlayout.text_box(unit, rotation, mirror, across=None)` MUST return that room for such a unit, and it is the text room of the conditions above. The Reference and the Value of an instance that is neither turned nor mirrored MUST stay where c0061 writes them, left-justified at angle 0.
- Satellites that are not snapped flow as units of their own, with the labels of "Generated sheet content".
- The function MUST be pure, MUST use integer nm, and two calls with equal arguments MUST return equal results.

#### Scenario: Resistor on an IC pin
- **GIVEN** a design with `U1` of `Mini:Mini_QFP32_IC` and `R1` of `Mini:Mini_R`, `R1` pin 1 on the net of `U1`'s first pin on its left side and `R1` pin 2 on `GND`, the pins beside that pin of `U1` on no net
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
- **GIVEN** a `schematic-placements.toml` that places `U1`, `R1` at its snapped origin and rotation, and `R2` at any other origin
- **WHEN** the sheet is generated
- **THEN** `R1` keeps its wire, and `R2` has no wire and two labels

#### Scenario: Deterministic
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_schlayout_snap.py -k deterministic` generates the sheets of the 25 designs of `tests/_gendesigns.py` with `modules=True` twice
- **THEN** the written texts are byte-identical

#### Scenario: Texts of a turned satellite
- **GIVEN** the sheets that `build` writes for the blink, for the lens acceptance design and for the 25 designs of `tests/_gendesigns.py` of each seed, where `R1` of the blink lies turned on its side to the left of pin 1 of `U1` and the label `LED_DRV` of the pair points up at its near pin
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_schgen_text_overlap.py` estimates from each written file the box of every Reference, Value and label (one font size per character, 2 mm per line, the frame of a label added, and both sides of the point for a justified text of a turned symbol), of every symbol's body and pins, and the ends of every wire
- **THEN** no Reference or Value box overlaps another box or holds a wire end, and `R1` and `330` are written centred at 90 degrees above the resistor, to the left of the room of `LED_DRV` and above the room of `LED_A`

### Requirement: Hierarchical sheets of a design
With `layout="readable"` (the default), `generate_schematic` SHALL give each module that holds a part, directly or below it, a child sheet, and SHALL return the root sheet as `sheet` and the child sheets as `children`; a design without such a module gets one sheet. With `layout="grid"`, it SHALL return the one sheet that c0061's generator builds, without satellites, and empty `children`.
- **Content.** The root MUST hold the units of the components outside every module, one sheet reference per top-level module with a part, and the power flags. A child sheet MUST hold the units of its module's own components and one sheet reference per sub-module with a part. The module of a component is its path without the last segment.
- **Files.** A child sheet's path MUST be `schgen.sheet_file(<module path>)`: `sheets/<module path with "/" replaced by ".">.kicad_sch`. The root's sheet references MUST name `sheets/<file>`, and a child's sheet references MUST name `<file>`, from the child's own folder (`H-K-SCH-HIER-FILE`). Two modules whose files are equal, or differ only in letter case, MUST give `build.sheet-file-collision` (error) naming both, and no child sheet.
- **Sheet references.** Each MUST be a `SheetRef` named by the module's last path segment, with no pin, a height of `REF_HEIGHT` (12 700 000 nm) and the width `schlayout.sheet_ref_size(name)`: the larger of 25 400 000 nm and `CHAR_ROOM` × (length of the name + 2), rounded up to `ORIGIN_STEP`. Its one `SheetUse` MUST give the path of the sheet that holds it and the child's page.
- **Pages.** The root's page MUST be `1`; the children MUST be numbered from `2` in depth-first order of their module paths, in natural order, and `children` MUST be in that order.
- **Paths.** A symbol of a child sheet MUST have the use path `/<root uuid>/<kicad uuids of the sheet references from the top down>`, and its entry in `paths` the footprint path `/<those sheet uuids>/<kicad uuid of the instance with the lowest unit>` (`H-K-SCH-HIER-PATH`).
- **Nets.** No hierarchical label and no sheet pin MUST be written; every net crosses sheets through its global labels, so net names stay those of the circuit.
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

#### Scenario: File collision
- **GIVEN** a top-level module `a.b` and a module `b` inside a module `a`, both with parts
- **WHEN** the sheets are generated
- **THEN** the issues hold `build.sheet-file-collision` naming `a.b` and `a/b`, and `children` is empty

