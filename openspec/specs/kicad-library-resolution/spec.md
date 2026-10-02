# kicad-library-resolution Specification

## Purpose
Resolve KiCad library identifiers (`NICKNAME:ENTRY`) to library files the way KiCad does for the common configurations: project, global, template and nested library tables, path variables with the versioned fallback, and official library sources from variables or a local install. Every failure is a typed issue of a closed set. Facts, Fenolite choices and sources: `docs/formats/kicad/libraries.md`.
## Requirements
### Requirement: Library issue codes
Library reading and resolution SHALL report problems only with the codes of this closed set. Every error MUST be raised as `LibraryError` (defined in `fenolite.backends.kicad.liberrors`, re-exported by `backends.kicad.libs`) whose `issue` carries the code. Warnings and infos MUST be appended to an issue list and never raised. `LibraryError.cli_code` MUST be `FEN-3001`.

| code | severity | when |
|---|---|---|
| `kicad.lib.invalid-id` | error | no colon, empty nickname or entry, or a second colon |
| `kicad.lib.unknown-nickname` | error | nickname in no effective row |
| `kicad.lib.disabled` | error | nickname only in disabled rows |
| `kicad.lib.unsupported-type` | error | row type other than `KiCad` and `Table` |
| `kicad.lib.unresolved-variable` | error | `${NAME}` without a value in a row that is needed |
| `kicad.lib.missing-library` | error | expanded library path absent or of the wrong kind |
| `kicad.lib.missing-entry` | error | item absent from an existing library |
| `kicad.lib.missing-parent` | error | `extends` names an absent symbol |
| `kicad.lib.extends-cycle` | error | `extends` chain loops |
| `kicad.lib.duplicate-nickname` | warning | second row with the same nickname in one table |
| `kicad.lib.table-cycle` | warning | nested table already being expanded |
| `kicad.lib.missing-table` | warning | nested table file absent |
| `kicad.lib.name-mismatch` | warning | footprint header name differs from the file stem |
| `kicad.lib.missing-3d-model` | warning | model file absent, or model path with an unresolved variable |
| `kicad.lib.kept-opaque` | info | partly or not representable child kept opaque |
| `kicad.lib.nested-table-target` | info | nested rows used with target major 9 |

#### Scenario: Closed set enforced
- **GIVEN** the module `fenolite.backends.kicad.liberrors`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_resolver.py -k closed_set` collects every issue code produced by the unit tests of this capability and of `kicad-library-read`
- **THEN** each code other than `kicad.version.*` is a key of `ISSUE_CODES` with the severity of this table

#### Scenario: No import cycle
- **WHEN** `fenolite.backends.kicad.sym` is imported in a fresh interpreter before `fenolite.backends.kicad.libs`
- **THEN** the import succeeds, and `libs.LibraryError is liberrors.LibraryError`

### Requirement: Library identifiers
`fenolite.backends.kicad.libs.split_lib_id(lib_id)` SHALL split a library identifier at its colon into `(nickname, entry)`. It MUST raise `LibraryError` with issue code `kicad.lib.invalid-id` when the identifier has no colon, an empty nickname, an empty entry, or more than one colon (S-0001, S-0046).

#### Scenario: Qualified identifier
- **GIVEN** the identifier `"Resistor_SMD:R_0603_1608Metric"`
- **WHEN** `split_lib_id` is called on it
- **THEN** it returns `("Resistor_SMD", "R_0603_1608Metric")`

#### Scenario: Unqualified identifier
- **WHEN** `split_lib_id("R_0603")` is called
- **THEN** `LibraryError` is raised with issue code `kicad.lib.invalid-id`

#### Scenario: Second colon
- **WHEN** `split_lib_id("A:B:C")` is called
- **THEN** `LibraryError` is raised with issue code `kicad.lib.invalid-id`

### Requirement: Library table parsing
`read_lib_table(source)` SHALL parse `fp_lib_table` and `sym_lib_table` files with quoted or bare atoms and with or without a `(version N)` child. It SHALL return a `LibTable` whose rows keep file order and carry `nickname`, `type`, `uri`, `options`, `descr`, `disabled` and `hidden`.
- A root other than `fp_lib_table` or `sym_lib_table` MUST raise `FormatError`.
- A second row with a nickname already seen in the same table MUST be dropped with the warning `kicad.lib.duplicate-nickname`. This rule is a Fenolite choice and MUST be labelled so in `docs/formats/kicad/libraries.md`.

#### Scenario: 10.0 syntax
- **GIVEN** `tests/data/libs/project/fp-lib-table` (`(version 7)`, quoted atoms)
- **WHEN** it is read
- **THEN** `version == 7` and the row `Mini` has `type == "KiCad"` and `uri == "${KIPRJMOD}/../Mini.pretty"`

#### Scenario: 9.0 syntax
- **GIVEN** `tests/data/libs/project/nested/fp-lib-table` (no version, bare atoms)
- **WHEN** it is read
- **THEN** `version is None` and its rows have the same fields as in the quoted form

#### Scenario: Disabled and hidden rows
- **WHEN** the mini project table is read
- **THEN** the row `MiniDisabled` has `disabled == True` and the row `MiniHidden` has `hidden == True`

#### Scenario: Duplicate nickname
- **GIVEN** a table with two rows named `Mini`
- **WHEN** it is read with an `issues` list
- **THEN** only the first row is kept and `issues` holds one warning `kicad.lib.duplicate-nickname`

#### Scenario: Design-block table refused
- **GIVEN** a file whose root is `design_block_lib_table`
- **WHEN** `read_lib_table` is called
- **THEN** `FormatError` is raised naming the head

### Requirement: Path variable expansion
The resolver SHALL expand `${NAME}` in table URIs and 3D model paths. It SHALL resolve each name in this order:
1. `KIPRJMOD` = the project folder, which no other source overrides
2. the process environment (`LibraryConfig.env`)
3. Fenolite defaults `KICAD<M>_FOOTPRINT_DIR`, `KICAD<M>_SYMBOL_DIR`, `KICAD<M>_3DMODEL_DIR` and `KICAD<M>_TEMPLATE_DIR` from the selected library source
4. the versioned fallback `KICAD<k>_X` → `KICAD<k+1>_X` for k below the target major

A name without a value MUST make the lookups that need it raise `LibraryError` with issue code `kicad.lib.unresolved-variable` naming the variable. KiCad's own configuration file `kicad_common.json` MUST NOT be read.

#### Scenario: KIPRJMOD cannot be overridden
- **GIVEN** `project_dir = P` and an environment with `KIPRJMOD=/elsewhere`
- **WHEN** `expand("${KIPRJMOD}/lib")` is called
- **THEN** it returns `P/lib`

#### Scenario: Environment wins over the source default
- **GIVEN** an install source of major 10 and `KICAD10_FOOTPRINT_DIR=/env` in `LibraryConfig.env`
- **WHEN** `${KICAD10_FOOTPRINT_DIR}` is expanded
- **THEN** the value is `/env`

#### Scenario: Versioned fallback
- **GIVEN** target major 10, `KICAD10_FOOTPRINT_DIR=/libs` and no `KICAD9_FOOTPRINT_DIR`
- **WHEN** `expand("${KICAD9_FOOTPRINT_DIR}/Mini.pretty")` is called
- **THEN** it returns `/libs/Mini.pretty`

#### Scenario: Unresolved variable
- **GIVEN** a project row with `uri "${MY_LIBS}/X.pretty"` and no `MY_LIBS` anywhere
- **WHEN** `locate("X:Item", "footprint")` is called
- **THEN** `LibraryError` is raised with issue code `kicad.lib.unresolved-variable` whose message names `MY_LIBS`

### Requirement: Table discovery and precedence
The resolver SHALL build the effective rows of each kind as follows.
- It SHALL start with the project table in `project_dir`, followed by the global table `<config>/<M>.0/<table>`. `<config>` is `LibraryConfig.config_home`, else `KICAD_CONFIG_HOME` when set, and otherwise the per-OS KiCad configuration folder.
- When the global table is absent, the resolver SHALL substitute the template table of the selected library source: the first existing file of `<install>/template/<table>`, `${KICAD<M>_TEMPLATE_DIR}/<table>`, and `<table>` inside the library folder of that kind. Each row MUST record its origin (`project`, `global` or `template`).
- A nickname present in the project table MUST hide the same nickname in later tables.
- Rows of type `Table` MUST be expanded in place, recursively, into the namespace of the table holding them.
  - A nested table already being expanded MUST be skipped with the warning `kicad.lib.table-cycle`.
  - A missing nested file MUST be skipped with the warning `kicad.lib.missing-table`.
  - With target major 9, the info `kicad.lib.nested-table-target` MUST be added.
- A relative URI MUST resolve against the folder of the table file that holds the row. For a row of a nested table, this is the nested table's folder.

#### Scenario: Project table wins
- **GIVEN** a project table and a global table that both define nickname `Mini` with different URIs
- **WHEN** `locate("Mini:Mini_R_0603", "footprint")` is called
- **THEN** the location's `origin` is `project` and its path comes from the project row

#### Scenario: Nested relative row resolves against the nested table
- **GIVEN** the mini project table with its `Table` row pointing to `nested/fp-lib-table`, which defines `NestedMini` with `uri "../../Mini_v9.pretty"`
- **WHEN** `locate("NestedMini:Mini_R_0603", "footprint")` is called
- **THEN** the item path is `tests/data/libs/Mini_v9.pretty/Mini_R_0603.kicad_mod`

#### Scenario: Nested cycle
- **GIVEN** table A nests table B and table B nests table A
- **WHEN** the resolver loads them
- **THEN** each table is expanded once and `issues` holds one warning `kicad.lib.table-cycle`

#### Scenario: Missing global table falls back to the template
- **GIVEN** `config_home` pointing to an empty folder and `install_dir` pointing to a temporary install of major 10 whose `template/fp-lib-table` lists `Mini`
- **WHEN** `rows("footprint")` is called
- **THEN** the `Mini` row is returned with origin `template`

#### Scenario: Relative URI in the project table
- **GIVEN** the project row `MiniRel` with `uri "../Mini.pretty"`
- **WHEN** it is located
- **THEN** the library path is `tests/data/libs/Mini.pretty`

### Requirement: Library sources
`find_library_sources(config)` SHALL report every available source of official libraries, as `LibrarySource(kind, root, major)`:
- `env`: library folders named by `KICAD9_*` or `KICAD10_*` variables of `LibraryConfig.env`
- `install`: `config.install_dir`, or when it is `None` a local KiCad install at the per-OS default location, with its major read from a symbol library header; a path that does not exist MUST give no install source

For target major M, the default library variables MUST come from an `env` source of major M, else from an install of major M. An install of another major MUST NOT be used.

#### Scenario: A 10.0 install is not used for target 9
- **GIVEN** only a KiCad 10.0 install and no `KICAD9_*` variable
- **WHEN** a resolver with `target_major = 9` expands `${KICAD9_FOOTPRINT_DIR}` in a needed row
- **THEN** `LibraryError` is raised with issue code `kicad.lib.unresolved-variable`, and the hint says to set `KICAD9_FOOTPRINT_DIR`

#### Scenario: Missing install path means no install
- **GIVEN** `install_dir` set to a path that does not exist and no library variable
- **WHEN** `find_library_sources(config)` is called
- **THEN** it returns an empty tuple

### Requirement: Locating and loading library items
`LibraryResolver.locate(lib_id, kind)` SHALL return a `Location` naming the row, origin, table file, library path and item path. `footprint(lib_id)` and `symbol(lib_id)` SHALL return definitions with `library` set to the nickname, and symbols MUST be flattened.
- For rows of type `KiCad`, a footprint library MUST be a folder holding `<entry>.kicad_mod`.
- A symbol library MUST be either a `.kicad_sym` file holding the top-level symbol `entry`, or a folder holding `<entry>.kicad_sym` (the resolver scans the folder when that file name is absent).

Each lookup failure MUST raise `LibraryError` with exactly one error code of the `Library issue codes` table. Parsed library files SHALL be cached while their path, modification time and size are unchanged.

#### Scenario: Footprint through the project table
- **GIVEN** a resolver with `project_dir = tests/data/libs/project`
- **WHEN** `footprint("Mini:Mini_QFP-32_7x7mm_P0.8mm")` is called
- **THEN** a `FootprintDef` with 32 pads and `library == "Mini"` is returned

#### Scenario: Derived symbol through a folder library
- **GIVEN** a project row whose URI is the folder generated by `make_symdir`
- **WHEN** `symbol("MiniDir:Mini_LED_Red")` is called
- **THEN** the definition carries the pins of `Mini_LED`

#### Scenario: Unsupported library type
- **GIVEN** the project row `MiniLegacy` of type `Legacy`
- **WHEN** `locate("MiniLegacy:X", "symbol")` is called
- **THEN** `LibraryError` is raised with issue code `kicad.lib.unsupported-type`

#### Scenario: Disabled library
- **WHEN** `footprint("MiniDisabled:Mini_R_0603")` is called
- **THEN** `LibraryError` is raised with issue code `kicad.lib.disabled`

#### Scenario: Missing entry
- **WHEN** `footprint("Mini:Does_Not_Exist")` is called
- **THEN** `LibraryError` is raised with issue code `kicad.lib.missing-entry`, and `issue.where` names the library path

#### Scenario: Missing library folder
- **GIVEN** a project row whose expanded URI does not exist
- **WHEN** an item of it is requested
- **THEN** `LibraryError` is raised with issue code `kicad.lib.missing-library`

#### Scenario: Invalid identifier through the resolver
- **WHEN** `footprint("Mini_R_0603")` is called
- **THEN** `LibraryError` is raised with issue code `kicad.lib.invalid-id`

### Requirement: Missing 3D models are warnings
`LibraryResolver.missing_models(fp)` SHALL expand every model path of a footprint definition. For each path that does not name an existing file, and for each path that contains a variable without a value, it SHALL return one warning `kicad.lib.missing-3d-model`; in the second case the message MUST name the variable. It MUST NOT raise, and it MUST NOT download anything.

#### Scenario: Mini resistor model absent
- **GIVEN** `Mini:Mini_R_0603`, whose model path is `${KICAD10_3DMODEL_DIR}/Mini.3dshapes/Mini_R_0603.step`, and `KICAD10_3DMODEL_DIR` set to an empty temporary folder
- **WHEN** `missing_models` is called on it
- **THEN** it returns exactly one warning `kicad.lib.missing-3d-model`, and no exception is raised

#### Scenario: Model variable without a value
- **GIVEN** the same footprint, no library source and no `KICAD10_3DMODEL_DIR`
- **WHEN** `missing_models` is called on it
- **THEN** it returns exactly one warning `kicad.lib.missing-3d-model` whose message names `KICAD10_3DMODEL_DIR`

### Requirement: Resolution evidence
Precedence, variable expansion, the versioned fallback, nested tables, relative URIs and `KICAD_CONFIG_HOME` handling SHALL be labelled `INFERRED` and linked to their `H-K-LIB-*` hypotheses until a `kicad-cli` run settles them. With official libraries available, the resolver SHALL resolve the reference items through the template tables of each available source. The census SHALL count the `Footprint` properties that fail to resolve, per code, and write the counts only to the report file named by `FENOLITE_CENSUS_OUT`.

#### Scenario: Reference items resolve on every source
- **GIVEN** an official library source of major 10 (install or `env`)
- **WHEN** `uv run pytest -m needs_libs tests/libs/test_official_resolve.py` runs
- **THEN** `symbol("Device:R")` and `footprint("Resistor_SMD:R_0603_1608Metric")` succeed for each available source

#### Scenario: Dangling footprint references are reported, not fatal
- **GIVEN** the official symbols of the available 10.0 source
- **WHEN** the `Footprint` property of every flattened symbol is resolved
- **THEN** empty values are skipped and counted apart, every failure has issue code `kicad.lib.missing-entry`, `kicad.lib.unknown-nickname` or `kicad.lib.invalid-id`, and the counts per code are written to the report file and to no tracked file

### Requirement: Project library tables are written per target
`fenolite.backends.kicad.libs.write_lib_table(table: LibTable, *, target: int = DEFAULT_TARGET) -> str` SHALL return the text of a project library table holding the rows of `table`, in their order, in the syntax of the target major.
- The root head MUST be the root name of the table's kind, the inverse of `libs.TABLE_ROOTS` (`footprint` → `fp_lib_table`, `symbol` → `sym_lib_table`), and each row MUST be written as `(lib (name …) (type …) (uri …) (options …) (descr …))`, with `(disabled)` and `(hidden)` only for rows that carry them.
- Target 10 MUST write a `(version 7)` child first and quote every atom, the form of the c0008 fixture `tests/data/libs/project/fp-lib-table` (S-0046).
- Target 9 MUST write no version child and bare atoms, quoting only an atom that cannot be written bare (empty, or holding a space, a parenthesis or a quote), the form of the 9.0.9 official tables (S-0042, S-0043).
- The text MUST end with a newline, use tab indentation, and depend only on `table` and `target`, so equal inputs give equal bytes.
- `read_lib_table` of the written text MUST give back a `LibTable` with the same rows, and `version == 7` for target 10 and `version is None` for target 9.
- A target other than 9 and 10 MUST raise `ValueError`.
- The build writes one `fp-lib-table` with a row `uri "${KIPRJMOD}/lib/<nickname>.pretty"` per vendored library; KiCad reading that table is `H-K-BUILD-LIBTABLE` (`kicad-oracle`, "Built projects pass the build oracle").

#### Scenario: Target 10 form
- **GIVEN** a `LibTable` of kind `footprint` with one row `Mini`, type `KiCad`, uri `${KIPRJMOD}/lib/Mini.pretty`, empty options and description
- **WHEN** `write_lib_table(table, target=10)` is called
- **THEN** the text starts with `(fp_lib_table` followed by `(version 7)`, and the row reads `(lib (name "Mini") (type "KiCad") (uri "${KIPRJMOD}/lib/Mini.pretty") (options "") (descr ""))`

#### Scenario: Target 9 form
- **WHEN** the same table is written with `target=9`
- **THEN** the text holds no `version` child, and the row reads `(lib (name Mini) (type KiCad) (uri ${KIPRJMOD}/lib/Mini.pretty) (options "") (descr ""))`

#### Scenario: Read back equal
- **WHEN** the texts of both targets are read with `read_lib_table`
- **THEN** both give the row `Mini` with the same `type`, `uri`, `options` and `descr`, and versions `7` and `None`

#### Scenario: Unknown target
- **WHEN** `write_lib_table(table, target=8)` is called
- **THEN** `ValueError` is raised

