## ADDED Requirements

### Requirement: Edit merge module
The module `fenolite.lens.edits` SHALL hold the three-way merge of the properties that a design script and an edited CAD file both decide, the edits file and the base record. It MUST import only the standard library, `core`, `model`, `backends` and `lens.placements` (`package-layering`), never `geometry`, `dsl`, `lens.build` or `lens.preserve`.

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes, and `src/fenolite/lens/edits.py` imports neither `fenolite.geometry`, `fenolite.dsl`, `fenolite.lens.build` nor `fenolite.lens.preserve`

### Requirement: Edit merge public names
`fenolite.lens.edits` SHALL export `EDITS_SCHEMA`, `EDITS_FILE`, `BASE_SCHEMA`, `BASE_FILE`, `PROPERTIES`, `PropertyKey`, `BaseEntry`, `BaseRecord`, `read_base`, `write_base`, `PartEdits`, `EditsFile`, `read_edits`, `write_edits`, `Decision`, `Conflict`, `Take`, `parse_takes`, `merge_property`, `merge_properties`, `PropertyMerge`, `capture_edits`, `EDIT_ISSUE_CODES` and `EVIDENCE` in `__all__`.

#### Scenario: Names exported
- **WHEN** `uv run pytest tests/unit/lens/test_edit_merge.py -k names` compares `fenolite.lens.edits.__all__` with the list
- **THEN** they are equal

### Requirement: Pure and exact merge functions
Every function of `fenolite.lens.edits` SHALL be pure: it reads no file and no environment variable and returns new objects without changing its arguments; the commands read and write the files. Values MUST be compared exactly: positions as integer nanometres, rotations as integer microdegrees, texts as code-point strings, and no float MUST be created.

#### Scenario: Equal inputs give equal decisions
- **WHEN** `merge_properties` runs twice on equal inputs, once under `PYTHONHASHSEED=0` and once under `PYTHONHASHSEED=1`
- **THEN** both results are equal and none of their numbers is a `float`

### Requirement: Property keys
A merged property SHALL be named by `PropertyKey(path, prop)`, printed `<component path>#<prop>`, where `path` is the part's component path (`docs/design-model.md`) and `prop` is a property name. Keys MUST sort by component path, then by the order of `PROPERTIES`, then by user property name.

#### Scenario: Key text
- **WHEN** `PropertyKey("buck1/L", "property:Part number")` is printed
- **THEN** the text is `buck1/L#property:Part number`

### Requirement: Merged property names
`PROPERTIES` SHALL be `("position", "rotation", "value", "footprint", "reference")`; a user property SHALL be named `property:<name>`, its name compared after `str.casefold()`. `position` is x and y, `rotation` is rotation and side together, `value` the `Value` text, `footprint` the library footprint id and `reference` the reference designator. Any other name MUST raise `ValueError`.

#### Scenario: Unknown property name refused
- **WHEN** `PropertyKey("R1", "colour")` is created
- **THEN** `ValueError` names `colour` and lists the names of `PROPERTIES`

### Requirement: Properties outside the merge
A footprint's lock in KiCad, field placement (`layout-lens`, "Footprint fields across rebuilds"), pads, silkscreen, copper, zones and symbol positions SHALL NOT be merged properties: they keep the rules of `layout-lens` and of `schematic-placements.toml`.

#### Scenario: Field placement keeps its rule
- **GIVEN** a confirmed blink build whose `Reference` field of `R1` is moved 1 mm by token edit
- **WHEN** the build runs again with `--confirm --json`
- **THEN** the field stays where it was moved, `result.preserved.fields.kept` is as before this change, and `result.preserved.edits` lists nothing for `R1`

### Requirement: Base record file
Every build that writes an output folder SHALL write the base record `<out>/fenolite-base.json`, beside `.fenolite/` and not in it, holding for each part and merged property the *code* value the build was given and the *out* value it wrote. The merge SHALL take the base only from this file, so a clone of the output folder without `.fenolite/` merges as the original does.

#### Scenario: Base written by a build
- **WHEN** the blink is built into an empty folder `B` with `--confirm --json`
- **THEN** `receipt.written` lists `B/fenolite-base.json`, whose `parts.R1.value` is `{"code": "330", "out": "330"}`

#### Scenario: Base is byte-stable
- **WHEN** the confirmed build runs a second time
- **THEN** `B/fenolite-base.json` keeps its bytes

### Requirement: Base record form
The base record SHALL be canonical JSON (`canonical-serialization`) with sorted keys, no date and the keys `schema` (`BASE_SCHEMA = "fenolite.base.v0"`), `target` (`kicad` or `altium`) and `parts`: component path → property name → `{"code": <value or null>, "out": <value>}`. A position MUST be `[x, y]` in board nanometres, a rotation `[microdegrees, "top"|"bottom"]`, other values strings; `code` is `null` when the code side gave no value.

#### Scenario: Position of a placed part
- **WHEN** the blink is built into an empty folder `B`
- **THEN** `parts.R1.position.code` and `parts.R1.position.out` of `B/fenolite-base.json` are both the position of `R1`'s `place()` in board nanometres

#### Scenario: Staged part
- **GIVEN** a blink variant whose `R1` has no `place()`
- **WHEN** it is built into an empty folder
- **THEN** `parts.R1.position.code` is `null` and `parts.R1.position.out` is its staging position

### Requirement: Base record code side
The code value of a property in the base record SHALL be the value after the edits file was applied ("Code side of a build"), so that a recorded edit is part of the code side, and the out value SHALL be the value written into the output file.

#### Scenario: Recorded edit in the base
- **GIVEN** an `edits.toml` whose `R1` table holds `value = "4k7"` over `330`
- **WHEN** the blink is built into an empty folder
- **THEN** `parts.R1.value` of the base record is `{"code": "4k7", "out": "4k7"}`

### Requirement: Base record is protected
A KiCad build and an Altium build SHALL plan the base record as a write under `--out`, list it in the receipt and record its SHA-256 in `.fenolite/build.json`, so `lens.build.check_existing` refuses to overwrite a base record changed since the last build (`build.layout-exists`).

#### Scenario: Base edited by hand
- **GIVEN** a confirmed blink build in `B` whose `fenolite-base.json` gets one character changed
- **WHEN** the build runs again with `--dry-run --json`
- **THEN** the exit code is 7 and `issues` hold `build.layout-exists` naming `fenolite-base.json`

### Requirement: Base record reading
`read_base(text, *, target, file="") -> BaseRecord` SHALL return the record of a valid text. A text that is not JSON, a different `schema` or `target`, or a malformed entry MUST give `edit.base-invalid` (warning) naming the file, and MUST be read as no record.

#### Scenario: Record of another target
- **GIVEN** a base record with `target` `altium`
- **WHEN** it is read with `target="kicad"`
- **THEN** the result is no record and the issues hold one `edit.base-invalid`

### Requirement: Base entries follow aliases
A part matched through a `moved()` alias (`layout-lens`, "Alias resolution") SHALL take the base entry of its old path.

#### Scenario: Renamed part keeps its base
- **GIVEN** a confirmed blink build whose board gets `R1`'s value `4k7` by token edit, after which `design.py` renames `R1` to `R7` and calls `d.moved("R1", "R7")`
- **WHEN** the build runs again with `--confirm --json`
- **THEN** `R7` holds `4k7`, and `issues` hold no `sync.conflict` and no `edit.base-missing`

### Requirement: The cache never decides
The merge MAY read the last build's model in `.fenolite/` to name base values in messages, and SHALL NOT let it change a decision, a planned byte or the exit code.

#### Scenario: Same result without the cache
- **GIVEN** a confirmed blink build in `B` whose board gets `R1`'s value `4k7` by token edit, and a copy of `B` without `.fenolite/`
- **WHEN** the build runs with `--dry-run --json` on both folders
- **THEN** both plans hold equal bytes for every file outside `.fenolite/`, and both exit codes are equal

### Requirement: Three-way property merge
`merge_property(key, *, base, code, cad, takes=()) -> Decision` SHALL decide one property, where the code side *changed* when it differs from the base `code` and a CAD side when it differs from the base `out`:

| code | CAD | result |
|---|---|---|
| unchanged | unchanged | the CAD value |
| unchanged | changed | the CAD value |
| changed | unchanged | the code value |
| changed | changed, equal to the code | the shared value |
| changed | changed, different | a conflict |

#### Scenario: CAD edit kept
- **GIVEN** base `{"code": "330", "out": "330"}`, code `330` and board value `4k7`
- **WHEN** `merge_property` runs for `R1#value`
- **THEN** the value is `4k7` from `cad`, and there is no conflict

#### Scenario: Code change written
- **GIVEN** base `{"code": "330", "out": "330"}`, code `470` and board value `330`
- **WHEN** `merge_property` runs
- **THEN** the value is `470` from `code`

#### Scenario: Both changed to different values
- **GIVEN** base `{"code": "330", "out": "330"}`, code `470` and board value `4k7`
- **WHEN** `merge_property` runs without a take
- **THEN** the decision holds a conflict with base `330`, code `470`, CAD `4k7` and the reason `both-changed`, and its value is the board's

#### Scenario: Table is exhaustive
- **WHEN** `uv run pytest tests/unit/lens/test_edit_merge.py -k table` runs every combination of changed and unchanged sides, with and without a base and a take
- **THEN** each result is the row of the table

### Requirement: Removed request keeps the CAD value
A code value of `null` whose base `code` was set, such as a `place()` removed from the script, SHALL give the CAD value: removing a request never changes the CAD file.

#### Scenario: place() removed
- **GIVEN** a confirmed blink build, after which `R1`'s `place()` is removed from `design.py`
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` keeps its board position and `issues` hold no `layout.unplaced`

### Requirement: Merge without a base
A property without a base entry SHALL follow the rule of before for its kind: the board for `position` and `rotation` (`layout-lens`, "Placement precedence"), the code for `value`, `footprint`, `reference` and user properties (`layout-lens`, "Kept and re-placed footprints"). One `edit.base-missing` (info) per build MUST give the count of such parts.

#### Scenario: Board built before this change
- **GIVEN** a confirmed blink build in `B` whose base record was deleted, and whose board gets `R1`'s value `4k7` by token edit
- **WHEN** the build runs again with `--confirm --json`
- **THEN** `R1` holds `330`, the script's, `issues` hold one `edit.base-missing`, and `B` holds a base record again

### Requirement: Locked requests win
A locked script request (`place(…, locked=True)`) SHALL give the code value for `position` and `rotation` whatever the table gives, with `layout.place-forced` when the board differed, as before.

#### Scenario: Locked part moved by hand
- **GIVEN** a confirmed blink build whose locked `U1` is moved 2 mm by token edit
- **WHEN** the build runs again with `--confirm --json`
- **THEN** `U1` is at its `place()` position, `issues` hold `layout.place-forced` and no `sync.conflict`

### Requirement: Decision record
`Decision` SHALL hold `key`, `value`, `source` (one of `base`, `code`, `cad`, `board`, `schematic` and `take`) and the `Conflict` when there is one.

#### Scenario: Source of a kept edit
- **GIVEN** base `{"code": "330", "out": "330"}`, code `330`, board `330` and schematic `4k7`
- **WHEN** `merge_property` runs for `R1#value`
- **THEN** the decision has value `4k7` and source `schematic`

### Requirement: CAD sides of a property
The CAD value of a property SHALL come from the board footprint for every merged property, and, when the project has a schematic, also from the symbol whose `fenolite.path` is the part's path for `value`, `footprint` (its `Footprint` field), `reference` and user properties. `position` and `rotation` have the board as their only side.

#### Scenario: Value edited in the schematic
- **GIVEN** a confirmed target-10 blink build with a schematic, whose symbol `R1` gets the value `4k7` by token edit while the board is unchanged
- **WHEN** the build runs again with `--confirm --json`
- **THEN** the board and the regenerated schematic both hold `4k7` for `R1`, and `issues` hold one `edit.unrecorded` naming `R1#value`

### Requirement: Schematic read as a CAD side
The build and `sync` SHALL read the root schematic and every sheet file it names with `sch.read_schematic` (c0060) when the root schematic exists, and `lens.preserve.read_existing` SHALL return their texts. A project built with `--schematic skip` has the board as its only CAD side.

#### Scenario: No schematic
- **GIVEN** a blink built with `--schematic skip`, whose board gets `R1`'s value `4k7` by token edit
- **WHEN** the build runs again with `--schematic skip --confirm`
- **THEN** `R1` holds `4k7` and no schematic file is read

### Requirement: CAD sides compared on their own
Each CAD side SHALL be compared with the base `out` on its own. When one side changed, its value is the CAD value; when both changed to one value, as KiCad's update of the board from the schematic writes it, that value is; when both changed to different values, the property MUST be a conflict with the reason `sides-disagree`.

#### Scenario: Board updated from the schematic
- **GIVEN** a confirmed blink build whose schematic and board both get `R1`'s value `4k7` by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` holds `4k7` on both, and `issues` hold no `sync.conflict`

#### Scenario: Sides disagree
- **GIVEN** the same build whose schematic gets `R1`'s value `4k7` and whose board gets `1k`
- **WHEN** the build runs again with `--dry-run --json`
- **THEN** the exit code is 5 and `issues` hold one `sync.conflict` naming `R1#value` with the reason `sides-disagree` and both CAD values

### Requirement: Units of a symbol
A multi-unit symbol SHALL be read through its first unit; units whose values disagree among themselves MUST count as a `sides-disagree` conflict naming the units.

#### Scenario: Two units disagree
- **GIVEN** a build with a two-unit symbol `U2`, whose unit 2 gets the value `X` by token edit
- **WHEN** the build runs again with `--dry-run --json`
- **THEN** `issues` hold one `sync.conflict` naming `U2#value` with the reason `sides-disagree`

### Requirement: Altium builds have no CAD side
An Altium build SHALL build from the script and the edits file only (`design-dsl`, "Placements file in a build"), and SHALL still write its base record with `target` `altium`. Reading Altium documents as a CAD side is not part of this change.

#### Scenario: Altium base record
- **WHEN** the blink is built with `--target altium` into an empty folder
- **THEN** the folder holds `fenolite-base.json` with `target` `altium`

### Requirement: Edits file schema
`fenolite.lens.edits` SHALL read and write `edits.toml`, the committed record beside the design script of the property values that differ from the script's, with `EDITS_SCHEMA = "fenolite.edits.v0"`, `EDITS_FILE = "edits.toml"`, `PartEdits`, `EditsFile(parts, issues)`, `read_edits(text, *, origin, file="")` and `write_edits(parts, *, origin)`. It generalises `placements.toml` and keeps its table form.

#### Scenario: Value and position edits
- **GIVEN** the text `schema = "fenolite.edits.v0"`, `[part."buck1/L"]`, `x = 12.7`, `y = 30`, `value = "6u8"`, `[part."buck1/L".over]`, `unplaced = true`, `value = "4u7"`
- **WHEN** it is read with `origin` (100 mm, 100 mm)
- **THEN** `buck1/L` has the position (112.7 mm, 130 mm), the value `6u8` over `4u7`, no rotation edit and no issue

### Requirement: Edits file tables
Each part SHALL be a table `[part."<component path>"]` with the optional keys `x` and `y` (millimetres, together), `rotation` (degrees in [0, 360)) and `side` (`"top"` or `"bottom"`) together, `locked` (boolean, only with `x` and `y`, default false), `value`, `footprint` and `reference` (strings), `properties` (an inline table of strings), and a sub-table `over`.

#### Scenario: A placements table is an edits table
- **GIVEN** the text of a `placements.toml` written by `write_placements`, with its `schema` line changed to `fenolite.edits.v0` and an `over` table holding `unplaced = true` added to each table
- **WHEN** it is read with `read_edits`
- **THEN** every entry has the position, rotation, side and lock that `read_placements` gives for the original text

### Requirement: Script values of an edit
For each edited property, the `over` table SHALL hold the script's value when the edit was recorded, under the same keys, or `unplaced = true` instead of `x`, `y`, `rotation` and `side` when the script gave the part no placement. An edit without its `over` key, an `over` key without its edit, or `unplaced` with a position key MUST give `layout.source-invalid` naming the table and key.

#### Scenario: Edit without its script value
- **GIVEN** a table `[part."R1"]` with `value = "4k7"` and no `over` table
- **WHEN** it is read
- **THEN** the issues hold one `layout.source-invalid` naming `R1` and `over.value`, and `R1` is left out

### Requirement: Edits file values
The edits file SHALL be read with `tomllib` and `parse_float=Decimal`. `x` and `y` MUST be whole nanometres and `rotation` whole microdegrees, in the frame of `place()`: `origin` plus (`x`, `y`) on reading and the position minus `origin` on writing, with `origin` = `dsl.BOARD_ORIGIN`, as in `placements.toml`.

#### Scenario: Value off the nanometre
- **GIVEN** an edits table with `x = 1.0000005` and `y = 0`
- **WHEN** it is read
- **THEN** the issues hold one `layout.source-invalid` naming the table and `x`, and the table is left out

### Requirement: Edits file errors
A text that is not TOML, or whose `schema` is missing or differs, SHALL raise `FormatError` (`FEN-3004`) naming the file. A table whose path is not a component path, an unknown key, or a value of the wrong type or off its unit MUST give `layout.source-invalid` (error), and that table MUST be left out.

#### Scenario: Missing schema
- **GIVEN** a text with one table and no `schema` key
- **WHEN** it is read with `file="edits.toml"`
- **THEN** `FormatError` is raised naming `edits.toml`

### Requirement: Edits file printing
`write_edits` SHALL write `# Written by fenolite sync --to-source.`, the `schema` line, an empty line, then per part in component-path order its table with the keys `x`, `y`, `rotation`, `side`, `locked`, `value`, `footprint`, `reference`, `properties` (names in code-point order) and its `over` table in the same order. `locked` MUST be printed only when true, numbers in their shortest exact decimal form.

#### Scenario: Printed order
- **WHEN** `write_edits` prints a part with a value edit and a position edit
- **THEN** `x` and `y` come before `value`, and the `over` table follows the part's table

### Requirement: Edits file round trip
`read_edits(write_edits(p, origin=o), origin=o).parts` SHALL equal `p` for every mapping of component paths to whole-unit edits, and the printed text MUST NOT depend on the clock, the platform or `PYTHONHASHSEED`.

#### Scenario: Round trip
- **WHEN** `uv run pytest tests/unit/lens/test_edits_file.py -k round_trip` runs its property test over generated edits
- **THEN** every printed text reads back to its edits, and printing them again gives the same text

### Requirement: Stale and redundant edits
An edit whose `over` value differs from the script's current value, and whose edited value also differs from it, SHALL be stale and MUST be a conflict with the reason `stale-edit`. An edit whose value equals the script's current value is redundant: it MUST apply without an issue, and the next capture drops it.

#### Scenario: Stale edit
- **GIVEN** an `edits.toml` whose `R1` table holds `value = "4k7"` over `330`, and a `design.py` whose `R1` value is now `470`
- **WHEN** the build runs with `--dry-run --json`
- **THEN** the exit code is 5 and `issues` hold one `sync.conflict` naming `R1#value` with the reason `stale-edit`, code `470` and CAD `4k7`

#### Scenario: Script catches up with an edit
- **GIVEN** the same `edits.toml` and a `design.py` whose `R1` value is now `4k7`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 0 and `R1` holds `4k7`

### Requirement: Property merge in a build
`merge_properties(design, *, board, sheets, match, base, edits, takes) -> PropertyMerge` SHALL decide `value`, `footprint`, `reference` and user properties of every part before the build; `lens.preserve.prepare` SHALL call it and give `build_design` the design it returns, a step that "Built project files" (`design-dsl`) allows.

#### Scenario: Value kept from the board
- **GIVEN** a confirmed blink build whose board gets `R1`'s value `4k7` by token edit
- **WHEN** the build runs again with `--confirm --json`
- **THEN** `R1` holds `4k7` on the board, in the schematic and in `.fenolite/circuit.json`

### Requirement: Code side of a build
The code value of a property SHALL be the script's, replaced by its edit in the edits file when that edit is not stale.

#### Scenario: Edits apply over the script
- **GIVEN** a confirmed blink build and an `edits.toml` whose `R1` table holds `value = "4k7"` over `330`
- **WHEN** the build runs again with `--confirm --json`
- **THEN** `R1` holds `4k7`, and `issues` hold no `edit.unrecorded`

### Requirement: Property merge result
`PropertyMerge` SHALL hold `design` (the model whose components have the decided `value`, `lib_footprint_ref`, `ref` and user properties), `decisions`, `base` (the `BaseRecord` the build writes) and `issues`; `prepare` MUST add to it the decisions of `position` and `rotation` that `effective_placements` takes with the same `base` and `takes`.

#### Scenario: Decisions of one build
- **GIVEN** a build that kept `R1`'s KiCad value and moved `D1` from a changed `place()`
- **WHEN** `uv run pytest tests/unit/lens/test_edit_merge.py -k result` reads its `PropertyMerge`
- **THEN** `decisions` hold `R1#value` from `cad` and `D1#position` from `code`

### Requirement: Footprints swapped in the CAD tool
A footprint kept from the board SHALL give the component the board's library footprint id, so the matched footprint is kept with its node (`layout-lens`, "Kept and re-placed footprints"). A footprint id that the build cannot resolve MUST give the build's library error for it (exit 3).

#### Scenario: Footprint changed in KiCad
- **GIVEN** a confirmed target-10 blink build whose board gets `R1`'s footprint replaced by the node of `Mini:Mini_R_0805` by token edit
- **WHEN** the build runs again with `--confirm --json`
- **THEN** `R1` keeps that node, `result.preserved.kept` lists `R1`, and `issues` hold no `layout.footprint-replaced` and one `edit.unrecorded` naming `R1#footprint`

### Requirement: Merge without a CAD file
With `--discard-layout`, into an empty folder and for `--target altium`, there SHALL be no CAD side: each property MUST take its code value, edits included.

#### Scenario: Edit survives a discarded layout
- **GIVEN** a confirmed blink build in `B` and an `edits.toml` whose `R1` value is `4k7` over `330`
- **WHEN** the build runs again with `--discard-layout --confirm`
- **THEN** `R1` holds `4k7`

### Requirement: Unrecorded CAD edits
Each CAD value that a build keeps and the edits file does not hold SHALL give `edit.unrecorded` (info) naming the key, with the hint "run fenolite sync --to-source to record it in edits.toml".

#### Scenario: Rebuild is stable
- **GIVEN** a build that kept `R1`'s KiCad value `4k7` without an edit recorded
- **WHEN** the build runs once more with `--confirm`
- **THEN** every file keeps its bytes, and `issues` hold `edit.unrecorded` naming `R1#value` again

### Requirement: Edits in the build result
`result.preserved.edits` SHALL hold `kept`, `code`, `taken` and `unrecorded` (sorted key texts) and `conflicts` (conflict records), which "Layout preservation evidence" allows. Every list MUST be empty on a first build and on a rebuild of an unedited board.

#### Scenario: Unedited rebuild
- **GIVEN** a confirmed blink build in `B`
- **WHEN** the build runs again with `--dry-run --json`
- **THEN** every list of `result.preserved.edits` is empty

### Requirement: Frozen builds refuse unrecorded edits
Under `build --frozen` (c0249), any `--take` and any `edit.unrecorded` SHALL be refused as `--frozen` refuses a change of the lock, because a frozen build must be reproducible from the source tree.

#### Scenario: Unrecorded edit under --frozen
- **GIVEN** a confirmed blink build whose board gets `R1`'s value `4k7` by token edit, and no `edits.toml`
- **WHEN** the build runs with `--frozen --dry-run --json`
- **THEN** the exit code is c0249's for a refused lock change, and `issues` name `R1#value`

### Requirement: Conflict record
A conflict SHALL be a `Conflict(key, base, code, cad, sides, reason)` with `reason` one of `both-changed`, `stale-edit`, `cad-locked` and `sides-disagree`, and `cad` holding the value of each CAD side that changed, keyed `board` or `schematic`. Conflicts MUST be reported in key order, one per key.

#### Scenario: Record of a conflict
- **GIVEN** base `{"code": "330", "out": "330"}`, code `470` and board value `4k7`
- **WHEN** `merge_property` runs
- **THEN** the conflict has `cad == {"board": "4k7"}` and the reason `both-changed`

### Requirement: Conflict finding
A conflict that no `--take` resolves SHALL give `sync.conflict` (error) in `build` and in `sync`. Its `where` MUST be the key text; its message MUST name the base, code and CAD values, in millimetres and degrees for positions and rotations, and the CAD file; its hint MUST name `--take code:<key>` and `--take cad:<key>`, or `board` and `schematic` for `sides-disagree`.

#### Scenario: Hint names the takes
- **GIVEN** the conflict of `R1#value`
- **WHEN** the build runs with `--dry-run --json`
- **THEN** the `sync.conflict` issue has `where` `R1#value` and a hint naming `--take code:R1#value` and `--take cad:R1#value`

### Requirement: Conflicts stop writes
A build with a `sync.conflict` SHALL plan no write and exit 5, and `sync` with one SHALL write nothing and exit 5.

#### Scenario: No file changes
- **GIVEN** a conflict of `R1#value`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 5 and no file of the output folder changes

### Requirement: Take option of build
`fenolite build` SHALL accept `--take SIDE[:TARGET]`, repeatable, an option that "Build command" (`design-dsl`) allows, where `SIDE` is `code`, `cad`, `board` or `schematic` and `TARGET` is a component path or a key text; `parse_takes` SHALL turn the values into `Take` objects. A malformed value MUST be a usage error (exit 2, `FEN-2001`) naming it.

#### Scenario: Malformed take
- **WHEN** the build runs with `--take mine:R1 --dry-run`
- **THEN** the exit code is 2 and stderr carries `FEN-2001` naming `mine:R1`

### Requirement: Take specificity
A take without `TARGET` SHALL apply to every conflict, one with a component path to every conflict of that part, and one with a key to that property; the most specific take MUST win. Two takes of the same target with different sides MUST be a usage error (exit 2, `FEN-2001`).

#### Scenario: Contradictory takes
- **WHEN** the build runs with `--take code:R1 --take cad:R1 --dry-run`
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Take the code for a whole part
- **GIVEN** conflicts of `R1#value` and `R1#position`
- **WHEN** the build runs with `--take code:R1 --confirm`
- **THEN** `R1` holds the script's value and position, and the next build without `--take` gives no conflict

### Requirement: Take effects
`code` SHALL write the code value; `cad` SHALL write the CAD value when one CAD side changed or both agree, and SHALL leave a `sides-disagree` conflict unresolved with the hint to take `board` or `schematic`; `board` and `schematic` SHALL write that side's value. A take never changes a property that is not in conflict.

#### Scenario: Take the CAD value
- **GIVEN** the conflict of `R1#value` with base `330`, code `470` and CAD `4k7`
- **WHEN** the build runs with `--take cad:R1#value --confirm --json`
- **THEN** the exit code is 0, `R1` holds `4k7`, and `fenolite-base.json` holds `{"code": "470", "out": "4k7"}` for it

### Requirement: Takes are reported
A resolved conflict SHALL be listed in `result.preserved.edits.taken`, and a take that keeps a CAD value also gives `edit.unrecorded`. A take that matches no conflict MUST give `edit.take-unused` (warning) naming it.

#### Scenario: Unused take
- **WHEN** a build without conflicts runs with `--take cad:R1#value --dry-run --json`
- **THEN** the exit code is 0 and `issues` hold one `edit.take-unused` naming `cad:R1#value`

### Requirement: Capture of CAD edits
`capture_edits(design, *, board, sheets, match, base, edits, origin)` SHALL give the edits that `fenolite sync --to-source` writes: for each matched part and merged property, the value the next build without `--take` would write, recorded with the script's value as `over` when it differs from the script's value, and nothing otherwise. A conflict MUST give `sync.conflict` and no edit for any part.

#### Scenario: Only differences are recorded
- **GIVEN** a confirmed blink build whose parts all have `place()`, whose board then gets `D1` moved 4 mm by token edit
- **WHEN** `capture_edits` runs with the base record
- **THEN** the result holds one part, `D1`, with `x` and `y` and an `over` table holding `D1`'s `place()` position

#### Scenario: Removed edit
- **GIVEN** an `edits.toml` whose `R1` value `4k7` was applied by the last build, after which the board's value of `R1` is set back to `330` by token edit
- **WHEN** `capture_edits` runs
- **THEN** the result holds no `value` for `R1`

### Requirement: Pending code changes are not captured
A code change over an unchanged CAD value SHALL NOT be recorded by `capture_edits`; `sync` lists it in `result.pending`, because the next build writes it.

#### Scenario: Script changed, board not
- **GIVEN** a confirmed blink build, after which `design.py` sets `R1`'s value to `470`
- **WHEN** `fenolite sync --to-source --dry-run --json` runs
- **THEN** `result.pending` lists `R1#value` and the planned `edits.toml` holds no `value` for `R1`

### Requirement: Staged parts are not captured
A part left at its staging position, or off the board, SHALL have no position or rotation edit, as staged parts had no entry in `placements.toml`.

#### Scenario: Staged part
- **GIVEN** a confirmed build of a blink variant whose `R1` has no `place()` and is staged
- **WHEN** `capture_edits` runs
- **THEN** the result holds no position for `R1`

### Requirement: Capture without a base
Without a base entry for a part, `capture_edits` SHALL capture its `position` and `rotation` from the board and SHALL NOT capture its `value`, `footprint`, `reference` or user properties; each such difference gives `sync.value-differs` (`layout-lens`, "Sync of the source tree").

#### Scenario: Old board synced
- **GIVEN** a confirmed blink build whose base record was deleted and whose board gets `R1`'s value `4k7` and `D1` moved 4 mm by token edit
- **WHEN** `capture_edits` runs
- **THEN** the result holds `D1`'s position and no value of `R1`, and the issues hold one `sync.value-differs` naming `R1`

### Requirement: Edits of parts the board does not place
An edit of the edits file for a part that the board does not place SHALL be kept unchanged by `capture_edits`.

#### Scenario: Edit of a part not on the board
- **GIVEN** an `edits.toml` with a table for `R9`, a part of the design that the board does not hold
- **WHEN** `capture_edits` runs
- **THEN** the result holds the table of `R9` unchanged

### Requirement: Reference edits
The code side of `reference` SHALL be the reference the build gives the part: the script's hand reference, or the reference recorded in `<script stem>.lock` (c0249). A `reference` in the edits file MUST count as a hand reference for c0249's assignment, so the lock records it; two parts with one decided reference MUST give the build's duplicate-reference error.

#### Scenario: Reannotated in KiCad
- **GIVEN** a confirmed blink build whose board and schematic get `R1` renamed `R7` by token edit
- **WHEN** the build runs again with `--confirm`, then `fenolite sync --to-source --confirm`
- **THEN** the board holds `R7`, the build's `issues` hold `edit.unrecorded` naming `R1#reference`, and `edits.toml` holds `reference = "R7"` over `R1`

### Requirement: User property edits
Only the user properties that the script names SHALL be merged (`design-dsl`, "User properties on built footprints"); a property added in KiCad stays an opaque property, as before. A named property that a CAD side removed MUST count as changed to the empty text.

#### Scenario: User property edited in KiCad
- **GIVEN** a confirmed build of a blink variant whose `R1` has `properties={"Part number": "PN-330"}`, whose board gets `Part number` `PN-470` by token edit
- **WHEN** the build runs again with `--confirm --json`
- **THEN** the board holds `PN-470` for `R1` and `issues` hold `edit.unrecorded` naming `R1#property:Part number`

### Requirement: Second-phase properties
`reference` and user properties MAY be implemented after `position`, `rotation`, `value` and `footprint`; until they are, they SHALL keep their rules of before and give no decision.

#### Scenario: Before the second phase
- **GIVEN** an implementation of the first four properties only, and a board whose `R1` reference was changed by token edit
- **WHEN** the build runs again
- **THEN** `R1`'s reference is the script's, as before this change

### Requirement: Edit merge error and warning codes
`EDIT_ISSUE_CODES` SHALL hold these codes, which `lens.build.BUILD_ISSUE_CODES` and `lens.sync.SYNC_ISSUE_CODES` include with the same severities:

| code | severity | when |
|---|---|---|
| `sync.conflict` | error | a conflict no take resolves |
| `edit.take-unused` | warning | a take matched no conflict |
| `edit.legacy-file` | warning | `placements.toml` beside `edits.toml` was not read |
| `edit.base-invalid` | warning | the base record was read as none |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/lens/test_edit_merge.py -k closed_set` collects every code produced by the edit merge tests
- **THEN** each `edit.*` and `sync.conflict` code is a key of `EDIT_ISSUE_CODES` with the severity of these tables, and every key is produced by at least one test

### Requirement: Edit merge info codes
`EDIT_ISSUE_CODES` SHALL also hold these codes, and no other:

| code | severity | when |
|---|---|---|
| `edit.unrecorded` | info | a kept CAD value is not in `edits.toml` |
| `edit.code-wins` | info | a script change was written over an unchanged CAD value |
| `edit.base-missing` | info | parts without a base entry were merged as before |

#### Scenario: Info does not fail
- **GIVEN** a build that gives `edit.unrecorded`, `edit.code-wins` and `edit.base-missing`
- **WHEN** it runs with `--confirm`
- **THEN** the exit code is 0

### Requirement: Edit merge evidence
`lens.edits.EVIDENCE` SHALL be `Evidence(Level.INFERRED, hypotheses=("H-K-LENS-KEEP", "H-K-SCH-UPDATE", "H-K-EDIT-SCH-VALUE"))`, and SHALL join the `build` and `sync` envelopes when a base record or an edits file was read. The level MUST stay `INFERRED`.

#### Scenario: Envelope with a base record
- **GIVEN** a confirmed blink build in `B`
- **WHEN** the build runs again with `--dry-run --json`
- **THEN** `evidence.hypotheses` contains `H-K-EDIT-SCH-VALUE`

### Requirement: Schematic edit hypothesis
`docs/hypotheses.md` SHALL register `H-K-EDIT-SCH-VALUE`: a value, `Footprint` field or reference changed in KiCad's schematic editor and saved is read back by `sch.read_schematic` as that property's text. It MUST stay `INFERRED` until a KiCad kit case of the maintainer confirms it.

#### Scenario: Row registered
- **WHEN** `uv run pytest tests/unit/test_hypotheses_register.py` runs
- **THEN** it passes and finds the row `H-K-EDIT-SCH-VALUE` with the label `INFERRED`

### Requirement: Three-way merge is documented
`docs/lens.md` SHALL describe the merge in sections "Three-way merge", "The base record", "edits.toml", "Conflicts and --take" and "From placements.toml to edits.toml", hold the table of "Three-way property merge", say that the base record is committed with the output folder and `.fenolite/` is not, and drop the sentence that calls the merge two-way without a stored base.

#### Scenario: Sections present
- **WHEN** `uv run pytest tests/unit/lens/test_edit_merge.py -k docs` reads `docs/lens.md`
- **THEN** the five sections are present and the sentence "There is no stored base" is not

### Requirement: Conflicts are explained and taught
`src/fenolite/cli/data/explain.toml` SHALL hold an entry for each code of `EDIT_ISSUE_CODES` and for `sync.placements-migrated`, `docs/cli-contract.md` SHALL describe `build --take` and the changed `sync`, and the agent guide SHALL run a build with `--take` after a `sync.conflict` in a tested `fenolite-recipe` block of `recovery.md`.

#### Scenario: Codes are explained
- **WHEN** `fenolite explain sync.conflict --json` runs
- **THEN** the exit code is 0 and the reply names `--take`

#### Scenario: Guide covers the option
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py` runs
- **THEN** it passes

### Requirement: Edit merge acceptance fixture
`tests/data/lens/edit_merge/` SHALL hold a design authored for Fenolite with a module, a user property and a schematic, and `tests/_layout_edit.py::edit_properties(board_text, schematic_text, changes)` SHALL apply value, footprint, reference, property and position changes by token edit. `tests/unit/lens/test_edit_merge_acceptance.py` MUST build, edit, rebuild, sync and rebuild again.

#### Scenario: Acceptance loop
- **WHEN** `uv run pytest tests/unit/lens/test_edit_merge_acceptance.py -q` runs
- **THEN** it passes, and its last rebuild writes every file with the bytes of the build before it

### Requirement: Merged files accepted by KiCad
`tests/kicad/lens/test_edit_merge_oracle.py` SHALL load each board and schematic that the acceptance loop rebuilds with `kicad-cli` 9.0.9 and 10.0.6, run DRC and ERC on them, and find nothing that the unedited build does not have.

#### Scenario: KiCad accepts the merged files
- **WHEN** `uv run pytest tests/kicad/lens/test_edit_merge_oracle.py -rA` runs on 9.0.9 and on 10.0.6
- **THEN** every board and schematic loads, and DRC and ERC report nothing new
