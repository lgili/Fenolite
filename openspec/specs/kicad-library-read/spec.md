# kicad-library-read Specification

## Purpose
Read KiCad footprint libraries (`.kicad_mod`) and symbol libraries (`.kicad_sym` files and `.kicad_symdir` folders) of KiCad 8.0 to 10.0 into the neutral, read-only definitions of `fenolite.model.library`. The readers keep unmodelled content as slots, reject values outside the documented vocabularies with located errors, follow the version policy of `kicad-version-gating`, and flatten derived symbols in a separate step. Facts and sources: `docs/formats/kicad/libraries.md`.
## Requirements
### Requirement: Footprint file reading
`fenolite.backends.kicad.mod.read_footprint(source, *, library=None, file="", issues=None)` SHALL accept an `os.PathLike` (a `.kicad_mod` file), a `str` (file text) or a parsed `Node`, and SHALL return one `FootprintDef`.
- For a path, `name` MUST be the file stem.
- For text or a node, `name` MUST be the header name.
- When a path's header name differs from its stem, the reader MUST append a warning `Issue` with code `kicad.lib.name-mismatch` to `issues` (when a list is given) and keep the stem.
- A given `library` MUST be copied into the definition. When `library` is `None`, it MUST default to the stem of the parent folder for a path whose parent folder ends in `.pretty`, and to `""` otherwise.
- With `library == ""`, `lib_id` MUST be the bare name.

#### Scenario: Mini resistor read from a path
- **GIVEN** `tests/data/libs/Mini.pretty/Mini_R_0603.kicad_mod`
- **WHEN** `read_footprint(Path(...))` is called without `library`
- **THEN** the result has `name == "Mini_R_0603"`, `library == "Mini"`, `lib_id == "Mini:Mini_R_0603"`, `kind == "smd"` and two pads numbered `"1"` and `"2"` with shape `roundrect`

#### Scenario: Header name differs from the file stem
- **GIVEN** a copy of the mini resistor saved as `Other.kicad_mod`
- **WHEN** it is read with an `issues` list
- **THEN** `name == "Other"` and `issues` holds one warning `kicad.lib.name-mismatch` naming both names

#### Scenario: Text input uses the header name and no library
- **WHEN** `read_footprint('(footprint "X" (version 20260206) (generator "t") (layer "F.Cu"))')` is called
- **THEN** the result has `name == "X"`, `library == ""`, `lib_id == "X"`, no pads and no graphics

### Requirement: Footprint content mapping
The reader SHALL map a footprint's children as follows.
- `descr` → `description`
- `tags` → `keywords`, split on whitespace (a projection)
- `attr` → `kind` (`smd`, `through_hole`, or `unspecified` when the type is absent) and `flags` (the remaining atoms as written, any symbol accepted)
- `property` → `properties[name] = value` (a projection)
- `model` → `models`, the path as written with variables unexpanded (a projection)
- `pad` → `pads`, as `Pad` entities with `net_id = None`, in file order
- `fp_line`, `fp_arc`, `fp_circle`, `fp_rect` and `fp_poly` → `graphics`, as `Graphic` entities of kind `line`, `arc`, `circle`, `rect` and `polygon`, in file order; the stroke width → `width` (a projection)

Pads MUST carry:
- `number` as written (possibly empty, possibly repeated)
- `kind` and `shape`
- `position` and `rotation`, relative to the footprint origin
- `size`
- `layers` as written, wildcards included
- `drill` in nanometres for the form `(drill D)`
- `padstack` when the pad has a `padstack` child: one `PadstackLayer` for the pad's front layer `F.Cu` from the pad's own shape and size, then one per `(layer NAME (shape S) (size W H) …)` child in file order, with layer names as written

All lengths MUST be integer nanometres and all angles integer microdegrees.

#### Scenario: Through-hole LED
- **GIVEN** `Mini_LED_THT_3mm.kicad_mod`
- **WHEN** it is read
- **THEN** `kind == "through_hole"`, both pads have `kind == "thru_hole"`, `layers == ("*.Cu", "*.Mask")` and an integer `drill`

#### Scenario: Attribute without a type
- **GIVEN** a footprint with `(attr exclude_from_pos_files exclude_from_bom)`
- **WHEN** it is read
- **THEN** `kind == "unspecified"` and `flags == ("exclude_from_pos_files", "exclude_from_bom")`

#### Scenario: Duplicate and empty pad numbers are kept
- **GIVEN** `Mini_Edge_Cases.kicad_mod`, which has two pads numbered `"1"` and one `np_thru_hole` pad numbered `""`
- **WHEN** it is read
- **THEN** all three pads are present in file order with distinct ids

#### Scenario: Padstack pad keeps its padstack
- **GIVEN** the `padstack` pad of `Mini_Edge_Cases.kicad_mod`, in mode `front_inner_back` with layers `Inner` and `B.Cu`
- **WHEN** it is read
- **THEN** `pad.padstack is not None`, its layers are `F.Cu`, `Inner` and `B.Cu` in that order, each with a shape and a size in nanometres, and the `padstack` child is an `Opaque` slot whose `min_version` is not older than `20240929`

#### Scenario: Courtyard graphics are selectable
- **GIVEN** `Mini_QFP-32_7x7mm_P0.8mm.kicad_mod`
- **WHEN** `graphics_on("F.CrtYd")` is called on the result
- **THEN** it returns the `line` graphics of the courtyard, each with two points in nanometres

### Requirement: Unmodelled footprint content is kept as slots
The reader MUST record the slot list of the footprint in `ext["kicad"]`, and the slot list of every pad and graphic in its own `ext["kicad"]`, using the encoding of `kicad-slots`.
- A child the model represents completely MUST be a `Modeled` slot.
- A child the model represents only partly MUST be an `Opaque` slot, with the representable part projected into the model field. This covers `tags`, a property, a model, every `stroke`, a padstack and a drill with an offset.
- A pad drill that is not a single diameter MUST give `drill = None` and stay opaque.
- A graphic whose geometry or fill cannot be represented MUST NOT appear in `graphics`. It MUST be an `Opaque` slot of the footprint. This covers an `arc` inside `pts`, a hatch or unknown fill, and an `fp_rect` with a corner radius.
- Every opaque slot that loses modelled meaning MUST add the info `kicad.lib.kept-opaque`. This covers an oval or offset drill, a padstack, a stroke type other than `solid` or `default`, and every unrepresentable graphic.

An opaque fragment MUST carry as minimum version the greatest minimum that the `kicad-token-inventory` gives for the token paths inside it, and the file version when the inventory has no row for the fragment's own head.

#### Scenario: Unknown child survives in place
- **GIVEN** a footprint whose third child is `(frobnicate 1)`
- **WHEN** it is read and `slots.from_ext(fp.ext["kicad"])` is inspected
- **THEN** the third slot is `Opaque` with fragment `(frobnicate 1)`

#### Scenario: Oval drill is kept opaque
- **GIVEN** a pad with `(drill oval 1.2 2.0)`
- **WHEN** it is read with an `issues` list
- **THEN** the pad has `drill is None`, its `ext["kicad"]` holds the drill fragment, and `issues` holds one info `kicad.lib.kept-opaque`

#### Scenario: Property is projected, not modelled
- **GIVEN** a footprint with `(property "Reference" "REF**" (at 0 -1.5 0) (layer "F.SilkS") (effects ...))`
- **WHEN** it is read
- **THEN** `properties["Reference"] == "REF**"` and the property child is an `Opaque` slot that includes its `effects`

#### Scenario: Stroke is projected
- **GIVEN** an `fp_line` with `(stroke (width 0.12) (type solid))`
- **WHEN** it is read
- **THEN** the graphic has `width == 120000` and its `stroke` child is an `Opaque` slot of the graphic

#### Scenario: Arc inside a polygon keeps the graphic opaque
- **GIVEN** an `fp_poly` whose `pts` contains `(arc (start 0 0) (mid 1 1) (end 2 0))`
- **WHEN** it is read with an `issues` list
- **THEN** the polygon is absent from `graphics`, it is an `Opaque` slot of the footprint, and `issues` holds one info `kicad.lib.kept-opaque`

### Requirement: Invalid modelled values are rejected
The readers MUST raise `FormatError` with `file`, a locator and the byte offset in these cases:
- a modelled or projected field holds a value outside its documented vocabulary: pad kind, pad shape (also inside a padstack layer), padstack mode, pin electrical type, pin graphic style, or pin angle other than 0/90/180/270
- a padstack layer lacks a shape or a size
- a length is not a whole number of nanometres, or an angle is not a whole number of microdegrees
- the root head is not `footprint` (for `read_footprint`) or `kicad_symbol_lib` (for `read_symbol_library`); the pre-6 root `module` MUST raise the `UnsupportedFormatError` of `kicad-version-gating`

`FormatError.locator` and `Provenance.locator` MUST both use the bare locator form of `kicad-sexpr` (`/head/child[index]`), without a prefix. S-expression syntax errors MUST propagate unchanged from `sexpr.parse`.

#### Scenario: Unknown pad type
- **GIVEN** a footprint whose fourth pad is `(pad "4" bogus rect ...)`
- **WHEN** it is read
- **THEN** a `FormatError` is raised with `locator == "/footprint/pad[3]"` and a message naming `bogus`

#### Scenario: Pre-6 module head
- **GIVEN** a file whose root is `(module R_0603 ...)`
- **WHEN** `read_footprint` is called
- **THEN** an `UnsupportedFormatError` is raised whose message says the head `module` is not supported and suggests `kicad-cli fp upgrade`

#### Scenario: Sub-nanometre length
- **GIVEN** a pad with `(size 1.0000001 1)`
- **WHEN** it is read
- **THEN** a `FormatError` is raised naming the value

#### Scenario: Unknown padstack mode
- **GIVEN** a pad with `(padstack (mode frobnicate) ...)`
- **WHEN** it is read
- **THEN** a `FormatError` is raised naming `frobnicate` and the locator of the pad

### Requirement: Version policy of library files
The readers MUST follow the read path of `kicad-version-gating`: they MUST call `versions.inspect` and `versions.require_readable` on the root, and MUST append `versions.version_issues` of the result to `issues`.
- Files of KiCad 8.0, 9.0 and 10.0, including development versions between them, SHALL be read.
- Older files MUST be refused with `UnsupportedFormatError`.
- Newer files SHALL be read with the warning `kicad.version.future`. Their opaque fragments MUST carry the file version as minimum version, so that no writer can emit them for a known target.

#### Scenario: 9.0 and 10.0 variants read alike
- **GIVEN** `Mini_v9.pretty/Mini_R_0603.kicad_mod` (`20241229`) and `Mini.pretty/Mini_R_0603.kicad_mod` (`20260206`)
- **WHEN** both are read with `library="Mini"`
- **THEN** their `pads` and `graphics` compare equal, ignoring provenance, ids and `ext`

#### Scenario: KiCad 7 footprint refused
- **GIVEN** a footprint with `(version 20221018)`
- **WHEN** it is read
- **THEN** `UnsupportedFormatError` is raised and its hint names `kicad-cli fp upgrade`

#### Scenario: Future version read with a warning
- **GIVEN** a footprint with `(version 20990101)` and otherwise the content of the mini resistor
- **WHEN** it is read with an `issues` list
- **THEN** a `FootprintDef` is returned, `issues` holds one warning `kicad.version.future`, and every opaque slot carries minimum version `20990101`

### Requirement: Symbol library reading
`fenolite.backends.kicad.sym.read_symbol_library(source, *, library=None, file="", issues=None)` SHALL accept a `.kicad_sym` file, a `.kicad_symdir` folder, file text or a parsed `Node`, and SHALL return the top-level symbols as written.
- A path MUST be treated as a folder when `Path.is_dir()` is true, whatever its suffix, and as a file otherwise.
- Symbols from a file are returned in file order. Symbols from a folder are returned in sorted file-name order, after reading every `*.kicad_sym` file inside it.
- When `library` is `None`, it MUST default to the file or folder stem for a path, and to `""` otherwise.
- Every file read MUST have the root `kicad_symbol_lib`.

#### Scenario: Folder and file give the same symbols
- **GIVEN** `tests/data/libs/Mini.kicad_sym` and the folder produced from it by `tests/_libs.py::make_symdir`
- **WHEN** both are read with `library="Mini"` and flattened
- **THEN** the two sets of definitions compare equal, ignoring provenance

#### Scenario: Folder with a foreign file
- **GIVEN** a `.kicad_symdir` folder containing a `.kicad_sym` file whose root is `footprint`
- **WHEN** it is read
- **THEN** a `FormatError` is raised naming that file

#### Scenario: Empty folder
- **GIVEN** an empty `Empty.kicad_symdir` folder
- **WHEN** it is read
- **THEN** an empty tuple is returned

### Requirement: Symbol content mapping
The reader SHALL map each top-level symbol as follows.
- Sub-symbols named `<name>_<U>_<S>` give `units` and the `unit`/`body_style` of their pins, with `S = 0` accepted as common to all body styles.
- Pins give `SymbolPin(number, name, etype, shape, position, rotation, length, hidden, alternates)` from `pin`, `at`, `length`, `name`, `number`, `hide` and `alternate`.
- `(power)` and `(power global)` give `power = "global"`, and `(power local)` gives `"local"`.
- `pin_names` gives the name offset and `pin_names_hidden`; `pin_numbers` gives `pin_numbers_hidden`.
- `in_bom`, `on_board` and `exclude_from_sim` give booleans.
- Properties give `properties`.

A pin, `pin_names` and `pin_numbers` MUST each be hidden by either `(hide yes)` or the bare atom `hide`. When the file version is below `20250318`, a pin name, pin number, alternate name or property value equal to `~` MUST decode to `""`; from `20250318` on, `~` MUST be kept. Every sub-symbol MUST be recorded as an `Opaque` slot of the symbol, because symbols are read-only projections.

#### Scenario: Units and common body style
- **GIVEN** `Mini_DualGate`, with sub-symbols `_1_1 _1_2 _2_1 _2_2 _3_0`
- **WHEN** it is read
- **THEN** `unit_count == 3`, `body_style_count == 2`, and `pins_of(3, 2)` returns the pins of `Mini_DualGate_3_0`

#### Scenario: Power symbol in both forms
- **GIVEN** `Mini_GND` from `Mini.kicad_sym` (`(power global)`) and from `Mini_v9.kicad_sym` (bare `(power)`)
- **WHEN** both are read
- **THEN** both have `power == "global"`, `reference == "#PWR"` and one hidden `power_in` pin of length 0

#### Scenario: Empty-text marker in a 9.0 library
- **GIVEN** `Mini_QFP32_IC` from `Mini_v9.kicad_sym`, whose empty pin name and `Datasheet` are written `~`, and the same symbol from `Mini.kicad_sym`, where they are written `""`
- **WHEN** both are read
- **THEN** the two pins have `name == ""`, both `datasheet` values are `""`, and the two `pins` tuples compare equal

#### Scenario: 8.0 hide atoms
- **GIVEN** an inline library with `(version 20231120)` whose symbol has `(pin_numbers hide)` and `(pin_names (offset 0) hide)`
- **WHEN** it is read
- **THEN** `pin_numbers_hidden` and `pin_names_hidden` are both true and `pin_name_offset == 0`

#### Scenario: Alternate pin function
- **GIVEN** the `Mini_QFP32_IC` pin that declares one `alternate`
- **WHEN** it is read
- **THEN** that pin has one `PinAlternate` with its name, electrical type and shape

#### Scenario: Unknown electrical type
- **GIVEN** a pin `(pin analog line (at 0 0 0) (length 2.54) ...)`
- **WHEN** it is read
- **THEN** a `FormatError` is raised naming `analog` and the locator of the pin

#### Scenario: Malformed unit suffix
- **GIVEN** a sub-symbol named `Mini_R_x_1` inside `Mini_R`
- **WHEN** it is read
- **THEN** a `FormatError` is raised naming the sub-symbol

### Requirement: Derived symbols
`sym.resolve_extends(symbols, *, issues=None)` SHALL return one definition per input symbol.
- A symbol with `extends = P` MUST receive P's pins, units, power kind, flags and pin-name settings, and P's properties overlaid key by key with its own. Its own id and its `extends` value MUST be kept.
- Chains of derivation MUST be followed.
- A missing parent MUST raise `LibraryError` with issue code `kicad.lib.missing-parent`.
- A cycle MUST raise `LibraryError` with `kicad.lib.extends-cycle`.

#### Scenario: Derived LED inherits pins
- **GIVEN** `Mini_LED_Red` with `(extends "Mini_LED")` and its own `Value`
- **WHEN** the library is read and flattened
- **THEN** `Mini_LED_Red.pins` equals `Mini_LED.pins`, its `value` is its own, and its `footprint` comes from its own property if present, otherwise from the parent

#### Scenario: Missing parent
- **GIVEN** a library holding only `(symbol "A" (extends "B") ...)`
- **WHEN** `resolve_extends` runs
- **THEN** `LibraryError` is raised with issue code `kicad.lib.missing-parent` naming `B`

#### Scenario: Cycle
- **GIVEN** symbols `A` extends `B` and `B` extends `A`
- **WHEN** `resolve_extends` runs
- **THEN** `LibraryError` is raised with issue code `kicad.lib.extends-cycle`

### Requirement: Provenance and identifiers of definitions
Every definition, pad, padstack and graphic created by the readers MUST carry provenance and an id as follows.
- Provenance is `Provenance(backend="kicad", file, file_sha256, locator, evidence)`.
  - `file_sha256` is the SHA-256 of the bytes read, or of the UTF-8 text when text is given.
  - `locator` is the bare `kicad-sexpr` locator of the node.
  - `evidence` is the module's `EVIDENCE`.
- Ids follow the `design-model` rules for library definitions:
  - a definition's native id is `<library>:<name>`, or `<name>` when `library` is empty
  - pads, padstacks and graphics use their `uuid` scoped by the definition's native id when present, and a content id with an occurrence counter otherwise

#### Scenario: Stable ids across reads
- **GIVEN** `Mini_QFP-32_7x7mm_P0.8mm.kicad_mod`
- **WHEN** it is read twice with `library="Mini"`
- **THEN** all ids of the two results are equal

#### Scenario: Copied uuids stay distinct across definitions
- **GIVEN** `Mini_R_0603.kicad_mod` and a copy named `Mini_R_0603_B.kicad_mod` in the same folder, with identical pad uuids
- **WHEN** both are read with `library="Mini"`
- **THEN** no pad id of the first equals a pad id of the second

#### Scenario: Locator of a pad
- **WHEN** the mini resistor is read
- **THEN** the second pad's `provenance.locator` is `/footprint/pad[1]`

### Requirement: Reading evidence
Before merge, the readers MUST reach the following evidence:
- The mini library MUST load in `kicad-cli` through `fp export svg` and `sym export svg`: the 10.0 and 9.0 variants on 10.0.6, and the `Mini_v9` variants on 9.0.9.
- Re-reading the mini library after `kicad-cli fp upgrade --force` and `sym upgrade --force` MUST give definitions equal to the originals, ignoring provenance and `ext`, on each major with that major's fixtures.
- Oracle tests MUST choose their fixtures from the running `kicad-cli` major, MUST run with `KICAD_CONFIG_HOME` set to an empty temporary folder, and MUST write `kicad-cli` output only to paths under `tmp_path` that do not exist before the call.
- With official libraries available (`needs_libs`), every official footprint and symbol of each available source MUST read without error, pad and pin counts MUST equal the counts of `pad` and `pin` nodes in the parsed tree, and ids MUST be unique within each library. The counts MUST be written only to the report file named by `FENOLITE_CENSUS_OUT`, never to a tracked file.

The readers' `EVIDENCE` SHALL stay `INFERRED` and be linked to `H-K-LIB-READ`; the census is supporting data, not a round trip.

#### Scenario: Mini library loads in KiCad 10
- **GIVEN** `kicad-cli` 10.0.6 and a copy of `tests/data/libs/Mini.pretty` in `tmp_path`
- **WHEN** `kicad-cli fp export svg <copy> -o <out>` runs
- **THEN** the exit code is 0 and one SVG per footprint exists

#### Scenario: Re-read after KiCad re-save
- **GIVEN** the output of `kicad-cli fp upgrade --force -o <tmp_path>/up/Mini.pretty` on the copied mini library, where only `<tmp_path>/up` exists before the call
- **WHEN** every footprint is read again
- **THEN** each definition, ids included, equals the original, ignoring provenance and `ext`

#### Scenario: Tilde rule confirmed by KiCad
- **GIVEN** `kicad-cli` 10.0.6 and `Mini_v9.kicad_sym` upgraded with `sym upgrade --force` into a new path under `tmp_path`
- **WHEN** the original and the upgraded file are read
- **THEN** their definitions compare equal, ignoring provenance and `ext`

#### Scenario: The 9.0 job uses the 9.0 fixtures
- **GIVEN** `kicad-cli` 9.0.9 in the `kicad-9` job
- **WHEN** `uv run pytest tests/kicad/libs -q` runs with `FENOLITE_REQUIRE=kicad`
- **THEN** the load and re-read tests pass on the `Mini_v9` files, loading `Mini.pretty` is asserted to fail, and the job does not fail because of a 10.0 fixture

#### Scenario: Official census
- **GIVEN** the official footprints of the local 10.0.6 install and `FENOLITE_CENSUS_OUT` naming a file under a temporary folder
- **WHEN** `uv run pytest -m needs_libs tests/libs/test_official_read.py` runs
- **THEN** every file reads without exception, the pad count of every definition equals its number of `pad` nodes, the counts are written to that file, and `git status --porcelain` is unchanged

### Requirement: Footprint files written by Fenolite read back equal
Every editable footprint definition (one not read from a future file) read by `read_footprint` or `footprint_from` SHALL survive `write_footprint` unchanged in the model, for the major it was read at and for any other target whose emit check passes without dropping a fragment. Definitions that `write_footprint` refuses (future files, too-new fragments without `allow_lossy`) are outside this requirement.
- For such a target `t`, `read_footprint(write_footprint(defn, target=t), library=defn.library)` MUST equal `defn`, ids included, ignoring provenance and `ext`. The opaque fragments of `defn` MUST reappear in the same order, apart from the header heads `version`, `generator` and `generator_version`, which the writer sets.
- The corpus round trip (`needs_corpus`) MUST cover every footprint of every non-heavy demo board that the board reader reads with 0 errors, written at the board's own major, and every footprint of the `pcb upgrade --force` copies of the third-party rows, made on 10.0.6 in `tmp_path` and never committed (origin `third-party`). The half that needs upgraded copies MUST also carry `needs_kicad` and `kicad_min_major(10)`.
- The written mini library MUST load with `kicad-cli fp export svg`: `Mini.pretty` written for target 10 on 10.0.6, and `Mini_v9.pretty` written for target 9 on 9.0.9. After `fp upgrade --force` into a new folder, every footprint MUST re-read equal to the original definition, ids included, ignoring provenance and `ext`.
- On 9.0.9, `tests/data/libs/Escapes_v9.pretty/Mini_Escapes.kicad_mod`, written for target 9, MUST keep every decoded property value and the description after `fp upgrade --force` (the 9.0 half of `H-K-SEXPR-ESCAPES`). Its properties MUST hold the ten escape forms of `tests/data/kicad/sexpr/escapes.kicad_pcb` and a non-ASCII value, and its description, set through the model, MUST hold the eight encoder values of the 10.0 proof.
- Every `kicad-cli` call MUST go through c0009's `KicadCli.run`, with results read from `CliRun.outputs`, and outcomes MUST be recorded under `fp-write-*` probe ids.

When the corpus round trip passes over both origins, the footprint half of `H-K-LIB-READ` SHALL be recorded as `CORPUS-VERIFIED`. The symbol half stays `INFERRED`, and the readers' `EVIDENCE` is governed by "Reading evidence".

#### Scenario: Demo board footprints round trip
- **GIVEN** the cached non-heavy demo boards of tags 10.0.6 and 9.0.9.1 that the board reader reads with 0 errors
- **WHEN** `uv run pytest tests/corpus/test_footprint_rt.py -k demo` runs
- **THEN** every footprint, read with `board_footprints`, written and read again, equals the original ignoring provenance and `ext`, with its opaque fragments in the same order

#### Scenario: Upgraded third-party footprints round trip
- **GIVEN** `kicad-cli` 10.0.6 and the `pcb upgrade --force` copies of the three third-party rows in `tmp_path`
- **WHEN** `uv run pytest tests/corpus/test_footprint_rt.py -k upgraded` runs
- **THEN** every footprint of every copy round trips as above, and `git status --porcelain` is unchanged afterwards

#### Scenario: Written mini library on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6 and `write_pretty` of the four definitions of `Mini.pretty` for target 10, passed to `KicadCli.run` in `files` as `Mini.pretty` with the empty folders `svg` and `up`
- **WHEN** `fp export svg Mini.pretty -o svg` and then `fp upgrade --force Mini.pretty -o up/Mini.pretty` run
- **THEN** the outputs of the first run hold four SVG files, and every footprint in the outputs of the second run re-reads equal to its original definition

#### Scenario: Written 9.0 library on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `write_pretty` of `Mini_v9.pretty` for target 9
- **WHEN** `uv run pytest tests/kicad/libs/test_mod_write_oracle.py` runs with `FENOLITE_REQUIRE=kicad`
- **THEN** the library loads, every upgraded footprint re-reads equal, and the test of `Mini.pretty` written for target 10 is skipped, not failed

#### Scenario: Escapes on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 and `Mini_Escapes` written for target 9, with one property value per escape form of `escapes.kicad_pcb` (`\"`, `\\`, `\n`, `\r`, `\t`, `\v`, `\7`, `\101`, `\x42`, `\e`) and a non-ASCII one, and a description set through the model to the concatenation of the eight encoder values (quote, backslash, line feed, carriage return, tab, vertical tab, `\x01`, non-ASCII)
- **WHEN** `fp upgrade --force` re-saves it and the result is read
- **THEN** every decoded property value and the description equal the values before the re-save

### Requirement: Board footprints read as definitions
`fenolite.backends.kicad.mod.footprint_from(loaded, *, library=None, issues=None, root_chain=("footprint",), index=0)` SHALL also accept `root_chain == ("kicad_pcb", "footprint")`. Then `loaded.node` is a board root, and the definition MUST be read from its `index`-th `footprint` child with the board's version policy (`FileKind.BOARD`) and locators `/kicad_pcb/footprint[index]/…`. `board_footprints(source, *, file="", issues=None)` SHALL return one definition per footprint of a board, in file order.
- When `library` is `None`, the header lib_id MUST be split at its first colon. A lib_id without a colon MUST give `library == ""` and the whole text as the name.
- Board-only children, when present (`at`, `path`, `sheetname`, `sheetfile`, the placement `uuid`, pad `net`, `pinfunction` and `pintype`), MUST be opaque slots of the definition or of its pads.
- Coordinates and angles MUST be taken as stored, without conversion to the library frame.
- With the default root chain, `footprint_from` MUST behave as before.

#### Scenario: Footprints placed in a board read as definitions
- **GIVEN** c0009's authored board `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `board_footprints(Path(...))` is called
- **THEN** two definitions are returned, `R_0603` and `LED_THT_3mm`, both with library `Fenolite_Test`, with provenance locators under `/kicad_pcb/footprint[0]` and `/kicad_pcb/footprint[1]`, and with the `at` child, the placement `uuid` and each pad's `net` and `pintype` (and, for `LED_THT_3mm`, `pinfunction`) as opaque slots

#### Scenario: Sheet links kept opaque
- **GIVEN** an inline board text whose one footprint holds `(path "/1f2e")`, `(sheetname "Root")` and `(sheetfile "a.kicad_sch")`
- **WHEN** `board_footprints` reads it
- **THEN** the three children are opaque slots of the definition, in file order

#### Scenario: Lib_id without a colon
- **GIVEN** an inline board text whose one footprint is named `R_0603`, without a library
- **WHEN** `board_footprints` reads it
- **THEN** the definition has `library == ""` and `name == "R_0603"`

