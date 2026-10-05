## ADDED Requirements

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
- **THEN** its `wire` and `junction` children are `Opaque` slots at their source positions, and the sheet has no field that lists wires

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
