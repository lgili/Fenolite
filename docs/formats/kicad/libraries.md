# KiCad libraries: footprints, symbols and library tables

`fenolite.backends.kicad.mod`, `.sym` and `.libs` read KiCad footprint and symbol libraries into the
neutral definitions of `fenolite.model.library`, and resolve library identifiers through library
tables. Nothing here writes a library file. Sources are listed in `docs/evidence/sources.md`; every
fact carries a source id and an evidence label, and the hypotheses are in `docs/hypotheses.md`.

No KiCad C++ source was read for this page. The keyword file S-0047, the build file S-0044 and the
version-history files S-0030/S-0031 were consulted for names and dated facts only.

## Library identifiers

- A design names a library item as `NICKNAME:ENTRY` (S-0001, S-0046; INFERRED). The nickname is a key
  of a library table and is never stored in the library file.
- The colon separates the two parts and may appear in neither (S-0046; INFERRED).
  `split_lib_id` refuses an identifier with no colon, an empty part or a second colon
  (`kicad.lib.invalid-id`).

## Footprint libraries

- A footprint library is a folder `<Lib>.pretty/` holding one `.kicad_mod` file per footprint
  (S-0040; INFERRED). The root is `(footprint "NAME" (version V) (generator G) …)`; the body is the
  footprint syntax of the common page (S-0001).
- The file version is the board format version: 8.0 `20240108`, 9.0 `20241229`, 10.0 `20260206`
  (S-0030, `versions.md`).
- **Entry name.** The entry is named after the file stem, not the header name (`H-K-LIB-NAME-STEM`,
  KICAD-VERIFIED (9.0.x, 10.0.x): a copy of a footprint named `Other.kicad_mod` exports `Other.svg`
  on 9.0.9 and 10.0.6). In the official library at tag 10.0.6 the two are equal in every file (S-0018). A path
  whose header name differs from its stem keeps the stem and adds the warning
  `kicad.lib.name-mismatch`. Text or a parsed node has no stem, so its header name is used.
- **Library name.** Without an explicit `library`, a file inside `<Lib>.pretty/` belongs to `Lib`;
  any other input belongs to the library `""`, whose `lib_id` is the bare name.

### Footprint mapping

Each child of the root is *modelled* (represented completely), *projected* (its representable part
copied into a field; the child stays an opaque slot) or *opaque* (kept verbatim, nothing projected).

| child | field | treatment |
|---|---|---|
| name (first atom) | `name` (text inputs only) | modelled |
| `descr` | `description` | modelled |
| `attr` | `kind` (`smd`, `through_hole`; `unspecified` when the type is absent) and `flags` (the other atoms as written) | modelled |
| `tags` | `keywords`, split on whitespace | projected |
| `property` | `properties[name] = value` | projected |
| `model` | `models`, path as written, variables unexpanded | projected |
| `pad` | `pads` | modelled (its own children are slots of the pad) |
| `fp_line`, `fp_arc`, `fp_circle`, `fp_rect`, `fp_poly` | `graphics` (`line`, `arc`, `circle`, `rect`, `polygon`) | modelled, unless the graphic cannot be represented |
| anything else (`version`, `generator`, `layer`, `fp_text`, `zone`, `group`, `point`, `embedded_fonts`, unknown heads) | — | opaque |

- `attr` flags accept any symbol (S-0018; INFERRED). The official library at 10.0.6 uses flags the
  common page does not list, and an `attr` without a type.
- Every official footprint at 10.0.6 carries `Reference` and `Value` properties. `Datasheet` and
  `Description` appear in files written by the footprint editor (S-0018).

### Pads

`(pad "NUMBER" TYPE SHAPE (at X Y [ANGLE]) (size W H) [(drill …)] (layers …) …)` (S-0001).

| part | field | treatment |
|---|---|---|
| number, type, shape (leading atoms) | `number`, `kind`, `shape` | modelled; the number as written, possibly empty or repeated (S-0018) |
| `at` | `position`, `rotation` (relative to the footprint origin) | modelled |
| `size` | `size` | modelled |
| `layers` | `layers`, as written, `*` wildcards kept | modelled |
| `uuid` | `native_ids["kicad"]` (the uuid as written) | modelled |
| `(drill D)` | `drill` | modelled |
| `(drill D (offset X Y))` | `drill = D` | projected, `kicad.lib.kept-opaque` |
| `(drill oval W H)` with unequal dimensions | `drill = min(W, H)`, `Padstack.hole_shape = slot`, `hole_length = max(W, H)`, axis follows the longer dimension in the footprint frame (S-0001; axis projection is `INFERRED`) | modelled |
| other drill forms, including offsets | projected or opaque, `kicad.lib.kept-opaque` |
| `padstack` | `padstack` | projected, `kicad.lib.kept-opaque` |
| `(zone_connect N)`, N from 0 to 3 | `zone_connection` (`none`, `thermal`, `solid`, `thru_hole_only`; c0031, `board.md`, "Zone settings") | modelled; written before `uuid` when a pad without it gains a value |
| `(zone_connect N)` with another value, or repeated | `zone_connection` from the first child when it is a code from 0 to 3, else `None` | projected, `kicad.lib.kept-opaque` |
| everything else (`roundrect_rratio`, `chamfer*`, `options`, `primitives`, margins, pad properties, `thermal_bridge_width`, `thermal_gap`, `thermal_bridge_angle`) | — | opaque |

- **Drill forms** are `(drill [oval] DIAMETER [WIDTH] [(offset X Y)])` (S-0001). Oval drills occur in
  the official library (S-0018).
  - The `(offset X Y)` stays opaque in the pad's slots, and the board frame reads it from there. It is
    in the pad's own frame and moves the pad's copper, not its hole: the hole stays at the pad's `at`
    (`frame.md`; `H-G-FRAME-OFFSET`, KICAD-VERIFIED on 9.0.x and 10.0.x;
    S-0020, S-0029).
- **Padstacks** exist since board version `20240929` (S-0030; inventory row `pad-padstack`) and load on
  9.0.9 and 10.0.6 (`H-K-03`, KICAD-VERIFIED). The official library at 10.0.6 has none (S-0018).
  - The pad's own `shape` and `size` are those of its front layer, so the projection is one
    `PadstackLayer("F.Cu", shape, size)` first.
  - Then comes one entry per `(layer NAME (shape S) (size W H) …)` child, in file order, with the layer
    name as written.
  - Per-layer extras (corner ratios, offsets, thermal settings) are not modelled, so the child stays
    opaque.
  - The mode must be `front_inner_back` or `custom` (inventory row `pad-padstack-mode`).
- Pads of a definition have `net_id = None`.
- **Ids.** A pad, padstack or graphic with a uuid gets an id derived from the definition's native id
  and the uuid (`docs/design-model.md`). The official library repeats graphic uuids inside single
  files (13 libraries of the 10.0.6 install, observed by the census; S-0018), so a repeated uuid gets
  an occurrence suffix and ids stay unique.

### Graphics

| part | field | treatment |
|---|---|---|
| `start`, `mid`, `end`, `center`, `pts` | `points` | modelled: line `start end`, arc `start mid end`, circle `center end`, rect `start end`, polygon the `xy` points |
| `layer` | `layer` | modelled |
| `uuid` | `native_ids["kicad"]` | modelled |
| `fill` `yes`/`solid`/`no`/`none` | `filled` | modelled |
| `stroke` | `width` | projected; a type other than `solid` or `default` adds `kicad.lib.kept-opaque` |
| `width` (older form) | `width` | modelled |
| anything else | — | opaque |

A graphic whose geometry or fill cannot be represented is left out of `graphics`. It becomes an
opaque child of the footprint and adds `kicad.lib.kept-opaque`. This covers:

- an `arc` inside `pts` (S-0018, `H-G-PTS-ARC`);
- a hatch fill (board version `20250222`, inventory rows `fill-hatch`, `fill-reverse-hatch`,
  `fill-cross-hatch`) or any other unknown fill value;
- an `fp_rect` with a corner `radius` (board version `20250829`, inventory row `gr-rect-radius`);
- a graphic without a layer or without the points its kind needs.

## Symbol libraries

- A symbol library is a `(kicad_symbol_lib (version V) (generator G) …)` file `.kicad_sym` holding
  zero or more symbols (S-0041; INFERRED). Versions: 8.0 `20231120`, 9.0 `20241209`, 10.0 `20251024`
  (S-0031, `versions.md`).
- **Folders.** KiCad 10 also reads a folder of `.kicad_sym` files as one library (S-0046; INFERRED).
  - The official source repository stores every library as a `<Lib>.kicad_symdir/` folder at tag
    10.0.6, and as single files at 9.0.9 (S-0043).
  - The installer packs the folders into single files (`KICAD_PACK_SYM_LIBRARIES`, S-0044).
  - `read_symbol_library` treats a path as a folder when it is a directory, whatever its suffix. It
    reads every `*.kicad_sym` inside in sorted file-name order, and each file must be a
    `kicad_symbol_lib`.
  - `kicad-cli` 10.0.6 reads such a folder as one library, `extends` across files included, and
    `sym upgrade` packs it into one file (`H-K-LIB-SYMDIR`, KICAD-VERIFIED (10.0.x)). 9.0.9 refuses a
    folder with exit 3 ("Symbol file does not exist or is not accessible").
- **Library name.** Without an explicit `library`, a path gives its stem (`Mini.kicad_sym` and
  `Mini.kicad_symdir` both give `Mini`); text or a node gives `""`.

### Symbol mapping

Symbols are read-only projections in this change. Every sub-symbol is an opaque slot of its symbol,
and pins and units are projected from it.

| child | field | treatment |
|---|---|---|
| name (first atom) | `name` | modelled |
| `extends` | `extends` | modelled |
| `power`, `(power global)` | `power = "global"` | modelled |
| `(power local)` | `power = "local"` | modelled |
| `pin_names` | `pin_name_offset` (from `offset`), `pin_names_hidden` | modelled |
| `pin_numbers` | `pin_numbers_hidden` | modelled |
| `in_bom`, `on_board`, `exclude_from_sim` | booleans, defaults `True`, `True`, `False` when absent | modelled |
| `property` | `properties[name] = value` | projected |
| sub-symbol `NAME_U_S` | `units`, and the pins with `unit = U`, `body_style = S` | projected (opaque) |
| anything else (`body_styles`, `in_pos_files`, `duplicate_pin_numbers_are_jumpers`, `embedded_fonts`, unknown heads) | — | opaque |

- **Sub-symbol names** are `"<name>_<U>_<S>"`: unit U and body style S (S-0001).
  - Unit 0 is common to all units (S-0001).
  - Body style 0, common to all body styles, is observed but not documented (S-0043; INFERRED).
    Fenolite accepts it.
  - U and S are the two integers after the parent's name. Any other suffix is a `FormatError`.
- **Pins** are `(pin ETYPE STYLE (at X Y A) (length L) [hide] (name "N" …) (number "M" …)
  (alternate "NAME" ETYPE STYLE)*)` (S-0001). Each gives a `SymbolPin`.
  - Electrical types: `input`, `output`, `bidirectional`, `tri_state`, `passive`, `free`,
    `unspecified`, `power_in`, `power_out`, `open_collector`, `open_emitter`, `no_connect`.
  - Graphic styles: `line`, `inverted`, `clock`, `inverted_clock`, `input_low`, `clock_low`,
    `output_low`, `edge_clock_high`, `non_logic`.
  - Angles: 0, 90, 180 and 270 degrees only (S-0001).
  - Any other value is a `FormatError` at the pin's locator.
- **Hiding.** A pin, `pin_names` and `pin_numbers` are hidden by `(hide yes)` or by the bare atom
  `hide`. The bare form is the grammar of the common page (S-0001) and of 8.0 files, and a local
  `sym upgrade` of an 8.0 file rewrites it as `(hide yes)` (S-0020; INFERRED).
- **Power symbols** are written `(power global)` or `(power local)` in 10.0 (S-0049) and bare
  `(power)` in 9.0 (S-0043). Fenolite reads the bare form as `global`.
- **Empty-text marker.** Before symbol-library version `20250318` (S-0031), a text `~` means empty
  text; from that version on it is a literal tilde. Below that version, a pin name, a pin number, an
  alternate name or a property value equal to `~` decodes to `""`. The 9.0 and 10.0 forms of a symbol
  therefore read equal. `sym upgrade` on 10.0.6 rewrites every `"~"` of a 9.0 file as `""`, and the
  upgraded file reads equal to the original (S-0020; KICAD-VERIFIED (10.0.x),
  `test_mini_oracle.py::test_tilde_after_upgrade`).
- **Convenience properties.** `reference`, `value`, `footprint`, `datasheet` and `description` read the
  properties `Reference`, `Value`, `Footprint`, `Datasheet` and `Description`. `keywords` and
  `footprint_filters` split `ki_keywords` and `ki_fp_filters` on whitespace. The mandatory properties of
  a parent symbol are `Reference`, `Value`, `Footprint` and `Datasheet` (S-0001).

### Derived symbols

- A derived symbol `(extends "PARENT")` differs from its parent only in its properties (S-0001).
- `read_symbol_library` returns it as written, without pins.
- `resolve_extends` flattens it. Pins, units, power kind, flags and pin-name settings come from the
  parent, and the parent's properties are overlaid key by key with the derived symbol's own. Chains
  are followed, and the derived symbol keeps its id and its `extends` value (`H-K-LIB-EXTENDS`,
  INFERRED).
- An absent parent raises `kicad.lib.missing-parent`, and a loop raises `kicad.lib.extends-cycle`.

## Vocabulary and units

- Unknown heads are opaque, never errors. A value of a modelled or projected field outside its
  documented vocabulary is a `FormatError` with the file, the bare locator (`/footprint/pad[3]`) and
  the byte offset. The vocabularies:
  - pad type `smd`, `thru_hole`, `np_thru_hole`, `connect` (S-0001)
  - pad shape `circle`, `rect`, `oval`, `roundrect`, `trapezoid`, `custom` (S-0001), also inside a
    padstack layer
  - padstack mode `front_inner_back`, `custom` (S-0030)
  - pin electrical types, graphic styles and angles (above)
- A padstack layer without a shape or a size is a `FormatError`.
- Lengths must be whole nanometres and angles whole microdegrees, else `FormatError`.
- S-expression syntax errors come unchanged from `sexpr.parse`.

## Version policy

The readers follow the read path of `versions.md`:

- Files of 8.0, 9.0 and 10.0 are read, development versions between them included (with the info
  `kicad.version.dev`).
- Older files raise `UnsupportedFormatError` with a `kicad-cli fp upgrade` or `sym upgrade` hint.
  The pre-6 root `module` is refused the same way.
- Newer files are read with the warning `kicad.version.future`. Every opaque fragment of such a file
  carries the file version as its minimum version, so no writer can emit it for a known target.

**Minimum version of an opaque fragment.** It is the greatest minimum that the token inventory
(`tokens.md`) gives for the token paths inside the fragment. When the inventory has no row for the
fragment's own head, it is the file version. For example, a padstack fragment carries at least
`20240929`, and an `fp_text` fragment carries the file version.

## Library tables

- `fp-lib-table` and `sym-lib-table` files have the roots `fp_lib_table` and `sym_lib_table`
  (S-0046, S-0047; INFERRED). The keyword file of 10.0.6 and 9.0.9.1 also lists
  `design_block_lib_table`, which is out of scope and refused.
- Rows are `(lib (name N) (type T) (uri U) (options O) (descr D) [(disabled)] [(hidden)])`
  (S-0046, S-0047).
- **Two syntaxes.** 10.0 tables start with `(version 7)` and quote every atom. The 9.0.9 tables of the
  official repositories have no version and leave most atoms bare (S-0042, S-0043). Both are read
  with the generic parser.
- Unknown children are ignored with the info `kicad.lib.kept-opaque`.
- **Row state.** A disabled library is not loaded at all. A hidden library is loaded but not shown in
  library browsers (S-0046). Fenolite never resolves a disabled row (`kicad.lib.disabled`) and
  resolves hidden rows normally.
- **Duplicate nicknames.** KiCad does not allow two rows with one nickname in the same table
  (S-0046). Fenolite keeps the first row and adds the warning `kicad.lib.duplicate-nickname`.
  *This is a Fenolite choice*: no public source says what KiCad does with such a file.
- **Types.** Fenolite resolves `KiCad` rows and expands `Table` rows. Any other type gives
  `kicad.lib.unsupported-type` when it is needed.

## Path variables

- URIs and 3D model paths may contain `${NAME}` (S-0045, S-0046; INFERRED). No other substitution
  syntax is expanded. A name is resolved in this order:
  1. `KIPRJMOD`, the project folder. KiCad defines it and it cannot be redefined (S-0045).
  2. The process environment, which overrides KiCad's own configuration (S-0045).
  3. On request (`LibraryConfig.read_common`), the path variables set in KiCad: the `environment.vars`
     object of `<config>/<M>.0/kicad_common.json` (`H-K-LIB-COMMON`, KICAD-VERIFIED (10.0.x)).
  4. Fenolite defaults for the target major M: `KICAD<M>_FOOTPRINT_DIR`, `_SYMBOL_DIR`, `_3DMODEL_DIR`
     and `_TEMPLATE_DIR` point into the selected library source (below).
  5. The versioned fallback: an undefined `KICAD<k>_X` with k < M resolves as `KICAD<k+1>_X`
     (S-0045; `H-K-LIB-FALLBACK`, KICAD-VERIFIED (10.0.x)). 9.0.9 has no such fallback for
     `KICAD9_X`: the probe's library is not found there, with or without `KICAD10_X`.
- A name without a value gives `kicad.lib.unresolved-variable` when a row that needs it is used. The
  hint names the variable to set.
- **KiCad's own path variables (`kicad_common.json`).** KiCad keeps one configuration folder per version,
  path variables can be set in KiCad, and the environment overrides that configuration (S-0045). No
  public page names the file or its layout: both are observed on the file that `kicad-cli` writes into
  an empty configuration folder, key names only (S-0020; `H-K-LIB-COMMON`, KICAD-VERIFIED (10.0.x)).
  `kicad-cli` 10.0.6 and 9.0.9 both write `<M>.0/kicad_common.json` on a first run, with an `environment`
  object whose only key is `vars`; a variable added there is used, and a process variable of the same
  name wins. Fenolite's rules:
  - **Opt-in.** By default the file is not read, so a path set only there is unresolved, and the hint of
    such a name says to set `LibraryConfig.read_common`. Reading it by default would make results depend
    on the machine.
  - **Order.** Configured values rank below the process environment (S-0045) and above Fenolite's
    source defaults, which stand in for KiCad's built-in values.
  - **One major.** Only the file of the target major is read, in the folder of the global table.
  - **Content.** A missing file, a file without `environment.vars`, or `vars` set to `null` give no
    variables. Invalid JSON, or `vars` that is not an object of strings, raises `FormatError` naming
    the file and the JSON pointer. Values are used as written: `${…}` inside a value is not expanded.
  - The file is read at most once per resolver, the first time a name reaches step 3.

## Discovery and precedence

- **Project table:** `fp-lib-table` or `sym-lib-table` in the project folder (S-0046).
- **Global table:** `<config>/<M>.0/<table>` (S-0045). `<config>` is `LibraryConfig.config_home`,
  else `KICAD_CONFIG_HOME` when set (`H-K-LIB-CONFIGHOME`, KICAD-VERIFIED (10.0.x): a table directly in
  that folder, without `<M>.0/`, is not read), else the per-OS folder:
  - Linux `~/.config/kicad`
  - macOS `~/Library/Preferences/kicad`
  - Windows `%APPDATA%\kicad`
- **Template fallback (Fenolite extension).** When the global table is absent, Fenolite reads the
  template table of the selected library source instead, with origin `template`. It takes the first
  existing file of:
  - `<install>/template/<table>`
  - `${KICAD<M>_TEMPLATE_DIR}/<table>`
  - `<table>` inside the footprint or symbol folder (the layout of the official repositories, S-0042,
    S-0043)

  KiCad instead offers a choice of library setup when it first starts without a configuration
  (S-0045), so this is Fenolite's choice, made so that CI and containers resolve the official
  libraries.
- **Directory scan (Fenolite extension; `H-K-LIB-SCAN`, INFERRED).** When neither a global table nor a
  template table exists, Fenolite scans the folder that `${KICAD<M>_FOOTPRINT_DIR}` or
  `${KICAD<M>_SYMBOL_DIR}` expands to and makes one `KiCad` row per library, in sorted name order,
  with origin `scan`:
  - a footprint library is a `<X>.pretty` folder; a symbol library is a `<X>.kicad_sym` file or a
    `<X>.kicad_symdir` folder, and the file wins for one stem;
  - the nickname is `X`, and the uri is the variable followed by the folder or file name;
  - a variable without a value, or one that names no folder, gives no row.

  The scan matches KiCad's namespace only if the official nicknames equal the library stems, which the
  census checks on the install and on both fetched trees.
- **Cache sources are always scanned.** The template search is skipped for a `cache` source (below).
  A fetched tree is a source tree, not an install: its root table is the template of an install
  (S-0042, S-0043), and at 10.0.6 the symbol tree stores each library as a folder that an install packs
  into a file (S-0043, S-0044). The scan follows what is on disk.
- **Project rows only.** With `LibraryConfig.use_global_table` false, neither the global table, the
  template nor the scan is used.
- **Precedence.** Project rows come first, then global (or template, or scanned) rows. A nickname of the project
  table hides the same nickname of the global table (S-0046). A disabled row hides nothing.
- **Nested tables.** `Table` rows are expanded in place, recursively, and their rows join the
  namespace of the table that holds them (S-0046, "loaded as if they were directly listed";
  `H-K-LIB-NESTED`, KICAD-VERIFIED (9.0.x, 10.0.x): 10.0.6 expands a nested table, 9.0.9 does not).
  - Since 10.0.1, path variables are resolved in nested tables (S-0049).
  - A default 10.0 global table holds a single `Table` row pointing at the install template (S-0046).
  - A table already being expanded is skipped with the warning `kicad.lib.table-cycle`.
  - A missing nested file, or one whose path has an unresolved variable, is skipped with the warning
    `kicad.lib.missing-table`.
  - With target 9 every expanded nested table adds the info `kicad.lib.nested-table-target`, because
    nested tables are new in 10.0.
- **Relative URIs.** `kicad-cli` resolves a relative uri against its working directory, in the project
  table, a nested table and the global table alike (`H-K-LIB-RELPATH-2`, KICAD-VERIFIED (10.0.x); the
  9.0.9 outcomes agree for project and global rows). Neither the folder of the table file nor the
  project folder counts: a library next to the board is not found when `kicad-cli` runs in the parent
  folder, and a nested row `../<lib>` does not reach the folder above the nested table. The first
  statement, "the folder of the table file that holds the row" (`H-K-LIB-RELPATH`), was refuted.
  - Fenolite joins a relative uri to `LibraryConfig.project_dir`, whatever table holds the row: the
    project folder stands for the working directory of a KiCad that runs in the project, and a result
    must not depend on where the caller runs. Without `project_dir` the path stays relative.
  - A relative uri therefore works in KiCad only when KiCad is started in the project folder. Rows that
    must work everywhere use `${KIPRJMOD}` or another variable, as Fenolite's own tables do.

## Library sources

`find_library_sources(config)` reports where official libraries can be found:

- `env`: a `KICAD9_*` or `KICAD10_*` footprint or symbol folder of the environment that exists.
- `cache`: the folder `<cache>/<tag>` of a pinned tag, when its `kicad-footprints` or `kicad-symbols`
  subfolder holds a stamp equal to its pin ("Library cache", below). It is opt-in: `<cache>` is
  `LibraryConfig.cache_dir`, else `FENOLITE_LIBS_CACHE` of the environment, and no default location is
  searched, so results never depend on what a machine happens to hold. A subfolder whose stamp is
  missing or differs from its pin is not used. The stamp is trusted: the resolver never re-hashes.
- `install`: `LibraryConfig.install_dir`, or else the default install folder (S-0045):
  - macOS `/Applications/KiCad/KiCad.app/Contents/SharedSupport`
  - Linux `/usr/share/kicad`
  - Windows `C:\Program Files\KiCad\<M>.0\share\kicad`

  A path that does not exist means no install. The major comes from the version header of one
  symbol library, read from its first 4 KiB.

For target M, the defaults of step 4 come from an `env` source of major M, else from a `cache` source
of major M, else from an install of major M: an explicit, pinned source ranks above an implicit
install. A source of another major is never used, because a 9.0 KiCad refuses 10.0 files
(`versions.md`). A `cache` source defines `KICAD<M>_FOOTPRINT_DIR` and `KICAD<M>_SYMBOL_DIR` only for
its verified subfolders. It defines no `KICAD<M>_3DMODEL_DIR`, because models are not fetched, and no
`KICAD<M>_TEMPLATE_DIR`.

## Library cache

The official libraries are CC-BY-SA 4.0 as a collection (S-0048), so they are fetched into a cache
outside the repository and never committed. `tools/kicad_libs_fetch.py` makes the cache, and
`backends/kicad/libcache.py` holds its rules. These are Fenolite's choices, built on three facts.

- GitLab serves the archive of one commit through `GET /projects/:id/repository/archive[.format]` with
  `sha` (S-0096; INFERRED).
- `tarfile` extraction filters (`filter="data"`, `tarfile.data_filter`) exist from Python 3.11.4, and
  `hasattr(tarfile, "data_filter")` tells whether they do. The `data` filter refuses absolute paths,
  `..` and special files (S-0095; INFERRED).
- `os.replace` renames atomically on POSIX when it succeeds, may fail across filesystems, and fails
  when the target is a non-empty folder (S-0097; INFERRED).

- **Pins.** `backends/kicad/data/libraries.toml` pins `kicad-footprints` and `kicad-symbols` at tags
  10.0.6 and 9.0.9: the tag's commit (S-0042, S-0043), and the tree hash and file count measured on the
  first verified fetch. The archive is always requested by commit, so a moved tag cannot change what is
  fetched. The archive's own hash is not pinned: GitLab generates archives on request, and nothing
  says their bytes are stable.
- **Tree hash, scheme `fenolite-tree-1`.** One line `<sha256 hex> <size> <path>` per regular file, with
  POSIX paths relative to the folder, sorted by their UTF-8 bytes, hashed with SHA-256. Modification
  times, permissions and empty folders do not count. A symlink or a special file is refused.
- **Stamp.** `<folder>/.fenolite-verified` is a JSON object with the keys `scheme`, `tag`, `repo`,
  `commit`, `tree` and `files`. A folder is usable when its stamp equals its pin. The stamp is not part
  of the tree hash.
- **Fetch.** For each selected pin: a folder whose stamp equals the pin is `cached`. Otherwise the
  archive of the pinned commit is downloaded into a temporary file inside `<cache>/<tag>/`, extracted
  with the `data` filter into a temporary folder there, and must hold exactly one top-level folder
  whose tree hash and file count equal the pin. The stamp is then written, an older folder is moved
  aside, the new one is moved into place with `os.replace`, and the old one is removed. Temporary
  files are removed in every case, and a failure leaves the cache as it was.
- **Limits.** 1 GiB per archive and 4 GiB per extracted tree.
- **Exit codes.** 0 when nothing failed; 2 for a usage or environment problem (a Python without the
  `data` filter, before any network or cache access); 3 for bad input (a download error, a refused
  member, a link, a top level that is not one folder); 5 when a tree differs from its pin.
- **Verify.** `--verify` re-hashes the cached folders and exits 5 naming a folder that changed.
- **Location.** The tool and the tests use `--cache`, else `FENOLITE_LIBS_CACHE`, else
  `~/.cache/fenolite/libs`. The resolver uses the cache only on request (above).

## 3D models

A footprint names its 3D model files with `(model "<path>" …)`. The official footprints write
`${KICAD<N>_3DMODEL_DIR}/<library>.3dshapes/<name>.step` (or `.wrl`), N being the major the library was
written for. `LibraryResolver.locate_model(path)` finds the file, `backends/kicad/models.py` plans a STEP
run with it, and `fenolite models` lists the result (change c0116). These rows say how `kicad-cli pcb
export step` itself finds a model; they were measured on 2026-10-05 on both majors and are probed by
`tests/kicad/export/test_document_probes.py` (recorded for 10.0.6, not yet for 9.0.9).

| fact | source | label | hypothesis |
|---|---|---|---|
| `pcb export step` takes `${KICAD<N>_3DMODEL_DIR}/<rel>` from the folder that the variable names in its environment, as an absolute path or as a path relative to its working folder; a `${KIPRJMOD}/<rel>` path is read from the board's folder | S-0020, S-0029 | INFERRED | H-K-EXPORT-MODELS |
| 9.0.9 does not read a `KICAD9_` path through `KICAD10_3DMODEL_DIR`: with only that variable set the STEP holds the board alone | S-0029 | INFERRED | H-K-EXPORT-MODELS |
| With no model variable in its environment, 10.0.6 takes `KICAD9_` and `KICAD10_` paths from the `3dmodels` folder of its own install (3.1 GB in the macOS application); the pinned 9.0.9 image holds no model folder | S-0020, S-0029 | INFERRED | H-K-EXPORT-MODELS |
| A model that is not found gives the two lines `Could not add 3D model for <ref>.` and `File not found: <path as written>` on standard output for each footprint, a STEP without that body and exit 0 | S-0020, S-0029 | INFERRED | H-K-EXPORT-MODELS |
| With `--subst-models`, a `.wrl` path whose file is present gives the body of its `.step` sibling; with only the sibling present nothing is substituted and the model counts as not found; without the option a present `.wrl` exits 2 with the board alone | S-0020, S-0029 | INFERRED | H-K-EXPORT-MODELS |
| A STEP holds one `NEXT_ASSEMBLY_USAGE_OCCURRENCE` named after the reference for each footprint whose model was added | S-0020, S-0029 | INFERRED | H-K-EXPORT-MODELS |

Fenolite's choices on top of these facts:

- **Sources, in order** (`locate_model`): for `${KICAD<N>_3DMODEL_DIR}/<rel>` the project's `3dmodels/<rel>`
  (`project`), the variable in the caller's environment (`env`), the same variable in KiCad's
  `kicad_common.json` of major N, read only with `read_common` (`kicad-config`), the `3dmodels` folder of the
  install whatever its major (`install`), and `<cache>/<tag>/kicad-packages3D/<rel>` of the model pin of major N
  when the file's SHA-256 equals its stamp entry (`cache`). `${KIPRJMOD}/<rel>` is `<project>/<rel>`
  (`project`); any other path is read where it is (`in-place`). `locate_model` defines no path variable, so
  "Library sources" is unchanged: a cache still gives no `KICAD<M>_3DMODEL_DIR`.
- **The run sees only what Fenolite located.** Each located official model is copied into the run as
  `3dmodels/<rel>`, and `KICAD<N>_3DMODEL_DIR=3dmodels` is set for every N that a path of the board names,
  also when none of its paths was located, so `kicad-cli` never falls back on its install. A `.wrl` model
  brings its `.step` and `.stp` siblings of the same source.
- **Model pins.** `data/libraries.toml` holds one `[[models]]` table per pinned tag: `tag`, `major`, `project`
  (`kicad/libraries/kicad-packages3D`) and `commit`, the tag's commit from the tags API (S-0700). No tree hash
  and no file count: one install holds 3.1 GB of models, beyond the archive limits of the library fetch.
- **Fetch, one file at a time.** `tools/kicad_libs_fetch.py --models PATH…` reads the model paths that boards or
  footprint files name, asks GitLab's files API for each file's size and SHA-256 at the pinned commit (`HEAD
  …/repository/files/<rel>?ref=<commit>`, headers `X-Gitlab-Size` and `X-Gitlab-Content-Sha256`; S-0024,
  S-0701), refuses more than 64 MiB, downloads the raw file into a temporary file, and keeps it only when both
  agree. Each kept file is recorded in `<cache>/<tag>/kicad-packages3D/.fenolite-models.json`, an object that
  maps `<rel>` to the SHA-256. A stamped file is `cached` and not requested again; `--verify` re-hashes the
  stamped files. No real fetch was made for c0116 (`H-G-MODELS-FETCH` is `INFERRED`): the tests replace both
  requests and use an authored model. The official models are CC-BY-SA 4.0 with the library exception
  (S-0048): they stay in the cache and are never committed.

## Locating items

- `locate(lib_id, kind)` gives the row, its origin, the table file, the library path and the item
  path.
- A footprint library must be a folder holding `<entry>.kicad_mod`.
- A symbol library is either a file holding the top-level symbol, or a folder. In a folder the
  resolver looks for `<entry>.kicad_sym` first and scans the other files only when that file is
  absent. The parent of a derived symbol is looked up the same way in the same folder.
- `footprint` and `symbol` return definitions whose `library` is the nickname. Symbols are flattened.
- Parsed files are cached while their path, modification time and size are unchanged (16 entries).
- `missing_models(fp)` locates each 3D model path with `locate_model` ("3D models"). It returns one warning
  per path that no source holds; the message names a variable of the path that has no value. It never
  downloads anything. Nearly half of the official
  model references do not resolve on a local install: 7 324 of 14 849 on the 10.0.6 install
  (`docs/evidence/kicad-libs.md`).

## Issue codes

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

Errors are raised as `LibraryError` (CLI code `FEN-3001`); warnings and infos are appended to an issue
list. The readers also report the `kicad.version.*` issues of `versions.md`.

## Writing footprints

`mod.write_footprint(defn, *, target, allow_lossy=False, issues=None)` returns the text of one
`.kicad_mod` file for KiCad `target` (9 or 10); `mod.write_pretty(defs, …)` maps `"<name>.kicad_mod"`
to text, sorted by name. Nothing is written to disk. These are writer decisions on top of the facts
above.

| fact | source | label | hypothesis |
|---|---|---|---|
| A footprint file's header carries `(version V)`, `(generator …)` and `(generator_version …)` after the name; `V` is the footprint format constant of the target major, equal to the board constant | S-0040, S-0030 | INFERRED | H-K-LIB-READ |
| `fp upgrade --force` re-saves a footprint library in the running major's format, and `fp export svg` loads it | S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-LIB-READ |

- **Editable input only.** The writer calls `require_editable` on the version the definition was read
  at: a definition read from a future file raises `FutureFormatError` (FEN-3002). A definition without
  a slot list raises `ValueError`: generating footprints from scratch is not supported.
- **Header per target.** `(version V)`, `(generator "fenolite")` and `(generator_version "<target>.0")`
  replace the source's `version`, `generator` and `generator_version` slots in place; missing ones are
  inserted after the name, in that order.
- **Slot order.** Every other child follows the definition's slot list. Modelled children (description,
  attributes, pads, graphics) come from the footprint emitter shared with the board writer; opaque
  children are written as read. Pads and graphics are never sorted, so the output does not imitate
  KiCad's save-time order; equality is judged on the model and on load.
- **Projections.** Before an opaque child that projects a field is written, it is projected again and
  compared with the definition. An edited `Reference` or `Value` property rewrites only that
  property's value atom. Any other difference (other properties, `keywords` from `tags`, `models` from
  `model`, a graphic's width from `stroke`, a pad's padstack) is the error
  `kicad.footprint.projection-read-only`, naming the field and the locator.
- **Gating.** The written node goes through `check_emittable` for the target. A `kicad.token.too-new`
  error inside an opaque child raises `LossyWriteError` (FEN-7001); with `allow_lossy` the smallest
  opaque child holding the token is removed, with the warning `kicad.footprint.dropped-too-new`. Any
  other error aborts. A definition read from a 10.0 file may be written for target 9 when every
  fragment passes.
- **Board footprints as definitions.** `mod.board_footprints(source)` reads every footprint of a board
  as a definition, with the board's version policy and locators `/kicad_pcb/footprint[i]/…`. The
  library is the lib_id text before its first colon (`""` without a colon). Board-only children (`at`,
  `path`, `sheetname`, `sheetfile`, the placement `uuid`, pad `net`, `pinfunction`, `pintype`) are
  opaque slots, and coordinates and angles are taken as stored. Two placements of one footprint give
  equal ids, so such definitions serve round trips and comparisons, not a `Library`.

| code | severity | when |
|---|---|---|
| `kicad.footprint.dropped-too-new` | warning | `allow_lossy` removed an opaque child the target cannot read |
| `kicad.footprint.projection-read-only` | error | an edited field that the writer keeps as written |

These codes are `mod.WRITE_ISSUE_CODES`.

## Writing library tables

`libs.write_lib_table(table, *, target)` returns the text of one `fp-lib-table` or `sym-lib-table` for
KiCad `target` (9 or 10). `fenolite build` writes one beside the project, with one row per vendored
nickname of any row origin (`docs/dsl.md`, "Vendored libraries"), sorted by nickname, type `KiCad`, uri `${KIPRJMOD}/lib/<nickname>.pretty`, and empty options
and description.

| fact | source | label | hypothesis |
|---|---|---|---|
| 10.0 tables start with `(version 7)` and quote every atom; the 9.0.9 tables of the official repositories have no version line and leave atoms bare unless they need quotes | S-0042, S-0043, S-0046 | INFERRED | H-K-BUILD-LIBTABLE |
| A project table sits beside the project file, and `${KIPRJMOD}` in a row expands to the project folder | S-0045, S-0046 | INFERRED | H-K-BUILD-LIBTABLE |
| On 10.0.6, a table written for target 9 or 10 whose rows name footprints copied under `${KIPRJMOD}/lib/` is read: DRC gives no `lib_footprint_issues` and no `lib_footprint_mismatch` with the table, and `lib_footprint_issues` without it, for 9-format definitions placed in boards of either target; 9.0.9 records the same outcome for target 9 | S-0020, S-0022 | KICAD-VERIFIED (10.0.x) | H-K-BUILD-LIBTABLE |
| A build vendors the placed footprints of global and template rows too, under their own nickname with one project row each; with an empty configuration folder DRC then gives no `lib_footprint_issues` and no `lib_footprint_mismatch`, against one `lib_footprint_issues` per footprint without vendoring, on 9.0.9 and 10.0.6 | S-0038, S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-VENDOR-GLOBAL |
| A project row hides a global row with the same nickname in the library check: footprints are compared with the project row's library only, and an item missing from it gives `lib_footprint_issues` even when the global library holds it | S-0046, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-VENDOR-SHADOW |

## Licence of the official libraries

The official libraries are CC-BY-SA 4.0, with an exception for designs that use them (S-0048).
Redistributing them as a collection is not covered by the exception, so Fenolite never commits them.
Tests read them from a local install or from folders named by `KICAD*` variables, and only counts go
into `docs/evidence/kicad-libs.md`.

## Evidence

- **Readers:** `INFERRED` (`H-K-LIB-READ`). The census of `tests/libs/` is supporting data, recorded in
  `docs/evidence/kicad-libs.md`.
- **Mini library:** the authored CC0 library under `tests/data/libs/` is checked with `kicad-cli`
  (`tests/kicad/libs/`). Results are recorded below with version and date. The 9.0.9 runs used the
  pinned image of `versions.md`, run locally; the `kicad-9` and `kicad-10` jobs run the same tests.
- **Resolution:** the versioned fallback, nested tables, relative URIs, the configuration folder and
  the variables of `kicad_common.json` are settled by the `pcb-libtable-*` probes of
  `tests/kicad/libs/test_lib_tables_drc.py` (change c0021; outcomes pinned per version in
  `docs/evidence/kicad/probes/`). Each probe places an altered footprint, whose one
  `lib_footprint_mismatch` shows that its library was found. Project-over-global precedence and the
  `${NAME}` syntax stay `INFERRED` (S-0045, S-0046): they are not probed.

| check | result |
|---|---|
| mini library loads (`fp export svg`, `sym export svg`) | KICAD-VERIFIED: the 10.0 and 9.0 variants load on 10.0.6, the `Mini_v9` variants on 9.0.9, and 9.0.9 refuses the 10.0 variants (2026-10-01) |
| re-read after `fp upgrade --force` / `sym upgrade --force` equals the original, ids included | KICAD-VERIFIED on 10.0.6 (`Mini.pretty`, `Mini_v9.pretty`, `Mini.kicad_sym`) and 9.0.9 (`Mini_v9.pretty`, `Mini_v9.kicad_sym`) (2026-10-01) |
| `~` rule: `Mini_v9.kicad_sym` upgraded by 10.0.6 reads equal | KICAD-VERIFIED (10.0.6, 2026-10-01) |

KiCad sorts what it writes: graphics and pads of a footprint, symbols of a library (derived symbols
last), and pins. 10.0.6 orders pins by number, while 9.0.9 orders them by position. The mini library
is written in that order, with pin numbers following positions, so a re-save keeps every tuple in place
(S-0020).

Fenolite's simple authored symbol subset writes the KiCad symbol-library root, symbol properties,
one-unit pin records, and library-table rows as described by S-0043. The emitted serialization remains
`INFERRED` until exercised by the KiCad oracle.

## Net-tie groups (c0114)

A footprint that joins pads of different nets on purpose lists them in one child,
`(net_tie_pad_groups "1, 2" …)`: one string per group, the pad numbers separated by commas.

| fact | source | label | hypothesis |
|---|---|---|---|
| A footprint file written with `(net_tie_pad_groups "1, 2")` right after `attr`, one string per group and `", "` between the numbers, loads in `kicad-cli`, and its DRC honours the group (`drc.md`, "Net ties") | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-NETTIE-DRC |
| The footprints of KiCad's own net-tie library write the child in that form and at that place, and join their pads with a filled polygon on each copper layer | S-0018, S-0042 | INFERRED | H-K-NETTIE-DRC |
| `"1,2"`, without the space, is read as the same group | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-NETTIE-DRC |

The second row is the reading of the two library trees that change c0114 states (twelve footprints, read
for the fact on 2026-10-05); this change did not fetch them again, so the row rests on the first.

- **Reading.** `read_footprint` projects the child into `FootprintDef.net_ties`: each string is one
  group, split at commas, with the spaces around a number and empty parts dropped. The child stays an
  opaque slot and is written back as read.
- **Writing.** A definition read from a file keeps its child: a `net_ties` that differs from it, or groups
  on a definition without the child, give `kicad.footprint.projection-read-only`. An authored definition
  (`fenolite.dsl.Footprint.net_tie`) is written from the field, the child right after `attr`; without
  groups no child is written, so its text is the one written before the field existed.
