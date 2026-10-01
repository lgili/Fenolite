## Context

- A design refers to library items by a *library identifier* `"NICKNAME:ENTRY"` (dev-docs, S-0001; Schematic Editor manual, S-0046). The nickname is a key of a library table and is never stored inside a library file, and a colon is forbidden in nicknames and entry names. Identifiers appear in schematic `lib_id`s, in the `Footprint` property of symbols and on footprints placed in boards.
- **Footprints.** A footprint library is a folder `<Lib>.pretty/` with one `.kicad_mod` file per footprint (S-0040). The file version equals the board version constant (8.0 `20240108`, 9.0 `20241229`, 10.0 `20260206`; c0007, S-0030). Observations on the official library at tag 10.0.6 (S-0042, 15 450 files):
  - the header name equals the file stem in every file
  - `attr` may lack its type and carries undocumented flags
  - pad numbers may be empty or repeated
  - drills may be oval
  - layer lists use `*` wildcards
  - 3D model paths use `${KICAD10_3DMODEL_DIR}`, and half of them do not resolve on a local install
  - padstacks are absent from the library, although the grammar exists since 9.0 (`20240929`, S-0030)
  - every file carries `Reference` and `Value` properties; `Datasheet` and `Description` appear only in files written by the footprint editor
- **Symbols.** A symbol library is a `(kicad_symbol_lib …)` file (S-0041) with versions 8.0 `20231120`, 9.0 `20241209` and 10.0 `20251024` (c0007, S-0031).
  - Top-level symbols contain sub-symbols `NAME_U_S` (unit U, body style S). S = 0 is observed but not documented (S-0043).
  - Derived symbols use `(extends "PARENT")` and carry only properties (S-0041, S-0043).
  - Power symbols are written `(power global|local)` in 10.0 and bare `(power)` in 9.0 (S-0043, S-0049).
  - Before symbol-library version `20250318`, a text `~` meant empty text; from that version on it is a literal tilde (S-0031). A local `kicad-cli sym upgrade` of a 9.0 file rewrites `(name "~")` and `(property "Datasheet" "~")` to `""` (S-0020).
  - The 8.0 grammar writes `(pin_numbers hide)` and `(pin_names (offset X) hide)` with a bare atom; 9.0 and 10.0 write `(hide yes)` (S-0041; the local `sym upgrade` of an 8.0 file rewrites the bare form, S-0020).
  - In 10.0 the official *source* repository stores each library as a folder `<Lib>.kicad_symdir/` with one file per symbol. The installer packs these folders into single `.kicad_sym` files (S-0043, S-0044). User projects may use either form in 10.0 (S-0046).
- **Tables.** `fp-lib-table`/`sym-lib-table` rows are `(lib (name) (type) (uri) (options) (descr) [(disabled)] [(hidden)])` (S-0046; keyword names confirmed in S-0047).
  - 10.0 tables start with `(version 7)` and quote their atoms. The 9.0.9 official table has no version and bare atoms (S-0042).
  - The project table takes precedence over the global table (S-0046).
  - 10.0 adds nested `(type "Table")` rows. A default 10.0 user global table holds a single `Table` row pointing at the install template (S-0042, observed locally). Path variables in nested tables are resolved since 10.0.1 (S-0049).
  - Global tables live in a per-OS, per-major user configuration folder, and `KICAD_CONFIG_HOME` overrides its base (S-0045).
  - Path variables are written `${NAME}`. The process environment overrides KiCad's configuration, and `KIPRJMOD` is the project folder and cannot be overridden. A missing `KICAD9_X` falls back to `KICAD10_X` (S-0045).
- **Licence.** The official libraries are CC-BY-SA 4.0 with an exception for designs that use them. Redistributing them as a collection is not covered by the exception (S-0048). The ip-hygiene capability already forbids committing them.
- **Upstream changes.** c0006 provides `sexpr` (`Atom`, `Node`, `parse`, `load`, `dumps`, `walk`, locators `/head/child[i]`), `slots` (`split`, `to_ext`, `from_ext`), the required-resource mode and the `kicad-10` job. c0007 provides `versions` (`FileKind`, constants, `kind_of`, `inspect`, `require_readable`, `require_editable`, `version_issues`, `min_version`), the token inventory and the `kicad-9` job, which runs `tests/kicad` in required mode with `kicad-cli` 9.0.9. Both merge before this change.
- **Environment.** KiCad 10.0.6 is installed locally. Three sampled files of its `footprints/` folder and its template `fp-lib-table` were byte-identical to tag 10.0.6 (S-0042); whole-tree identity is not claimed. No 9.0 install is available; 9.0 behaviour comes from the `kicad-9` job.

## Goals / Non-Goals

**Goals:**
- Neutral, immutable library definitions that later changes (board backend, checks, DSL) consume without knowing KiCad files.
- Readers for `.kicad_mod`, `.kicad_sym` and `.kicad_symdir` in the 8.0, 9.0 and 10.0 formats. They are lossless in the slot sense, strict on the vocabulary they model, and never assert what the file does not say.
- A resolver that finds the same file KiCad would for the common configurations: project table, global table, install template, path variables and nested tables. Every failure is a typed, located issue.
- An authored mini library that `kicad-cli` 9.0.9 and 10.0.6 load.

**Non-Goals:**
- Writing any library file or table, and placing footprints in boards (board backend change).
- Symbol body drawings, footprint texts, text boxes, dimensions, zones, groups and points. Custom-pad primitives and non-round drills are not modelled either. All of these stay as opaque slots.
- Library types other than `KiCad` and `Table`, design-block tables, and files older than 8.0.
- The items moved to the follow-up change (Decision 18).
- 3D model fetching, footprint generation, library linting, a CLI command, and a CI job for library tests.
- Neutral layer naming: layer names stay as the backend writes them (`F.CrtYd`). Mapping them to `Layer` kinds is the board backend's job.
- Axis conventions: coordinates are stored as written in the file.

## Decisions

1. **Library definitions live in `fenolite.model.library`, outside `Design`.** Definitions are reference data shared by many designs. They are not state of one design, so they do not appear in `.fenolite/` and the six-file layout of `canonical-serialization` is unchanged. `Library(name, footprints, symbols)` is the schema root of `schemas/fenolite.model.v0/library.json` (`fenolite.library.v0`). `fenolite.model.schema` gains `LIBRARY_SCHEMA`, and `tools/gen_schemas.py` gains one target, covered by the drift test.
   - Rejected: a seventh layer file `library.json` in `.fenolite/`. It would modify a normative requirement for data that is not per-design.
   - Rejected: keeping definitions inside `backends.kicad`. Checks and the DSL must not import a backend (`package-layering`).

2. **Reuse board entities, add value types for symbols.** `FootprintDef.pads: tuple[Pad, …]` and `graphics: tuple[Graphic, …]` reuse `fenolite.model.board`, with `Pad.net_id = None` and positions relative to the footprint origin. A per-layer pad uses the existing `Pad.padstack: Padstack` (Decision 5).
   - Symbol pins are plain value objects: `SymbolPin`, `PinAlternate` and `SymbolUnit` are frozen dataclasses without the entity header, like `PadstackLayer`. A pin is identified by `(unit, body_style, number)`.
   - `PinType` is reused from `fenolite.model.circuit`. `PinShape` and `PowerKind` are new literals.
   - Every collection field has a default (`field(default=())` or `default_factory=dict`), so the dataclasses construct without a `TypeError`. Order-semantic tuples (`keywords`, `flags`, `pads`, `graphics`, `models`, `units`, `pins`, `alternates`) carry `metadata=ORDERED`, so `canonical.to_data` keeps file order.
   - `properties` is a `dict[str, str]`. Canonical form sorts it by key; the file order of properties survives only in the slot list, which is enough for a later writer.
   - No existing dataclass changes, so `board.json` and `circuit.json` do not drift.
   - Rejected: a separate `PadDef`, which duplicates `Pad`. Rejected: entity pins, which bring thousands of ids per library with no consumer. Rejected: properties as ordered pairs, which complicates every lookup for an order no consumer needs.

3. **Ids.** The closed prefix table gains `fpd` (footprint definition) and `sym` (symbol definition).
   - A definition's native id is `"<library>:<name>"`, or `"<name>"` when `library` is empty. Its id is `derived_id(prefix, "kicad", native)`. Reading the same item twice gives the same id; the same file under two nicknames gives two ids.
   - Sub-entities are scoped to their definition. Pads, graphics and padstacks with a `(uuid U)` use `derived_id(prefix, "kicad", f"{native}:{U}")` (a padstack uses its pad's uuid plus `:padstack`). Without a uuid they use `content_id(prefix, "kicad", native, "pad" | "gfx", digest)`, where the digest covers the normalised content plus an occurrence counter among identical contents.
   - A uuid repeated inside one definition keeps that form for its first occurrence; its k-th repetition uses `f"{native}:{U}:{k}"`. The installed 10.0.6 footprints repeat graphic uuids inside single files in 13 libraries (observed by the census; S-0018), so the plain rule alone would collide.
   - Ids are therefore unique within a `Library`, even when two files share copied uuids. The census asserts this (Decision 17). Placing a footprint twice on a board needs distinct pad ids; the board backend change re-derives them from the placement.
   - Rejected: ids from the file hash (forbidden by `design-model`). Rejected: ids from the item index, which changes when another pad is inserted.

4. **Reader inputs.**
   - `read_footprint(source, *, library=None, file="", issues=None)`: an `os.PathLike` is a file, a `str` is file text, and a `Node` is an already parsed tree. The entry name is the file stem for a path and the header name otherwise.
   - `library=None` means the default: for a path whose parent folder ends in `.pretty`, the folder stem; otherwise `""`. With `library == ""`, `lib_id` is the bare name.
   - A header name that differs from the stem appends the warning `kicad.lib.name-mismatch` (`H-K-LIB-NAME-STEM`).
   - `issues` is an optional list that receives warnings and infos. Errors are raised: `FormatError` with `file`, a locator and an offset.
   - **Locators.** `FormatError.locator` and `Provenance.locator` both use the bare `kicad-sexpr` locator form (`/footprint/pad[1]`), without a scheme prefix. `Provenance.locator` is opaque outside the backend (`design-model`), so no prefix is needed to tell it apart.
   - The same conventions apply to `read_symbol_library`, where the default library is the file or folder stem.
   - Rejected: returning `(def, issues)` tuples, which break the signatures agreed across changes.

5. **Slots: modelled, projected or opaque.** A child is `Modeled` only when the model represents it completely. When a child is only partly represented, it stays `Opaque` and the representable part is *projected* into the field. When a child cannot be represented at all, it is `Opaque` and nothing is projected.
   - **How slots are built.** `slots.split` classifies by head only. The readers call it with the heads that may be modelled, then post-process its result: a slot whose value is not completely representable is replaced (`dataclasses.replace` on the slot tuple) by `Opaque(dumps(child, style="compact"), mv)`. `mv` is the greatest `versions.min_version(kind, path)` over the token paths inside the fragment. When the fragment's own head has no inventory row, `mv` is the file version, as `kicad-slots` requires. Slot lists go into `ext["kicad"]` through `slots.to_ext`.
   - **Footprint root.**
     - modelled: `descr` → `description`, `attr` → `kind` + `flags`, `pad` → `pads`, `fp_line|fp_arc|fp_circle|fp_rect|fp_poly` → `graphics`
     - projected: `tags` → `keywords` (split on whitespace; the original spacing stays in the fragment), `property` → `properties[name] = value`, `model` → `models` (path as written)
     - opaque: everything else (`version`, `generator`, `layer`, `fp_text`, `zone`, `group`, `point`, `embedded_fonts`, `duplicate_pad_numbers_are_jumpers`, unknown heads)
   - **Pad.**
     - positional: number, kind, shape
     - modelled: `at` → `position` + `rotation`, `size`, `layers` (atoms as written, wildcards kept), `uuid` → `native_ids`, and `drill` only in the form `(drill D)`
     - other drill forms: an oval drill gives `drill = None`; an offset drill projects `drill = D`. Both stay opaque and add the info `kicad.lib.kept-opaque`.
     - `padstack` is projected: `Pad.padstack` gets one `PadstackLayer(layer, shape, size)` for the pad's own front layer (`F.Cu`, from the pad's `shape` and `size`, which the grammar defines as the front layer) and one per `(layer NAME (shape S) (size W H) …)` child, in file order, with layer names as written. The child stays opaque with `kicad.lib.kept-opaque`, because per-layer extras (ratios, offsets, thermal settings) are not modelled. `mode` must be `front_inner_back` or `custom`, and each layer must give a shape and a size; anything else is a `FormatError` (Decision 6). `Pad.padstack` is never `None` for a pad that has a `padstack` child.
     - `roundrect_rratio`, `chamfer*`, `options`, `primitives`, pad properties and margins are opaque in `pad.ext["kicad"]`.
   - **Graphic.**
     - modelled: `start`/`mid`/`end`/`center`/`pts` → `points`, `layer`, `uuid`, and `fill yes|solid|no|none` → `filled`
     - `stroke` is always projected: its width goes into `width`, and the child stays opaque, because the model cannot tell `solid` from `default`. A type other than `solid` or `default` adds `kicad.lib.kept-opaque`.
     - A graphic whose geometry or fill cannot be represented is a whole opaque child of the footprint, is absent from `graphics`, and adds `kicad.lib.kept-opaque`. This covers an `arc` inside `pts`, a hatch fill, an unknown fill value, and an `fp_rect` with a corner radius (board version `20250829`; the token name is the one of the c0007 inventory row).
   - **Symbols** are read-only projections in this change. Every sub-symbol is an opaque slot, and pins and units are projected from it. Writing symbols belongs to the schematic change.
   - Rejected: storing sub-trees in model fields (the model must not know S-expressions). Rejected: dropping partial children (breaks the slot rule). Rejected: `padstack = None` for a padstack pad, which the model defines as "one shape on all layers" and would be false.

6. **Strict vocabularies, tolerant structure.** Unknown heads are opaque, never errors. Values of modelled or projected fields must belong to the documented vocabulary; otherwise `FormatError` is raised with the locator. The documented vocabulary covers:
   - pad kind `smd|thru_hole|np_thru_hole|connect` and pad shape `circle|rect|oval|roundrect|trapezoid|custom` (S-0040, S-0042), also inside padstack layers
   - padstack mode `front_inner_back|custom` (S-0030; c0007 inventory)
   - the twelve pin electrical types and nine graphic styles (S-0041, S-0043)
   - pin angles `0|90|180|270` (S-0041)

   Lengths go through `Atom.to_nm(exact=True)` and angles through `core.units.parse_angle`, so a value that is not a whole number of nm or µdeg is a `FormatError`. `attr` flags accept any symbol atom, because the official library uses undocumented flags (`allow_soldermask_bridges`, `allow_missing_courtyard`, `dnp`; S-0042).
   - Rejected: lenient coercion of unknown enum values. A silent `passive` for an unknown pin type would corrupt ERC and netlists.

7. **Symbol mapping.**
   - Sub-symbol names are `"<name>_<U>_<S>"`. U and S are parsed from the last two `_`-separated integers after stripping the parent name, and S may be 0 (common to all body styles). A malformed suffix is a `FormatError`.
   - `(power)` and `(power global)` both give `power = "global"`, and `(power local)` gives `"local"`.
   - A pin is hidden by `(hide yes)` or by the bare atom `hide`.
   - `pin_names` sets `pin_name_offset` from `(offset X)` and `pin_names_hidden` from either `(hide yes)` or a bare `hide` atom; `pin_numbers` sets `pin_numbers_hidden` the same way. The bare form is the 8.0 grammar (S-0041).
   - **Empty-text marker.** When the file version is below `20250318` (S-0031), a pin name, a pin number, an alternate name or a property value equal to `~` decodes to `""`. From `20250318` on, `~` is kept literally. The 9.0 and 10.0 forms of the same symbol therefore give equal definitions. The rule is a documented fact of `docs/formats/kicad/libraries.md` (S-0031, S-0020) and is checked by the oracle test (Decision 17).
   - `in_bom`, `on_board` and `exclude_from_sim` map to booleans. Their defaults when absent are `True`, `True` and `False`.
   - All properties go into `properties`. Convenience properties read `Reference`, `Value`, `Footprint`, `Datasheet` and `Description`, and split `ki_keywords` and `ki_fp_filters` on whitespace.

8. **Derived symbols are flattened by a separate step.** `read_symbol_library` returns symbols as written, so a derived symbol has `extends` set and no pins. `resolve_extends(symbols, *, issues=None)` returns flattened definitions:
   - pins, units, power, flags and pin-name settings come from the parent
   - properties are the parent's, overlaid key by key with the derived symbol's
   - chains are followed, a cycle raises `LibraryError(kicad.lib.extends-cycle)`, and a missing parent raises `LibraryError(kicad.lib.missing-parent)`
   - the derived symbol keeps its own id and its `extends` value

   The resolver always returns flattened symbols. Inheritance of non-mandatory properties is `H-K-LIB-EXTENDS`.
   - Rejected: flattening inside the reader, which hides what the file says and makes folder reads load every parent eagerly.

9. **`.kicad_symdir` folders.** `read_symbol_library(path)` dispatches on `Path.is_dir()`, not on the suffix. For a folder, every `*.kicad_sym` file inside it is read in sorted file-name order, and each file must be a `kicad_symbol_lib`. The resolver looks for `<entry>.kicad_sym` first and scans the folder only if that file is absent. The parent of a derived symbol is looked up in the same folder (`H-K-LIB-SYMDIR`).

10. **Version policy is the read path of `kicad-version-gating`.** Library definitions are read-only in this change, so the readers call `info = versions.inspect(node)` and `versions.require_readable(info)`, and append `versions.version_issues(info)` to `issues`:
    - older than 8.0: `UnsupportedFormatError` (`FEN-3003`), with a hint to run `kicad-cli fp upgrade` or `sym upgrade`
    - 8.0, 9.0 and 10.0, including development versions: read; a development version adds the info `kicad.version.dev`
    - newer than the newest known version: read, with the warning `kicad.version.future`. Every opaque fragment of such a file carries the file version as its minimum, so a later writer refuses to emit it for any known target, and the board backend calls `require_editable` before embedding a definition.

    The pre-6 root `module` raises `UnsupportedFormatError` through `versions.kind_of`. Any other root that is not `footprint` or `kicad_symbol_lib` is a `FormatError`.
    - Rejected: refusing future files. `kicad-version-gating` makes future files readable and refuses only editing; libraries follow it without an exception.

11. **Library tables through the generic parser.** `read_lib_table` parses with `sexpr.parse`, so quoted and bare atoms are handled alike.
    - `version` is optional.
    - Rows keep their order and all six fields plus `disabled`/`hidden`.
    - Unknown row children are ignored with the info `kicad.lib.kept-opaque`.
    - A root other than `fp_lib_table`/`sym_lib_table` is a `FormatError`, including `design_block_lib_table`, which is out of scope.
    - A duplicate nickname within one table keeps the first row and adds the warning `kicad.lib.duplicate-nickname`. This is a Fenolite choice with no public source; KiCad may refuse such a table instead. The docs page labels it as such.

12. **Path variables.** `${NAME}` is the only substitution syntax. A name is resolved in this order:
    1. `KIPRJMOD` = the project folder, which nothing overrides
    2. the process environment (`LibraryConfig.env`, default a snapshot of `os.environ`)
    3. Fenolite defaults for the target major M: `KICAD<M>_FOOTPRINT_DIR`, `_SYMBOL_DIR`, `_3DMODEL_DIR` and `_TEMPLATE_DIR` point into the selected library source (Decision 14)
    4. the versioned fallback: `KICAD<k>_X` with k < M resolves as `KICAD<k+1>_X` (S-0045; `H-K-LIB-FALLBACK`)

    An unresolved name makes the row unusable and gives the error `kicad.lib.unresolved-variable`, naming the variable. It is raised only when that row is needed. Values set in KiCad's own configuration (`kicad_common.json`) are not read in this change; the docs page states this limitation.
    - Rejected: expanding `$(NAME)` or `%NAME%`, which have no public source.

13. **Table discovery and precedence.**
    - **Project table**: `fp-lib-table` or `sym-lib-table` in `project_dir`.
    - **Global table**: `<config>/<M>.0/<table>`. `<config>` is `LibraryConfig.config_home`, else `KICAD_CONFIG_HOME` if set (`H-K-LIB-CONFIGHOME`), otherwise the per-OS base: Linux `~/.config/kicad`, macOS `~/Library/Preferences/kicad`, Windows `%APPDATA%\kicad` (S-0045).
    - **Missing global table**: Fenolite substitutes the template table of the selected source, first found of `<install>/template/<table>` (install source), `${KICAD<M>_TEMPLATE_DIR}/<table>`, and `<table>` inside the footprint or symbol folder (the layout of the official repositories, S-0042, S-0043). Its rows have origin `template`. This fallback is a Fenolite extension, labelled as such. With no template, only project rows exist.
    - **Effective rows**: project rows first, then global (or template) rows. A nickname found in the project table hides the global one (S-0046).
    - **Nested rows**: `type "Table"` rows are expanded in place, recursively. The nested rows join the nickname namespace of the table that holds them (`H-K-LIB-NESTED`).
      - A cycle adds the warning `kicad.lib.table-cycle` and skips the repeated table.
      - A missing nested file adds the warning `kicad.lib.missing-table`. A dangling template reference exists in a real 10.0.6 install (S-0042).
      - With target 9, a nested row adds the info `kicad.lib.nested-table-target`.
    - **Relative uris** resolve against the folder of the table file that holds the row: the project folder for project rows, the nested table's folder for nested rows (`H-K-LIB-RELPATH`).
    - **Row state**: `disabled` rows never resolve (`kicad.lib.disabled`). `hidden` rows resolve normally (S-0046).
    - Rejected: silently merging nicknames across tables in file order (contradicts S-0046). Rejected: failing when the global table is absent, which is the normal state in CI and containers.

14. **Library sources.** `find_library_sources(config)` returns `LibrarySource(kind, root, major)` for two kinds of source:
    - **Explicit variables** (`env`): `KICAD9_*` or `KICAD10_*` library folders set in the environment.
    - **Local install** (`install`): `LibraryConfig.install_dir`, or when it is `None` the per-OS default share folder (macOS bundle `Contents/SharedSupport`, Linux `/usr/share/kicad`, Windows `C:\Program Files\KiCad\<M>.0\share\kicad`; S-0045). A path that does not exist means no install. Its major comes from the version header of one `.kicad_sym` file, read from the first 4 KiB.

    The source for target M is an `env` source of major M, else an install of major M. With neither, the library variables stay unresolved and the error hint says to set `KICAD<M>_FOOTPRINT_DIR` and `KICAD<M>_SYMBOL_DIR`.
    - Rejected: using a 10.0 install for target 9. KiCad 9 refuses 10.0 files (c0007 gating).

15. **Resolver and issues.** `LibraryResolver(config)` loads the tables lazily on first use and keeps table-level issues in `.issues`. Lookups go through three methods:
    - `locate(lib_id, kind) -> Location` gives the row, origin, table, library path and item path, so agents can explain a resolution.
    - `footprint(lib_id)` and `symbol(lib_id)` return definitions with `library` set to the nickname. Symbols are flattened.
    - Every lookup failure raises `LibraryError`. `LibraryError.issue` is an `Issue` whose code is one of the error rows below.

    `LibraryError` and the code constants live in the leaf module `backends/kicad/liberrors.py`, which imports only `core`. `sym.py` and `libs.py` import it, and `libs.py` and `backends/kicad/__init__.py` re-export it, so there is no `sym` ↔ `libs` import cycle. `LibraryError.cli_code = "FEN-3001"` (registered: input missing or unreadable), so the c0007 dispatcher maps it to exit 3 with the issue message instead of `FEN-1001`.

    Parsed files are cached by `(path, mtime_ns, size)` in a bounded LRU of 16 entries. The closed issue set:

    | code | severity | when |
    |---|---|---|
    | `kicad.lib.invalid-id` | error | no colon, empty part, or a second colon |
    | `kicad.lib.unknown-nickname` | error | nickname in no effective row |
    | `kicad.lib.disabled` | error | nickname only in disabled rows |
    | `kicad.lib.unsupported-type` | error | row type other than `KiCad` and `Table` |
    | `kicad.lib.unresolved-variable` | error | `${NAME}` without a value |
    | `kicad.lib.missing-library` | error | expanded path does not exist or has the wrong kind |
    | `kicad.lib.missing-entry` | error | item absent from an existing library |
    | `kicad.lib.missing-parent` | error | `extends` names an absent symbol |
    | `kicad.lib.extends-cycle` | error | `extends` chain loops |
    | `kicad.lib.duplicate-nickname` | warning | second row with the same nickname in one table |
    | `kicad.lib.table-cycle` | warning | nested table already on the path |
    | `kicad.lib.missing-table` | warning | nested table file absent |
    | `kicad.lib.name-mismatch` | warning | footprint header name ≠ file stem |
    | `kicad.lib.missing-3d-model` | warning | `missing_models()` finds no file, or a model path has an unresolved variable |
    | `kicad.lib.kept-opaque` | info | partly or not representable child kept opaque |
    | `kicad.lib.nested-table-target` | info | nested rows used with target 9 |

    The readers also append the `kicad.version.*` issues of `kicad-version-gating`; those codes belong to that capability. `missing_models(fp)` expands each model path with the same variables. It returns warnings only, never raises, and never downloads anything. Nearly half of the official references do not resolve on a normal install (S-0042).

16. **Authored mini library (CC0).** It lives under `tests/data/libs/` and is declared `origin = "authored"` in `tests/data/MANIFEST.toml`. Its geometry is synthetic and explicitly not a validated land pattern. Every name starts with `Mini`, so it cannot be confused with official items.
    - `Mini.pretty/` (10.0):
      - `Mini_R_0603` (SMD, roundrect pads, `fp_rect` courtyard, 3D path to a non-existent model)
      - `Mini_LED_THT_3mm` (through-hole, `*.Cu` wildcards, `fp_circle`/`fp_arc`)
      - `Mini_QFP-32_7x7mm_P0.8mm` (32 SMD pads, courtyard from `fp_line`s, `fp_poly` on silkscreen)
      - `Mini_Edge_Cases` (duplicate pad numbers, empty-number NPTH, oval drill, custom pad, a `padstack` pad in mode `front_inner_back`, `fp_text`)
    - `Mini_v9.pretty/Mini_R_0603.kicad_mod` in 9.0 format.
    - `Mini.kicad_sym` (10.0):
      - `Mini_R`, `Mini_LED`, and `Mini_LED_Red`, which extends `Mini_LED`
      - `Mini_GND` (power global, hidden `power_in` pin of length 0)
      - `Mini_QFP32_IC` (32 pins, one alternate, one hidden pin, one pin named `""`)
      - `Mini_DualGate` (units `_1_1 _1_2 _2_1 _2_2 _3_0` with `body_styles demorgan`)
    - `Mini_v9.kicad_sym` (9.0): `Mini_GND` with bare `(power)`, and `Mini_QFP32_IC` whose empty pin name is written `~` and whose `Datasheet` is `~`.
    - `project/fp-lib-table` and `project/sym-lib-table` (10.0 syntax): `${KIPRJMOD}` rows, one relative row, one disabled row, one hidden row, one `Legacy` row and one `Table` row. The `Table` row points to `project/nested/fp-lib-table`, which uses 9.0 syntax (bare atoms, no version) and holds the relative row `NestedMini` → `../../Mini_v9.pretty`.
    - The `.kicad_symdir` form is generated at test time from `Mini.kicad_sym` by `tests/_libs.py::make_symdir`, so no content is committed twice.
    - **Re-save stability.** Every footprint carries the properties `Reference`, `Value`, `Datasheet` and `Description`, and every symbol carries `Reference`, `Value`, `Footprint`, `Datasheet` and `Description`, in the order KiCad writes them, because a KiCad re-save adds missing mandatory properties (S-0020). Every pad, graphic and padstack pad carries a `uuid`, because a re-save gives uuid-less pads a random one.
    - Rejected: trimmed copies of official items. They are derived from a CC-BY-SA collection and would trip the residue test.

17. **Tests and oracles.**
    - Unit tests use the mini library and inline strings.
    - **Census** (`needs_libs`, `slow`, `tests/libs/`) over the `env` or `install` source of each major found:
      - every footprint and symbol reads without exception
      - pad and pin counts equal the counts of `pad` and `pin` nodes in the parsed tree
      - ids are unique within each `Library`
      - every `extends` parent is found
      - `Device:R` and `Resistor_SMD:R_0603_1608Metric` resolve through the template tables
      - the `Footprint` property of every symbol is resolved: empty values are skipped and counted apart, and failures are counted by code (`missing-entry`, `unknown-nickname`, `invalid-id`)
      - footprints whose `fp_poly` or custom-pad `gr_poly` `pts` contains an `arc` are counted (supporting data for c0005's `H-G-PTS-ARC`)
      - `missing_models` warnings are counted
    - The census writes its counts, time and source to the JSON file named by `FENOLITE_CENSUS_OUT` when set, and never to a tracked file. A closing task copies the numbers into `docs/evidence/kicad-libs.md` (public numbers only).
    - **Oracle tests** (`needs_kicad`, `tests/kicad/libs/`) read the running major with `tests/_resources.kicad_cli_major()` (reusing c0007's helper when it has one). They run in `tmp_path` with `KICAD_CONFIG_HOME` set to an empty folder, so the user's tables and variables cannot affect them. They pick fixtures per major: on 10.0 the 10.0 and 9.0 variants, on 9.0 only the `Mini_v9` variants.
      - the fixtures load with `fp export svg` and `sym export svg`
      - re-reading after `fp upgrade --force` and `sym upgrade --force` gives definitions equal except for provenance and `ext`. The `-o` target is a not-yet-existing child of `tmp_path`, because `kicad-cli` refuses an existing output path.
      - on 10.0, `Mini_v9.kicad_sym` upgraded by `kicad-cli` reads equal to the original (`~` rule)
      - on 9.0, loading the 10.0 fixtures is asserted to fail (expected refusal); the `.kicad_symdir` probe is `xfail(strict=False)` with its outcome recorded
      - the hypothesis probes of the table below

18. **Moved to a follow-up change.** The planned budget cannot hold them. A follow-up change with its own budget line (about one week) takes them, with these constraints recorded now:
    - `tools/kicad_libs_fetch.py`, `backends/kicad/data/libraries.toml` (commit and tree-hash pins for `kicad-footprints` and `kicad-symbols` at 10.0.6 and 9.0.9) and a `cache` source kind. The tool extracts into `tempfile.mkdtemp(dir=<cache>/<tag>)` and moves with `os.replace`, so the rename never crosses filesystems. It requires `tarfile.data_filter` (Python ≥ 3.11.4) and exits 2 with a clear message otherwise. After a successful check it writes `<cache>/<tag>/<dir>/.fenolite-verified` (tree hash, file count); sources compare the stamp with the pin, and `--verify` re-hashes on demand.
    - The 9.0.9 and fetched-10.0.6 census, a check of the install tree against the 10.0.6 pin, and the residue comparison against the cache.
    - `kicad_common.json` variables and the directory-scan fallback.
    - Demo-library corpus rows tagged `rt0` and `libs`, the `kicad-10` fetch extended with `--uses libs`, and a test that rebuilds the demo project layout in `tmp_path` before resolving.
    - The DRC harness (`H-K-LIB-DRC`, and the probes of `H-K-LIB-RELPATH`, `-FALLBACK`, `-NESTED`, `-CONFIGHOME`). Its criterion names the DRC JSON violation type observed on 10.0.6 (`lib_footprint_issues` on a copy of a demo board); every run sets `KICAD_CONFIG_HOME` to an empty folder and passes the tested variables explicitly.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/model/library.py` | `FootprintKind = Literal["smd", "through_hole", "unspecified"]`; `PinShape` (9 literals); `PowerKind = Literal["", "global", "local"]`; `@dataclass(frozen=True, slots=True) class FootprintDef(Entity)`: `name: str`, `library: str = ""`, `description: str = ""`, `keywords: tuple[str, ...] = field(default=(), metadata=ORDERED)`, `kind: FootprintKind = "unspecified"`, `flags` (ORDERED), `properties: dict[str, str] = field(default_factory=dict)`, `pads: tuple[Pad, ...]` (ORDERED), `graphics: tuple[Graphic, ...]` (ORDERED), `models: tuple[str, ...]` (ORDERED), all defaulting to `()`; properties `lib_id`, `reference`, `value`; `graphics_on(layer: str) -> tuple[Graphic, ...]`; `class PinAlternate(name: str, etype: PinType, shape: PinShape)`; `class SymbolPin(number: str, name: str, etype: PinType, position: Point, shape: PinShape = "line", rotation: Udeg = 0, length: Nm = 0, unit: int = 0, body_style: int = 0, hidden: bool = False, alternates: tuple[PinAlternate, ...] = ())` (alternates ORDERED); `class SymbolUnit(unit: int, body_style: int, name: str = "")`; `class SymbolDef(Entity)`: `name: str`, `library = ""`, `extends = ""`, `power: PowerKind = ""`, `properties: dict[str, str] = field(default_factory=dict)`, `in_bom = True`, `on_board = True`, `exclude_from_sim = False`, `pin_names_hidden = False`, `pin_numbers_hidden = False`, `pin_name_offset: Nm \| None = None`, `units: tuple[SymbolUnit, ...] = ()` (ORDERED), `pins: tuple[SymbolPin, ...] = ()` (ORDERED); properties `lib_id`, `reference`, `value`, `footprint`, `datasheet`, `description`, `keywords`, `footprint_filters`, `unit_count`, `body_style_count`; `pins_of(unit: int, body_style: int = 1) -> tuple[SymbolPin, ...]` (includes unit 0 and body style 0); `class Library(name: str = "", footprints: tuple[FootprintDef, ...] = (), symbols: tuple[SymbolDef, ...] = ())` |
| `src/fenolite/model/schema.py` | `LIBRARY_SCHEMA: tuple[str, str, str] = ("library.json", "fenolite.library.v0", "fenolite.model.library:Library")` |
| `src/fenolite/core/ids.py` | `PREFIXES` gains `"fpd"`, `"sym"` |
| `src/fenolite/backends/kicad/liberrors.py` | `class LibraryError(FenoliteError)` with `issue: Issue` and `cli_code = "FEN-3001"`; `ISSUE_CODES: Mapping[str, Severity]` (the table of Decision 15); imports only `core` |
| `src/fenolite/backends/kicad/mod.py` | `read_footprint(source: str \| os.PathLike[str] \| Node, *, library: str \| None = None, file: str = "", issues: list[Issue] \| None = None) -> FootprintDef`; `FOOTPRINT_FIELDS`, `PAD_FIELDS`, `GRAPHIC_HEADS` (slot maps); `EVIDENCE: Evidence` |
| `src/fenolite/backends/kicad/sym.py` | `read_symbol_library(source: str \| os.PathLike[str] \| Node, *, library: str \| None = None, file: str = "", issues: list[Issue] \| None = None) -> tuple[SymbolDef, ...]`; `resolve_extends(symbols: Sequence[SymbolDef], *, issues: list[Issue] \| None = None) -> tuple[SymbolDef, ...]`; `split_unit_name(parent: str, name: str) -> tuple[int, int]`; `EVIDENCE: Evidence` |
| `src/fenolite/backends/kicad/libs.py` | `TableKind = Literal["footprint", "symbol"]`; `RowOrigin = Literal["project", "global", "template"]`; re-export of `LibraryError`; `split_lib_id(lib_id: str) -> tuple[str, str]`; `@dataclass(frozen=True, slots=True) class LibRow(nickname, type, uri, options="", descr="", disabled=False, hidden=False)`; `class LibTable(kind: TableKind, rows: tuple[LibRow, ...], version: int \| None = None, path: str = "")`; `read_lib_table(source: str \| os.PathLike[str], *, file: str = "", issues: list[Issue] \| None = None) -> LibTable`; `class LibrarySource(kind: Literal["env", "install"], root: Path, major: int)`; `find_library_sources(config: LibraryConfig) -> tuple[LibrarySource, ...]`; `class LibraryConfig(target_major: int = 10, project_dir: Path \| None = None, env: Mapping[str, str] \| None = None, config_home: Path \| None = None, install_dir: Path \| None = None, use_global_table: bool = True)`; `class Location(lib_id, kind, row: LibRow, origin: RowOrigin, table: str, library_path: Path, item_path: Path)`; `class LibraryResolver` with `__init__(config: LibraryConfig = LibraryConfig())`, `issues`, `variables() -> dict[str, str]`, `expand(text: str, *, row_table: str = "") -> str`, `rows(kind: TableKind) -> tuple[tuple[LibRow, RowOrigin, str], ...]`, `locate(lib_id: str, kind: TableKind) -> Location`, `footprint(lib_id: str) -> FootprintDef`, `symbol(lib_id: str) -> SymbolDef`, `missing_models(fp: FootprintDef) -> tuple[Issue, ...]` |
| `src/fenolite/backends/kicad/__init__.py` | re-exports `read_footprint`, `read_symbol_library`, `resolve_extends`, `LibraryResolver`, `LibraryConfig`, `LibraryError`, `split_lib_id` |
| `src/fenolite/backends/kicad/PROVENANCE.md` | rows for footprint grammar, symbol grammar, tables, path variables, library layout and licence |
| `schemas/fenolite.model.v0/library.json` | generated |
| `tests/_resources.py` | `kicad_library_dirs()` extended to the `KICAD9_*` variables and the per-OS installs; `kicad_install_dir()` honouring `FENOLITE_KICAD_INSTALL_DIR` (a missing path means no install); `kicad_cli_major() -> int \| None` |
| `tests/conftest.py` | `needs_libs` skip message of the modified `Skip markers` requirement |
| `tests/_libs.py` | `MINI = Path("tests/data/libs")`, `make_symdir(src: Path, dst: Path) -> Path`, `isolated_kicad_env(tmp_path) -> dict[str, str]` |
| `tests/unit/model/test_library.py`, `tests/unit/backends/kicad/test_mod.py`, `test_mod_pads.py`, `test_sym.py`, `test_sym_extends.py`, `test_lib_table.py`, `test_lib_vars.py`, `test_libs_sources.py`, `test_resolver_rows.py`, `test_resolver.py`, `tests/unit/test_conftest_libs.py` | hermetic tests |
| `tests/libs/README.md`, `tests/libs/test_official_read.py`, `tests/libs/test_official_resolve.py` | `needs_libs` (+ `slow`) census |
| `tests/kicad/libs/test_mini_oracle.py`, `tests/kicad/libs/test_lib_hypotheses.py` | `needs_kicad`, major-aware |
| `tests/data/libs/**` | authored fixtures (Decision 16) |
| `docs/formats/kicad/libraries.md` | facts with source ids, labels and hypotheses |
| `docs/design-model.md` | section "Library definitions" |
| `docs/evidence/kicad-libs.md` | census results (counts per source, no content) |

Layering: `model.library` imports `core` and `model.board`/`model.circuit`. `backends.kicad.{mod,sym,libs,liberrors}` import `core`, `model`, and `backends.kicad.{sexpr,slots,versions,liberrors}`; `libs` imports `mod` and `sym`, and neither imports `libs`. All edges stay within `package-layering`.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0040 | https://dev-docs.kicad.org/en/file-formats/sexpr-footprint/index.html | not stated on the page (to verify) | `.kicad_mod`: one footprint per file, header, `attr`, pads, drills, custom pads, 3D model; third-party generator names |
| S-0041 | https://dev-docs.kicad.org/en/file-formats/sexpr-symbol-lib/index.html | not stated on the page (to verify) | `.kicad_sym`: header, symbols, sub-symbol naming, `extends`, pins, electrical types and graphic styles, mandatory properties, bare `hide` forms |
| S-0042 | https://gitlab.com/kicad/libraries/kicad-footprints/-/tree/10.0.6 (also `/-/tree/9.0.9`); tags https://gitlab.com/api/v4/projects/kicad%2Flibraries%2Fkicad-footprints/repository/tags/10.0.6 and `…/tags/9.0.9` | CC-BY-SA-4.0 with library exception | observed footprint tokens and counts, `fp-lib-table` syntax per tag, tag commits; three sampled install files byte-identical to 10.0.6 |
| S-0043 | https://gitlab.com/kicad/libraries/kicad-symbols/-/tree/10.0.6 (also `/-/tree/9.0.9`); tags https://gitlab.com/api/v4/projects/kicad%2Flibraries%2Fkicad-symbols/repository/tags/10.0.6 and `…/tags/9.0.9` | CC-BY-SA-4.0 with library exception | `.kicad_symdir` layout, `sym-lib-table`, body style 0, `(power)` in 9.0, alternates, derived-symbol content |
| S-0044 | https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/10.0.6/CMakeLists.txt | repository licence (fact only) | symbol folders packed into single files at install (`KICAD_PACK_SYM_LIBRARIES`) |
| S-0045 | https://docs.kicad.org/10.0/en/kicad/kicad.html (also `/9.0/`) | to verify on the page | configuration folders, `KICAD_CONFIG_HOME`, template tables, path variables, precedence of environment, `KIPRJMOD`, versioned fallback |
| S-0046 | https://docs.kicad.org/10.0/en/eeschema/eeschema.html (also `/9.0/`) | to verify on the page | library tables, types, project-over-global precedence, `disabled`/`hidden`, nested tables, folder libraries, colon rule |
| S-0047 | https://gitlab.com/kicad/code/kicad/-/blob/10.0.6/common/lib_table.keywords (also at 9.0.9.1) | GPL-3.0-or-later (keyword names only) | table vocabulary identical in 9.0 and 10.0 |
| S-0048 | https://gitlab.com/kicad/libraries/kicad-footprints/-/blob/10.0.6/LICENSE.md and https://www.kicad.org/libraries/license/ | CC-BY-SA-4.0 (licence text) | library licence, exception, redistribution rule |
| S-0049 | https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/ and https://www.kicad.org/blog/2026/04/KiCad-10.0.1-Release/ | to verify on the page | local power symbols, STEP-only models; path variables in nested tables (10.0.1) |

Rows of other changes cited here are S-0001 (library identifier), S-0020 (observed `kicad-cli` 10.0.6 behaviour, c0006), S-0030 (board version history, padstack and rounded-rectangle versions) and S-0031 (symbol-library version history, the `~` change at `20250318`), both c0007. If a URL above is already registered when this change is implemented, the existing id is cited and the row is not duplicated. Only S-0047 and the version-history files of S-0030/S-0031 come from the KiCad source tree; they are read for names and dated facts only.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-LIB-READ | The readers' projection of every official footprint and symbol is what KiCad loads | supporting: `tests/libs/test_official_read.py` (census); settling: the round trip of the writer change (board backend) | supporting data recorded: 0 read errors and equal counts per source; `CORPUS-VERIFIED` only when the writer round trip holds on manifest files from ≥ 2 origins |
| H-K-LIB-NAME-STEM | KiCad names a footprint library item after its file stem, not its header name | `tests/kicad/libs/test_lib_hypotheses.py::test_name_stem`: copy the major's `Mini_R_0603.kicad_mod` to `Other.kicad_mod` in a temporary `.pretty`, then run `kicad-cli fp export svg` | the SVG is named after `Other`, on 10.0.6 and 9.0.9 |
| H-K-LIB-SYMDIR | `kicad-cli` 10 reads a `.kicad_symdir` folder as one library, resolving `extends` across its files | `test_lib_hypotheses.py::test_symdir`: `sym export svg` on the generated folder (load oracle), and `sym upgrade --force -o <tmp>/packed.kicad_sym` on it, then re-read the packed file | on 10.0.6: exit 0, one SVG per symbol, and the packed re-read gives the same flattened definitions; the 9.0.9 outcome is recorded (`xfail`, non-strict) |
| H-K-LIB-EXTENDS | A derived symbol inherits pins, units, flags and the parent properties it does not redefine | placeholder `tests/kicad/test_sch_netlist.py::test_derived_symbol_pins`, owned by the schematic backend change (task "netlist export of an authored schematic placing `Mini_LED_Red`") | exported pins and fields equal `resolve_extends` output |
| H-K-LIB-RELPATH | A relative `uri` resolves against the folder of the table file holding the row | placeholder `tests/kicad/libs/test_lib_tables_drc.py::test_relpath` (follow-up change) | no library violation on 10.0.6 |
| H-K-LIB-FALLBACK | `${KICAD9_X}` resolves to `KICAD10_X` in `kicad-cli` 10 when `KICAD9_X` is undefined | placeholder `test_lib_tables_drc.py::test_fallback` (follow-up change) | no library violation on 10.0.6 |
| H-K-LIB-NESTED | Rows of a nested `Table` join the parent namespace (`Nick:Item` unchanged) in 10.0; 9.0 does not expand them | placeholder `test_lib_tables_drc.py::test_nested` (follow-up change) | no violation on 10.0.6; a violation on 9.0.9 |
| H-K-LIB-CONFIGHOME | With `KICAD_CONFIG_HOME=D`, the global table is read from `D/<M>.0/` | placeholder `test_lib_tables_drc.py::test_config_home` (follow-up change) | no library violation on 10.0.6 |

The resolver's behaviour does not depend on the outcome of the placeholder rows; they stay `INFERRED` until the follow-up change runs them.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Footprint and symbol reading (fields, pads, padstacks, graphics, units, pins, alternates, power, flags) | INFERRED (`H-K-LIB-READ`), with the install census as recorded supporting data | unit tests, `tests/libs/test_official_read.py` |
| Mini library valid for KiCad | KICAD-VERIFIED on 10.0.6 (local and `kicad-10`) and on 9.0.9 for the `Mini_v9` files (`kicad-9`) | `tests/kicad/libs/test_mini_oracle.py` |
| Reader invariance under a KiCad re-save | KICAD-VERIFIED on 10.0.6 and 9.0.9 | `test_mini_oracle.py::test_reread_after_upgrade` |
| `~` decoding before `20250318` | KICAD-VERIFIED (10.0.6) | `test_mini_oracle.py::test_tilde_after_upgrade` |
| Bare `hide` in `pin_names`/`pin_numbers` | INFERRED (S-0041, observation S-0020) | unit tests |
| Vocabulary rejections, version policy | mechanical (unit tests); census rejections recorded as supporting data | unit tests, census |
| `extends` flattening | INFERRED (`H-K-LIB-EXTENDS`) | `test_sym_extends.py`, census |
| `.kicad_symdir` reading | KICAD-VERIFIED (10.0.6) if `H-K-LIB-SYMDIR` holds, otherwise INFERRED | probe |
| Table parsing (both syntaxes) | INFERRED (S-0046, S-0047); the install template tables parse in the census | `test_lib_table.py`, `test_official_resolve.py` |
| Precedence, variables, fallback, nested, relative, config home | INFERRED (S-0045, S-0046) with `H-K-LIB-*` | `test_lib_vars.py`, `test_resolver_rows.py`, `test_resolver.py` |
| Library sources | mechanical (no format claim) | `test_libs_sources.py`, `tests/unit/test_conftest_libs.py` |
| Missing 3D models as warnings | mechanical; the count is recorded | census |

`EVIDENCE` in `mod.py` and `sym.py` is `INFERRED` and stays so after this change. Every `Provenance` created by the readers carries it.

## Budget (about 1.5 weeks; the plan line was half a week)

| work | days |
|---|---|
| sources, hypotheses, provenance rows, format page | 0.5 |
| model, ids, schema | 0.75 |
| mini library and first load test | 0.75 |
| footprint reader (root, slots, version policy; pads, padstacks, graphics, ids) | 1.5 |
| symbol reader, folders, `extends` | 1.0 |
| tables, variables, sources | 0.75 |
| effective rows and resolver | 1.0 |
| test resources, install census | 0.5 |
| oracle tests on both majors, closing | 0.5 |
| **total** | **7.25** |

The overrun against the plan's half week is stated here and in the proposal. The items of Decision 18 add about one week in their own change.

## Risks / Trade-offs

- [Pure-Python parsing of the whole symbol collection (about 220 MB packed) is slow] → the census is marked `slow`; the resolver parses one library at a time behind the LRU; folder entries are read per file. The throughput is recorded.
- [Resolver semantics diverge from KiCad in a corner case] → every rule is labelled and tied to a hypothesis; `locate()` exposes the table, origin and path so a divergence is diagnosable; template rows carry their origin.
- [Users who set path variables only in KiCad's preferences get `unresolved-variable`] → the hint names the variable; the docs page states the limitation; the follow-up change reads `kicad_common.json`.
- [Layer names in library definitions are KiCad names] → documented as backend names, like `Board.layers`; the board backend maps them.
- [Projected fields (`properties`, `models`, `keywords`, `width`, `padstack`) diverge from their opaque source after an edit] → definitions are read-only in this change; the board writer change must reconcile projections before re-emitting them.
- [The `kicad-9` job rejects a fixture or a probe outcome differs] → oracle tests are major-aware; expected 9.0 refusals are explicit assertions, and the only unknown 9.0 outcome (folder libraries) is a non-strict `xfail`.
- [Budget overruns further] → the `H-K-LIB-SYMDIR` probe and the census resolve test are dropped first. The model, readers, resolver, mini library and oracle load tests are not optional.

## Migration Plan

- Additive: new modules, two id prefixes and one schema file. `board.json`/`circuit.json` are unchanged. To roll back, remove the modules, the prefixes and `library.json`.

## Open Questions

- Should `LibraryError` get its own registered code (for example `FEN-3004`, "library item cannot be resolved") when the first command uses the resolver? The default is `FEN-3001`, which exists today.
- c0007's design writes locators with a `sexpr:` prefix in an example; this change uses the bare `kicad-sexpr` form everywhere. c0007 should drop the prefix from its example so the three changes agree.
- Should library definitions get a canonical on-disk cache (for example `~/.cache/fenolite/libdefs/`) for speed? The default is no, until profiling shows a need.
- Several counts in `docs/evidence/kicad-libs.md` come from the official libraries. They are public numbers, but a reviewer must confirm that the file quotes no library content.
