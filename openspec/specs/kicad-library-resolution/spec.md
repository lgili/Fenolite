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
3. when `LibraryConfig.read_common` is true, the `environment.vars` object of `<config>/<M>.0/kicad_common.json`, where `<config>` is the configuration folder of "Table discovery and precedence" and M the target major
4. Fenolite defaults `KICAD<M>_FOOTPRINT_DIR`, `KICAD<M>_SYMBOL_DIR`, `KICAD<M>_3DMODEL_DIR` and `KICAD<M>_TEMPLATE_DIR` from the selected library source
5. the versioned fallback `KICAD<k>_X` → `KICAD<k+1>_X` for k below the target major

Path variables set in KiCad live in its configuration, which the environment overrides (S-0045). The file name and the `environment.vars` layout are observed facts (`H-K-LIB-COMMON`).

`LibraryConfig.read_common` MUST default to false, and while it is false KiCad's configuration files MUST NOT be read. When it is true:
- the `kicad_common.json` of another major MUST NOT be read;
- a missing file, a file without `environment.vars`, or `environment.vars` set to `null` MUST give no variables;
- a file that is not valid JSON, or whose `environment.vars` is neither `null` nor an object whose values are all strings, MUST raise `FormatError` naming the file;
- values MUST be used as written, so `${…}` inside a value is not expanded;
- the file MUST be read at most once per resolver.

A name without a value MUST make the lookups that need it raise `LibraryError` with issue code `kicad.lib.unresolved-variable` naming the variable. While `read_common` is false, the hint for a name other than `KIPRJMOD` and the `KICAD<k>_FOOTPRINT_DIR`, `_SYMBOL_DIR`, `_3DMODEL_DIR` and `_TEMPLATE_DIR` variables MUST name `LibraryConfig.read_common`.

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

#### Scenario: KiCad's configuration is read only on request
- **GIVEN** `config_home = C`, an empty `env`, and `C/10.0/kicad_common.json` holding `{"environment": {"vars": {"MY_LIBS": "/common"}}}`
- **WHEN** `expand("${MY_LIBS}/X.pretty")` is called by a resolver with `read_common` false, and by one with `read_common` true
- **THEN** the first raises `LibraryError` with issue code `kicad.lib.unresolved-variable` whose hint names `LibraryConfig.read_common`, and the second returns `/common/X.pretty`

#### Scenario: Process environment wins over KiCad's configuration
- **GIVEN** the same file, `read_common` true and `MY_LIBS=/env` in `LibraryConfig.env`
- **WHEN** `expand("${MY_LIBS}")` is called
- **THEN** it returns `/env`

#### Scenario: KiCad's configuration wins over the source default
- **GIVEN** an install source of major 10, `read_common` true, and `C/10.0/kicad_common.json` defining `KICAD10_FOOTPRINT_DIR` as `/common`
- **WHEN** `${KICAD10_FOOTPRINT_DIR}` is expanded
- **THEN** the value is `/common`

#### Scenario: Only the target major's file is read
- **GIVEN** `read_common` true, target major 10, and `MY_LIBS` defined only in `C/9.0/kicad_common.json`
- **WHEN** `expand("${MY_LIBS}")` is called
- **THEN** `LibraryError` is raised with issue code `kicad.lib.unresolved-variable`

#### Scenario: Malformed configuration file
- **GIVEN** `read_common` true and `C/10.0/kicad_common.json` holding `{"environment": {"vars": ["x"]}}`
- **WHEN** a name that the process environment does not define is expanded
- **THEN** `FormatError` is raised naming that file

### Requirement: Table discovery and precedence
The resolver SHALL build the effective rows of each kind as follows.
- It SHALL start with the project table in `project_dir`, followed by the global table `<config>/<M>.0/<table>`. `<config>` is `LibraryConfig.config_home`, else `KICAD_CONFIG_HOME` when set, and otherwise the per-OS KiCad configuration folder.
- When the global table is absent, the resolver SHALL substitute the template table of the selected library source: the first existing file of `<install>/template/<table>`, `${KICAD<M>_TEMPLATE_DIR}/<table>`, and `<table>` inside the library folder of that kind. When the selected source is a `cache` source, the template search MUST be skipped.
- When neither a global table nor a template table is found, the resolver SHALL scan the folder that `${KICAD<M>_FOOTPRINT_DIR}` (footprints) or `${KICAD<M>_SYMBOL_DIR}` (symbols) expands to, and add one row per library, in sorted name order. This directory scan is a Fenolite extension (`H-K-LIB-SCAN`):
  - a library is a `<X>.pretty` folder for footprints, and a `<X>.kicad_sym` file or a `<X>.kicad_symdir` folder for symbols; the file wins over a folder of the same stem;
  - its row has nickname `X`, type `KiCad`, uri `${KICAD<M>_FOOTPRINT_DIR}/<name>` or `${KICAD<M>_SYMBOL_DIR}/<name>`, where `<name>` is the folder or file name, and empty options and description;
  - when the variable has no value or names no folder, no row is added.
- With `LibraryConfig.use_global_table` false, neither the global table, the template nor the scan is used.
- Each row MUST record its origin (`project`, `global`, `template` or `scan`).
- A nickname present in the project table MUST hide the same nickname in later tables.
- Rows of type `Table` MUST be expanded in place, recursively, into the namespace of the table holding them.
  - A nested table already being expanded MUST be skipped with the warning `kicad.lib.table-cycle`.
  - A missing nested file MUST be skipped with the warning `kicad.lib.missing-table`.
  - With target major 9, the info `kicad.lib.nested-table-target` MUST be added.
- A relative URI MUST be joined to `LibraryConfig.project_dir` when it is set, whatever table holds the row: the project table, a nested table or the global table. Without `project_dir` it MUST stay relative. `kicad-cli` resolves a relative URI against its working directory and never against the folder of the table file (`H-K-LIB-RELPATH-2`); `project_dir` stands for the working directory of a KiCad that runs in the project folder, so that a result does not depend on where the caller runs.

#### Scenario: Project table wins
- **GIVEN** a project table and a global table that both define nickname `Mini` with different URIs
- **WHEN** `locate("Mini:Mini_R_0603", "footprint")` is called
- **THEN** the location's `origin` is `project` and its path comes from the project row

#### Scenario: Nested relative row resolves against the project folder
- **GIVEN** the mini project table with its `Table` row pointing to `nested/fp-lib-table`, which defines `NestedMini` with `uri "../Mini_v9.pretty"`, and `project_dir` naming `tests/data/libs/project`
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

#### Scenario: Scanned rows when no table exists
- **GIVEN** an empty `config_home`, an `install_dir` that does not exist, and `KICAD10_FOOTPRINT_DIR` in `LibraryConfig.env` naming a folder that holds `B.pretty` and `A.pretty` and no `fp-lib-table`
- **WHEN** `rows("footprint")` is called with target major 10
- **THEN** it returns the rows `A` and `B`, in that order, with origin `scan`, type `KiCad` and the uris `${KICAD10_FOOTPRINT_DIR}/A.pretty` and `${KICAD10_FOOTPRINT_DIR}/B.pretty`

#### Scenario: A cache source is scanned, not templated
- **GIVEN** an empty `config_home` and a verified `cache` source of major 10 whose footprint folder holds an `fp-lib-table` listing only `Other`, and the folder `Mini.pretty`
- **WHEN** `rows("footprint")` is called with target major 10
- **THEN** it returns one row, `Mini`, with origin `scan`

#### Scenario: Symbol file wins over a folder of the same stem
- **GIVEN** no table and a folder named by `KICAD10_SYMBOL_DIR` that holds `S.kicad_sym`, `S.kicad_symdir/` and `T.kicad_symdir/`
- **WHEN** `rows("symbol")` is called with target major 10
- **THEN** it returns `S` with uri `${KICAD10_SYMBOL_DIR}/S.kicad_sym` and `T` with uri `${KICAD10_SYMBOL_DIR}/T.kicad_symdir`

#### Scenario: Project rows only
- **GIVEN** `use_global_table` false, a project table listing only `Mini`, an empty `config_home`, an `install_dir` that does not exist, and `KICAD10_FOOTPRINT_DIR` in `LibraryConfig.env` naming a folder that holds `A.pretty` and no `fp-lib-table`
- **WHEN** `rows("footprint")` is called with target major 10
- **THEN** it returns only the row `Mini`, with origin `project`, and no row of origin `scan`

### Requirement: Library sources
`find_library_sources(config)` SHALL report every available source of official libraries, as `LibrarySource(kind, root, major)`, in this order:
- `env`: library folders named by `KICAD9_*` or `KICAD10_*` variables of `LibraryConfig.env`
- `cache`: for each tag pinned in `libraries.toml` ("Library pins"), the folder `<cache>/<tag>`, when its subfolder `kicad-footprints` or `kicad-symbols` holds a stamp equal to that subfolder's pin. Its major is the pin's major. `<cache>` is `LibraryConfig.cache_dir`, else the value of `FENOLITE_LIBS_CACHE` in `LibraryConfig.env`. With neither, or with a path that does not exist, there MUST be no cache source, and no default location is searched. A subfolder whose stamp is missing or differs from its pin MUST NOT be used.
- `install`: `config.install_dir`, or when it is `None` a local KiCad install at the per-OS default location, with its major read from a symbol library header; a path that does not exist MUST give no install source

For target major M, the default library variables MUST come from an `env` source of major M, else from a `cache` source of major M, else from an install of major M. A source of another major MUST NOT be used. A `cache` source MUST define `KICAD<M>_FOOTPRINT_DIR` and `KICAD<M>_SYMBOL_DIR` only for its verified subfolders, and MUST define neither `KICAD<M>_3DMODEL_DIR` nor `KICAD<M>_TEMPLATE_DIR`.

#### Scenario: A 10.0 install is not used for target 9
- **GIVEN** only a KiCad 10.0 install and no `KICAD9_*` variable
- **WHEN** a resolver with `target_major = 9` expands `${KICAD9_FOOTPRINT_DIR}` in a needed row
- **THEN** `LibraryError` is raised with issue code `kicad.lib.unresolved-variable`, and the hint says to set `KICAD9_FOOTPRINT_DIR`

#### Scenario: Missing install path means no install
- **GIVEN** `install_dir` set to a path that does not exist and no library variable
- **WHEN** `find_library_sources(config)` is called
- **THEN** it returns an empty tuple

#### Scenario: Verified cache source
- **GIVEN** `cache_dir = C`, where `C/9.0.9/kicad-footprints/.fenolite-verified` equals the 9.0.9 footprint pin, an empty `env` and an `install_dir` that does not exist
- **WHEN** `find_library_sources(config)` is called
- **THEN** it returns `(LibrarySource("cache", C / "9.0.9", 9),)`

#### Scenario: Stale stamp is ignored
- **GIVEN** the same folder, whose stamp names another commit
- **WHEN** `find_library_sources(config)` is called
- **THEN** it returns an empty tuple

#### Scenario: Cache before install
- **GIVEN** `cache_dir = C` with a verified `C/10.0.6/kicad-footprints`, and an install of major 10
- **WHEN** a resolver with target major 10 expands `${KICAD10_FOOTPRINT_DIR}`
- **THEN** the value is `C/10.0.6/kicad-footprints`, and expanding `${KICAD10_3DMODEL_DIR}` raises `LibraryError` with issue code `kicad.lib.unresolved-variable`

#### Scenario: No default cache location
- **GIVEN** `env={}`, `cache_dir=None`, an `install_dir` that does not exist, and `home` pointing to a folder whose `.cache/fenolite/libs` holds a verified cache
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
`LibraryResolver.missing_models(fp)` SHALL locate every model path of a footprint definition with `locate_model` ("3D model location"). For each path that it does not locate it SHALL return one warning `kicad.lib.missing-3d-model`; when the path holds a variable that no source gives a value, the message MUST name the variable. It MUST NOT raise, and it MUST NOT download anything.

#### Scenario: Mini resistor model absent
- **GIVEN** `Mini:Mini_R_0603`, whose model path is `${KICAD10_3DMODEL_DIR}/Mini.3dshapes/Mini_R_0603.step`, and `KICAD10_3DMODEL_DIR` set to an empty temporary folder
- **WHEN** `missing_models` is called on it
- **THEN** it returns exactly one warning `kicad.lib.missing-3d-model`, and no exception is raised

#### Scenario: Model variable without a value
- **GIVEN** the same footprint, no library source and no `KICAD10_3DMODEL_DIR`
- **WHEN** `missing_models` is called on it
- **THEN** it returns exactly one warning `kicad.lib.missing-3d-model` whose message names `KICAD10_3DMODEL_DIR`

#### Scenario: A vendored copy is not missing
- **GIVEN** the same footprint, no `KICAD10_3DMODEL_DIR`, and a resolver whose `project_dir` holds `3dmodels/Mini.3dshapes/Mini_R_0603.step`
- **WHEN** `missing_models` is called on it
- **THEN** it returns no warning

### Requirement: Resolution evidence
Precedence, variable expansion, the versioned fallback, nested tables, relative URIs, `KICAD_CONFIG_HOME` handling and the variables of `kicad_common.json` SHALL be labelled `INFERRED` and linked to their `H-K-LIB-*` hypotheses until the probes of `kicad-oracle` "Library table probes" settle them. A rule whose probe holds SHALL then be labelled `KICAD-VERIFIED` with the majors it holds on, and a refuted rule SHALL be changed to the observed behaviour. The directory scan SHALL be labelled `INFERRED` and linked to `H-K-LIB-SCAN`.

With official libraries available, the resolver SHALL resolve the reference items through the rows of each available source, at the source's major: template rows for `env` and `install` sources, scanned rows for `cache` sources. The census SHALL count the `Footprint` properties that fail to resolve, per code. For every source that has a template table, it SHALL compare the template rows with the rows a scan of the same folder gives, and count:
- template rows whose nickname differs from the stem of the last part of their uri;
- nicknames found only in the template, and nicknames found only by the scan;
- template rows that are `disabled` or `hidden`.

Every count SHALL be written only to the report file named by `FENOLITE_CENSUS_OUT`.

#### Scenario: Reference items resolve on every source
- **GIVEN** an official library source of major 10 (install, `env` or `cache`)
- **WHEN** `uv run pytest -m needs_libs tests/libs/test_official_resolve.py` runs
- **THEN** `symbol("Device:R")` and `footprint("Resistor_SMD:R_0603_1608Metric")` succeed for each available source

#### Scenario: Dangling footprint references are reported, not fatal
- **GIVEN** the official symbols of the available 10.0 source
- **WHEN** the `Footprint` property of every flattened symbol is resolved
- **THEN** empty values are skipped and counted apart, every failure has issue code `kicad.lib.missing-entry`, `kicad.lib.unknown-nickname` or `kicad.lib.invalid-id`, and the counts per code are written to the report file and to no tracked file

#### Scenario: Fetched 9.0.9 libraries resolve
- **GIVEN** a verified 9.0.9 cache and no other source of major 9
- **WHEN** `uv run pytest -m needs_libs tests/libs/test_official_resolve.py` runs
- **THEN** a resolver with target major 9 returns `symbol("Device:R")` and `footprint("Resistor_SMD:R_0603_1608Metric")` through rows of origin `scan`

#### Scenario: Scanned rows compared with the template
- **GIVEN** the local 10.0.6 install and `FENOLITE_CENSUS_OUT` naming a file under a temporary folder
- **WHEN** `uv run pytest -m needs_libs tests/libs/test_official_resolve.py -k scan` runs
- **THEN** the four counts of the comparison for footprints and symbols are written to that file, and `git status --porcelain` is unchanged

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

### Requirement: Library pins
`src/fenolite/backends/kicad/data/libraries.toml` SHALL pin the official footprint and symbol libraries at tags 10.0.6 and 9.0.9, and `fenolite.backends.kicad.libcache.load_pins(path=None)` SHALL return them as `LibraryPin(tag, major, repo, project, commit, tree, files)` values, in file order.
- `repo` MUST be `kicad-footprints` or `kicad-symbols`, and `project` its GitLab path `kicad/libraries/<repo>`. There MUST be exactly one pin per tag and repo, and the pins of one major MUST name one tag.
- `commit` MUST be the 40 lowercase hex digits that the tags API gives for the tag (S-0042, S-0043). `tree` MUST be 64 lowercase hex digits and `files` a positive integer, both measured on a fetched tree.
- The file SHALL also hold `archive`, the download URL template with the fields `{project}` (URL-encoded) and `{commit}` (S-0096).
- A pins file that breaks these rules MUST raise `ValueError` naming the file and the key.

`libcache.tree_hash(folder)` SHALL return `(digest, files)`. `files` is the number of regular files under `folder`, the stamp excluded. `digest` is the SHA-256 hex digest of one line `<sha256 hex> <size> <path>\n` per such file, where `<path>` is the POSIX path relative to `folder`, with the lines sorted by the UTF-8 bytes of `<path>`. The result MUST NOT depend on modification times, permissions or listing order. A symlink, or an entry that is neither a regular file nor a folder, MUST raise `ValueError` naming it.

The stamp `<folder>/.fenolite-verified` SHALL be a JSON object with exactly the keys `scheme` (`"fenolite-tree-1"`), `tag`, `repo`, `commit`, `tree` and `files`. A stamp equals a pin when its scheme is `"fenolite-tree-1"` and every other value equals the pin's field of the same name.

#### Scenario: Pins of both tags
- **WHEN** `load_pins()` is called
- **THEN** it returns four pins: `kicad-footprints` and `kicad-symbols` at 10.0.6 with major 10 and at 9.0.9 with major 9, each with a 40-hex commit, a 64-hex tree and a positive file count

#### Scenario: Tree hash ignores order and times
- **GIVEN** two folders holding the same files, written in different orders and with different modification times
- **WHEN** `tree_hash` is called on each
- **THEN** both results are equal, and they differ once one byte of one file is changed

#### Scenario: Stamp not hashed
- **GIVEN** a folder and its `tree_hash`
- **WHEN** a `.fenolite-verified` file is added to it
- **THEN** `tree_hash` of the folder is unchanged

#### Scenario: Symlink refused
- **GIVEN** a folder holding a symlink `a` pointing to `b`
- **WHEN** `tree_hash` is called on it
- **THEN** `ValueError` is raised naming `a`

#### Scenario: Malformed pin
- **GIVEN** a pins file whose commit has 39 hex digits
- **WHEN** `load_pins(path)` is called
- **THEN** `ValueError` is raised naming the file and `commit`

### Requirement: Library cache fetch
`tools/kicad_libs_fetch.py` SHALL put each pinned tree into `<cache>/<tag>/<repo>/`, where `<cache>` is `--cache DIR`, else `FENOLITE_LIBS_CACHE`, else `~/.cache/fenolite/libs`. `--tag TAG` and `--repo REPO` (both repeatable) select pins, and by default every pin is selected. `--pins PATH` replaces the package's pins file.
- Before any network or cache access, it MUST exit 2 with a message naming Python 3.11.4 when the `tarfile` module has no `data_filter` (S-0095).
- A folder whose stamp equals its pin MUST be reported `cached` and MUST NOT be downloaded again. With `--verify`, the tool MUST re-hash every selected cached folder, and MUST exit 5 naming the folder when its tree hash or file count differs from the pin.
- Otherwise the tool MUST download the archive of the pinned commit into a temporary file inside `<cache>/<tag>/`, extract it with the `data` filter into `tempfile.mkdtemp(dir=<cache>/<tag>)`, and require exactly one top-level folder. When that folder's tree hash and file count equal the pin, it MUST write the stamp into it and move it to `<cache>/<tag>/<repo>` with `os.replace` (S-0097). An older `<repo>` folder MUST be moved aside first and removed only after the move.
- A download error, a member refused by the filter, a symlink, or a top level other than one folder MUST exit 3. A tree hash or file count that differs from the pin MUST exit 5. In both cases `<cache>/<tag>/<repo>` MUST be left as it was, and the temporary files MUST be removed.
- `--print-pin --tag TAG --repo REPO --commit SHA` MUST download and hash the archive of that commit, print its pin as TOML, and leave the cache as it was.
- The tool MUST print one line per selected folder, ending in `fetched`, `cached`, `verified` or `failed`, and MUST exit 0 when no folder failed.

#### Scenario: Python without the data filter
- **GIVEN** a `tarfile` module without `data_filter`
- **WHEN** `main(["--cache", str(C)])` runs
- **THEN** it returns 2, the message names 3.11.4, and `C` holds no file

#### Scenario: Fetch, stamp and move
- **GIVEN** a pins file whose `archive` template names a local `file://` tarball with one top-level folder, and whose `tree` and `files` match that folder
- **WHEN** the tool runs with `--cache C`
- **THEN** it exits 0 reporting `fetched`, the stamp of `C/<tag>/<repo>` equals the pin, and `C/<tag>/` holds nothing else

#### Scenario: Cached folders are not downloaded again
- **GIVEN** the folder fetched above, and its tarball deleted
- **WHEN** the tool runs again
- **THEN** it exits 0 reporting `cached`

#### Scenario: Tree mismatch
- **GIVEN** a pins file whose `tree` differs from the tarball's
- **WHEN** the tool runs
- **THEN** it exits 5, `C/<tag>/<repo>` does not exist, and `C/<tag>/` holds no temporary file or folder

#### Scenario: Unsafe member
- **GIVEN** a tarball holding the member `../outside.txt`
- **WHEN** the tool runs with `--cache C`
- **THEN** it exits 3, no `outside.txt` exists next to `C`, and `C/<tag>/<repo>` does not exist

#### Scenario: Verify finds a change
- **GIVEN** a fetched folder in which one file was edited afterwards
- **WHEN** the tool runs with `--verify`
- **THEN** it exits 5 naming the folder

#### Scenario: Pin printed
- **GIVEN** a local tarball and its 40-hex commit
- **WHEN** the tool runs with `--print-pin --tag 10.0.6 --repo kicad-footprints --commit <commit>`
- **THEN** it prints a TOML pin holding that commit and the tarball's tree hash and file count, and `C/10.0.6/kicad-footprints` does not exist

### Requirement: Install tree compared with its pin
`tests/libs/test_install_pin.py` (`needs_libs`, `slow`) SHALL compare a local KiCad install with the verified cache of the same major. It SHALL skip, naming the missing tree and the fetch command, when either is absent.
- Footprints: each `<X>.pretty/<Y>.kicad_mod` of either tree is counted as equal (in both trees, same bytes), different, only in the install, or only in the cache.
- Symbols: each library is counted the same way. Equal means that the install's `<X>.kicad_sym` and the cache's `<X>.kicad_symdir` folder or `<X>.kicad_sym` file read to the same multiset of flattened definitions, ignoring provenance and `ext`, because the install packs folders into files (S-0044). The order of the definitions MUST NOT count, because a folder has none.

The counts SHALL be written only to the report file named by `FENOLITE_CENSUS_OUT`. A difference MUST NOT fail the test. `docs/evidence/kicad-libs.md` MAY claim that an install equals its pinned tag only when every count other than "equal" is 0.

#### Scenario: Install of 10.0.6 compared with its pin
- **GIVEN** the local 10.0.6 install, a verified 10.0.6 cache and `FENOLITE_CENSUS_OUT` naming a file under a temporary folder
- **WHEN** `uv run pytest -m needs_libs tests/libs/test_install_pin.py` runs
- **THEN** the four counts for footprints and for symbol libraries are written to that file, and `git status --porcelain` is unchanged

#### Scenario: No cache of the install's major
- **GIVEN** an install of major 10 and `FENOLITE_LIBS_CACHE` naming a folder without a verified 10.0.6 tree
- **WHEN** the same command runs
- **THEN** the test is skipped with a reason naming the 10.0.6 cache and `tools/kicad_libs_fetch.py`

### Requirement: 3D model location
`LibraryResolver.locate_model(path) -> ModelLocation | None` SHALL find the file that a footprint's 3D model path names, from the sources below in this order, and SHALL return the first regular file found as `ModelLocation(path, rel, file, source)`, or `None` when no source holds one. It MUST NOT raise and MUST NOT download anything.
- **`${KICAD<N>_3DMODEL_DIR}/<rel>`**, for any N, with `rel` the part after the variable:
  - `project`: `<project_dir>/3dmodels/<rel>`, the folder that `fenolite models --vendor` writes;
  - `env`: the value of `KICAD<N>_3DMODEL_DIR` in `LibraryConfig.env`, joined with `<rel>`;
  - `kicad-config`: the same variable in KiCad's `kicad_common.json` of major N, read only with `read_common`;
  - `install`: the `3dmodels` folder of the install that `install_dir` or the per-OS default gives, whatever its major, because `kicad-cli` 10.0.6 reads `KICAD9_` and `KICAD10_` paths there (`H-K-EXPORT-MODELS`);
  - `cache`: `<cache>/<tag>/kicad-packages3D/<rel>`, `<tag>` being the tag of the model pin of major N ("3D model pins"), when the file's SHA-256 equals its entry in that folder's model stamp ("3D model fetch").
- **`${KIPRJMOD}/<rel>`**: `<project_dir>/<rel>`, source `project`, when it lies inside the project folder.
- **Any other form** (an absolute path, another variable that `expand` resolves): that file, source `in-place`, `rel` `None`.
- "Library sources" is unchanged: `locate_model` defines no path variable.

#### Scenario: The vendored copy wins
- **GIVEN** a project folder holding `3dmodels/Fenolite.3dshapes/Box_2x1.step`, and `env` setting `KICAD10_3DMODEL_DIR` to `tests/data/models`, which holds the same path
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_locate_model.py -k vendored` locates `${KICAD10_3DMODEL_DIR}/Fenolite.3dshapes/Box_2x1.step`
- **THEN** the source is `project` and the file is the project's copy

#### Scenario: The environment before the install
- **GIVEN** no project copy, `env` setting `KICAD9_3DMODEL_DIR` to `tests/data/models`, and a fake install from `tests/_libs.make_install` whose `3dmodels` folder holds the same path
- **WHEN** `${KICAD9_3DMODEL_DIR}/Fenolite.3dshapes/Box_2x1.step` is located, and then again with an empty `env`
- **THEN** the first source is `env` and the second `install`

#### Scenario: A stale cache entry is not used
- **GIVEN** a cache whose `10.0.6/kicad-packages3D` holds the file and a stamp entry with another SHA-256, and no other source
- **WHEN** the path is located with major 10
- **THEN** the result is `None`, and with the stamp entry corrected the source is `cache`

#### Scenario: Not found
- **GIVEN** no source holding the file, and no value for `KICAD10_3DMODEL_DIR`
- **WHEN** the path is located
- **THEN** the result is `None` and no exception is raised

### Requirement: 3D model pins
`src/fenolite/backends/kicad/data/libraries.toml` SHALL hold one `[[models]]` table per tag of its `[[pin]]` tables, and `fenolite.backends.kicad.libcache.load_model_pins(path=None)` SHALL return them as `ModelPin(tag, major, project, commit)` values, in file order.
- `project` MUST be `kicad/libraries/kicad-packages3D` and `commit` the 40 lowercase hex digits that the tags API gives for the tag (S-0700). There MUST be exactly one model pin per tag, and its major MUST be that of the tag's `[[pin]]` tables.
- No tree hash and no file count are pinned: the models are fetched one file at a time ("3D model fetch").
- A table that breaks these rules MUST raise `ValueError` naming the file and the key. `load_pins` MUST ignore the `[[models]]` tables and return what it returned before.

#### Scenario: Model pins of both tags
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_libcache_models.py -k pins` calls `load_model_pins()`
- **THEN** it returns two pins, `10.0.6` with major 10 and `9.0.9` with major 9, each naming `kicad/libraries/kicad-packages3D` with a 40-hex commit, and `load_pins()` still returns four pins

#### Scenario: Malformed model pin
- **GIVEN** a pins file whose `[[models]]` table has a 39-hex commit
- **WHEN** `load_model_pins(path)` is called
- **THEN** `ValueError` is raised naming the file and `commit`

### Requirement: 3D model fetch
`tools/kicad_libs_fetch.py --models PATH [PATH ...]` SHALL fetch, one file at a time, the official 3D models that the boards or footprint files `PATH` name as `${KICAD<N>_3DMODEL_DIR}/<rel>`, into `<cache>/<tag>/kicad-packages3D/<rel>` for the model pin of major N, and SHALL record each file in that folder's stamp `.fenolite-models.json`, a JSON object mapping `<rel>` to the file's SHA-256. `<cache>` is chosen as for the library fetch.
- A file whose stamp entry equals its SHA-256 MUST be reported `cached` and MUST NOT be requested.
- Otherwise the tool MUST ask the files API for the file's size and SHA-256 at the pinned commit (`HEAD https://gitlab.com/api/v4/projects/<project>/repository/files/<rel>?ref=<commit>`, headers `X-Gitlab-Size` and `X-Gitlab-Content-Sha256`; S-0024, S-0701), refuse a size above `MAX_MODEL_BYTES` (64 MiB) with exit 3, download the raw file of that commit into a temporary file under `<cache>/<tag>/`, and compare its size and SHA-256 with the headers. On equality it MUST move the file into place with `os.replace` and add its stamp entry; on a difference it MUST exit 5. A failed file MUST leave its target and the stamp as they were and remove the temporary file.
- A path whose N has no model pin, or that names no `${KICAD<N>_3DMODEL_DIR}`, MUST be reported `skipped`.
- `--verify` MUST re-hash every stamped file of the selected tags and exit 5 naming a file whose SHA-256 differs from its entry.
- The tool MUST print one line per model path, ending in `fetched`, `cached`, `skipped` or `failed`, MUST exit 0 when no file failed, and MUST NOT download a repository archive in this mode. The unit tests MUST replace the two requests and make none.

#### Scenario: Fetch and stamp
- **GIVEN** a board naming two models of one tag, a pins file with that tag's model pin, and request functions replaced by the test that answer with a size, a SHA-256 and bytes that match
- **WHEN** `uv run pytest tests/unit/test_libs_fetch_models.py -k fetch` runs the tool with `--cache C --models <board>`
- **THEN** it exits 0 reporting two `fetched`, both files are under `C/<tag>/kicad-packages3D/`, and the stamp maps both `<rel>` to their SHA-256

#### Scenario: Cached files are not requested
- **GIVEN** the cache fetched above and request functions that raise
- **WHEN** the tool runs again
- **THEN** it exits 0 reporting two `cached`

#### Scenario: Digest mismatch
- **GIVEN** request functions whose bytes do not have the announced SHA-256
- **WHEN** the tool runs
- **THEN** it exits 5, the target file does not exist, the stamp has no entry for it, and `C/<tag>/` holds no temporary file

#### Scenario: A model of another library
- **GIVEN** a board naming `${KIPRJMOD}/models/x.step` and `${KICAD8_3DMODEL_DIR}/y.step`
- **WHEN** the tool runs
- **THEN** both are reported `skipped`, no request is made, and the exit code is 0
