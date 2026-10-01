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
| `(drill oval W H …)`, any other drill form | `drill = None` | opaque, `kicad.lib.kept-opaque` |
| `padstack` | `padstack` | projected, `kicad.lib.kept-opaque` |
| everything else (`roundrect_rratio`, `chamfer*`, `options`, `primitives`, margins, pad properties) | — | opaque |

- **Drill forms** are `(drill [oval] DIAMETER [WIDTH] [(offset X Y)])` (S-0001). Oval drills occur in
  the official library (S-0018).
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
  3. Fenolite defaults for the target major M: `KICAD<M>_FOOTPRINT_DIR`, `_SYMBOL_DIR`, `_3DMODEL_DIR`
     and `_TEMPLATE_DIR` point into the selected library source (below).
  4. The versioned fallback: an undefined `KICAD<k>_X` with k < M resolves as `KICAD<k+1>_X`
     (S-0045; `H-K-LIB-FALLBACK`, INFERRED).
- A name without a value gives `kicad.lib.unresolved-variable` when a row that needs it is used. The
  hint names the variable to set.
- **Limitation.** Values set in KiCad's own preferences (`kicad_common.json`) are not read. A path
  set only there is unresolved for Fenolite.

## Discovery and precedence

- **Project table:** `fp-lib-table` or `sym-lib-table` in the project folder (S-0046).
- **Global table:** `<config>/<M>.0/<table>` (S-0045). `<config>` is `LibraryConfig.config_home`,
  else `KICAD_CONFIG_HOME` when set (`H-K-LIB-CONFIGHOME`, INFERRED), else the per-OS folder:
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
- **Precedence.** Project rows come first, then global (or template) rows. A nickname of the project
  table hides the same nickname of the global table (S-0046). A disabled row hides nothing.
- **Nested tables.** `Table` rows are expanded in place, recursively, and their rows join the
  namespace of the table that holds them (S-0046, "loaded as if they were directly listed";
  `H-K-LIB-NESTED`, INFERRED).
  - Since 10.0.1, path variables are resolved in nested tables (S-0049).
  - A default 10.0 global table holds a single `Table` row pointing at the install template (S-0046).
  - A table already being expanded is skipped with the warning `kicad.lib.table-cycle`.
  - A missing nested file, or one whose path has an unresolved variable, is skipped with the warning
    `kicad.lib.missing-table`.
  - With target 9 every expanded nested table adds the info `kicad.lib.nested-table-target`, because
    nested tables are new in 10.0.
- **Relative URIs** resolve against the folder of the table file that holds the row: the project
  folder for project rows, the nested table's folder for nested rows (`H-K-LIB-RELPATH`, INFERRED).

## Library sources

`find_library_sources(config)` reports where official libraries can be found:

- `env`: a `KICAD9_*` or `KICAD10_*` footprint or symbol folder of the environment that exists.
- `install`: `LibraryConfig.install_dir`, or else the default install folder (S-0045):
  - macOS `/Applications/KiCad/KiCad.app/Contents/SharedSupport`
  - Linux `/usr/share/kicad`
  - Windows `C:\Program Files\KiCad\<M>.0\share\kicad`

  A path that does not exist means no install. The major comes from the version header of one
  symbol library, read from its first 4 KiB.

For target M, the defaults of step 3 come from an `env` source of major M, else from an install of
major M. An install of another major is never used, because a 9.0 KiCad refuses 10.0 files
(`versions.md`).

## Locating items

- `locate(lib_id, kind)` gives the row, its origin, the table file, the library path and the item
  path.
- A footprint library must be a folder holding `<entry>.kicad_mod`.
- A symbol library is either a file holding the top-level symbol, or a folder. In a folder the
  resolver looks for `<entry>.kicad_sym` first and scans the other files only when that file is
  absent. The parent of a derived symbol is looked up the same way in the same folder.
- `footprint` and `symbol` return definitions whose `library` is the nickname. Symbols are flattened.
- Parsed files are cached while their path, modification time and size are unchanged (16 entries).
- `missing_models(fp)` expands each 3D model path. It returns one warning per path that names no
  existing file or has an unresolved variable. It never downloads anything. Nearly half of the official
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
- **Resolution:** precedence, variables, the fallback, nested tables, relative URIs and the
  configuration folder are `INFERRED` (S-0045, S-0046) until the follow-up change runs their probes.

| check | result |
|---|---|
| mini library loads (`fp export svg`, `sym export svg`) | KICAD-VERIFIED: the 10.0 and 9.0 variants load on 10.0.6, the `Mini_v9` variants on 9.0.9, and 9.0.9 refuses the 10.0 variants (2026-10-01) |
| re-read after `fp upgrade --force` / `sym upgrade --force` equals the original, ids included | KICAD-VERIFIED on 10.0.6 (`Mini.pretty`, `Mini_v9.pretty`, `Mini.kicad_sym`) and 9.0.9 (`Mini_v9.pretty`, `Mini_v9.kicad_sym`) (2026-10-01) |
| `~` rule: `Mini_v9.kicad_sym` upgraded by 10.0.6 reads equal | KICAD-VERIFIED (10.0.6, 2026-10-01) |

KiCad sorts what it writes: graphics and pads of a footprint, symbols of a library (derived symbols
last), and pins. 10.0.6 orders pins by number, while 9.0.9 orders them by position. The mini library
is written in that order, with pin numbers following positions, so a re-save keeps every tuple in place
(S-0020).
