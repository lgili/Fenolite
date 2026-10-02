## MODIFIED Requirements

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

## ADDED Requirements

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
- Symbols: each library is counted the same way. Equal means that the install's `<X>.kicad_sym` and the cache's `<X>.kicad_symdir` folder or `<X>.kicad_sym` file read to the same flattened definitions, ignoring provenance and `ext`, because the install packs folders into files (S-0044).

The counts SHALL be written only to the report file named by `FENOLITE_CENSUS_OUT`. A difference MUST NOT fail the test. `docs/evidence/kicad-libs.md` MAY claim that an install equals its pinned tag only when every count other than "equal" is 0.

#### Scenario: Install of 10.0.6 compared with its pin
- **GIVEN** the local 10.0.6 install, a verified 10.0.6 cache and `FENOLITE_CENSUS_OUT` naming a file under a temporary folder
- **WHEN** `uv run pytest -m needs_libs tests/libs/test_install_pin.py` runs
- **THEN** the four counts for footprints and for symbol libraries are written to that file, and `git status --porcelain` is unchanged

#### Scenario: No cache of the install's major
- **GIVEN** an install of major 10 and `FENOLITE_LIBS_CACHE` naming a folder without a verified 10.0.6 tree
- **WHEN** the same command runs
- **THEN** the test is skipped with a reason naming the 10.0.6 cache and `tools/kicad_libs_fetch.py`
