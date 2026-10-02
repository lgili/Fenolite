## ADDED Requirements

### Requirement: User properties in the DSL
`Part(ref, lib_id, footprint=None, value="", *, properties=None)` SHALL record user properties of a part, such as a part number or a supplier code, as text, and SHALL raise `DslError` at the call for every property it cannot record unambiguously.
- `properties` MUST be `None` (no property) or a mapping whose keys and values are `str`. Any other type, or a key or value that is not a `str`, MUST raise `DslError` naming the part.
- A name MUST be non-empty, MUST have no leading or trailing whitespace, and MUST satisfy `str.isprintable()` (S-0105). A value MUST satisfy `str.isprintable()` and MAY be empty. A tab, a newline or another control character is therefore refused.
- A name MUST NOT equal a reserved name (`Reference`, `Value`, `Footprint`, `Datasheet`, `Description`) and MUST NOT start with a reserved prefix (`fenolite.`, `ki_`). Both are compared after `str.casefold()` (S-0105). `Reference` and `Value` come from `ref` and `value`, the other three names are fields of the footprint library, `fenolite.path` is the component path, and `ki_` names are KiCad's own. The sets are `fenolite.dsl.part.RESERVED_PROPERTIES` and `RESERVED_PREFIXES`, are not re-exported, and MUST equal those of `lens.build`.
- Two names of one part that are equal after `str.casefold()` MUST raise `DslError` naming both.
- `Part.properties` MUST be a read-only mapping whose keys are in code-point order, whatever the order of the script.
- The DSL MUST NOT compare names with the properties of a footprint library; the build does ("User properties on built footprints").

#### Scenario: Properties recorded in name order
- **GIVEN** `r1 = Part("R1", "Mini:Mini_R", properties={"Supplier code": "S-1", "Part number": "PN-330"})`
- **WHEN** `r1.properties` is read, and then `r1.properties["X"] = "y"` is attempted
- **THEN** the mapping equals `{"Part number": "PN-330", "Supplier code": "S-1"}` with its keys in this order, and the assignment raises `TypeError`

#### Scenario: Reserved names in any letter case
- **WHEN** `Part("R1", "Mini:Mini_R", properties={"datasheet": "x"})` and `Part("R2", "Mini:Mini_R", properties={"KI_keywords": "x"})` are called
- **THEN** each call raises `DslError`, the first naming `datasheet` and `Datasheet`, the second naming the prefix `ki_`

#### Scenario: The path property is not the script's
- **WHEN** `Part("R1", "Mini:Mini_R", properties={"fenolite.path": "R9"})` is called
- **THEN** `DslError` is raised naming the prefix `fenolite.`

#### Scenario: Values are printable text
- **WHEN** `Part("R1", "Mini:Mini_R", properties={"Qty": 2})` and `Part("R2", "Mini:Mini_R", properties={"Part number": "A\nB"})` are called
- **THEN** each call raises `DslError` naming the property

#### Scenario: Names that differ only in case
- **WHEN** `Part("R1", "Mini:Mini_R", properties={"MPN": "a", "mpn": "b"})` is called
- **THEN** `DslError` is raised naming `MPN` and `mpn`

#### Scenario: Reserved sets agree
- **WHEN** `uv run pytest tests/unit/dsl/test_properties.py -k reserved_sets` runs
- **THEN** `fenolite.dsl.part.RESERVED_PROPERTIES` and `RESERVED_PREFIXES` equal `fenolite.lens.build.RESERVED_PROPERTIES` and `RESERVED_PREFIXES`

### Requirement: User properties on built footprints
The build SHALL write every user property of a component onto its placed footprint through `embed.with_property`, and SHALL refuse, with an issue and no file, a user property that it cannot write unambiguously.
- The user properties of a component are the entries of `Component.properties` other than `fenolite.path`, which carries the component path ("DSL to model").
- **Checks.** They run with the build checks of "Built project files", and each issue names the component path in `where`:
  - a name equal to a reserved name, or starting with a reserved prefix, after `str.casefold()` (`lens.build.RESERVED_PROPERTIES` and `RESERVED_PREFIXES`, the sets of "User properties in the DSL"): `build.property-reserved` (error);
  - an empty name, a name with leading or trailing whitespace, a name or value that fails `str.isprintable()`, or two names equal after `str.casefold()`: `build.property-invalid` (error);
  - a name equal, after `str.casefold()`, to the name of a property of the resolved footprint definition: when both the name and the value are identical, nothing is appended and the definition's property stands; otherwise `build.property-conflict` (error) naming the property and the library's value.
- **Form and order.** Each user property MUST be appended by one call `embed.with_property(<definition>, name=<name>, value=<value>)`, in code-point order of names, after the path property; when `H-K-BUILD-PATHPROP` is refuted and no path property is written, after the definition's last property. Each is therefore hidden, on `F.Fab` at `(at 0 0 0)` with c0011's font, and `place_footprint` puts it on `B.Fab` with a mirrored text for a bottom part. Values are written with the string escapes of the s-expression writer (`H-K-SEXPR-ESCAPES`).
- Adding or removing a user property MUST NOT change the uuid of any node other than the user properties that come after it, because new nodes are appended after the existing ones and locator indices count earlier siblings with the same head (`kicad-sexpr`).
- **Model.** `Component.properties` MUST equal what `read_board` projects from the written footprint: the definition's properties, `fenolite.path`, the user properties, `Reference` and `Value`. c0017's "Projected fields on write" stays unchanged and passes, because every property of the model is a fragment of the footprint.
- **Readback.** `read_board` of the written board MUST give every user property with its value, for targets 9 and 10.
- Visibility, position, layer and size of these properties cannot be set by this change (field placement, c0030).

#### Scenario: Written after the path property
- **GIVEN** a blink variant whose `R1` has `properties={"Supplier code": "S-1 \"q\" \\ µ", "Part number": "PN-330"}`
- **WHEN** it is built for target 10 and the board text is parsed
- **THEN** the last three `property` nodes of `R1`'s footprint are `fenolite.path`, `Part number` and `Supplier code`, in this order, each on layer `F.Fab` with `(hide yes)`, and `read_board` gives `properties["Supplier code"] == "S-1 \"q\" \\ µ"` and `properties["Part number"] == "PN-330"`

#### Scenario: Bottom part
- **GIVEN** the blink, whose `D1` is on the bottom side, with `properties={"Part number": "PN-LED"}` on `D1`
- **WHEN** it is built for target 9
- **THEN** the `Part number` node of `D1` has layer `B.Fab`, `(hide yes)` and `mirror` in its `justify`

#### Scenario: Writer accepts the properties and reads them back
- **WHEN** the variant with properties on `R1` and `D1` is built for targets 9 and 10, and each written board is read with `read_board`
- **THEN** `write_triad` raises no `kicad.board.projection-read-only`, and each built component's `properties` equals the read-back component's `properties`

#### Scenario: No other uuid moves
- **GIVEN** the blink built once as it is and once with `properties={"Part number": "PN-330"}` on `R1`
- **WHEN** the uuids of the two boards are compared
- **THEN** they are equal, except the uuid of the new `Part number` node, which only the second board has

#### Scenario: Reserved name through the model
- **GIVEN** `to_model` of the blink, with `"Datasheet": "x"` added to the `properties` of `R1` in the test
- **WHEN** `build_design` runs
- **THEN** `files` is empty, and `issues` holds `build.property-reserved` whose `where` is `R1`

#### Scenario: Library property with the same name
- **GIVEN** a footprint authored in the test whose properties include `Part number` with value `LIB`, used by `R1`
- **WHEN** it is built with `R1` given `properties={"Part number": "PN-330"}`, and again with `properties={"Part number": "LIB"}`
- **THEN** the first build gives `build.property-conflict` naming `Part number` and `LIB` with no file, and the second build writes the footprint with exactly one `Part number` node

#### Scenario: Control character through the model
- **GIVEN** `to_model` of the blink, with `"Part number": "A\tB"` added to the `properties` of `R1` in the test
- **WHEN** `build_design` runs
- **THEN** `files` is empty, and `issues` holds `build.property-invalid` naming `R1`

### Requirement: Footprints of every row origin are vendored
With `vendor="all"`, the default of `build_design` and of `fenolite build`, the build SHALL copy every footprint it places into the project's library folder, whatever the origin of the row that resolved it, so that a built project needs no global or template table.
- Row origins are those of `LibraryResolver`: `project`, `global` and `template`, and any origin that a later change adds, such as c0021's `scan`. A footprint of any origin MUST be copied byte for byte from `Location.item_path` to `lib/<nickname>.pretty/<entry>.kicad_mod`, `nickname` being the nickname of the row that resolved it, with one `fp-lib-table` row per vendored nickname ("Built project files").
- Lib ids MUST stay unchanged: the board's footprint names, `Component.lib_footprint_ref` and the `.fenolite/` texts keep the nicknames of the design. In KiCad's library check, the vendored row hides a global row with the same nickname, and with it the items that were not vendored (`H-K-VENDOR-SHADOW`).
- Only placed footprints MUST be copied: no whole library, no 3D model, no symbol and no `sym-lib-table`. Symbol libraries get the same rule when built projects get schematics (v0.2a).
- With `vendor="project"` (`fenolite build --vendor project`), a footprint of a row whose origin is not `project` MUST NOT be copied and gets no row. Each such footprint gives `build.global-library` (info), as c0011 did.
- **Unsafe names.** A vendored nickname that holds `/` or `\`, or a character that fails `str.isprintable()`, MUST give `build.vendor-unsafe-name` (error) with the build checks, and two vendored paths that differ but are equal after `str.casefold()` MUST give it too. Then no file is written outside `lib/`, and the folder survives a file system that ignores letter case.
- **Library changes.** When `record` (the hashes that `read_record` returns) holds a hash for the path of a vendored file, and the planned bytes have another SHA-256, the build MUST give `build.library-changed` (warning) naming the file, because its library changed since the last build. The planned copy still replaces an old copy that is untouched since the last build ("Edited outputs are not overwritten").
- Vendored bytes are the source bytes, so two builds with the same libraries give identical files ("Reproducible builds").
- Copies are written only into the `--out` folder. The official libraries are CC-BY-SA 4.0 with an exception for designs, and redistributing the collection is not covered by it (S-0048). `docs/dsl.md` MUST say so without legal advice, and MUST name `--vendor project`.

#### Scenario: Global footprints vendored
- **GIVEN** the blink built from a folder without project tables, every symbol and footprint served by the global tables of a `KICAD_CONFIG_HOME` authored in the test, whose rows `Mini` name a temporary copy of `tests/data/libs/Mini_v9.pretty` and `Mini_v9.kicad_sym`
- **WHEN** `build_design` runs for target 9, and again for target 10
- **THEN** each `files` holds the three footprints under `lib/Mini.pretty/`, byte-equal to the copy, and an `fp-lib-table` with the one row `Mini` naming `${KIPRJMOD}/lib/Mini.pretty`; `issues` holds no `build.global-library`; `summary["libraries"]["Mini:Mini_R_0603"]` is `global`; and the board names the footprint `Mini:Mini_R_0603`

#### Scenario: Template footprints vendored
- **GIVEN** a fake install made with `tests/_libs.make_install`, whose template tables name the same copies through `${KICAD10_FOOTPRINT_DIR}` and `${KICAD10_SYMBOL_DIR}`, and an empty configuration folder
- **WHEN** the blink is built for target 10 from a folder without project tables
- **THEN** `summary["libraries"]["Mini:Mini_R_0603"]` is `template`, and the files under `lib/Mini.pretty/` and the table are those of the previous scenario

#### Scenario: Vendoring kept to project rows on request
- **GIVEN** the global setup of the first scenario
- **WHEN** `build_design` runs with `vendor="project"`
- **THEN** `files` holds nothing under `lib/`, `fp-lib-table` holds no row, and `issues` holds three `build.global-library` infos, one for each footprint

#### Scenario: Unsafe nickname
- **GIVEN** a global row named `a/b`, made in the test, that serves `R1`'s footprint
- **WHEN** `build_design` runs
- **THEN** `files` is empty, and `issues` holds `build.vendor-unsafe-name` naming `a/b`

#### Scenario: Library changed since the last build
- **GIVEN** a first build of the global setup and the hashes of its `.fenolite/build.json`, and then pad `1` of the global copy of `Mini_R_0603.kicad_mod` moved 0.05 mm in the test
- **WHEN** `build_design` runs again with `record` set to those hashes
- **THEN** `issues` holds one `build.library-changed` warning naming `lib/Mini.pretty/Mini_R_0603.kicad_mod`, and the planned copy is byte-equal to the changed source; without the change, no such warning is given

#### Scenario: Built folder resolves alone
- **GIVEN** a build of the global setup, written to a folder and copied to another folder
- **WHEN** a resolver with `project_dir` set to the copy, an empty configuration folder and no install locates `Mini:Mini_R_0603`
- **THEN** the origin is `project`, and the item path is `lib/Mini.pretty/Mini_R_0603.kicad_mod` inside the copy

## MODIFIED Requirements

### Requirement: DSL to model
`dsl.to_model(design) -> fenolite.model.Design` SHALL convert a DSL design into model types only, with the ids of `design-model` "Identifier derivation" (fourth case).
- **Circuit.** One `Component` per added part, with `ref`, `value`, `lib_symbol_ref`, `lib_footprint_ref` (empty when `Part.footprint` is `None`), empty `pins`, empty `path` and `properties` holding `"fenolite.path"` mapped to the component path and every entry of `Part.properties` ("User properties in the DSL"), keys in code-point order. Nets whose `PinRef.pin` holds the designator as written. Net classes with `Net.netclass_id`. Interfaces. One `Module` per DSL module, with `path`, `parent` and `component_ids`.
- **Board.** A keyed `Board` without layers and footprints, whose `Outline` is the rectangle from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)` in the order of c0017's "Outline lowering", or no outline when `board()` was not called.
- **Other layers.** An empty keyed `RuleSet`, a keyed `Manifest` and a keyed header named after the design.
- Every object MUST have `provenance = None`, so no absolute user path reaches `.fenolite/`.
- `to_model` MUST NOT call `Design.validate()`, MUST NOT resolve libraries, and MUST NOT change the DSL design.

#### Scenario: Blink in the model
- **GIVEN** the DSL design of `examples/blink_2layer/design.py`
- **WHEN** `to_model` runs
- **THEN** `R1` has `lib_symbol_ref == "Mini:Mini_R"`, `lib_footprint_ref == "Mini:Mini_R_0603"`, `pins == ()`, `path == ""` and `properties == {"fenolite.path": "R1"}`, and the outline points are (100 mm, 100 mm), (150 mm, 100 mm), (150 mm, 130 mm) and (100 mm, 130 mm)

#### Scenario: Designators as written
- **GIVEN** `connect(gnd, u1["GND"])`
- **WHEN** `to_model` runs
- **THEN** the net `GND` holds `PinRef(<U1 id>, "GND")`

#### Scenario: No provenance and no absolute path
- **WHEN** the texts of `canonical.dump_texts(to_model(design))` are searched for the absolute path of the script folder
- **THEN** no text contains it, and no entity has a provenance

#### Scenario: User properties in the model
- **GIVEN** `Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330", properties={"Supplier code": "S-1", "Part number": "PN-330"})` added to a design
- **WHEN** `to_model` runs
- **THEN** the component `R1` has `properties == {"Part number": "PN-330", "Supplier code": "S-1", "fenolite.path": "R1"}`, with its keys in this order

### Requirement: Placement of built parts
The build SHALL place every placed part with c0017's `embed.place_footprint` and SHALL stage every unplaced part in one row beside the outline.
- A placed part MUST be `embed.place_footprint(<extended>, component=…, at=…, rotation=…, side=…, locked=…, key=<component path>, copper=<copper names>)`, with `at`, `rotation`, `side` and `locked` from its `Placement`. `<extended>` is `embed.with_property(defn, name=PATH_PROPERTY, value=<component path>)` followed by one `embed.with_property` call per user property of the component, in code-point order of names ("User properties on built footprints"). The path property is written while `H-K-BUILD-PATHPROP` holds (`kicad-file-backend`, "Path property on placed footprints"); without it, `<extended>` starts from `defn`.
- Every `place_footprint` call, staged parts included, MUST pass the part's `<extended>` definition and, as `copper`, the names of the copper layers of `layers.created_layers(copper)`, in table order (`kicad-file-backend`, MODIFIED "Footprint embedding"), so wildcard pad layers cover every copper layer of a four-layer board.
- Unplaced parts MUST be staged in component-path order in one row that starts `STAGING_OFFSET = 5_000_000` nm right of the outline's bounding box and is top-aligned with it. Each part's `footprint_extent` box MUST be left-aligned on the cursor, which then advances by the box width plus `STAGING_GAP = 2_000_000` nm. Staged parts are on the top side at 0° and unlocked, and each gives one `layout.unplaced` warning. Staging is a fixed row, not a placer (c0022).
- `Board.layers` MUST be `layers.created_layers(copper)`, re-keyed by layer name.
- A design without `board()` MUST give `build.no-board` (error).
- `Component.properties` MUST be set to exactly what `read_board` projects from the written footprint (the definition's properties, `fenolite.path`, the user properties, `Reference` and `Value`), so c0017's "Projected fields on write" passes unchanged. `Component.path` MUST stay empty: no footprint `path`, `sheetname` or `sheetfile` is written before schematics (v0.2a).
- `lens` MUST read the `footprint_extent` box by attribute and MUST NOT import `geometry`.

#### Scenario: Placed parts
- **WHEN** the blink is built
- **THEN** each footprint instance has `position` equal to `BOARD_ORIGIN` plus its DSL offset, `D1` has `side == "bottom"`, `U1` has `locked == True`, and the footprint instances carry the ids of c0017's placed copies with keys `U1`, `R1` and `D1`

#### Scenario: Staging row
- **GIVEN** a blink variant in which `D1` and `R1` are not placed
- **WHEN** it is built
- **THEN** the extent box of `D1`, moved to its position, has its left edge at 155 mm and its top edge at 100 mm, the box of `R1` has its left edge 2 mm right of the right edge of `D1`'s box and its top edge at 100 mm, `issues` holds two `layout.unplaced` warnings, and the exit code is 0

#### Scenario: No board
- **GIVEN** a blink variant without `board()`
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds `build.no-board`, and nothing is written

#### Scenario: Write accepts the built properties
- **WHEN** the blink is built for targets 9 and 10
- **THEN** `write_triad` raises no `kicad.board.projection-read-only`, and every component has `path == ""` and `properties["fenolite.path"]` equal to its component path

#### Scenario: Staged parts carry their properties
- **GIVEN** a blink variant in which `R1` is not placed and has `properties={"Part number": "PN-330"}`
- **WHEN** it is built and the written board is read with `read_board`
- **THEN** the staged `R1` footprint holds the hidden `Part number` property after `fenolite.path`, and the read-back `R1` has `properties["Part number"] == "PN-330"`

#### Scenario: Four-layer build
- **GIVEN** a blink variant whose board is declared with `copper=4`
- **WHEN** it is built for target 10 with `--confirm` and the written board is read with `read_board`
- **THEN** the exit code is 0, and pad `"1"` of `D1` (`Mini_LED_THT_3mm`) has the copper layers `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu` in the built model and in the read-back board

### Requirement: Built project files
`lens.build.build_design(design, placements, *, name, copper, resolver, target=DEFAULT_TARGET, allow_lossy=False, vendor="all", record=None) -> BuildOutput` SHALL return every file of a self-contained KiCad project as bytes, and SHALL return no file when any issue has severity `error`.
- The steps MUST run in this order: resolve libraries; fill pins and resolve net members; place, stage, set layers and assign pad nets; run the build checks (those of "Pins and pads in a build", "Placement of built parts", "User properties on built footprints" and "Footprints of every row origin are vendored") and `Design.validate()`; call c0010's `triad.write_triad(design, name=name, target=target, existing_project=None, allow_lossy=allow_lossy, issues=…)`, which lowers rules through c0018 and net classes through c0010; add the vendored footprints, `fp-lib-table`, the `.fenolite/` texts and `.fenolite/build.json`; combine evidence.
- An issue of severity `error` before the writer MUST return a `BuildOutput` with its issues and empty `files`. Writer refusals (`LossyWriteError`, `RulesLossError`, `FEN-7001`) MUST propagate with their issues.
- `BuildOutput` is a frozen dataclass with `design`, `files: Mapping[str, bytes]` (paths relative to `--out`), `issues`, `evidence` and `summary`.
- The layout MUST be `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`, `fp-lib-table`, `lib/<nickname>.pretty/<entry>.kicad_mod`, the six layer files under `.fenolite/` and `.fenolite/build.json`.
- Every vendored footprint MUST be copied byte for byte from `Location.item_path` to `lib/<nickname>.pretty/<entry>.kicad_mod`, and `fp-lib-table` MUST hold one row per vendored nickname with `uri "${KIPRJMOD}/lib/<nickname>.pretty"`, written by `libs.write_lib_table` for the target. With `vendor="all"`, every footprint that the build places is vendored, whatever the origin of its row; with `vendor="project"`, only footprints resolved through a project-table row are ("Footprints of every row origin are vendored"). Any other `vendor` MUST raise `ValueError`.
- With `vendor="project"`, footprints from rows of another origin MUST NOT be vendored and get no row (`build.global-library`, info). A vendored file whose header version is newer than the target's newest format MUST give `build.library-too-new` (warning). With `record`, a vendored file whose bytes differ from the hash recorded for its path MUST give `build.library-changed` (warning).
- The build MUST NOT write a `sym-lib-table`, a symbol file, a `.kicad_prl`, a `native/` folder or a date.
- The `.fenolite/` layer texts MUST come from `canonical.dump_texts`, with an empty `findings.json` and no `FootprintDef`. `.fenolite/build.json` MUST have `schema` `fenolite.build-record.v0`, sorted keys and no date, and MUST record the SHA-256 of every file outside `.fenolite/` that the build writes. It is regenerable and marks a built project.

#### Scenario: Files of a target-9 build
- **WHEN** the blink is built for target 9
- **THEN** `files` holds exactly the triad `blink.*`, `fp-lib-table` without a `version` child, three files under `lib/Mini.pretty/` byte-equal to their sources in `tests/data/libs/Mini_v9.pretty/`, the six layer files under `.fenolite/` and `.fenolite/build.json`

#### Scenario: Build record
- **WHEN** `.fenolite/build.json` of a blink build is read
- **THEN** its `schema` is `fenolite.build-record.v0`, it holds no date, and it maps each of the seven files outside `.fenolite/` to its SHA-256

#### Scenario: Errors produce no files
- **GIVEN** a blink variant with `connect(led, r1["X"])`
- **WHEN** `build_design` runs
- **THEN** the returned `files` is empty and `issues` holds `build.unknown-pin`

#### Scenario: Unsafe class pattern refused
- **GIVEN** a blink variant with a net `D[0]` in class `PWR` and a net `D0` beside it
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 7, stderr carries `FEN-7001`, `issues` holds `kicad.project.pattern-unsafe`, and nothing is written

#### Scenario: Global footprint vendored
- **GIVEN** a blink variant whose `R1` footprint `G:Mini_R_0603` resolves through a global `fp-lib-table` row of a `KICAD_CONFIG_HOME` authored in the test, the other footprints resolving through the project table
- **WHEN** `build_design` runs with the default `vendor`
- **THEN** `files` holds `lib/G.pretty/Mini_R_0603.kicad_mod`, byte-equal to its source, `fp-lib-table` holds the rows `G` and `Mini` in this order, and `issues` holds no `build.global-library`

#### Scenario: Global footprint kept out on request
- **GIVEN** the same variant
- **WHEN** `build_design` runs with `vendor="project"`
- **THEN** `issues` holds one `build.global-library` info naming `G:Mini_R_0603`, `files` holds no file under `lib/G.pretty/`, and `fp-lib-table` holds no row named `G`

#### Scenario: Unknown vendoring policy
- **WHEN** `build_design` runs with `vendor="none"`
- **THEN** `ValueError` is raised naming `all` and `project`

#### Scenario: Vendored file newer than the target
- **GIVEN** a blink variant whose project table names a folder holding a copy of `Mini_v9.pretty/Mini_R_0603.kicad_mod` authored in the test with header version `20260206` and no 10-only token
- **WHEN** `build_design` runs for target 9
- **THEN** `issues` holds one `build.library-too-new` warning naming the vendored file, and `files` holds the vendored copy byte-equal to its source

#### Scenario: The built folder moves whole
- **GIVEN** a confirmed blink build copied to another folder
- **WHEN** a resolver with `project_dir` set to the copy locates `Mini:Mini_R_0603`
- **THEN** the item path is `lib/Mini.pretty/Mini_R_0603.kicad_mod` inside the copy

### Requirement: Build command
`fenolite build DESIGN.py --out DIR [--discard-layout] [--vendor all|project]` (`src/fenolite/cli/cmd_build.py`, schema `fenolite.build.v0`) SHALL be a mutating command that runs the script, converts it with `to_model` and `placements`, builds it with `lens.build.build_design` for `Context.kicad_target` and the `--vendor` policy, and returns every output file as a planned write under `DIR`.
- It MUST accept the global flags `--dry-run`, `--confirm`, `--seed`, `--timestamp`, `--no-backup`, `--kicad-version 9|10` and `--allow-lossy`. `--out` is required. `--discard-layout` and `--vendor` (choices `all` and `project`, default `all`, passed to `build_design` as `vendor`) are `build` options. The help text of `--vendor` MUST say that `all` copies the placed footprints of every library into `DIR/lib/` and that the copies keep their library's licence.
- An `--out` folder that resolves to the script folder MUST be a usage error (exit 2, `FEN-2001`), so the design's own tables are never overwritten.
- `input` MUST hold the script path and its SHA-256, with kind `fenolite-dsl`.
- The triad stem MUST be the design name, and plan entries MUST be sorted by path.
- `result` MUST hold `design` (the name), `target`, `out`, `files` (the planned paths), `components` and `nets` (counts), `placed` and `staged` (component paths), `vendored` (vendored footprint files), `libraries` (lib id to row origin `project`, `global` or `template`) and `script_output`, plus the dispatcher's `plan`.
- `cmd_build` MUST turn a `DslError` raised by `to_model` or `placements`, which run after `run_design_script` has returned, into `DesignScriptError` with `file` = the script path and no locator (`FEN-3004`, exit 3).
- `cmd_build` MUST read the last build record once with `lens.build.read_record(DIR)`, pass it to `build_design` and to `lens.build.check_existing` as `record`, and call `check_existing` before it returns the plan ("Edited outputs are not overwritten").
- A build with an issue of severity `error` MUST return no planned write, so it exits 5 and writes nothing.
- `example_args` (with `--dry-run`) and `mutation_example_args` MUST use the packaged `src/fenolite/dsl/_minimal.py` (Apache-2.0 header; a board with one net class and no parts), located through `fenolite.dsl.__file__`, so the consistency suite is hermetic from any working directory.

#### Scenario: Confirmation required
- **GIVEN** an empty folder `B`
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --json` runs without `--confirm`
- **THEN** the exit code is 4, `result.plan` lists every planned file, and `B` is still empty

#### Scenario: Confirmed build
- **WHEN** the same command runs with `--confirm`
- **THEN** the exit code is 0, and `receipt.written` lists `B/blink.kicad_pcb`, `B/blink.kicad_pro`, `B/blink.kicad_dru`, `B/fp-lib-table`, the three footprints under `B/lib/Mini.pretty/` and the seven files under `B/.fenolite/`

#### Scenario: Rebuild is identical
- **WHEN** the confirmed build runs a second time
- **THEN** the exit code is 0, every file that the first build wrote has the same bytes as after the first build, and the only new files are the `.bak` copies that the mutation protocol keeps

#### Scenario: Output folder is the script folder
- **WHEN** `fenolite build examples/blink_2layer/design.py --out examples/blink_2layer --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Vendoring policy on the command line
- **GIVEN** a blink variant whose `R1` footprint `G:Mini_R_0603` resolves through a global row of a `KICAD_CONFIG_HOME` authored in the test and set in the environment of the run
- **WHEN** `fenolite build design.py --out B --dry-run --json` runs, and then the same command with `--vendor project`
- **THEN** the first `result.vendored` lists `lib/G.pretty/Mini_R_0603.kicad_mod`, and the second lists no file under `lib/G.pretty/` and its `issues` hold `build.global-library` naming `G:Mini_R_0603`

#### Scenario: Consistency suite
- **WHEN** `uv run pytest tests/consistency` runs from a temporary working directory
- **THEN** it passes, with `build` covered by the mutation protocol

### Requirement: Build issue codes
The build SHALL report its own findings only with the codes of the closed table `lens.build.BUILD_ISSUE_CODES`. Codes of the writers (`kicad.board.*`, `kicad.project.*`, `rules.*`), of the resolver (`kicad.lib.*`) and of `Design.validate()` (`model.*`) MUST pass through unchanged.

| code | severity | when |
|---|---|---|
| `build.unknown-pin` | error | a designator is neither a pin number nor a pin name |
| `build.pin-on-two-nets` | error | a resolved pin is on two nets |
| `build.pin-without-pad` | error | a connected pin has no pad of its number |
| `build.no-footprint` | error | neither the part nor the symbol names a footprint |
| `build.no-board` | error | the design has no `board()` |
| `build.name-case-collision` | error | net or class names differ only in letter case |
| `build.layout-exists` | error | an output changed since the last build (carried by `LayoutExistsError`) |
| `build.property-reserved` | error | a user property has a reserved name or prefix |
| `build.property-invalid` | error | a user property name or value is not printable text, a name has surrounding whitespace, or two names differ only in letter case |
| `build.property-conflict` | error | the footprint definition holds a property of the same name with another value |
| `build.vendor-unsafe-name` | error | a vendored nickname holds a path separator or a non-printable character, or two vendored paths differ only in letter case |
| `build.pin-ambiguous` | warning | a pin number is also another pin's name |
| `build.unused-pin-without-pad` | warning | an unconnected pin has no pad of its number |
| `build.library-too-new` | warning | a vendored file is newer than the target's newest format |
| `build.library-changed` | warning | a vendored file differs from the copy that the last build recorded |
| `layout.unplaced` | warning | a part was staged beside the outline |
| `build.pad-without-pin` | info | a numbered pad has no pin of its number |
| `build.global-library` | info | with `vendor="project"`, a footprint came from a row whose origin is not `project` and is not vendored |
| `build.interface-not-lowered` | info | a `diff_pair` interface is kept in the model only |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/lens/test_build_issues.py -k closed_set` collects every issue code produced by the build tests
- **THEN** each code other than `kicad.*`, `rules.*` and `model.*` is a key of `BUILD_ISSUE_CODES` with the severity of this table, and every key of the table is produced by at least one test

#### Scenario: Warnings do not fail
- **GIVEN** the blink with `R1` not placed
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 0 and `issues` holds one `layout.unplaced` warning naming `R1`

### Requirement: Build evidence
The `build` envelope SHALL carry `Evidence.combine` (lowest wins) of `lens.build.BUILD_EVIDENCE` (`INFERRED`; `H-K-BUILD-TRIAD`, `H-K-BUILD-CLASS`, `H-K-BUILD-LIBTABLE`, `H-K-BUILD-PATHPROP`), `sym.EVIDENCE` and `mod.EVIDENCE` (`H-K-LIB-READ`), `pcb.WRITE_EVIDENCE` (`H-K-PCB-WRITE`), `pro.EVIDENCE` (`H-K-PRO-PATTERNS`), `lowering.EVIDENCE`, when a part is on the bottom side `embed.EVIDENCE`, when a user property is written `lens.build.PROPERTY_EVIDENCE` (`INFERRED`; `H-K-VENDOR-PROPS`, `H-K-VENDOR-DUPNAME`), and when a footprint of a row whose origin is not `project` is vendored `lens.build.VENDOR_EVIDENCE` (`INFERRED`; `H-K-VENDOR-GLOBAL`, `H-K-VENDOR-SHADOW`).
- The level MUST stay `INFERRED` while any of these is below `KICAD-VERIFIED`.
- `PROPERTY_EVIDENCE` and `VENDOR_EVIDENCE` MUST stay `INFERRED` after their rows are settled, because the oracle covers the blink and its variants, not every design.
- `KICAD-VERIFIED` applies to the blink example only, through the oracle suite (`kicad-oracle`, "Built projects pass the build oracle"), and MUST NOT be reported for an arbitrary build.

#### Scenario: Blink envelope
- **WHEN** the blink is built with `--dry-run --json`
- **THEN** `evidence.level` is `INFERRED`, and `evidence.hypotheses` contains `H-K-BUILD-TRIAD`, `H-K-LIB-READ` and `H-K-PCB-WRITE`

#### Scenario: Bottom parts add the flip rows
- **GIVEN** the blink, whose `D1` is on the bottom, and a variant with `D1` on the top
- **WHEN** both are built with `--dry-run --json`
- **THEN** only the first envelope's `evidence.hypotheses` contains the hypotheses of `embed.EVIDENCE`

#### Scenario: Properties and vendoring add their rows
- **GIVEN** the blink, a variant with `properties={"Part number": "PN-330"}` on `R1`, and a variant whose footprints come from a global table authored in the test
- **WHEN** the three are built with `--dry-run --json`
- **THEN** only the second envelope's `evidence.hypotheses` contains `H-K-VENDOR-PROPS`, only the third contains `H-K-VENDOR-GLOBAL`, and every `evidence.level` is `INFERRED`
